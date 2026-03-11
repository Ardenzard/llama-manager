"""
Main application window: LlamaManagerApp.

Tabs
----
Models    – view, add, remove, edit and toggle GGUF model entries.
Pipeline  – download a HuggingFace model, convert to GGUF, and quantise.
Settings  – all configuration fields plus pipeline path configuration.
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .config import DEFAULT_CONFIG, LlamaConfigManager
from .constants import (
    DEFAULT_CONVERT_SCRIPT,
    DEFAULT_GGUF_DIR,
    DEFAULT_QUANTIZE_BIN,
    DEFAULT_QUANTIZED_DIR,
    DEFAULT_SAFETENSORS_DIR,
    QUANTS,
)
from .downloader import HAS_REQUESTS, ModelDownloader
from .themes import MODERN_THEME, THEMES
from .widgets import ThemedButton


class LlamaManagerApp:
    """Root window controller for Llama Manager."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Llama Manager')
        self.root.geometry('980x660')
        self.root.minsize(820, 520)

        self.manager = LlamaConfigManager()
        saved_theme  = self.manager.config.get('app_theme', 'modern')
        self.current_theme = THEMES.get(saved_theme, MODERN_THEME)

        self._apply_ttk_style()
        self.setup_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # Theme / style
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_ttk_style(self) -> None:
        """Configure ttk styles to match the current theme."""
        t     = self.current_theme
        style = ttk.Style()

        if t['name'] == 'modern':
            try:
                style.theme_use('clam')
            except Exception:
                pass

            style.configure('.',
                background=t['bg'], foreground=t['fg'],
                font=t['font_body'], bordercolor=t['border'],
                troughcolor=t['bg_surface'], fieldbackground=t['bg_input'],
                selectbackground=t['accent_dim'], selectforeground=t['fg'])

            style.configure('TFrame',  background=t['bg'])
            style.configure('TLabel',  background=t['bg'], foreground=t['fg'], font=t['font_body'])
            style.configure('TEntry',
                fieldbackground=t['bg_input'], foreground=t['fg'],
                bordercolor=t['border'], insertcolor=t['accent'],
                selectbackground=t['accent_dim'], padding=6)
            style.map('TEntry', bordercolor=[('focus', t['border_focus'])])

            style.configure('TCheckbutton',
                background=t['bg'], foreground=t['fg'], font=t['font_body'])
            style.map('TCheckbutton',
                indicatorcolor=[('selected', t['accent']), ('!selected', t['bg_input'])],
                background=[('active', t['bg'])])

            style.configure('Treeview',
                background=t['bg_surface'], foreground=t['fg'],
                fieldbackground=t['bg_surface'], borderwidth=0,
                font=t['font_body'], rowheight=30)
            style.configure('Treeview.Heading',
                background=t['bg_raised'], foreground=t['fg_dim'],
                font=t['font_head'], relief='flat', borderwidth=0)
            style.map('Treeview',
                background=[('selected', t['tree_row_sel'])],
                foreground=[('selected', t['tree_row_sel_fg'])])
            style.map('Treeview.Heading',
                background=[('active', t['bg_raised'])],
                foreground=[('active', t['accent'])])

            style.configure('Vertical.TScrollbar',
                background=t['scrollbar_thumb'], troughcolor=t['scrollbar_bg'],
                borderwidth=0, relief='flat', arrowsize=12)
            style.configure('TCombobox',
                fieldbackground=t['bg_input'], background=t['bg_raised'],
                foreground=t['fg'], selectbackground=t['bg_input'],
                selectforeground=t['fg'], bordercolor=t['border'],
                lightcolor=t['border'], darkcolor=t['border'],
                arrowcolor=t['fg_dim'], arrowsize=14)
            style.map('TCombobox',
                fieldbackground=[('readonly', t['bg_input']), ('disabled', t['bg'])],
                foreground=[('disabled', t['fg_dim'])],
                bordercolor=[('focus', t['border_focus'])],
                arrowcolor=[('hover', t['accent'])])
            style.configure('TSpinbox',
                fieldbackground=t['bg_input'], background=t['bg_raised'],
                foreground=t['fg'], selectbackground=t['accent_dim'],
                selectforeground=t['fg'], bordercolor=t['border'],
                lightcolor=t['border'], darkcolor=t['border'],
                arrowcolor=t['fg_dim'], arrowsize=12)
            style.map('TSpinbox',
                bordercolor=[('focus', t['border_focus'])],
                arrowcolor=[('hover', t['accent'])])
            style.configure('TLabelframe',
                background=t['bg'], bordercolor=t['border'], relief='flat')
            style.configure('TLabelframe.Label',
                background=t['bg'], foreground=t['accent'], font=t['font_head'])
        else:
            try:
                style.theme_use('vista' if os.name == 'nt' else 'clam')
            except Exception:
                style.theme_use('clam')
            style.configure('Treeview', rowheight=26)
            style.configure('Treeview.Heading', font=t['font_head'])

        self.root.configure(bg=t['bg'])

    def _on_theme_change(self) -> None:
        chosen = self.theme_var.get()
        if chosen != self.current_theme['name']:
            self.switch_theme(chosen)

    def _add_entry_shortcuts(self, widget) -> None:
        """Add standard keyboard shortcuts (Ctrl+A, Ctrl+V, etc.) to an Entry/Spinbox."""
        widget.bind('<Control-a>', lambda e: self._select_all(e, widget))
        widget.bind('<Control-A>', lambda e: self._select_all(e, widget))
        # Ensure standard copy/paste work even if the OS-level defaults are missing
        widget.bind('<Control-v>', lambda e: widget.event_generate('<<Paste>>'))
        widget.bind('<Control-V>', lambda e: widget.event_generate('<<Paste>>'))
        widget.bind('<Control-c>', lambda e: widget.event_generate('<<Copy>>'))
        widget.bind('<Control-C>', lambda e: widget.event_generate('<<Copy>>'))
        widget.bind('<Control-x>', lambda e: widget.event_generate('<<Cut>>'))
        widget.bind('<Control-X>', lambda e: widget.event_generate('<<Cut>>'))

    def _select_all(self, event, widget) -> str:
        widget.selection_range(0, 'end')
        widget.icursor('end')
        return 'break'

    def switch_theme(self, theme_name: str) -> None:
        """Rebuild the entire UI under a new theme."""
        prev_tab = getattr(self, '_active_tab', 'settings')
        self.current_theme = THEMES.get(theme_name, MODERN_THEME)
        self.manager.config['app_theme'] = theme_name
        self._apply_ttk_style()
        for w in self.root.winfo_children():
            w.destroy()
        self.setup_ui()
        self._switch_tab(prev_tab)

    # ══════════════════════════════════════════════════════════════════════════
    # Top-level UI layout
    # ══════════════════════════════════════════════════════════════════════════

    def setup_ui(self) -> None:
        t = self.current_theme

        # ── Header ───────────────────────────────────────────────────────────
        self.header = tk.Frame(self.root, bg=t['bg_surface'], height=58, bd=0, highlightthickness=0)
        self.header.pack(side='top', fill='x')
        self.header.pack_propagate(False)
        inner_h = tk.Frame(self.header, bg=t['bg_surface'])
        inner_h.pack(fill='both', expand=True, padx=20)
        tk.Label(inner_h, text='\u2b21', font=('Segoe UI', 20),
                 fg=t['accent'], bg=t['bg_surface']).pack(side='left', pady=10, padx=(0, 10))
        title_stack = tk.Frame(inner_h, bg=t['bg_surface'])
        title_stack.pack(side='left', fill='y', pady=10)
        tk.Label(title_stack, text='LLAMA MANAGER',
                 font=('Segoe UI Semibold', 12), fg=t['fg'],
                 bg=t['bg_surface']).pack(anchor='w')
        tk.Label(title_stack, text='llama.cpp & Open WebUI controller',
                 font=('Segoe UI', 8), fg=t['fg_dim'],
                 bg=t['bg_surface']).pack(anchor='w')
        tk.Frame(self.root, bg=t['border'], height=1).pack(side='top', fill='x')

        # ── Bottom action bar ─────────────────────────────────────────────────
        tk.Frame(self.root, bg=t['border'], height=1).pack(side='bottom', fill='x')
        self.action_bar = tk.Frame(self.root, bg=t['bg_surface'], height=62, bd=0, highlightthickness=0)
        self.action_bar.pack(side='bottom', fill='x')
        self.action_bar.pack_propagate(False)
        inner_a = tk.Frame(self.action_bar, bg=t['bg_surface'])
        inner_a.pack(fill='both', expand=True, padx=16)

        self.btn_save   = ThemedButton(inner_a, text='Save Settings',       command=self.update_all,   btn_style='secondary', theme=t, canvas_bg=t['bg_surface'])
        self.btn_llama  = ThemedButton(inner_a, text='Launch Llama Server', command=self.launch_llama, btn_style='secondary', theme=t, canvas_bg=t['bg_surface'])
        self.btn_webui  = ThemedButton(inner_a, text='Launch Open WebUI',   command=self.launch_webui, btn_style='secondary', theme=t, canvas_bg=t['bg_surface'])
        self.btn_update = ThemedButton(inner_a, text='\u2191 Update WebUI', command=self.update_webui, btn_style='secondary', theme=t, canvas_bg=t['bg_surface'])
        self.btn_both   = ThemedButton(inner_a, text='Launch Both \u25b6',  command=self.launch_both,  btn_style='primary',   theme=t, canvas_bg=t['bg_surface'])
        self.btn_save.pack(side='left',   padx=(0, 6), pady=14)
        self.btn_llama.pack(side='left',  padx=6,      pady=14)
        self.btn_webui.pack(side='left',  padx=6,      pady=14)
        self.btn_update.pack(side='left', padx=6,      pady=14)
        self.btn_both.pack(side='right',  padx=(6, 0), pady=14)

        # ── Tab strip ─────────────────────────────────────────────────────────
        # Layout: [1px left] [Tab] [1px divider] … [spacer]
        # Fully custom so we can control borders on every side precisely.
        tab_strip = tk.Frame(self.root, bg=t['bg_surface'])
        tab_strip.pack(side='top', fill='x')
        tk.Frame(tab_strip, bg=t['border'], width=1).pack(side='left', fill='y')

        self._tab_meta = {}
        tab_defs = [('models', 'Models'), ('pipeline', 'Pipeline'), ('settings', 'Settings')]
        for _i, (key, label) in enumerate(tab_defs):
            wrap = tk.Frame(tab_strip, bg=t['bg_surface'], cursor='hand2')
            wrap.pack(side='left')
            lbl = tk.Label(wrap, text=f'  {label}  ', font=t['font_body'],
                           fg=t['fg_dim'], bg=t['bg_surface'], pady=9, padx=2)
            lbl.pack()
            ind = tk.Frame(wrap, height=2, bg=t['bg_surface'])
            ind.pack(fill='x')
            self._tab_meta[key] = {'lbl': lbl, 'ind': ind, 'wrap': wrap}
            for w in (wrap, lbl, ind):
                w.bind('<Button-1>', lambda e, k=key: self._switch_tab(k))
            tk.Frame(tab_strip, bg=t['border'], width=1).pack(side='left', fill='y')

        tk.Frame(self.root, bg=t['border'], height=1).pack(side='top', fill='x')

        # ── Content area ──────────────────────────────────────────────────────
        content = tk.Frame(self.root, bg=t['bg'])
        content.pack(side='top', fill='both', expand=True)
        self.models_tab   = tk.Frame(content, bg=t['bg'])
        self.settings_tab = tk.Frame(content, bg=t['bg'])
        self.pipeline_tab = tk.Frame(content, bg=t['bg'])
        for f in (self.models_tab, self.settings_tab, self.pipeline_tab):
            f.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._active_tab = None
        self._switch_tab('models')
        self.setup_models_tab()
        self.setup_settings_tab()
        self.setup_pipeline_tab()

    def _switch_tab(self, name: str) -> None:
        t = self.current_theme
        self._active_tab = name
        for key, meta in self._tab_meta.items():
            active = (key == name)
            meta['lbl'].config(fg=t['accent'] if active else t['fg_dim'])
            meta['ind'].config(bg=t['accent'] if active else t['bg_surface'])
        frames = {'models': self.models_tab, 'pipeline': self.pipeline_tab, 'settings': self.settings_tab}
        frames[name].lift()

    # ══════════════════════════════════════════════════════════════════════════
    # Models tab
    # ══════════════════════════════════════════════════════════════════════════

    def setup_models_tab(self) -> None:
        t = self.current_theme

        toolbar = tk.Frame(self.models_tab, bg=t['bg'], height=50)
        toolbar.pack(side='top', fill='x', padx=16, pady=(12, 0))
        toolbar.pack_propagate(False)
        left_tools = tk.Frame(toolbar, bg=t['bg'])
        left_tools.pack(side='left', fill='y')

        self.btn_toggle = ThemedButton(left_tools, text='Toggle Enabled', command=self.toggle_enabled, btn_style='secondary', theme=t, btn_width=130)
        self.btn_add    = ThemedButton(left_tools, text='+ Add Model',    command=self.add_model,      btn_style='secondary', theme=t, btn_width=115)
        self.btn_remove = ThemedButton(left_tools, text='Remove',         command=self.remove_model,   btn_style='danger',    theme=t, btn_width=90)
        self.btn_edit   = ThemedButton(left_tools, text='Edit',           command=self.edit_model,     btn_style='secondary', theme=t, btn_width=80)
        for btn in (self.btn_toggle, self.btn_add, self.btn_remove, self.btn_edit):
            btn.pack(side='left', padx=(0, 6), pady=8)

        self.model_count_label = tk.Label(toolbar, text='', font=t['font_body'], fg=t['fg_dim'], bg=t['bg'])
        self.model_count_label.pack(side='right', padx=8)

        tree_outer = tk.Frame(self.models_tab, bg=t['border'])
        tree_outer.pack(side='top', fill='both', expand=True, padx=16, pady=10)
        tree_inner = tk.Frame(tree_outer, bg=t['bg_surface'])
        tree_inner.pack(fill='both', expand=True, padx=1, pady=1)

        cols = ('Enabled', 'Name', 'Path', 'Ctx Size')
        self.tree = ttk.Treeview(tree_inner, columns=cols, show='headings', selectmode='browse')
        for col, w, anchor, stretch in [
            ('Enabled',  72,  'center', False),
            ('Name',    185,  'w',      True),
            ('Path',    490,  'w',      True),
            ('Ctx Size', 85,  'center', False),
        ]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=anchor, stretch=stretch)

        self.tree.tag_configure('enabled',  foreground=t['tag_yes'])
        self.tree.tag_configure('disabled', foreground=t['tag_no'])
        self.tree.tag_configure('alt',      background=t['tree_row_alt'])
        self.tree.tag_configure('alt_dis',  background=t['tree_row_alt'], foreground=t['tag_no'])

        vsb = ttk.Scrollbar(tree_inner, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda e: self.edit_model())

        self.context_menu = tk.Menu(self.root, tearoff=0,
            bg=t['bg_raised'], fg=t['fg'],
            activebackground=t['accent_dim'], activeforeground=t['fg'],
            font=t['font_body'], bd=0, relief='flat')
        self.context_menu.add_command(label='Copy Path',      command=self.copy_model_path)
        self.context_menu.add_command(label='Edit Model',     command=self.edit_model)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Toggle Enabled', command=self.toggle_enabled)
        self.context_menu.add_command(label='Remove Model',   command=self.remove_model)
        self.tree.bind('<Button-3>', self.show_context_menu)

        self.refresh_tree()

    def show_context_menu(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def copy_model_path(self) -> None:
        selected = self.tree.selection()
        if selected:
            idx = self.tree.index(selected[0])
            self.root.clipboard_clear()
            self.root.clipboard_append(self.manager.models[idx]['model'])

    def refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, m in enumerate(self.manager.models):
            enabled = m.get('enabled', True)
            alt     = (i % 2 == 1)
            tag     = ('alt', 'enabled') if (alt and enabled) else \
                      ('enabled',)       if enabled           else \
                      ('alt_dis',)       if alt               else \
                      ('disabled',)
            enabled_str = '\u25cf Yes' if enabled else '\u25cb  No'
            self.tree.insert('', 'end',
                             values=(enabled_str, m['name'], m['model'], m['ctx_size']),
                             tags=tag)
        total  = len(self.manager.models)
        active = sum(1 for m in self.manager.models if m.get('enabled', True))
        if hasattr(self, 'model_count_label'):
            self.model_count_label.config(text=f'{active} active \u00b7 {total} total')

    def toggle_enabled(self) -> None:
        selected = self.tree.selection()
        if selected:
            idx = self.tree.index(selected[0])
            m = self.manager.models[idx]
            m['enabled'] = not m.get('enabled', True)
            self.refresh_tree()

    def add_model(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.root,
            filetypes=[('GGUF files', '*.gguf'), ('All files', '*.*')])
        if file_path:
            file_path = os.path.normpath(file_path)
            name      = os.path.basename(file_path).replace('.gguf', '')
            self.manager.models.append({
                'name': name, 'model': file_path, 'ctx_size': '2048', 'enabled': True,
            })
            self.refresh_tree()

    def remove_model(self) -> None:
        selected = self.tree.selection()
        if selected:
            del self.manager.models[self.tree.index(selected[0])]
            self.refresh_tree()

    def edit_model(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        idx   = self.tree.index(selected[0])
        model = self.manager.models[idx]
        t     = self.current_theme

        win = tk.Toplevel(self.root)
        win.title('Edit Model')
        win.configure(bg=t['bg'])
        win.geometry('580x230')
        win.resizable(True, False)
        win.transient(self.root)
        win.grab_set()
        win.columnconfigure(1, weight=1)

        hdr = tk.Frame(win, bg=t['bg_surface'], height=40)
        hdr.grid(row=0, column=0, columnspan=3, sticky='ew')
        hdr.grid_propagate(False)
        tk.Label(hdr, text='Edit Model', font=t['font_head'],
                 fg=t['fg'], bg=t['bg_surface']).pack(side='left', padx=16, pady=10)
        tk.Frame(win, bg=t['border'], height=1).grid(row=1, column=0, columnspan=3, sticky='ew')

        def field_row(r, label, default, mono=False):
            tk.Label(win, text=label, font=t['font_body'],
                     fg=t['fg'], bg=t['bg'], anchor='w').grid(
                row=r + 2, column=0, padx=(16, 8), pady=9, sticky='w')
            var = tk.StringVar(value=default)
            e = tk.Entry(win, textvariable=var,
                         font=t['font_mono'] if mono else t['font_body'],
                         bg=t['bg_input'], fg=t['fg'],
                         insertbackground=t['accent'],
                         selectbackground=t['accent_dim'], selectforeground=t['fg'],
                         relief='flat', bd=4,
                         highlightthickness=1,
                         highlightbackground=t['border'],
                         highlightcolor=t['border_focus'])
            e.grid(row=r + 2, column=1, padx=(0, 8), pady=7, sticky='ew')
            self._add_entry_shortcuts(e)
            return var

        name_var = field_row(0, 'Name:',     model['name'])
        ctx_var  = field_row(1, 'Ctx Size:', model['ctx_size'])
        path_var = field_row(2, 'Path:',     model['model'], mono=True)

        def browse():
            f = filedialog.askopenfilename(
                parent=win,
                filetypes=[('GGUF files', '*.gguf'), ('All files', '*.*')])
            if f:
                path_var.set(os.path.normpath(f))

        ThemedButton(win, text='\u2026', command=browse,
                     btn_style='secondary', theme=t, btn_width=36).grid(
            row=4, column=2, padx=(0, 12), pady=7)
        tk.Frame(win, bg=t['border'], height=1).grid(row=5, column=0, columnspan=3, sticky='ew')
        btn_row = tk.Frame(win, bg=t['bg'])
        btn_row.grid(row=6, column=0, columnspan=3, pady=14)

        def save_edit():
            self.manager.models[idx]['name']     = name_var.get()
            self.manager.models[idx]['ctx_size'] = ctx_var.get()
            self.manager.models[idx]['model']    = os.path.normpath(path_var.get())
            self.refresh_tree()
            win.destroy()

        ThemedButton(btn_row, text='Save',   command=save_edit,   btn_style='primary',   theme=t, btn_width=110).pack(side='left', padx=6)
        ThemedButton(btn_row, text='Cancel', command=win.destroy, btn_style='secondary', theme=t, btn_width=110).pack(side='left', padx=6)

    # ══════════════════════════════════════════════════════════════════════════
    # Settings tab
    # ══════════════════════════════════════════════════════════════════════════

    def setup_settings_tab(self) -> None:
        t     = self.current_theme
        outer = tk.Frame(self.settings_tab, bg=t['bg'])
        outer.pack(fill='both', expand=True)

        canvas = tk.Canvas(outer, bg=t['bg'], bd=0, highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        self.sf = tk.Frame(canvas, bg=t['bg'])
        self.sf.columnconfigure(0, weight=1)

        def on_resize(e):        canvas.configure(scrollregion=canvas.bbox('all'))
        def on_canvas_resize(e): canvas.itemconfig(frame_id, width=e.width)

        self.sf.bind('<Configure>', on_resize)
        frame_id = canvas.create_window((0, 0), window=self.sf, anchor='nw')
        canvas.bind('<Configure>', on_canvas_resize)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _wheel)

        self.setting_vars = {}

        self._section_header(self.sf, 'Appearance', 0)
        appear_card = self._section_card(self.sf, 1)
        theme_row   = tk.Frame(appear_card, bg=t['bg_surface'])
        theme_row.pack(fill='x', padx=16, pady=12)
        tk.Label(theme_row, text='UI Theme:', font=t['font_body'],
                 fg=t['fg_dim'], bg=t['bg_surface'], width=20, anchor='w').pack(side='left')
        self.theme_var = tk.StringVar(value=t['name'])
        for val, label in [('modern', 'Dark Modern'), ('classic', 'Classic')]:
            tk.Radiobutton(theme_row, text=f'  {label}  ',
                           variable=self.theme_var, value=val,
                           command=self._on_theme_change,
                           font=t['font_body'], fg=t['fg'],
                           bg=t['bg_surface'], activebackground=t['bg_surface'],
                           activeforeground=t['accent'], selectcolor=t['bg_raised'],
                           cursor='hand2', bd=0, relief='flat').pack(side='left', padx=(0, 16))

        self._section_header(self.sf, 'GUI Settings', 2)
        gui_card = self._section_card(self.sf, 3)
        for i, key in enumerate(['close_on_launch_both']):
            self._setting_row(gui_card, key, self.manager.config.get(key, DEFAULT_CONFIG.get(key)), i)

        self._section_header(self.sf, 'Server & Llama.cpp Settings', 4)
        server_card = self._section_card(self.sf, 5)
        skip = {'saved_models', 'app_theme', 'close_on_launch_both', 'models_ini_path'}
        for i, (key, value) in enumerate([(k, v) for k, v in self.manager.config.items() if k not in skip]):
            self._setting_row(server_card, key, value, i)

        self._setting_path_row(server_card, 'models_ini_path', 'Models Ini Path',
                               self.manager.config.get('models_ini_path'),
                               len(self.manager.config) - len(skip), is_file=True)

        self._section_header(self.sf, 'Pipeline Paths', 6)
        pipeline_card = self._section_card(self.sf, 7)
        pipeline_path_defs = [
            ('pipeline_safetensors_dir', 'SafeTensors Dir',    DEFAULT_SAFETENSORS_DIR, False),
            ('pipeline_gguf_dir',        'GGUF Dir',           DEFAULT_GGUF_DIR,        False),
            ('pipeline_quantized_dir',   'Quantized Dir',      DEFAULT_QUANTIZED_DIR,   False),
            ('pipeline_convert_script',  'convert_hf_to_gguf', DEFAULT_CONVERT_SCRIPT,  True),
            ('pipeline_quantize_bin',    'llama-quantize',     DEFAULT_QUANTIZE_BIN,    True),
        ]
        for i, (key, label, default, is_file) in enumerate(pipeline_path_defs):
            saved_val = self.manager.config.get(key, default)
            self._setting_path_row(pipeline_card, key, label, saved_val, i, is_file)

    # ── Settings helpers ──────────────────────────────────────────────────────

    def _section_header(self, parent, title: str, row: int) -> None:
        t   = self.current_theme
        hdr = tk.Frame(parent, bg=t['bg'])
        hdr.grid(row=row, column=0, sticky='ew', padx=20, pady=(18, 4))
        hdr.columnconfigure(1, weight=1)
        tk.Label(hdr, text=title.upper(), font=('Segoe UI Semibold', 8),
                 fg=t['accent'], bg=t['bg']).grid(row=0, column=0, sticky='w')
        tk.Frame(hdr, bg=t['border'], height=1).grid(
            row=0, column=1, sticky='ew', padx=(12, 0), pady=7)

    def _section_card(self, parent, row: int):
        t    = self.current_theme
        card = tk.Frame(parent, bg=t['bg_surface'], bd=0,
                        highlightthickness=1, highlightbackground=t['border'])
        card.grid(row=row, column=0, sticky='ew', padx=20, pady=(0, 2))
        card.columnconfigure(1, weight=1)
        return card

    def _setting_row(self, card, key: str, value, row_idx: int) -> None:
        t   = self.current_theme
        bg  = t['bg_raised'] if row_idx % 2 == 1 else t['bg_surface']
        row_f = tk.Frame(card, bg=bg)
        row_f.pack(fill='x')
        row_f.columnconfigure(1, weight=1)
        tk.Label(row_f, text=key.replace('_', ' ').title(),
                 font=t['font_body'], fg=t['fg_dim'], bg=bg,
                 width=24, anchor='w').pack(side='left', padx=(16, 8), pady=8)
        if isinstance(value, bool):
            var = tk.BooleanVar(value=value)
            tk.Checkbutton(row_f, variable=var,
                           bg=bg, activebackground=bg,
                           fg=t['fg'], activeforeground=t['fg'],
                           selectcolor=t['bg_input'],
                           highlightthickness=0, bd=0,
                           cursor='hand2').pack(side='left', padx=4, pady=8)
        else:
            var = tk.StringVar(value=str(value))
            e = tk.Entry(row_f, textvariable=var, font=t['font_mono'],
                         bg=t['bg_input'], fg=t['fg'],
                         insertbackground=t['accent'],
                         selectbackground=t['accent_dim'], selectforeground=t['fg'],
                         relief='flat', bd=4,
                         highlightthickness=1,
                         highlightbackground=t['border'],
                         highlightcolor=t['border_focus'])
            e.pack(side='left', fill='x', expand=True, padx=(0, 16), pady=6)
            self._add_entry_shortcuts(e)
        self.setting_vars[key] = var

    def _setting_path_row(self, card, key: str, label: str, value, row_idx: int, is_file: bool = False) -> None:
        """A setting row with an additional browse (…) button for file/dir paths."""
        t   = self.current_theme
        bg  = t['bg_raised'] if row_idx % 2 == 1 else t['bg_surface']
        row_f = tk.Frame(card, bg=bg)
        row_f.pack(fill='x')
        row_f.columnconfigure(1, weight=1)
        tk.Label(row_f, text=label, font=t['font_body'], fg=t['fg_dim'], bg=bg,
                 width=24, anchor='w').pack(side='left', padx=(16, 8), pady=8)
        var = tk.StringVar(value=str(value))

        def _browse(v=var, f=is_file):
            p = filedialog.askopenfilename(parent=self.root) if f else filedialog.askdirectory(parent=self.root)
            if p:
                v.set(os.path.normpath(p))

        ThemedButton(row_f, text='…', command=_browse,
                     btn_style='secondary', theme=t, btn_width=36,
                     canvas_bg=bg).pack(side='right', padx=(4, 12), pady=6)
        e = tk.Entry(row_f, textvariable=var, font=t['font_mono'],
                     bg=t['bg_input'], fg=t['fg'],
                     insertbackground=t['accent'],
                     selectbackground=t['accent_dim'], selectforeground=t['fg'],
                     relief='flat', bd=4,
                     highlightthickness=1,
                     highlightbackground=t['border'],
                     highlightcolor=t['border_focus'])
        e.pack(side='left', fill='x', expand=True, padx=(0, 4), pady=6)
        self._add_entry_shortcuts(e)
        self.setting_vars[key] = var

    # ══════════════════════════════════════════════════════════════════════════
    # Settings persistence + launch actions
    # ══════════════════════════════════════════════════════════════════════════

    def update_all(self) -> None:
        """Collect all setting vars and save to disk."""
        for key, var in self.setting_vars.items():
            self.manager.config[key] = var.get()
        self.manager.config['app_theme'] = self.current_theme['name']
        self.manager.save_config()
        # save_models() writes to the legacy models.ini file if a path is set.
        self.manager.save_models()
        self._toast('Settings saved.')

    def _toast(self, msg: str) -> None:
        """Show a brief floating notification in the bottom-right corner."""
        t       = self.current_theme
        TRANSP  = '#010101'
        pad_x, pad_y, r = 18, 10, 8
        fnt     = tkfont.Font(family=t['font_body'][0], size=t['font_body'][1])
        label_text = '  ✓  ' + msg + '  '
        tw = int(fnt.measure(label_text)) + pad_x * 2
        th = int(fnt.metrics('linespace')) + pad_y * 2

        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes('-topmost', True)
        try:
            pop.attributes('-transparentcolor', TRANSP)
        except Exception:
            pass
        pop.configure(bg=TRANSP)

        c = tk.Canvas(pop, width=tw, height=th, bg=TRANSP, bd=0, highlightthickness=0)
        c.pack()
        bg = t['accent']
        c.create_arc(0,      0,      2*r,    2*r,    start=90,  extent=90, style='pieslice', fill=bg, outline='')
        c.create_arc(tw-2*r, 0,      tw,     2*r,    start=0,   extent=90, style='pieslice', fill=bg, outline='')
        c.create_arc(0,      th-2*r, 2*r,    th,     start=180, extent=90, style='pieslice', fill=bg, outline='')
        c.create_arc(tw-2*r, th-2*r, tw,     th,     start=270, extent=90, style='pieslice', fill=bg, outline='')
        c.create_rectangle(r, 0,   tw-r, th,   fill=bg, outline='')
        c.create_rectangle(0, r,   tw,   th-r, fill=bg, outline='')
        c.create_text(tw // 2, th // 2, text=label_text,
                      fill=t['btn_primary_fg'], font=fnt, anchor='center')

        self.root.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()
        ry = self.root.winfo_y() + self.root.winfo_height()
        pop.geometry(f'{tw}x{th}+{rx - tw - 24}+{ry - th - 76}')
        pop.after(2500, pop.destroy)

    # ── Process launchers ─────────────────────────────────────────────────────

    def launch_llama(self) -> None:
        enabled = [m for m in self.manager.models if m.get('enabled', True)]
        cmd = [
            self.manager.config['llama_server_path'],
            '--models-preset', self.manager.config['models_ini_path'],
            '--models-max',    str(len(enabled)),
            '--host',          str(self.manager.config['host']),
            '--port',          str(self.manager.config['llama_port']),
            '--api-key',       str(self.manager.config['api_key']),
            '-t',              str(self.manager.config['threads']),
            '-ngl',            str(self.manager.config['ngl']),
            '--fit',           str(self.manager.config['fit']),
            '--fit-target',    str(self.manager.config['fit_target']),
            '-b',              str(self.manager.config['batch_size']),
            '-np',             str(self.manager.config['parallel']),
            '-fa',             str(self.manager.config['flash_attn']),
        ]
        if self.manager.config.get('context_shift'):
            cmd.append('--context-shift')
        flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
        try:
            subprocess.Popen(cmd, creationflags=flags)
        except FileNotFoundError:
            messagebox.showerror('Error', f"Llama server not found:\n{self.manager.config['llama_server_path']}")
        except Exception as e:
            messagebox.showerror('Error', f'Failed to launch Llama server:\n{e}')

    def launch_webui(self) -> None:
        cmd = [
            self.manager.config['open_webui_path'], 'serve',
            '--host', str(self.manager.config['host']),
            '--port', str(self.manager.config['webui_port']),
        ]
        flags     = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
        webui_dir = os.path.dirname(self.manager.config['models_ini_path'])
        try:
            subprocess.Popen(cmd, creationflags=flags, cwd=webui_dir or None)
        except FileNotFoundError:
            messagebox.showerror('Error', f"Open WebUI not found:\n{self.manager.config['open_webui_path']}")
        except Exception as e:
            messagebox.showerror('Error', f'Failed to launch Open WebUI:\n{e}')

    def update_webui(self) -> None:
        """Upgrade open-webui via pip inside its venv in a new console window."""
        webui_exe   = self.manager.config.get('open_webui_path', '')
        scripts_dir = os.path.dirname(webui_exe)

        if os.name == 'nt':
            pip_candidates = [os.path.join(scripts_dir, 'pip.exe'),
                              os.path.join(scripts_dir, 'pip3.exe')]
        else:
            pip_candidates = [os.path.join(scripts_dir, 'pip'),
                              os.path.join(scripts_dir, 'pip3')]

        pip_path = next((p for p in pip_candidates if os.path.isfile(p)), None)
        if not pip_path:
            messagebox.showerror(
                'Update Failed',
                f'Could not find pip in the venv Scripts directory:\n{scripts_dir}\n\n'
                'Check that open_webui_path points to the venv executable.',
            )
            return

        cmd   = [pip_path, 'install', '--upgrade', 'open-webui']
        flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
        try:
            subprocess.Popen(cmd, creationflags=flags)
            self._toast('\u2191 Updating Open WebUI\u2026  watch the console for progress.')
        except Exception as e:
            messagebox.showerror('Update Failed', f'Could not start pip update:\n{e}')

    def launch_both(self) -> None:
        self.launch_llama()
        self.launch_webui()
        if self.manager.config.get('close_on_launch_both', False):
            self.root.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # Pipeline tab
    # ══════════════════════════════════════════════════════════════════════════

    def setup_pipeline_tab(self) -> None:
        t = self.current_theme

        outer  = tk.Frame(self.pipeline_tab, bg=t['bg'])
        outer.pack(fill='both', expand=True)
        canvas = tk.Canvas(outer, bg=t['bg'], bd=0, highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        sf     = tk.Frame(canvas, bg=t['bg'])
        sf.columnconfigure(1, weight=1)

        def _on_resize(e):        canvas.configure(scrollregion=canvas.bbox('all'))
        def _on_canvas_resize(e): canvas.itemconfig(frame_id, width=e.width)
        sf.bind('<Configure>', _on_resize)
        frame_id = canvas.create_window((0, 0), window=sf, anchor='nw')
        canvas.bind('<Configure>', _on_canvas_resize)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _wheel)

        pad = {'padx': 16, 'pady': 4}
        row = 0

        def section_header(title, r):
            hdr = tk.Frame(sf, bg=t['bg'])
            hdr.grid(row=r, column=0, columnspan=3, sticky='ew', padx=20, pady=(16, 4))
            hdr.columnconfigure(1, weight=1)
            tk.Label(hdr, text=title.upper(), font=('Segoe UI Semibold', 8),
                     fg=t['accent'], bg=t['bg']).grid(row=0, column=0, sticky='w')
            tk.Frame(hdr, bg=t['border'], height=1).grid(
                row=0, column=1, sticky='ew', padx=(12, 0), pady=7)

        def entry_row(r, label, default, mono=False):
            tk.Label(sf, text=label, font=t['font_body'], fg=t['fg_dim'],
                     bg=t['bg'], anchor='w', width=22).grid(row=r, column=0, sticky='w', **pad)
            var = tk.StringVar(value=default)
            e = tk.Entry(sf, textvariable=var,
                         font=t['font_mono'] if mono else t['font_body'],
                         bg=t['bg_input'], fg=t['fg'],
                         insertbackground=t['accent'],
                         selectbackground=t['accent_dim'], selectforeground=t['fg'],
                         relief='flat', bd=4,
                         highlightthickness=1, highlightbackground=t['border'],
                         highlightcolor=t['border_focus'])
            e.grid(row=r, column=1, sticky='ew', **pad)
            self._add_entry_shortcuts(e)
            return var

        def browse_btn(r, var, is_file):
            def _browse():
                p = filedialog.askopenfilename(parent=self.root) if is_file else filedialog.askdirectory(parent=self.root)
                if p:
                    var.set(os.path.normpath(p))
            ThemedButton(sf, text='…', command=_browse,
                         btn_style='secondary', theme=t, btn_width=36,
                         canvas_bg=t['bg']).grid(row=r, column=2, padx=(0, 16), pady=4)

        # ── HuggingFace source ────────────────────────────────────────────────
        section_header('HuggingFace Source', row); row += 1
        self._pl_model_var  = entry_row(row, 'HF Model (user/repo):', '');     row += 1
        self._pl_branch_var = entry_row(row, 'Branch:',               'main'); row += 1

        # ── Options ───────────────────────────────────────────────────────────
        section_header('Options', row); row += 1

        tk.Label(sf, text='Quantization:', font=t['font_body'],
                 fg=t['fg_dim'], bg=t['bg'], anchor='w', width=22).grid(
            row=row, column=0, sticky='w', **pad)
        self._pl_quant_var = tk.StringVar(value='Q4_K_M')
        ttk.Combobox(sf, textvariable=self._pl_quant_var,
                     values=QUANTS, state='readonly', width=16).grid(
            row=row, column=1, sticky='w', **pad); row += 1

        tk.Label(sf, text='Download Threads:', font=t['font_body'],
                 fg=t['fg_dim'], bg=t['bg'], anchor='w', width=22).grid(
            row=row, column=0, sticky='w', **pad)
        self._pl_threads_var = tk.IntVar(value=4)
        sp = ttk.Spinbox(sf, from_=1, to=16, textvariable=self._pl_threads_var, width=6)
        sp.grid(row=row, column=1, sticky='w', **pad)
        self._add_entry_shortcuts(sp)
        row += 1

        self._pl_delete_var = tk.BooleanVar(value=True)
        tk.Checkbutton(sf, text='Delete intermediate files after each step',
                       variable=self._pl_delete_var,
                       font=t['font_body'], bg=t['bg'], fg=t['fg'],
                       activebackground=t['bg'], activeforeground=t['fg'],
                       selectcolor=t['bg_input'],
                       highlightthickness=0, bd=0, cursor='hand2').grid(
            row=row, column=0, columnspan=3, sticky='w', **pad); row += 1

        # ── Progress bars ─────────────────────────────────────────────────────
        section_header('Progress', row); row += 1
        self._pl_bars    = {}
        self._pl_plabels = {}
        for key, label in [('download', 'Download:'), ('convert', 'Convert:'), ('quantize', 'Quantize:')]:
            tk.Label(sf, text=label, font=t['font_body'], fg=t['fg_dim'],
                     bg=t['bg'], width=14, anchor='w').grid(row=row, column=0, sticky='w', **pad)
            bar = ttk.Progressbar(sf, maximum=100, mode='determinate')
            bar.grid(row=row, column=1, sticky='ew', **pad)
            lbl = tk.Label(sf, text='  0%', font=t['font_mono'],
                           fg=t['fg_dim'], bg=t['bg'], width=6, anchor='w')
            lbl.grid(row=row, column=2, sticky='w', padx=(0, 16))
            self._pl_bars[key]    = bar
            self._pl_plabels[key] = lbl
            row += 1

        # ── Run / Stop ────────────────────────────────────────────────────────
        btn_row = tk.Frame(sf, bg=t['bg'])
        btn_row.grid(row=row, column=0, columnspan=3, sticky='w', padx=20, pady=10)
        self._pl_run_btn  = ThemedButton(btn_row, text='▶  Run Pipeline',
                                         command=self._pl_start,
                                         btn_style='primary', theme=t, btn_width=150,
                                         canvas_bg=t['bg'])
        self._pl_stop_btn = ThemedButton(btn_row, text='■  Stop',
                                         command=self._pl_stop,
                                         btn_style='danger', theme=t, btn_width=100,
                                         canvas_bg=t['bg'])
        self._pl_run_btn.pack(side='left', padx=(0, 8))
        self._pl_stop_btn.pack(side='left')
        row += 1

        # ── Log ───────────────────────────────────────────────────────────────
        log_outer = tk.Frame(sf, bg=t['border'])
        log_outer.grid(row=row, column=0, columnspan=3, sticky='nsew', padx=20, pady=(4, 16))
        sf.rowconfigure(row, weight=1)
        self.pl_log_box = scrolledtext.ScrolledText(
            log_outer, height=10,
            bg=t['bg_input'], fg=t['fg_dim'],
            font=t['font_mono'], insertbackground=t['accent'],
            relief='flat', borderwidth=0, state='disabled',
        )
        self.pl_log_box.pack(fill='both', expand=True, padx=1, pady=1)

        self._pl_stop_event = threading.Event()
        self._pl_running    = False

    # ── Pipeline helpers ──────────────────────────────────────────────────────

    def _pl_log(self, msg: str) -> None:
        self.root.after(0, self._pl_append_log, msg)

    def _pl_append_log(self, msg: str) -> None:
        self.pl_log_box.configure(state='normal')
        self.pl_log_box.insert('end', msg + '\n')
        self.pl_log_box.see('end')
        self.pl_log_box.configure(state='disabled')

    def _pl_set_bar(self, key: str, fraction: float) -> None:
        pct = int(min(max(fraction, 0.0), 1.0) * 100)
        self.root.after(0, self._pl_update_bar, key, pct)

    def _pl_update_bar(self, key: str, pct: int) -> None:
        self._pl_bars[key]['value']   = pct
        self._pl_plabels[key]['text'] = f'{pct:3d}%'

    def _pl_reset_bars(self) -> None:
        for key in self._pl_bars:
            self._pl_update_bar(key, 0)

    def _pl_set_buttons(self, running: bool) -> None:
        if running:
            self._pl_run_btn._command  = None
            self._pl_stop_btn._command = self._pl_stop
        else:
            self._pl_run_btn._command  = self._pl_start
            self._pl_stop_btn._command = self._pl_stop

    def _pl_start(self) -> None:
        if not HAS_REQUESTS:
            messagebox.showerror('Missing Dependency',
                "The 'requests' package is required for the pipeline.\n\n"
                "Install it with:  pip install requests")
            return
        model = self._pl_model_var.get().strip()
        if not model:
            messagebox.showerror('Error', 'Please enter a HuggingFace model name (user/repo).')
            return
        self._pl_stop_event.clear()
        self._pl_running = True
        self._pl_set_buttons(True)
        self._pl_reset_bars()
        self._pl_append_log('─' * 60)
        threading.Thread(target=self._pl_run_pipeline, daemon=True).start()

    def _pl_stop(self) -> None:
        self._pl_log('⚠  Stop requested…')
        self._pl_stop_event.set()

    def _pl_finish(self, success: bool = True) -> None:
        self._pl_running = False
        self.root.after(0, self._pl_set_buttons, False)
        if success:
            self._pl_log('✓  Pipeline complete!')
            self.root.after(0, lambda: messagebox.showinfo('Done', 'Pipeline finished successfully!'))
        else:
            self._pl_log('✗  Pipeline stopped or failed.')

    def _pl_run_pipeline(self) -> None:
        model       = self._pl_model_var.get().strip()
        branch      = self._pl_branch_var.get().strip() or 'main'
        st_dir      = self.setting_vars.get('pipeline_safetensors_dir', tk.StringVar(value=DEFAULT_SAFETENSORS_DIR)).get()
        gguf_dir    = self.setting_vars.get('pipeline_gguf_dir',        tk.StringVar(value=DEFAULT_GGUF_DIR)).get()
        quant_dir   = self.setting_vars.get('pipeline_quantized_dir',   tk.StringVar(value=DEFAULT_QUANTIZED_DIR)).get()
        conv_script = self.setting_vars.get('pipeline_convert_script',  tk.StringVar(value=DEFAULT_CONVERT_SCRIPT)).get()
        quant_bin   = self.setting_vars.get('pipeline_quantize_bin',    tk.StringVar(value=DEFAULT_QUANTIZE_BIN)).get()
        quant       = self._pl_quant_var.get()
        threads     = self._pl_threads_var.get()
        delete_mid  = self._pl_delete_var.get()

        try:
            # Step 1 — Download ───────────────────────────────────────────────
            self._pl_log('━━━  STEP 1 / 3 — DOWNLOAD  ━━━')
            model_name   = model.split('/')[-1]
            model_folder = os.path.join(st_dir, model.replace('/', '_'))

            downloader = ModelDownloader(
                log_fn      = self._pl_log,
                progress_fn = lambda v: self._pl_set_bar('download', v),
            )
            output_folder = downloader.download(
                model, branch, model_folder,
                threads=threads, stop_event=self._pl_stop_event,
            )
            if self._pl_stop_event.is_set():
                return self._pl_finish(False)
            self._pl_set_bar('download', 1.0)

            # Step 2 — Convert ────────────────────────────────────────────────
            self._pl_log('')
            self._pl_log('━━━  STEP 2 / 3 — CONVERT TO GGUF  ━━━')
            gguf_out  = os.path.join(gguf_dir, f'{model_name}_GGUF')
            os.makedirs(gguf_out, exist_ok=True)
            gguf_file = os.path.join(gguf_out, 'ggml-model-f16.gguf')

            cmd = [sys.executable, conv_script, str(output_folder),
                   '--outtype', 'f16', '--outfile', gguf_file]
            self._pl_log(f'$ {" ".join(cmd)}')
            self._pl_run_subprocess(cmd, 'convert')

            if self._pl_stop_event.is_set():
                return self._pl_finish(False)
            if not os.path.exists(gguf_file):
                raise RuntimeError(f'Conversion failed — {gguf_file} not found.')
            self._pl_set_bar('convert', 1.0)
            self._pl_log('Conversion complete.')

            if delete_mid:
                self._pl_log(f'Deleting SafeTensors folder: {output_folder}')
                shutil.rmtree(str(output_folder), ignore_errors=True)

            # Step 3 — Quantize ───────────────────────────────────────────────
            self._pl_log('')
            self._pl_log('━━━  STEP 3 / 3 — QUANTIZE  ━━━')
            quant_model_dir = os.path.join(quant_dir, f'{model_name}_GGUF')
            quant_out_dir   = os.path.join(quant_model_dir, f'{model_name}-{quant}')
            os.makedirs(quant_out_dir, exist_ok=True)
            quant_out_file  = os.path.join(quant_out_dir, f'ggml-model-{quant}.gguf')

            cmd = [quant_bin, gguf_file, quant_out_file, quant]
            self._pl_log(f'$ {" ".join(cmd)}')
            self._pl_run_subprocess(cmd, 'quantize')

            if self._pl_stop_event.is_set():
                return self._pl_finish(False)
            if not os.path.exists(quant_out_file):
                raise RuntimeError(f'Quantization failed — {quant_out_file} not found.')
            self._pl_set_bar('quantize', 1.0)
            self._pl_log('Quantization complete.')

            if delete_mid:
                self._pl_log(f'Deleting GGUF f16 folder: {gguf_out}')
                shutil.rmtree(gguf_out, ignore_errors=True)

            self._pl_log(f'\nFinal model: {quant_out_file}')
            self._pl_finish(True)

        except Exception as e:
            self._pl_log(f'✗  Error: {e}')
            self._pl_finish(False)

    def _pl_run_subprocess(self, cmd: list, bar_key: str) -> None:
        """Stream subprocess output to the log and parse progress percentage."""
        pct_pattern  = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        frac_pattern = re.compile(r'\[\s*(\d+)\s*/\s*(\d+)\s*\]')
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                if self._pl_stop_event.is_set():
                    proc.terminate()
                    return
                line = line.rstrip()
                if line:
                    self._pl_log(f'  {line}')
                m = pct_pattern.search(line)
                if m:
                    self._pl_set_bar(bar_key, float(m.group(1)) / 100.0)
                    continue
                m = frac_pattern.search(line)
                if m:
                    num, den = int(m.group(1)), int(m.group(2))
                    if den > 0:
                        self._pl_set_bar(bar_key, num / den)
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f'Process exited with code {proc.returncode}')
        except FileNotFoundError:
            raise RuntimeError(f'Executable not found: {cmd[0]}')
