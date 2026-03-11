"""
Tests for LlamaConfigManager and DEFAULT_CONFIG.

Covers:
- Default config values and structure
- Loading config from disk / merging with defaults
- Saving and reloading round-trips
- Loading models from models.ini (legacy format)
- Loading models from saved_models in app_config.json
- Adding, removing, and toggling model entries
- Enabled/disabled filtering in save_models()
- Path normalisation
- Missing / empty models_ini_path handling
"""

import configparser
import json
import os
import sys
import tempfile
import unittest

# Allow running tests from the repo root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DEFAULT_CONFIG, LlamaConfigManager


class TestDefaultConfig(unittest.TestCase):
    """Sanity-check the shape and safe defaults of DEFAULT_CONFIG."""

    def test_required_keys_present(self):
        required = {
            'llama_server_path', 'open_webui_path', 'models_ini_path',
            'host', 'llama_port', 'webui_port', 'api_key',
            'threads', 'ngl', 'fit', 'fit_target', 'batch_size', 'parallel',
            'context_shift', 'flash_attn', 'close_on_launch_both', 'app_theme',
        }
        self.assertTrue(required.issubset(DEFAULT_CONFIG.keys()))

    def test_no_personal_paths(self):
        """Path fields must not contain hard-coded personal directory references."""
        path_keys = ('llama_server_path', 'open_webui_path', 'models_ini_path')
        for key in path_keys:
            self.assertEqual(DEFAULT_CONFIG[key], '',
                             f'{key} should be empty in DEFAULT_CONFIG')

    def test_host_is_localhost(self):
        self.assertEqual(DEFAULT_CONFIG['host'], '127.0.0.1')

    def test_api_key_is_blank(self):
        self.assertEqual(DEFAULT_CONFIG['api_key'], '')

    def test_boolean_fields(self):
        self.assertIsInstance(DEFAULT_CONFIG['context_shift'], bool)
        self.assertIsInstance(DEFAULT_CONFIG['close_on_launch_both'], bool)

    def test_theme_is_modern(self):
        self.assertEqual(DEFAULT_CONFIG['app_theme'], 'modern')


class TestConfigLoadSave(unittest.TestCase):
    """LlamaConfigManager load / save behaviour."""

    def setUp(self):
        self.tmpdir    = tempfile.mkdtemp()
        self.cfg_path  = os.path.join(self.tmpdir, 'app_config.json')
        self.ini_path  = os.path.join(self.tmpdir, 'models.ini')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── Fresh start ───────────────────────────────────────────────────────────

    def test_fresh_config_uses_defaults(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        for key, value in DEFAULT_CONFIG.items():
            self.assertIn(key, mgr.config)
            self.assertEqual(mgr.config[key], value)

    def test_fresh_config_empty_model_list(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        self.assertEqual(mgr.models, [])

    # ── Partial override ──────────────────────────────────────────────────────

    def test_disk_values_override_defaults(self):
        on_disk = {'host': '192.168.1.100', 'llama_port': '9999'}
        with open(self.cfg_path, 'w') as f:
            json.dump(on_disk, f)

        mgr = LlamaConfigManager(config_file=self.cfg_path)
        self.assertEqual(mgr.config['host'], '192.168.1.100')
        self.assertEqual(mgr.config['llama_port'], '9999')
        # Keys not on disk should still come from defaults
        self.assertEqual(mgr.config['app_theme'], DEFAULT_CONFIG['app_theme'])

    def test_missing_keys_filled_from_defaults(self):
        # Write a config that's missing several keys
        with open(self.cfg_path, 'w') as f:
            json.dump({'host': '10.0.0.1'}, f)

        mgr = LlamaConfigManager(config_file=self.cfg_path)
        self.assertIn('threads', mgr.config)
        self.assertEqual(mgr.config['threads'], DEFAULT_CONFIG['threads'])

    # ── Save round-trip ───────────────────────────────────────────────────────

    def test_save_config_creates_file(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.save_config()
        self.assertTrue(os.path.exists(self.cfg_path))

    def test_save_load_roundtrip(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.config['host'] = '10.10.10.10'
        mgr.models = [{'name': 'MyModel', 'model': '/tmp/m.gguf', 'ctx_size': '4096', 'enabled': True}]
        mgr.save_config()

        mgr2 = LlamaConfigManager(config_file=self.cfg_path)
        self.assertEqual(mgr2.config['host'], '10.10.10.10')
        self.assertEqual(len(mgr2.models), 1)
        self.assertEqual(mgr2.models[0]['name'], 'MyModel')

    def test_saved_models_key_takes_priority_over_ini(self):
        """When saved_models exists in JSON it must win over models.ini."""
        # Write a models.ini that would produce a different model list
        with open(self.ini_path, 'w') as f:
            f.write('[IniModel]\nmodel = /ini/model.gguf\nctx-size = 1024\n')

        saved = [{'name': 'JsonModel', 'model': '/json/model.gguf', 'ctx_size': '2048', 'enabled': True}]
        with open(self.cfg_path, 'w') as f:
            json.dump({'models_ini_path': self.ini_path, 'saved_models': saved}, f)

        mgr = LlamaConfigManager(config_file=self.cfg_path)
        self.assertEqual(len(mgr.models), 1)
        self.assertEqual(mgr.models[0]['name'], 'JsonModel')


class TestLegacyIniLoading(unittest.TestCase):
    """Loading model list from a models.ini file (no saved_models key)."""

    def setUp(self):
        self.tmpdir   = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, 'app_config.json')
        self.ini_path = os.path.join(self.tmpdir, 'models.ini')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_ini(self, content: str):
        with open(self.ini_path, 'w') as f:
            f.write(content)

    def _make_manager(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.config['models_ini_path'] = self.ini_path
        mgr.models = mgr.load_models()
        return mgr

    def test_single_model_loaded(self):
        self._write_ini('[TestModel]\nmodel = /path/to/model.gguf\nctx-size = 2048\n')
        mgr = self._make_manager()
        self.assertEqual(len(mgr.models), 1)
        self.assertEqual(mgr.models[0]['name'], 'TestModel')
        self.assertEqual(mgr.models[0]['ctx_size'], '2048')

    def test_path_normalised(self):
        self._write_ini('[TestModel]\nmodel = /path/to/model.gguf\nctx-size = 2048\n')
        mgr = self._make_manager()
        self.assertEqual(mgr.models[0]['model'],
                         os.path.normpath('/path/to/model.gguf'))

    def test_multiple_models_loaded(self):
        self._write_ini(
            '[Alpha]\nmodel = /a.gguf\nctx-size = 1024\n'
            '[Beta]\nmodel = /b.gguf\nctx-size = 4096\n'
        )
        mgr = self._make_manager()
        names = [m['name'] for m in mgr.models]
        self.assertIn('Alpha', names)
        self.assertIn('Beta', names)

    def test_all_loaded_models_enabled_by_default(self):
        self._write_ini('[M]\nmodel = /m.gguf\nctx-size = 2048\n')
        mgr = self._make_manager()
        self.assertTrue(mgr.models[0]['enabled'])

    def test_missing_ctx_size_defaults_to_2048(self):
        self._write_ini('[NoCtx]\nmodel = /x.gguf\n')
        mgr = self._make_manager()
        self.assertEqual(mgr.models[0]['ctx_size'], '2048')

    def test_nonexistent_ini_returns_empty_list(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.config['models_ini_path'] = '/does/not/exist.ini'
        mgr.models = mgr.load_models()
        self.assertEqual(mgr.models, [])

    def test_empty_ini_path_returns_empty_list(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.config['models_ini_path'] = ''
        mgr.models = mgr.load_models()
        self.assertEqual(mgr.models, [])


class TestModelOperations(unittest.TestCase):
    """Adding, removing, toggling, and persisting models."""

    def setUp(self):
        self.tmpdir   = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, 'app_config.json')
        self.ini_path = os.path.join(self.tmpdir, 'models.ini')
        with open(self.ini_path, 'w') as f:
            f.write('[Base]\nmodel = /base.gguf\nctx-size = 2048\n')
        self.mgr = LlamaConfigManager(config_file=self.cfg_path)
        self.mgr.config['models_ini_path'] = self.ini_path
        self.mgr.models = self.mgr.load_models()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_model(self):
        self.mgr.models.append(
            {'name': 'New', 'model': '/new.gguf', 'ctx_size': '4096', 'enabled': True}
        )
        self.assertEqual(len(self.mgr.models), 2)
        self.assertEqual(self.mgr.models[-1]['name'], 'New')

    def test_remove_model(self):
        self.mgr.models.append(
            {'name': 'Extra', 'model': '/extra.gguf', 'ctx_size': '1024', 'enabled': True}
        )
        self.mgr.models.pop(0)
        self.assertEqual(len(self.mgr.models), 1)
        self.assertEqual(self.mgr.models[0]['name'], 'Extra')

    def test_toggle_enabled(self):
        self.mgr.models[0]['enabled'] = not self.mgr.models[0].get('enabled', True)
        self.assertFalse(self.mgr.models[0]['enabled'])
        self.mgr.models[0]['enabled'] = not self.mgr.models[0]['enabled']
        self.assertTrue(self.mgr.models[0]['enabled'])

    def test_save_models_writes_ini(self):
        self.mgr.models.append(
            {'name': 'Added', 'model': '/added.gguf', 'ctx_size': '8192', 'enabled': True}
        )
        self.mgr.save_models()
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.ini_path)
        self.assertIn('Added', cfg.sections())
        self.assertEqual(cfg.get('Added', 'ctx-size'), '8192')

    def test_save_models_excludes_disabled(self):
        self.mgr.models = [
            {'name': 'On',  'model': '/on.gguf',  'ctx_size': '2048', 'enabled': True},
            {'name': 'Off', 'model': '/off.gguf', 'ctx_size': '2048', 'enabled': False},
        ]
        self.mgr.save_models()
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.ini_path)
        self.assertIn('On',  cfg.sections())
        self.assertNotIn('Off', cfg.sections())

    def test_save_models_returns_false_without_ini_path(self):
        self.mgr.config['models_ini_path'] = ''
        result = self.mgr.save_models()
        self.assertFalse(result)

    def test_save_models_returns_true_with_valid_ini_path(self):
        result = self.mgr.save_models()
        self.assertTrue(result)

    def test_save_config_includes_saved_models(self):
        self.mgr.models = [
            {'name': 'Stored', 'model': '/s.gguf', 'ctx_size': '4096', 'enabled': True}
        ]
        self.mgr.save_config()
        with open(self.cfg_path) as f:
            data = json.load(f)
        self.assertIn('saved_models', data)
        self.assertTrue(any(m['name'] == 'Stored' for m in data['saved_models']))

    def test_model_ctx_size_preserved_after_roundtrip(self):
        self.mgr.models = [
            {'name': 'Big', 'model': '/big.gguf', 'ctx_size': '32768', 'enabled': True}
        ]
        self.mgr.save_config()
        mgr2 = LlamaConfigManager(config_file=self.cfg_path)
        self.assertEqual(mgr2.models[0]['ctx_size'], '32768')


class TestConfigEdgeCases(unittest.TestCase):
    """Edge cases and defensive behaviour."""

    def setUp(self):
        self.tmpdir   = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, 'app_config.json')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_config_with_extra_unknown_keys(self):
        """Unknown keys from disk are passed through without error."""
        with open(self.cfg_path, 'w') as f:
            json.dump({'future_setting': 'value', 'host': '1.2.3.4'}, f)
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        self.assertEqual(mgr.config.get('future_setting'), 'value')

    def test_reload_after_save(self):
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.config['threads'] = '16'
        mgr.save_config()
        mgr.load_config()
        self.assertEqual(mgr.config['threads'], '16')

    def test_default_config_not_mutated(self):
        """Modifying an instance's config must not affect DEFAULT_CONFIG."""
        mgr = LlamaConfigManager(config_file=self.cfg_path)
        mgr.config['host'] = 'mutated'
        self.assertEqual(DEFAULT_CONFIG['host'], '127.0.0.1')


if __name__ == '__main__':
    unittest.main()
