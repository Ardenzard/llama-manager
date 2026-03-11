"""
Custom tkinter widgets that respect the active application theme.
"""

import tkinter as tk
import tkinter.font as tkfont


class ThemedButton(tk.Canvas):
    """
    A fully custom rounded-rectangle button drawn on a Canvas.

    Using a Canvas rather than tk.Button / ttk.Button gives pixel-perfect
    rounded corners whose transparent gaps are invisible against any
    background colour.

    Parameters
    ----------
    parent : tk widget
        Parent widget.
    text : str
        Button label.
    command : callable, optional
        Called when the button is clicked.
    btn_style : {'primary', 'secondary', 'danger'}
        Colour preset drawn from *theme*.
    theme : dict
        Theme dict (see ``themes.py``).
    btn_width : int, optional
        Fixed width in pixels.  Defaults to text width + 36, minimum 100.
    canvas_bg : str, optional
        Background colour of the canvas — must match whatever is painted
        *behind* the button so the rounded corner gaps disappear.
    """

    def __init__(
        self,
        parent,
        text: str = '',
        command=None,
        btn_style: str = 'secondary',
        theme: dict | None = None,
        btn_width: int | None = None,
        canvas_bg: str | None = None,
        **kwargs,
    ):
        from .themes import MODERN_THEME
        self.theme      = theme or MODERN_THEME
        t               = self.theme
        self._btn_style = btn_style
        self._text      = text
        self._command   = command
        self._hover     = False
        self._pressed   = False
        self._bg_color, self._fg_color = self._get_colors()

        self._font = tkfont.Font(family=t['font_btn'][0], size=t['font_btn'][1], weight='bold')
        # int() cast: Font.measure() can return str on some Windows builds.
        text_w     = int(self._font.measure(text))
        self._btn_w = int(btn_width) if btn_width is not None else max(text_w + 36, 100)
        self._btn_h = 34

        # canvas_bg must match whatever is painted behind the button so the
        # rounded corner gaps are invisible.
        if canvas_bg is not None:
            self._canvas_bg = canvas_bg
        else:
            try:
                self._canvas_bg = parent.cget('bg')
            except Exception:
                self._canvas_bg = t['bg']

        super().__init__(
            parent,
            width=self._btn_w, height=self._btn_h,
            bg=self._canvas_bg, bd=0, highlightthickness=0,
            cursor='hand2',
            **kwargs,
        )
        self._draw()
        self.bind('<Enter>',          self._on_enter)
        self.bind('<Leave>',          self._on_leave)
        self.bind('<Button-1>',       self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    # ── Colour helpers ────────────────────────────────────────────────────────

    def _get_colors(self) -> tuple[str, str]:
        t = self.theme
        return {
            'primary':   (t['btn_primary_bg'],   t['btn_primary_fg']),
            'secondary': (t['btn_secondary_bg'],  t['btn_secondary_fg']),
            'danger':    (t['btn_danger_bg'],     t['btn_danger_fg']),
        }.get(self._btn_style, (t['btn_secondary_bg'], t['btn_secondary_fg']))

    @staticmethod
    def _adjust(color: str, factor: float) -> str:
        """Lighten (factor > 1) or darken (factor < 1) a hex colour."""
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            if factor > 1:
                r = min(255, int(r + (255 - r) * (factor - 1)))
                g = min(255, int(g + (255 - g) * (factor - 1)))
                b = min(255, int(b + (255 - b) * (factor - 1)))
            else:
                r = max(0, int(r * factor))
                g = max(0, int(g * factor))
                b = max(0, int(b * factor))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return color

    @staticmethod
    def _rounded_rect_points(x1: int, y1: int, x2: int, y2: int, r: int) -> list:
        """Return polygon points for a rounded rectangle with corner radius *r*."""
        return [
            x1+r, y1,  x2-r, y1,
            x2,   y1,  x2,   y1+r,
            x2,   y2-r, x2,  y2,
            x2-r, y2,  x1+r, y2,
            x1,   y2,  x1,   y2-r,
            x1,   y1+r, x1,  y1,
        ]

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.delete('all')
        t  = self.theme
        r  = int(t['radius'])
        bg = self._bg_color
        fg = self._fg_color
        if self._pressed:
            bg = self._adjust(bg, 0.82)
        elif self._hover:
            bg = self._adjust(bg, 1.18)
        cbg = getattr(self, '_canvas_bg', t['bg'])
        w, h = self._btn_w, self._btn_h
        self.configure(bg=cbg)
        pts = self._rounded_rect_points(0, 0, w, h, r)
        self.create_polygon(pts, fill=bg, outline='', smooth=True)
        self.create_text(w // 2, h // 2, text=self._text, fill=fg, font=self._font, anchor='center')

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_enter(self, _):    self._hover = True;  self._draw()
    def _on_leave(self, _):    self._hover = False; self._pressed = False; self._draw()
    def _on_press(self, _):    self._pressed = True; self._draw()

    def _on_release(self, _):
        self._pressed = False; self._hover = True; self._draw()
        if self._command:
            self._command()

    # ── Theme update ──────────────────────────────────────────────────────────

    def update_theme(self, theme: dict) -> None:
        """Re-draw the button using a new theme dict."""
        self.theme = theme
        self.configure(bg=theme['bg'])
        self._bg_color, self._fg_color = self._get_colors()
        self._draw()
