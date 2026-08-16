from __future__ import annotations

import types
import tkinter as tk
import webbrowser
from tkinter import messagebox

BG = '#04101b'
PANEL = '#071a29'
PANEL2 = '#0a2235'
PANEL_HOVER = '#0d2a40'
TEXT = '#f2f7fb'
MUTED = '#88a5ba'
ACCENT = '#079cff'
GOLD = '#f4c542'
GREEN = '#2bd672'
LINE = '#155273'

TRACKS = (
    {
        'name': 'SPRING CREEK / MILLVILLE',
        'release': '2024 ARLMX RD7 – MILLVILLE',
        'discipline': 'MX',
        'media_track': 'Millville Club',
        'aliases': 'Race Day Live: Millville Club • Spring Creek',
        'url': 'https://mxbikes-shop.com/downloads/2024-arlmx-rd7-millville/',
    },
    {
        'name': 'BUCHANAN / REDBUD',
        'release': '2025 ARLMX RD6 – BUCHANAN',
        'discipline': 'MX',
        'media_track': 'RedBud Club',
        'aliases': 'Race Day Live: RedBud Club • RedBud',
        'url': 'https://mxbikes-shop.com/downloads/2025-arlmx-rd6-buchanan/',
    },
    {
        'name': 'PALA / FOX RACEWAY',
        'release': '2025 ARLMX RD1 – PALA',
        'discipline': 'MX',
        'media_track': 'Fox Raceway',
        'aliases': 'Race Day Live: Fox Raceway • Pala Finale',
        'url': 'https://mxbikes-shop.com/downloads/2025-arlmx-rd1-pala/',
    },
    {
        'name': 'ANAHEIM 1',
        'release': '2025 FXR ARL SUPERCROSS • ROUND 1',
        'discipline': 'SX',
        'media_track': 'Anaheim Stadium',
        'aliases': 'Race Day Live: Anaheim Stadium • Anaheim 1',
        'url': 'https://mxbikes-shop.com/downloads/2025-fxr-arl-supercross-series-presented-by-motooption-round-1/',
    },
    {
        'name': 'SAN DIEGO',
        'release': '2023 ARL SX ROUND 02 – SAN DIEGO',
        'discipline': 'SX',
        'media_track': 'San Diego Stadium',
        'aliases': 'Race Day Live: San Diego Stadium • San Diego',
        'url': 'https://www.mxbikes-shop.com/downloads/2023-arl-sx-round-02-san-diego/',
    },
)


def _open_track_page(track):
    url = str(track.get('url') or '').strip()
    if not url:
        return
    try:
        if not webbrowser.open_new_tab(url):
            webbrowser.open(url)
    except Exception as exc:
        messagebox.showerror('MXB-Shop Track', f'Could not open the track page.\n\n{exc}')


def _bind_click_recursive(widget, command):
    try:
        widget.configure(cursor='hand2')
    except Exception:
        pass
    try:
        widget.bind('<Button-1>', lambda _event: command(), add='+')
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _bind_click_recursive(child, command)
    except Exception:
        pass


def _track_card(self, parent, track):
    card = tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1, bd=0)
    opener = lambda t=track: _open_track_page(t)

    photo = self._track_photo(
        card,
        track['discipline'],
        track['media_track'],
        size=(520, 292),
        on_click=opener,
    )
    photo.pack(fill='x', padx=1, pady=1)

    info = tk.Frame(card, bg=PANEL)
    info.pack(fill='x', padx=17, pady=(12, 10))

    top = tk.Frame(info, bg=PANEL)
    top.pack(fill='x')
    tk.Label(
        top,
        text=track['discipline'],
        fg='#04101b',
        bg=ACCENT if track['discipline'] == 'MX' else GOLD,
        font=('Segoe UI Black', 8),
        padx=8,
        pady=3,
    ).pack(side='left')
    tk.Label(
        top,
        text='MXB-SHOP • VERIFIED DIRECT LINK',
        fg=GREEN,
        bg=PANEL,
        font=('Segoe UI Black', 8),
    ).pack(side='right', pady=3)

    tk.Label(
        info,
        text=track['name'],
        fg=TEXT,
        bg=PANEL,
        font=('Segoe UI Black', 17, 'italic'),
        anchor='w',
        justify='left',
    ).pack(fill='x', pady=(10, 2))
    tk.Label(
        info,
        text=track['release'],
        fg=ACCENT,
        bg=PANEL,
        font=('Segoe UI Black', 9),
        anchor='w',
        justify='left',
    ).pack(fill='x')
    tk.Label(
        info,
        text=track['aliases'],
        fg=MUTED,
        bg=PANEL,
        font=('Segoe UI', 8),
        anchor='w',
        justify='left',
    ).pack(fill='x', pady=(4, 2))

    button = tk.Label(
        card,
        text='OPEN TRACK PAGE  ›',
        fg=TEXT,
        bg='#072f4d',
        activeforeground='white',
        activebackground='#0b4169',
        font=('Segoe UI Black', 9),
        padx=10,
        pady=10,
        cursor='hand2',
    )
    button.pack(fill='x', padx=16, pady=(0, 15))
    button.bind('<Button-1>', lambda _event: opener())

    _bind_click_recursive(info, opener)
    return card


def _page_tracks(self):
    try:
        inner = self._scrollable(self.content, padx=28, pady=(0, 26))
    except Exception:
        inner = tk.Frame(self.content, bg=BG)
        inner.pack(fill='both', expand=True, padx=28, pady=(0, 26))

    heading = tk.Frame(inner, bg=BG)
    heading.pack(fill='x', pady=(4, 15))
    tk.Label(
        heading,
        text='TRACKS',
        fg=TEXT,
        bg=BG,
        font=('Segoe UI Black', 26, 'italic'),
    ).pack(anchor='w')
    tk.Label(
        heading,
        text='Verified MXB-Shop releases. Click any track image, card, or button to open its exact track page.',
        fg=MUTED,
        bg=BG,
        font=('Segoe UI Semibold', 9),
    ).pack(anchor='w', pady=(2, 0))

    grid = tk.Frame(inner, bg=BG)
    grid.pack(fill='x')
    grid.grid_columnconfigure(0, weight=1, uniform='tracks')
    grid.grid_columnconfigure(1, weight=1, uniform='tracks')

    for index, track in enumerate(TRACKS):
        row, col = divmod(index, 2)
        card = _track_card(self, grid, track)
        card.grid(
            row=row,
            column=col,
            sticky='nsew',
            padx=(0, 7) if col == 0 else (7, 0),
            pady=(0, 14),
        )

    tk.Label(
        inner,
        text='Track artwork and links are pinned to the same verified MXB-Shop mappings used by Race Day Live race cards.',
        fg=MUTED,
        bg=BG,
        font=('Segoe UI', 8),
    ).pack(anchor='w', pady=(0, 4))


def install_tracks_ui(app):
    """Add the dedicated Tracks route without replacing any existing Race Day Live behavior."""
    app.page_tracks = types.MethodType(_page_tracks, app)

    if getattr(app, '_tracks_ui_version', '') == '0.5.16':
        return
    app._tracks_ui_version = '0.5.16'
    app._tracks_base_show = app.show

    def tracks_show(self, name, force=False):
        page = str(name or '').upper()
        if page != 'TRACKS':
            return self._tracks_base_show(name, force)

        self.current_page = 'TRACKS'
        try:
            for child in self.content.winfo_children():
                child.destroy()
        except Exception:
            pass

        self.page_tracks()
        try:
            from .profile_first_ui import _sync_top_nav
            _sync_top_nav(self)
        except Exception:
            for nav_page, button in getattr(self, '_race_theme_nav', {}).items():
                try:
                    button.set_active(nav_page == 'TRACKS')
                except Exception:
                    pass
        return None

    app.show = types.MethodType(tracks_show, app)
