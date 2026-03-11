"""
Shared constants used across the application.
"""

import os

# ── HuggingFace ───────────────────────────────────────────────────────────────

HF_BASE = os.environ.get('HF_ENDPOINT') or 'https://huggingface.co'

# ── Quantisation types ────────────────────────────────────────────────────────

QUANTS = [
    'Q8_0', 'Q6_K', 'Q5_K_M', 'Q5_K_S', 'Q5_1',
    'Q4_K_M', 'Q4_K_S', 'Q4_1', 'IQ4_NL', 'IQ4_XS',
    'Q3_K_L', 'Q3_K_M', 'Q3_K_S', 'Q2_K', 'IQ2_M',
]

# ── Pipeline path defaults ────────────────────────────────────────────────────
# These are intentionally left empty so that each user sets their own paths
# via the Settings → Pipeline Paths panel on first run.

DEFAULT_SAFETENSORS_DIR = ''
DEFAULT_GGUF_DIR        = ''
DEFAULT_QUANTIZED_DIR   = ''
DEFAULT_CONVERT_SCRIPT  = ''   # path to convert_hf_to_gguf.py
DEFAULT_QUANTIZE_BIN    = ''   # path to llama-quantize executable
