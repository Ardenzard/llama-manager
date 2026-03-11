"""
Visual theme definitions.

Each theme is a plain dict that every widget and the app pull from.
To add a new theme, define a dict following the same key schema and add
it to the THEMES registry at the bottom of this file.
"""

MODERN_THEME = {
    'name': 'modern',
    'bg':             '#0f1117',
    'bg_surface':     '#171b24',
    'bg_raised':      '#1e2433',
    'bg_input':       '#141820',
    'border':         '#2a3348',
    'border_focus':   '#00c9a7',
    'accent':         '#00c9a7',
    'accent_dim':     '#00876f',
    'fg':             '#e2e8f4',
    'fg_dim':         '#7a8ba8',
    'danger':         '#ff4d6d',
    'tag_yes':        '#00c9a7',
    'tag_no':         '#ff4d6d',
    'font_body':      ('Segoe UI', 10),
    'font_head':      ('Segoe UI Semibold', 10),
    'font_mono':      ('Consolas', 9),
    'font_btn':       ('Segoe UI Semibold', 9),
    'btn_primary_bg':    '#00c9a7',
    'btn_primary_fg':    '#0a0e14',
    'btn_secondary_bg':  '#1e2433',
    'btn_secondary_fg':  '#b0bdd4',
    'btn_danger_bg':     '#2a1520',
    'btn_danger_fg':     '#ff4d6d',
    'tree_row_alt':      '#171b24',
    'tree_row_sel':      '#1a3030',
    'tree_row_sel_fg':   '#00c9a7',
    'scrollbar_bg':      '#1e2433',
    'scrollbar_thumb':   '#2a3348',
    'radius':         6,
}

CLASSIC_THEME = {
    'name': 'classic',
    'bg':             '#f0f0f0',
    'bg_surface':     '#ffffff',
    'bg_raised':      '#e8e8e8',
    'bg_input':       '#ffffff',
    'border':         '#c0c0c0',
    'border_focus':   '#0078d7',
    'accent':         '#0078d7',
    'accent_dim':     '#005a9e',
    'fg':             '#1a1a1a',
    'fg_dim':         '#555555',
    'danger':         '#cc0000',
    'tag_yes':        '#007700',
    'tag_no':         '#cc0000',
    'font_body':      ('Segoe UI', 10),
    'font_head':      ('Segoe UI Semibold', 10),
    'font_mono':      ('Consolas', 9),
    'font_btn':       ('Segoe UI', 9),
    'btn_primary_bg':    '#0078d7',
    'btn_primary_fg':    '#ffffff',
    'btn_secondary_bg':  '#e1e1e1',
    'btn_secondary_fg':  '#1a1a1a',
    'btn_danger_bg':     '#fde8e8',
    'btn_danger_fg':     '#cc0000',
    'tree_row_alt':      '#f5f5f5',
    'tree_row_sel':      '#cce4f7',
    'tree_row_sel_fg':   '#003d6b',
    'scrollbar_bg':      '#f0f0f0',
    'scrollbar_thumb':   '#c0c0c0',
    'radius':         3,
}

# Registry: name → theme dict
THEMES = {
    'modern':  MODERN_THEME,
    'classic': CLASSIC_THEME,
}
