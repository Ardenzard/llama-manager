"""
llama_manager (app) — GUI controller for llama.cpp servers and Open WebUI.

Typical usage::

    python -m llama_manager

Non-GUI submodules (config, constants, downloader, themes) are imported
eagerly and are safe to use in headless / test environments.  The GUI
modules (app, widgets) require tkinter and are imported lazily so that
test suites can import the rest of the package without a display.
"""

from .config import DEFAULT_CONFIG, LlamaConfigManager
from .constants import HF_BASE, QUANTS
from .downloader import ModelDownloader
from .themes import CLASSIC_THEME, MODERN_THEME, THEMES

__all__ = [
    'LlamaManagerApp',
    'LlamaConfigManager',
    'DEFAULT_CONFIG',
    'ModelDownloader',
    'ThemedButton',
    'MODERN_THEME',
    'CLASSIC_THEME',
    'THEMES',
    'QUANTS',
    'HF_BASE',
]


def __getattr__(name):
    # Lazily import GUI classes so that importing the package in a headless
    # environment (e.g. during tests) does not raise ModuleNotFoundError.
    if name == 'LlamaManagerApp':
        from .app import LlamaManagerApp
        return LlamaManagerApp
    if name == 'ThemedButton':
        from .widgets import ThemedButton
        return ThemedButton
    raise AttributeError(f"module 'llama_manager' has no attribute {name!r}")
