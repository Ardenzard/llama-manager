"""
Application configuration and model list management.

LlamaConfigManager handles reading/writing app_config.json and the
optional models.ini legacy format.
"""

import configparser
import json
import os

CONFIG_FILE = 'app_config.json'

# ── Default configuration ─────────────────────────────────────────────────────
# All path fields are intentionally blank so users supply their own on first run.
# The Settings panel will prompt for each value.

DEFAULT_CONFIG = {
    'llama_server_path': '',
    'open_webui_path':   '',
    'models_ini_path':   '',
    'host':              '127.0.0.1',
    'llama_port':        '5001',
    'webui_port':        '5002',
    'api_key':           '',
    'threads':           '4',
    'ngl':               'auto',
    'fit':               'on',
    'fit_target':        '1024',
    'batch_size':        '512',
    'parallel':          '1',
    'context_shift':     True,
    'flash_attn':        'auto',
    'close_on_launch_both': False,
    'app_theme':         'modern',
}


class LlamaConfigManager:
    """Load, persist, and expose application config and model list."""

    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.load_config()
        self.models = self.load_models()

    # ── Config ────────────────────────────────────────────────────────────────

    def load_config(self) -> None:
        """Read config from disk, falling back to defaults for missing keys."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = {**DEFAULT_CONFIG, **json.load(f)}
        else:
            self.config = DEFAULT_CONFIG.copy()

    def save_config(self) -> None:
        """Persist current config (including model list) to disk."""
        self.config['saved_models'] = self.models
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    # ── Models ────────────────────────────────────────────────────────────────

    def load_models(self) -> list:
        """
        Return the model list.

        Priority:
        1. ``saved_models`` key in config (JSON format used by this app).
        2. Legacy models.ini pointed to by ``models_ini_path``.
        3. Empty list.
        """
        if 'saved_models' in self.config:
            models = self.config['saved_models']
            for m in models:
                if 'model' in m:
                    m['model'] = os.path.normpath(m['model'])
            return models

        models = []
        path = self.config.get('models_ini_path')
        if path and os.path.exists(path):
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(path)
            for section in cfg.sections():
                models.append({
                    'name':     section,
                    'model':    os.path.normpath(cfg.get(section, 'model',    fallback='')),
                    'ctx_size': cfg.get(section, 'ctx-size', fallback='2048'),
                    'enabled':  True,
                })
        return models

    def save_models(self) -> bool:
        """
        Write enabled models back to the legacy models.ini file.

        Returns True on success, False if ``models_ini_path`` is not configured.
        """
        path = self.config.get('models_ini_path')
        if not path or not path.strip():
            return False
        cfg = configparser.ConfigParser(interpolation=None)
        for m in [x for x in self.models if x.get('enabled', True)]:
            cfg[m['name']] = {
                'model':    os.path.normpath(m['model']),
                'ctx-size': m['ctx_size'],
            }
        with open(path, 'w') as f:
            cfg.write(f)
        return True
