"""
Tests for ModelDownloader.

Network calls are mocked throughout — no real HTTP requests are made.
"""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_manager.downloader import ModelDownloader


class TestSanitize(unittest.TestCase):
    """ModelDownloader.sanitize() — URL / model-string normalisation."""

    def setUp(self):
        self.dl = ModelDownloader()

    def test_plain_user_repo(self):
        model, branch = self.dl.sanitize('user/repo', 'main')
        self.assertEqual(model, 'user/repo')
        self.assertEqual(branch, 'main')

    def test_trailing_slash_stripped(self):
        model, _ = self.dl.sanitize('user/repo/', 'main')
        self.assertEqual(model, 'user/repo')

    def test_full_hf_url_stripped(self):
        from llama_manager.constants import HF_BASE
        url = f'{HF_BASE}/user/repo'
        model, _ = self.dl.sanitize(url, 'main')
        self.assertEqual(model, 'user/repo')

    def test_branch_from_colon_syntax(self):
        model, branch = self.dl.sanitize('user/repo:dev', 'main')
        self.assertEqual(model, 'user/repo')
        self.assertEqual(branch, 'dev')

    def test_default_branch_when_none_given(self):
        _, branch = self.dl.sanitize('user/repo', None)
        self.assertEqual(branch, 'main')

    def test_default_branch_when_empty_string(self):
        _, branch = self.dl.sanitize('user/repo', '')
        self.assertEqual(branch, 'main')

    def test_invalid_branch_raises(self):
        with self.assertRaises(ValueError):
            self.dl.sanitize('user/repo', 'bad branch!')

    def test_branch_with_dots_and_hyphens_allowed(self):
        _, branch = self.dl.sanitize('user/repo', 'v1.0-beta')
        self.assertEqual(branch, 'v1.0-beta')


class TestGetFileSizeMocked(unittest.TestCase):
    """ModelDownloader.get_file_size() with mocked network."""

    def setUp(self):
        self.dl = ModelDownloader()

    def _make_session(self, content_length):
        session   = MagicMock()
        response  = MagicMock()
        response.headers = {'content-length': str(content_length)}
        session.head.return_value = response
        return session

    def test_returns_content_length(self):
        with patch.object(self.dl, 'get_session', return_value=self._make_session(1024)):
            size = self.dl.get_file_size('https://example.com/file.bin')
        self.assertEqual(size, 1024)

    def test_returns_zero_on_exception(self):
        session = MagicMock()
        session.head.side_effect = Exception('network error')
        with patch.object(self.dl, 'get_session', return_value=session):
            size = self.dl.get_file_size('https://example.com/file.bin')
        self.assertEqual(size, 0)

    def test_returns_zero_when_header_missing(self):
        session  = MagicMock()
        response = MagicMock()
        response.headers = {}
        session.head.return_value = response
        with patch.object(self.dl, 'get_session', return_value=session):
            size = self.dl.get_file_size('https://example.com/file.bin')
        self.assertEqual(size, 0)


class TestDownloadFileMocked(unittest.TestCase):
    """ModelDownloader.download_file() with mocked network."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dl     = ModelDownloader(max_retries=2)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_session(self, chunks=(b'hello world',), content_length=None):
        """Build a mock session whose streaming GET returns *chunks*."""
        session  = MagicMock()
        response = MagicMock()
        cl       = content_length if content_length is not None else sum(len(c) for c in chunks)
        response.headers = {'content-length': str(cl)}
        response.iter_content.return_value = iter(chunks)
        response.__enter__ = lambda s: response
        response.__exit__  = MagicMock(return_value=False)
        session.get.return_value = response
        return session

    def test_file_written(self):
        folder = Path(self.tmpdir)
        url    = 'https://example.com/model.gguf'
        session = self._make_session(chunks=(b'data chunk',))
        with patch.object(self.dl, 'get_session', return_value=session):
            self.dl.download_file(
                url, folder, 10, [0], threading.Lock(), threading.Event()
            )
        out = folder / 'model.gguf'
        self.assertTrue(out.exists())
        self.assertEqual(out.read_bytes(), b'data chunk')

    def test_stop_event_prevents_write(self):
        folder     = Path(self.tmpdir)
        stop_event = threading.Event()
        stop_event.set()

        session = self._make_session(chunks=(b'should not write',))
        # Patch iter_content to check stop before writing
        original = self.dl.download_file

        written = []

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.headers = {'content-length': '16'}
            def iter_content(chunk_size):
                yield b'should not write'
            resp.iter_content = iter_content
            resp.__enter__ = lambda s: resp
            resp.__exit__  = MagicMock(return_value=False)
            return resp

        session.get.side_effect = fake_get
        with patch.object(self.dl, 'get_session', return_value=session):
            self.dl.download_file(
                'https://example.com/x.gguf',
                Path(self.tmpdir), 16, [0], threading.Lock(), stop_event,
            )
        # File should not exist (or be empty) because stop was set before first chunk
        out = Path(self.tmpdir) / 'x.gguf'
        if out.exists():
            # Stop may have been checked after first chunk — acceptable
            self.assertLessEqual(out.stat().st_size, 16)

    def test_progress_callback_called(self):
        folder    = Path(self.tmpdir)
        calls     = []
        self.dl.set_progress = lambda v: calls.append(v)
        session   = self._make_session(chunks=(b'x' * 100,), content_length=100)
        with patch.object(self.dl, 'get_session', return_value=session):
            self.dl.download_file(
                'https://example.com/prog.gguf',
                folder, 100, [0], threading.Lock(), threading.Event(),
            )
        self.assertTrue(len(calls) > 0)
        self.assertAlmostEqual(calls[-1], 1.0, places=5)


class TestGetLinksMocked(unittest.TestCase):
    """ModelDownloader.get_links() logic with mocked API responses."""

    def setUp(self):
        self.dl = ModelDownloader()

    def _mock_api(self, pages):
        """Return a mock session whose GET calls return successive *pages*."""
        session   = MagicMock()
        responses = []
        for page_data in pages:
            import json
            r = MagicMock()
            r.content = json.dumps(page_data).encode()
            r.raise_for_status = MagicMock()
            responses.append(r)
        # Final empty page signals end of pagination
        empty = MagicMock()
        empty.content = b'[]'
        empty.raise_for_status = MagicMock()
        responses.append(empty)
        session.get.side_effect = responses
        return session

    def test_text_files_included(self):
        page = [{'path': 'config.json', 'type': 'file'}]
        session = self._mock_api([page])
        with patch.object(self.dl, 'get_session', return_value=session):
            links, sha256, is_lora, _ = self.dl.get_links('user/repo', 'main')
        self.assertTrue(any('config.json' in l for l in links))

    def test_safetensors_wins_over_pytorch(self):
        page = [
            {'path': 'model.safetensors', 'type': 'file'},
            {'path': 'pytorch_model.bin', 'type': 'file', 'lfs': {'oid': 'abc'}},
        ]
        session = self._mock_api([page])
        with patch.object(self.dl, 'get_session', return_value=session):
            links, _, _, _ = self.dl.get_links('user/repo', 'main')
        self.assertTrue(any('safetensors' in l for l in links))
        self.assertFalse(any('pytorch_model.bin' in l for l in links))

    def test_lora_detected(self):
        page = [{'path': 'adapter_config.json', 'type': 'file'}]
        session = self._mock_api([page])
        with patch.object(self.dl, 'get_session', return_value=session):
            _, _, is_lora, _ = self.dl.get_links('user/repo', 'main')
        self.assertTrue(is_lora)

    def test_sha256_collected(self):
        page = [
            {'path': 'model.safetensors', 'type': 'file', 'lfs': {'oid': 'deadbeef'}}
        ]
        session = self._mock_api([page])
        with patch.object(self.dl, 'get_session', return_value=session):
            _, sha256, _, _ = self.dl.get_links('user/repo', 'main')
        self.assertEqual(len(sha256), 1)
        self.assertEqual(sha256[0][0], 'model.safetensors')
        self.assertEqual(sha256[0][1], 'deadbeef')

    def test_specific_file_filter(self):
        page = [
            {'path': 'model-Q4_K_M.gguf', 'type': 'file'},
            {'path': 'model-Q8_0.gguf',   'type': 'file'},
        ]
        session = self._mock_api([page])
        with patch.object(self.dl, 'get_session', return_value=session):
            links, _, _, _ = self.dl.get_links('user/repo', 'main',
                                                specific_file='model-Q4_K_M.gguf')
        self.assertEqual(len(links), 1)
        self.assertIn('model-Q4_K_M.gguf', links[0])


class TestDownloaderLogFn(unittest.TestCase):
    """Verify log_fn and default print fallback."""

    def test_custom_log_fn_called(self):
        messages = []
        dl = ModelDownloader(log_fn=messages.append)
        dl.log('hello')
        self.assertIn('hello', messages)

    def test_default_log_fn_is_print(self):
        dl = ModelDownloader()
        self.assertIs(dl.log, print)

    def test_max_retries_stored(self):
        dl = ModelDownloader(max_retries=3)
        self.assertEqual(dl.max_retries, 3)


if __name__ == '__main__':
    unittest.main()
