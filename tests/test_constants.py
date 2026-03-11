"""
Tests for shared constants.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_manager.constants import (
    DEFAULT_CONVERT_SCRIPT,
    DEFAULT_GGUF_DIR,
    DEFAULT_QUANTIZE_BIN,
    DEFAULT_QUANTIZED_DIR,
    DEFAULT_SAFETENSORS_DIR,
    HF_BASE,
    QUANTS,
)


class TestQuants(unittest.TestCase):

    def test_quants_is_nonempty_list(self):
        self.assertIsInstance(QUANTS, list)
        self.assertTrue(len(QUANTS) > 0)

    def test_q4_k_m_present(self):
        """Q4_K_M is the primary auto-selected quant — must always exist."""
        self.assertIn('Q4_K_M', QUANTS)

    def test_all_quants_are_strings(self):
        for q in QUANTS:
            self.assertIsInstance(q, str)

    def test_no_duplicate_quants(self):
        self.assertEqual(len(QUANTS), len(set(QUANTS)))


class TestHFBase(unittest.TestCase):

    def test_hf_base_is_string(self):
        self.assertIsInstance(HF_BASE, str)

    def test_hf_base_default(self):
        """When HF_ENDPOINT env var is unset the default is huggingface.co."""
        import os
        if not os.environ.get('HF_ENDPOINT'):
            self.assertEqual(HF_BASE, 'https://huggingface.co')

    def test_hf_base_no_trailing_slash(self):
        self.assertFalse(HF_BASE.endswith('/'))


class TestPipelineDefaults(unittest.TestCase):
    """Pipeline path defaults must be blank (no personal paths hard-coded)."""

    def test_safetensors_dir_blank(self):
        self.assertEqual(DEFAULT_SAFETENSORS_DIR, '')

    def test_gguf_dir_blank(self):
        self.assertEqual(DEFAULT_GGUF_DIR, '')

    def test_quantized_dir_blank(self):
        self.assertEqual(DEFAULT_QUANTIZED_DIR, '')

    def test_convert_script_blank(self):
        self.assertEqual(DEFAULT_CONVERT_SCRIPT, '')

    def test_quantize_bin_blank(self):
        self.assertEqual(DEFAULT_QUANTIZE_BIN, '')


if __name__ == '__main__':
    unittest.main()
