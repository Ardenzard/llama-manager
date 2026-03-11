"""
Tests for theme definitions and the THEMES registry.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_manager.themes import CLASSIC_THEME, MODERN_THEME, THEMES

REQUIRED_KEYS = {
    'name', 'bg', 'bg_surface', 'bg_raised', 'bg_input',
    'border', 'border_focus', 'accent', 'accent_dim',
    'fg', 'fg_dim', 'danger', 'tag_yes', 'tag_no',
    'font_body', 'font_head', 'font_mono', 'font_btn',
    'btn_primary_bg', 'btn_primary_fg',
    'btn_secondary_bg', 'btn_secondary_fg',
    'btn_danger_bg', 'btn_danger_fg',
    'tree_row_alt', 'tree_row_sel', 'tree_row_sel_fg',
    'scrollbar_bg', 'scrollbar_thumb', 'radius',
}


class TestThemeStructure(unittest.TestCase):

    def _check_theme(self, theme):
        for key in REQUIRED_KEYS:
            self.assertIn(key, theme, f"Missing key '{key}' in theme '{theme.get('name')}'")

    def test_modern_theme_complete(self):
        self._check_theme(MODERN_THEME)

    def test_classic_theme_complete(self):
        self._check_theme(CLASSIC_THEME)

    def test_modern_name_field(self):
        self.assertEqual(MODERN_THEME['name'], 'modern')

    def test_classic_name_field(self):
        self.assertEqual(CLASSIC_THEME['name'], 'classic')

    def test_themes_registry_contains_both(self):
        self.assertIn('modern',  THEMES)
        self.assertIn('classic', THEMES)

    def test_themes_registry_references_correct_objects(self):
        self.assertIs(THEMES['modern'],  MODERN_THEME)
        self.assertIs(THEMES['classic'], CLASSIC_THEME)

    def test_colour_values_are_hex_strings(self):
        """Spot-check that colour fields look like CSS hex strings."""
        colour_keys = ('bg', 'accent', 'fg', 'danger', 'border')
        for theme in (MODERN_THEME, CLASSIC_THEME):
            for key in colour_keys:
                val = theme[key]
                self.assertIsInstance(val, str)
                self.assertTrue(val.startswith('#'),
                                f"theme '{theme['name']}' key '{key}' = {val!r} is not a hex colour")
                self.assertIn(len(val), (4, 7),
                              f"unexpected hex colour length: {val!r}")

    def test_font_tuples_have_two_elements(self):
        font_keys = ('font_body', 'font_head', 'font_mono', 'font_btn')
        for theme in (MODERN_THEME, CLASSIC_THEME):
            for key in font_keys:
                self.assertEqual(len(theme[key]), 2,
                                 f"'{key}' in '{theme['name']}' should be (family, size)")

    def test_radius_is_numeric(self):
        for theme in (MODERN_THEME, CLASSIC_THEME):
            self.assertIsInstance(theme['radius'], (int, float))
            self.assertGreaterEqual(theme['radius'], 0)


if __name__ == '__main__':
    unittest.main()
