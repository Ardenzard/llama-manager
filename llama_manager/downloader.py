"""
HuggingFace model downloader with resume support and parallel workers.

Usage (standalone)::

    downloader = ModelDownloader(log_fn=print)
    output_folder = downloader.download('mistralai/Mistral-7B-v0.1', 'main', './models/mistral')
"""

import base64
import datetime
import json
import os
import re
import threading
from pathlib import Path
from time import sleep
from concurrent.futures import ThreadPoolExecutor

from .constants import HF_BASE

try:
    import requests
    from requests.adapters import HTTPAdapter
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class ModelDownloader:
    """Download model files from HuggingFace with retry and resume support."""

    def __init__(self, max_retries: int = 5, log_fn=None, progress_fn=None):
        self.max_retries  = max_retries
        self.log          = log_fn or print
        self.set_progress = progress_fn or (lambda v: None)

    # ── Session ───────────────────────────────────────────────────────────────

    def get_session(self):
        """Return a requests Session with auth headers if a token is available."""
        if not HAS_REQUESTS:
            raise RuntimeError(
                "'requests' package is not installed.\nRun: pip install requests"
            )
        session = requests.Session()
        if self.max_retries:
            session.mount('https://cdn-lfs.huggingface.co', HTTPAdapter(max_retries=self.max_retries))
            session.mount('https://huggingface.co',         HTTPAdapter(max_retries=self.max_retries))

        # Auth: huggingface_hub token takes priority, then env var
        token = None
        try:
            from huggingface_hub import get_token
            token = get_token()
        except ImportError:
            token = os.getenv('HF_TOKEN')
        if token:
            session.headers = {'authorization': f'Bearer {token}'}

        if os.getenv('HF_USER') and os.getenv('HF_PASS'):
            session.auth = (os.getenv('HF_USER'), os.getenv('HF_PASS'))
        return session

    # ── URL / branch helpers ──────────────────────────────────────────────────

    def sanitize(self, model: str, branch: str) -> tuple[str, str]:
        """
        Normalise a model identifier and branch name.

        Accepts full HuggingFace URLs, ``user/repo:branch`` shorthand, or
        plain ``user/repo`` strings.
        """
        if model.endswith('/'):
            model = model[:-1]
        if model.startswith(HF_BASE + '/'):
            model = model[len(HF_BASE) + 1:]
        parts  = model.split(':')
        model  = parts[0]
        branch = parts[1] if len(parts) > 1 else (branch or 'main')
        if not re.match(r'^[a-zA-Z0-9._/-]+$', branch):
            raise ValueError('Invalid branch name.')
        return model, branch

    # ── File listing ──────────────────────────────────────────────────────────

    def get_links(
        self,
        model: str,
        branch: str,
        text_only: bool = False,
        specific_file: str | None = None,
    ) -> tuple[list, list, bool, bool]:
        """
        Return (links, sha256_pairs, is_lora, is_gguf_specific) for a model repo.

        When the repo contains both safetensors and pytorch/gguf files, the
        pytorch/gguf variants are dropped in favour of safetensors.  For GGUF-
        only repos the Q4_K_M quantisation is preferred when available.
        """
        session = self.get_session()
        page    = f'/api/models/{model}/tree/{branch}'
        cursor  = b''
        links, sha256, classifications = [], [], []
        has_pytorch = has_pt = has_gguf = has_safetensors = is_lora = False

        while True:
            url = f'{HF_BASE}{page}' + (f'?cursor={cursor.decode()}' if cursor else '')
            r   = session.get(url, timeout=10)
            r.raise_for_status()
            data = json.loads(r.content)
            if not data:
                break

            for item in data:
                fname = item['path']
                if specific_file not in [None, ''] and fname != specific_file:
                    continue
                if not is_lora and fname.endswith(('adapter_config.json', 'adapter_model.bin')):
                    is_lora = True

                is_pytorch    = re.match(r'(pytorch|adapter|gptq)_model.*\.bin', fname)
                is_safetensor = re.match(r'.*\.safetensors', fname)
                is_pt_file    = re.match(r'.*\.pt', fname)
                is_gguf_file  = re.match(r'.*\.gguf', fname)
                is_tiktoken   = re.match(r'.*\.tiktoken', fname)
                is_tokenizer  = re.match(r'(tokenizer|ice|spiece).*\.model', fname) or is_tiktoken
                is_text       = re.match(r'.*\.(txt|json|py|md)', fname) or is_tokenizer

                if any((is_pytorch, is_safetensor, is_pt_file, is_gguf_file, is_tokenizer, is_text)):
                    if 'lfs' in item:
                        sha256.append([fname, item['lfs']['oid']])
                    if is_text:
                        links.append(f'{HF_BASE}/{model}/resolve/{branch}/{fname}')
                        classifications.append('text')
                        continue
                    if not text_only:
                        links.append(f'{HF_BASE}/{model}/resolve/{branch}/{fname}')
                        if is_safetensor:
                            has_safetensors = True; classifications.append('safetensors')
                        elif is_pytorch:
                            has_pytorch = True;     classifications.append('pytorch')
                        elif is_pt_file:
                            has_pt = True;          classifications.append('pt')
                        elif is_gguf_file:
                            has_gguf = True;        classifications.append('gguf')

            cursor = base64.b64encode(f'{{"file_name":"{data[-1]["path"]}"}}'.encode()) + b':50'
            cursor = base64.b64encode(cursor).replace(b'=', b'%3D')

        # Prefer safetensors over pytorch/pt/gguf when both are present
        if (has_pytorch or has_pt or has_gguf) and has_safetensors:
            for i in range(len(classifications) - 1, -1, -1):
                if classifications[i] in ('pytorch', 'pt', 'gguf'):
                    links.pop(i); classifications.pop(i)

        # For GGUF-only repos, prefer Q4_K_M when available
        if has_gguf and specific_file is None:
            has_q4km = any('q4_k_m' in l.lower() for l in links)
            for i in range(len(classifications) - 1, -1, -1):
                if classifications[i] == 'gguf':
                    if has_q4km and 'q4_k_m' not in links[i].lower():
                        links.pop(i); classifications.pop(i)
                    elif not has_q4km:
                        links.pop(i); classifications.pop(i)

        return links, sha256, is_lora, has_gguf and specific_file is not None

    # ── Size probe ────────────────────────────────────────────────────────────

    def get_file_size(self, url: str) -> int:
        """Return remote file size in bytes, or 0 if unknown."""
        try:
            r = self.get_session().head(url, timeout=10, allow_redirects=True)
            return int(r.headers.get('content-length', 0))
        except Exception:
            return 0

    # ── Single-file download ──────────────────────────────────────────────────

    def download_file(
        self,
        url: str,
        output_folder: Path,
        total_bytes: int,
        downloaded_ref: list,
        lock: threading.Lock,
        stop_event: threading.Event,
    ) -> None:
        """Download a single file, resuming if a partial file exists."""
        filename    = Path(url.rsplit('/', 1)[1])
        output_path = output_folder / filename
        attempt     = 0

        while attempt < self.max_retries:
            attempt += 1
            session = self.get_session()
            headers = {}
            mode    = 'wb'
            try:
                if output_path.exists():
                    r = session.get(url, stream=True, timeout=20)
                    remote_size = int(r.headers.get('content-length', 0))
                    if output_path.stat().st_size >= remote_size:
                        self.log(f'  ✓ Already complete: {filename}')
                        return
                    headers = {'Range': f'bytes={output_path.stat().st_size}-'}
                    mode    = 'ab'

                with session.get(url, stream=True, headers=headers, timeout=30) as r:
                    r.raise_for_status()
                    with open(output_path, mode) as f:
                        for chunk in r.iter_content(1024 * 256):
                            if stop_event.is_set():
                                return
                            f.write(chunk)
                            with lock:
                                downloaded_ref[0] += len(chunk)
                                if total_bytes > 0:
                                    self.set_progress(min(downloaded_ref[0] / total_bytes, 1.0))
                return
            except Exception as e:
                self.log(f'  ✗ Error ({filename}): {e}  [attempt {attempt}/{self.max_retries}]')
                if attempt < self.max_retries:
                    sleep(2 ** attempt)
                else:
                    self.log(f'  ✗ Failed to download {filename} after {self.max_retries} attempts.')

    # ── Batch download ────────────────────────────────────────────────────────

    def download(
        self,
        model: str,
        branch: str,
        output_folder: str | os.PathLike,
        threads: int = 4,
        stop_event: threading.Event | None = None,
    ) -> Path:
        """
        Download all files for *model* at *branch* into *output_folder*.

        Returns the output folder path.  Raises RuntimeError if no files are
        found or the download is stopped via *stop_event*.
        """
        if stop_event is None:
            stop_event = threading.Event()

        model, branch = self.sanitize(model, branch)
        self.log(f'Fetching file list for {model} @ {branch}…')
        links, sha256, is_lora, is_llamacpp = self.get_links(model, branch)
        if not links:
            raise RuntimeError('No files found for this model.')

        self.log(f'Found {len(links)} file(s). Measuring sizes…')
        sizes       = [self.get_file_size(l) for l in links]
        total_bytes = sum(sizes)
        self.log(f'Total download size: {total_bytes / 1e9:.2f} GB')

        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)

        # Write metadata file
        meta = (
            f'url: https://huggingface.co/{model}\n'
            f'branch: {branch}\n'
            f'download date: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n'
        )
        sha_lines = '\n'.join(f'    {h} {f}' for f, h in sha256)
        if sha_lines:
            meta += f'sha256sum:\n{sha_lines}\n'
        (output_folder / 'huggingface-metadata.txt').write_text(meta)

        downloaded_ref = [0]
        lock = threading.Lock()
        self.set_progress(0.0)

        with ThreadPoolExecutor(max_workers=threads) as ex:
            futures = [
                ex.submit(
                    self.download_file,
                    url, output_folder, total_bytes, downloaded_ref, lock, stop_event,
                )
                for url in links
            ]
            for f in futures:
                f.result()

        if not stop_event.is_set():
            self.set_progress(1.0)
            self.log('Download complete.')
        return output_folder
