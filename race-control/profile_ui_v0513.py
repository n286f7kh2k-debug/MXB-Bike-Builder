from __future__ import annotations

import types
import tkinter as tk
from datetime import datetime

# v0.5.13 visual language: deep race-night navy, thin cyan outlines, restrained accents.
BG = '#04101b'
PANEL = '#071a29'
PANEL2 = '#0a2235'
PANEL_HOVER = '#0d2a40'
TEXT = '#f2f7fb'
MUTED = '#88a5ba'
ACCENT = '#079cff'
ACCENT_SOFT = '#0c5f8f'
GOLD = '#f4c542'
GREEN = '#2bd672'
RED = '#ff5964'
LINE = '#155273'


def _round_rect(canvas, x1, y1, x2, y2, radius=14, **kwargs):
    r = max(4, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2,
        x1 + r, y2, x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, splinesteps=24, **kwargs)


class RoundedNavButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=112, active=False):
        super().__init__(parent, width=width, height=40, bg=BG, bd=0, highlightthickness=0,
                         cursor='hand2')
        self._text = text
        self._command = command
        self._active = bool(active)
        self._hover = False
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', self._click)
        self.after_idle(self._draw)

    def set_active(self, value):
        self._active = bool(value)
        self._draw()

    def _enter(self, _event=None):
        self._hover = True
        self._draw()

    def _leave(self, _event=None):
        self._hover = False
        self._draw()

    def _click(self, _event=None):
        if callable(self._command):
            self._command()

    def _draw(self, _event=None):
        self.delete('all')
        w = max(70, int(self.winfo_width()))
        h = max(34, int(self.winfo_height()))
        selected = self._active or self._hover
        fill = '#0b2b43' if self._active else (PANEL2 if self._hover else BG)
        outline = ACCENT if selected else LINE
        _round_rect(self, 1, 2, w - 2, h - 3, 11, fill=fill, outline=outline,
                    width=2 if self._active else 1)
        self.create_text(w / 2, h / 2, text=self._text, fill=TEXT if selected else MUTED,
                         font=('Segoe UI Black' if self._active else 'Segoe UI Semibold', 9))


class ActionCard(tk.Canvas):
    def __init__(self, parent, kicker, title, detail='', command=None, accent=ACCENT, height=132):
        super().__init__(parent, height=height, bg=BG, bd=0, highlightthickness=0,
                         cursor='hand2')
        self._kicker = kicker
        self._title = title
        self._detail = detail
        self._command = command
        self._accent = accent
        self._hover = False
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', self._click)
        self.after_idle(self._draw)

    def _enter(self, _event=None):
        self._hover = True
        self._draw()

    def _leave(self, _event=None):
        self._hover = False
        self._draw()

    def _click(self, _event=None):
        if callable(self._command):
            self._command()

    def _draw(self, _event=None):
        self.delete('all')
        w = max(160, int(self.winfo_width()))
        h = max(88, int(self.winfo_height()))
        fill = PANEL_HOVER if self._hover else PANEL
        _round_rect(self, 2, 2, w - 3, h - 3, 15, fill=fill,
                    outline=self._accent if self._hover else LINE, width=2)
        self.create_text(20, 16, text=self._kicker, anchor='nw', fill=self._accent,
                         font=('Segoe UI Black', 8))
        self.create_text(20, 40, text=self._title, anchor='nw', fill=TEXT,
                         font=('Segoe UI Black', 15), width=max(140, w - 60))
        if self._detail:
            self.create_text(20, h - 19, text=self._detail, anchor='sw', fill=MUTED,
                             font=('Segoe UI', 9), width=max(140, w - 58))
        self.create_text(w - 20, h - 20, text='›', anchor='se', fill=self._accent,
                         font=('Segoe UI Black', 22))


class MetricCard(tk.Canvas):
    def __init__(self, parent, label, value, accent=TEXT):
        super().__init__(parent, height=68, bg=BG, bd=0, highlightthickness=0)
        self._label = label
        self._value = value
        self._accent = accent
        self.bind('<Configure>', self._draw)
        self.after_idle(self._draw)

    def _draw(self, _event=None):
        self.delete('all')
        w = max(120, int(self.winfo_width()))
        h = max(56, int(self.winfo_height()))
        _round_rect(self, 1, 1, w - 2, h - 2, 11, fill=PANEL, outline=LINE, width=1)
        self.create_text(14, 12, text=self._label, anchor='nw', fill=MUTED,
                         font=('Segoe UI Semibold', 7))
        self.create_text(14, 31, text=self._value, anchor='nw', fill=self._accent,
                         font=('Segoe UI Black', 12))


def _themed_card(self, parent):
    return tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1, bd=0)


def _career_strip(self, parent, rider):
    row = tk.Frame(parent, bg=BG)
    row.pack(fill='x', pady=(2, 12))
    values = [
        ('CAREER STARTS', str(rider['starts'] or 0), TEXT),
        ('WINS / PODIUMS', f"{rider['wins'] or 0} / {rider['podiums'] or 0}", TEXT),
        ('CHAMPIONSHIPS', str(rider['championships'] or 0), GOLD),
        ('CAREER EARNINGS', f"${float(rider['career_earnings'] or 0):,.0f}", GOLD),
    ]
    for index, (label, value, color) in enumerate(values):
        card = MetricCard(row, label, value, color)
        card.pack(side='left', fill='x', expand=True,
                  padx=(0, 7 if index < len(values) - 1 else 0))


def _registered_races(self, rider):
    try:
        return list(self.conn.execute('''
            SELECT rc.*,rg.amount_paid,rg.signed_up_at
            FROM registrations rg
            JOIN races rc ON rc.id=rg.race_id
            WHERE rg.rider_id=? AND rc.status!='COMPLETE'
            ORDER BY rc.start_time
        ''', (rider['id'],)))
    except Exception:
        return []


def _race_list_panel(self, parent, rider):
    rows = _registered_races(self, rider)
    canvas = tk.Canvas(parent, height=308, bg=BG, bd=0, highlightthickness=0)
    canvas.grid(row=0, column=0, sticky='nsew', padx=(0, 7))

    def open_my_races(_event=None):
        self._set_profile_section('RACES')

    def find_race(_event=None):
        self.show('UPCOMING')

    def draw(_event=None):
        canvas.delete('all')
        w = max(420, int(canvas.winfo_width()))
        h = max(280, int(canvas.winfo_height()))
        _round_rect(canvas, 2, 2, w - 3, h - 3, 16, fill=PANEL, outline=LINE, width=2)
        canvas.create_text(20, 17, text='MY RACES', anchor='nw', fill=TEXT,
                           font=('Segoe UI Black', 15))
        canvas.create_text(w - 20, 21, text='VIEW ALL  ›', anchor='ne', fill=ACCENT,
                           font=('Segoe UI Black', 8), tags=('view_all',))
        canvas.tag_bind('view_all', '<Button-1>', open_my_races)

        y = 57
        if rows:
            for index, race in enumerate(rows[:4]):
                y1 = y + index * 49
                y2 = y1 + 41
                tag = f'race_{race["id"]}'
                _round_rect(canvas, 16, y1, w - 16, y2, 9, fill=PANEL2,
                            outline='#123e59', width=1, tags=(tag,))
                cls = self.race_class_label(race)
                canvas.create_text(28, y1 + 8, text=f'{cls}  •  {race["track"]}', anchor='nw',
                                   fill=ACCENT, font=('Segoe UI Black', 7), tags=(tag,))
                canvas.create_text(28, y1 + 22, text=race['name'], anchor='nw',
                                   fill=TEXT, font=('Segoe UI Semibold', 9), tags=(tag,))
                try:
                    when = datetime.fromisoformat(race['start_time']).strftime('%b %d  %I:%M %p')
                except Exception:
                    when = str(race['start_time'] or '')
                canvas.create_text(w - 28, y1 + 21, text=when, anchor='e', fill=MUTED,
                                   font=('Segoe UI Semibold', 8), tags=(tag,))
                canvas.tag_bind(tag, '<Button-1>', lambda e, rid=race['id']: self.open_race_details(rid))
        else:
            canvas.create_text(24, 92, text='No upcoming registrations yet.', anchor='nw',
                               fill=TEXT, font=('Segoe UI Semibold', 11))
            canvas.create_text(24, 119, text='Find a race and your registered events will stay here on your profile.',
                               anchor='nw', fill=MUTED, font=('Segoe UI', 9), width=max(280, w - 56))

        _round_rect(canvas, 16, h - 54, w - 16, h - 15, 10, fill='#072f4d',
                    outline=ACCENT, width=1, tags=('find',))
        canvas.create_text(w / 2, h - 34, text='FIND A RACE', fill=TEXT,
                           font=('Segoe UI Black', 9), tags=('find',))
        canvas.tag_bind('find', '<Button-1>', find_race)

    canvas.bind('<Configure>', draw)
    canvas.after_idle(draw)
    return rows


def _next_race_card(self, parent, rider, registered):
    race = registered[0] if registered else None
    kicker = 'NEXT REGISTERED RACE' if race is not None else 'NEXT OPEN RACE'
    if race is None:
        try:
            eligible = [x for x in self.conn.execute(
                "SELECT * FROM races WHERE status='REGISTRATION' ORDER BY start_time"
            ) if self.eligible(x, rider)]
            race = eligible[0] if eligible else None
        except Exception:
            race = None

    if race is None:
        card = ActionCard(parent, 'RACE DAY', 'NO OPEN RACES',
                          'Open Find a Race to check again.', command=lambda: self.show('UPCOMING'))
    else:
        try:
            when = datetime.fromisoformat(race['start_time']).strftime('%b %d  •  %I:%M %p')
        except Exception:
            when = str(race['start_time'] or '')
        detail = f"{self.race_class_label(race)}  •  {race['track']}  •  {when}"
        card = ActionCard(parent, kicker, race['name'], detail,
                          command=lambda rid=race['id']: self.open_race_details(rid), accent=ACCENT)
    card.pack(fill='x', pady=(0, 7))


def _latest_result_card(self, parent, rider):
    row = None
    try:
        row = self.conn.execute('''
            SELECT rs.position,rs.payout,rs.fast_lap_bonus,rc.name,rc.track
            FROM results rs
            JOIN races rc ON rc.id=rs.race_id
            WHERE rs.rider_id=?
            ORDER BY rc.start_time DESC LIMIT 1
        ''', (rider['id'],)).fetchone()
    except Exception:
        pass
    if row:
        earned = float(row['payout'] or 0) + float(row['fast_lap_bonus'] or 0)
        title = f"P{row['position']}  •  {row['name']}"
        detail = f"{row['track']}  •  ${earned:,.0f} earned"
    else:
        title = 'NO RESULTS YET'
        detail = 'Completed race results will appear here.'
    card = ActionCard(parent, 'LATEST RESULT', title, detail,
                      command=lambda: self.show('RESULTS'), accent=GOLD)
    card.pack(fill='x')


def _profile_overview(self, rider):
    inner = self._scrollable(self.content, padx=28, pady=(0, 26))
    _career_strip(self, inner, rider)

    main = tk.Frame(inner, bg=BG)
    main.pack(fill='x')
    main.grid_columnconfigure(0, weight=2, uniform='profile_main')
    main.grid_columnconfigure(1, weight=1, uniform='profile_main')

    registered = _race_list_panel(self, main, rider)
    right = tk.Frame(main, bg=BG)
    right.grid(row=0, column=1, sticky='nsew', padx=(7, 0))
    _next_race_card(self, right, rider, registered)
    _latest_result_card(self, right, rider)

    hint = tk.Label(inner,
                    text='Profile, races and results stay front and center. Account and system tools are under MENU.',
                    fg=MUTED, bg=BG, font=('Segoe UI', 8))
    hint.pack(anchor='w', pady=(10, 0))


def _profile_subnav(self):
    row = tk.Frame(self.content, bg=BG)
    row.pack(fill='x', padx=28, pady=(0, 10))
    for label, key, width in [('OVERVIEW', 'OVERVIEW', 104), ('MY RACES', 'RACES', 110)]:
        button = RoundedNavButton(row, label, command=lambda k=key: self._set_profile_section(k),
                                  width=width, active=self.profile_section == key)
        button.pack(side='left', padx=(0, 6))


def _build_menu(app):
    menu = tk.Menu(app, tearoff=0, bg=PANEL, fg=TEXT, activebackground=ACCENT,
                   activeforeground='white', selectcolor=ACCENT, bd=0, relief='flat',
                   font=('Segoe UI Semibold', 10))
    menu.add_command(label='My Races', command=lambda: app._set_profile_section('RACES'))
    menu.add_command(label='Wallet', command=lambda: app._set_profile_section('WALLET'))
    menu.add_command(label='Rankings', command=lambda: app.show('RANKINGS'))
    menu.add_separator()
    menu.add_command(label='Profile Settings', command=lambda: app._set_profile_section('SETTINGS'))
    if hasattr(app, '_profile_membership'):
        menu.add_command(label='Membership', command=lambda: app._set_profile_section('MEMBERSHIP'))
    menu.add_separator()
    if hasattr(app, '_garage_sync_now'):
        menu.add_command(label='Sync MX Bikes', command=app._garage_sync_now)
    if hasattr(app, '_launch_mx_game'):
        menu.add_command(label='Launch MX Bikes', command=app._launch_mx_game)
    if hasattr(app, 'do_update'):
        menu.add_command(label='Check for Updates', command=app.do_update)
    if app.is_admin():
        menu.add_separator()
        menu.add_command(label='Admin Control', command=lambda: app.show('ADMIN'))
    menu.add_separator()
    menu.add_command(label='Exit', command=app._on_close)
    return menu


def _make_top_nav(app):
    try:
        app.nav.pack_forget()
    except Exception:
        pass
    try:
        app.update_btn.pack_forget()
    except Exception:
        pass
    try:
        body = app.content.master
        app.content.pack_forget()
    except Exception:
        return

    old = getattr(app, '_race_theme_topnav', None)
    try:
        if old is not None and old.winfo_exists():
            old.destroy()
    except Exception:
        pass

    bar = tk.Frame(body, bg=BG, height=56)
    bar.pack(side='top', fill='x', padx=18, pady=(7, 1))
    bar.pack_propagate(False)
    app.content.pack(side='top', fill='both', expand=True)
    app._race_theme_topnav = bar
    app._race_theme_nav = {}

    primary = [
        ('PROFILE', 'PROFILE', 96),
        ('FIND A RACE', 'UPCOMING', 126),
        ('CHAMPIONSHIPS', 'CHAMPIONSHIPS', 140),
        ('GARAGE', 'GARAGE', 96),
        ('LIVE', 'LIVE', 78),
        ('RESULTS', 'RESULTS', 94),
    ]
    left = tk.Frame(bar, bg=BG)
    left.pack(side='left', fill='y')
    for label, page, width in primary:
        button = RoundedNavButton(left, label, command=lambda p=page: app.show(p),
                                  width=width, active=app.current_page == page)
        button.pack(side='left', padx=(0, 5), pady=7)
        app._race_theme_nav[page] = button

    right = tk.Frame(bar, bg=BG)
    right.pack(side='right', fill='y')

    # Tiny connection indicator only; the detailed sync controls live in MENU.
    status = tk.Label(right, text='● MX', fg=MUTED, bg=BG, font=('Segoe UI Black', 8))
    status.pack(side='left', padx=(6, 7), pady=20)
    app._race_theme_status = status

    menu_button = None

    def post_menu():
        nonlocal menu_button
        if menu_button is None:
            return
        menu = _build_menu(app)
        app._race_theme_menu = menu
        try:
            menu.tk_popup(menu_button.winfo_rootx(),
                          menu_button.winfo_rooty() + menu_button.winfo_height())
        finally:
            try:menu.grab_release()
            except Exception:pass

    menu_button = RoundedNavButton(right, 'MENU  ☰', command=post_menu, width=100, active=False)
    menu_button.pack(side='right', pady=7)

    def refresh_status():
        try:
            text = str(app.mx_status_label.cget('text') or '')
            color = str(app.mx_status_label.cget('fg') or MUTED)
            if 'CONNECTED' in text.upper():
                app._race_theme_status.configure(text='● MX', fg=GREEN)
            elif 'NOT FOUND' in text.upper() or 'ERROR' in text.upper():
                app._race_theme_status.configure(text='● MX', fg=RED)
            else:
                app._race_theme_status.configure(text='● MX', fg=color)
            app.after(1500, refresh_status)
        except Exception:
            pass
    app.after(400, refresh_status)


def _sync_top_nav(app):
    current = getattr(app, 'current_page', 'PROFILE')
    for page, button in getattr(app, '_race_theme_nav', {}).items():
        try:button.set_active(page == current)
        except Exception:pass


def install_profile_first_ui(app):
    """Install the v0.5.13 race-night UI without changing existing app behavior/routes."""
    try:app.configure(bg=BG)
    except Exception:pass

    # Reuse the existing data/actions; only replace presentation/navigation.
    app.card = types.MethodType(_themed_card, app)
    app._profile_overview = types.MethodType(_profile_overview, app)
    app._profile_subnav = types.MethodType(_profile_subnav, app)

    # Wrap show once so the compact navigation always reflects the actual page.
    if not hasattr(app, '_race_theme_base_show'):
        app._race_theme_base_show = app.show

        def themed_show(self, name, force=False):
            result = self._race_theme_base_show(name, force)
            _sync_top_nav(self)
            return result

        app.show = types.MethodType(themed_show, app)

    _make_top_nav(app)
    _sync_top_nav(app)
