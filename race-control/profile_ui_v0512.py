import types
import tkinter as tk

BG = '#0b0d10'
PANEL = '#15191e'
PANEL2 = '#1d232a'
TEXT = '#f3f5f7'
MUTED = '#98a2ad'
ACCENT = '#0b84ff'
GOLD = '#ffc247'
GREEN = '#45d483'
LINE = '#24303c'


def _round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    r = max(4, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2,
        x1 + r, y2, x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class RoundedTile(tk.Canvas):
    def __init__(self, parent, title, subtitle='', kicker='', value='', command=None,
                 accent=ACCENT, height=132, compact=False):
        super().__init__(parent, bg=BG, highlightthickness=0, bd=0,
                         height=height, cursor='hand2')
        self._title = title
        self._subtitle = subtitle
        self._kicker = kicker
        self._value = value
        self._command = command
        self._accent = accent
        self._hover = False
        self._compact = compact
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', self._click)

    def _enter(self, _event=None):
        self._hover = True
        self._draw()

    def _leave(self, _event=None):
        self._hover = False
        self._draw()

    def _click(self, _event=None):
        if self._command:
            self._command()

    def _draw(self, _event=None):
        self.delete('all')
        w = max(80, self.winfo_width())
        h = max(48, self.winfo_height())
        fill = '#1b222a' if self._hover else PANEL
        outline = self._accent if self._hover else LINE
        _round_rect(self, 2, 2, w - 3, h - 3, 19, fill=fill, outline=outline, width=2)
        if self._hover:
            self.create_rectangle(18, h - 5, w - 18, h - 3, fill=self._accent, outline='')
        left = 20
        if self._compact:
            self.create_text(left, 15, text=self._title, anchor='nw', fill=TEXT,
                             font=('Segoe UI Semibold', 10))
            if self._subtitle:
                self.create_text(left, 37, text=self._subtitle, anchor='nw', fill=MUTED,
                                 font=('Segoe UI', 8))
            return
        if self._kicker:
            self.create_text(left, 16, text=self._kicker, anchor='nw', fill=self._accent,
                             font=('Segoe UI Black', 8))
        self.create_text(left, 40 if self._kicker else 25, text=self._title, anchor='nw', fill=TEXT,
                         font=('Segoe UI Black', 17))
        if self._value:
            self.create_text(w - 22, 24, text=self._value, anchor='ne', fill=GOLD,
                             font=('Segoe UI Black', 15))
        if self._subtitle:
            self.create_text(left, h - 39, text=self._subtitle, anchor='sw', fill=MUTED,
                             font=('Segoe UI', 9), width=max(120, w - 64))
        self.create_text(w - 22, h - 24, text='›', anchor='e', fill=self._accent,
                         font=('Segoe UI Black', 24))


class RoundedPill(tk.Canvas):
    def __init__(self, parent, text, command=None, active=False, width=126):
        super().__init__(parent, bg=BG, highlightthickness=0, bd=0,
                         height=44, width=width, cursor='hand2')
        self.text = text
        self.command = command
        self.active = active
        self.hover = False
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', self._click)
        self.after_idle(self._draw)

    def set_active(self, active):
        self.active = bool(active)
        self._draw()

    def _enter(self, _event=None):
        self.hover = True
        self._draw()

    def _leave(self, _event=None):
        self.hover = False
        self._draw()

    def _click(self, _event=None):
        if self.command:
            self.command()

    def _draw(self, _event=None):
        self.delete('all')
        w = max(70, self.winfo_width())
        h = max(36, self.winfo_height())
        active = self.active or self.hover
        fill = '#152538' if self.active else ('#171d24' if self.hover else BG)
        outline = ACCENT if active else LINE
        _round_rect(self, 2, 3, w - 3, h - 4, 17, fill=fill, outline=outline, width=2 if active else 1)
        self.create_text(w / 2, h / 2, text=self.text, fill=TEXT if active else MUTED,
                         font=('Segoe UI Black' if self.active else 'Segoe UI Semibold', 9))


def _section_title(parent, title, subtitle=''):
    block = tk.Frame(parent, bg=BG)
    block.pack(fill='x', pady=(12, 9))
    tk.Label(block, text=title, fg=TEXT, bg=BG,
             font=('Segoe UI Black', 16)).pack(anchor='w')
    if subtitle:
        tk.Label(block, text=subtitle, fg=MUTED, bg=BG,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(2, 0))
    return block


def _stat_strip(self, parent, rider):
    row = tk.Frame(parent, bg=BG)
    row.pack(fill='x', pady=(2, 12))
    stats = []
    try:
        bal = self.conn.execute('SELECT balance_cents FROM wallets WHERE rider_id=?',
                                (rider['id'],)).fetchone()
        amount = (int(bal['balance_cents']) / 100.0) if bal else 0.0
        stats.append(('WALLET', f'${amount:,.2f}', GOLD))
    except Exception:
        pass
    try:
        stats += [
            ('OVERALL RANK', f'#{self.overall_rank(rider)}', GOLD),
            ('SKILL', f"{str(rider['skill_class']).upper()}  •  {rider['skill_rating']} MMR", TEXT),
            ('ETIQUETTE', f"{rider['racecraft_grade']}  •  {self.etiquette_text(rider)}", GREEN),
        ]
    except Exception:
        pass
    for label, value, color in stats[:4]:
        box = tk.Frame(row, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        box.pack(side='left', fill='both', expand=True, padx=(0, 8))
        tk.Label(box, text=label, fg=MUTED, bg=PANEL,
                 font=('Segoe UI Semibold', 8)).pack(anchor='w', padx=14, pady=(10, 2))
        tk.Label(box, text=value, fg=color, bg=PANEL,
                 font=('Segoe UI Black', 13)).pack(anchor='w', padx=14, pady=(0, 10))


def _profile_subnav(self):
    row = tk.Frame(self.content, bg=BG)
    row.pack(fill='x', padx=28, pady=(0, 12))
    items = [('OVERVIEW', 'OVERVIEW'), ('MY RACES', 'RACES'), ('WALLET', 'WALLET')]
    if hasattr(self, '_profile_membership'):
        items.append(('MEMBERSHIP', 'MEMBERSHIP'))
    items.append(('PROFILE SETTINGS', 'SETTINGS'))
    for label, key in items:
        pill = RoundedPill(row, label, command=lambda k=key: self._set_profile_section(k),
                           active=self.profile_section == key,
                           width=154 if label == 'PROFILE SETTINGS' else 126)
        pill.pack(side='left', padx=(0, 7))


def _profile_overview(self, rider):
    inner = self._scrollable(self.content, padx=28, pady=(0, 28))
    _stat_strip(self, inner, rider)

    _section_title(inner, 'RIDER HUB', 'Everything you do in Race Day Live starts from your rider profile.')
    grid = tk.Frame(inner, bg=BG)
    grid.pack(fill='x')
    for col in range(3):
        grid.grid_columnconfigure(col, weight=1, uniform='hub')

    tiles = [
        ('FIND A RACE', 'Browse eligible races, entry fees and open gates.', 'RACE DAY', '', lambda: self.show('UPCOMING'), ACCENT),
        ('MY RACES', 'Your signed-up races, schedule and race history.', 'PROFILE', '', lambda: self._set_profile_section('RACES'), GOLD),
        ('GARAGE', 'Bike, rider and installed MX Bikes content.', 'MX BIKES', '', lambda: self.show('GARAGE'), '#45d483'),
        ('WALLET', 'Balance, funding and race transactions.', 'ACCOUNT', '', lambda: self._set_profile_section('WALLET'), GOLD),
        ('LIVE', 'Open the live race viewer and race broadcast.', 'WATCH', '', lambda: self.show('LIVE'), '#ff5757'),
        ('RESULTS', 'Completed race results and payouts.', 'HISTORY', '', lambda: self.show('RESULTS'), '#20a8ff'),
        ('CHAMPIONSHIPS', 'Series, rounds, standings and event details.', 'SERIES', '', lambda: self.show('CHAMPIONSHIPS'), '#a98bff'),
        ('RANKINGS', 'Skill ranking, MMR and etiquette standings.', 'COMPETE', '', lambda: self.show('RANKINGS'), '#74d7ff'),
        ('PROFILE SETTINGS', 'Edit your rider info, photo, banner and profile details.', 'CUSTOMIZE', '', lambda: self._set_profile_section('SETTINGS'), ACCENT),
    ]
    if hasattr(self, '_profile_membership'):
        tiles.append(('MEMBERSHIP', 'Membership status, plan and included race benefits.', 'ACCOUNT', '', lambda: self._set_profile_section('MEMBERSHIP'), GOLD))
    if self.is_admin():
        tiles.append(('ADMIN CONTROL', 'Manage races, payouts, tracks, schedules and app settings.', 'OWNER', '', lambda: self.show('ADMIN'), '#ff7a30'))
    if hasattr(self, '_garage_sync_now'):
        tiles.append(('SYNC MX BIKES', 'Refresh installed bikes, tracks, rider gear and game content.', 'SYSTEM', '', self._garage_sync_now, GREEN))

    for index, (title, sub, kicker, value, command, accent) in enumerate(tiles):
        tile = RoundedTile(grid, title, sub, kicker, value, command, accent=accent)
        tile.grid(row=index // 3, column=index % 3, sticky='nsew', padx=6, pady=6)

    _section_title(inner, 'RACE SNAPSHOT', 'Your next available race and latest result at a glance.')
    snap = tk.Frame(inner, bg=BG)
    snap.pack(fill='x', pady=(0, 18))
    snap.grid_columnconfigure(0, weight=1, uniform='snapshot')
    snap.grid_columnconfigure(1, weight=1, uniform='snapshot')

    next_title = 'NO OPEN RACE'
    next_sub = 'There are no currently eligible races in registration.'
    next_cmd = lambda: self.show('UPCOMING')
    try:
        eligible = [x for x in self.conn.execute("SELECT * FROM races WHERE status='REGISTRATION' ORDER BY start_time") if self.eligible(x, rider)]
        if eligible:
            race = eligible[0]
            next_title = race['name']
            next_sub = f"{self.race_class_label(race)}  •  {race['track']}  •  ${race['entry_fee']:.2f} entry"
            next_cmd = lambda rid=race['id']: self.open_race_details(rid)
    except Exception:
        pass
    RoundedTile(snap, next_title, next_sub, 'NEXT ELIGIBLE RACE', command=next_cmd,
                accent=ACCENT, height=116).grid(row=0, column=0, sticky='nsew', padx=(0, 6))

    result_title = 'NO RESULTS YET'
    result_sub = 'Completed race results will show here automatically.'
    try:
        x = self.conn.execute('''SELECT rs.position,rs.payout,rs.fast_lap_bonus,rc.name,rc.track
                                 FROM results rs JOIN races rc ON rc.id=rs.race_id
                                 WHERE rs.rider_id=? ORDER BY rc.start_time DESC LIMIT 1''',
                              (rider['id'],)).fetchone()
        if x:
            result_title = f"P{x['position']}  •  {x['name']}"
            result_sub = f"{x['track']}  •  ${float(x['payout'] or 0) + float(x['fast_lap_bonus'] or 0):,.0f} earned"
    except Exception:
        pass
    RoundedTile(snap, result_title, result_sub, 'LATEST RESULT', command=lambda: self.show('RESULTS'),
                accent=GOLD, height=116).grid(row=0, column=1, sticky='nsew', padx=(6, 0))


def _make_top_nav(app):
    try:
        app.nav.pack_forget()
    except Exception:
        pass
    try:
        body = app.content.master
        app.content.pack_forget()
    except Exception:
        return

    bar = tk.Frame(body, bg=BG, height=62)
    bar.pack(side='top', fill='x', padx=18, pady=(10, 2))
    bar.pack_propagate(False)
    app.content.pack(side='top', fill='both', expand=True)
    app._profile_first_topnav = bar
    app._profile_first_nav_pills = {}

    nav = [
        ('PROFILE', 'PROFILE', 108),
        ('GARAGE', 'GARAGE', 104),
        ('FIND A RACE', 'UPCOMING', 132),
        ('LIVE', 'LIVE', 92),
        ('RESULTS', 'RESULTS', 102),
        ('SERIES', 'CHAMPIONSHIPS', 96),
        ('RANKINGS', 'RANKINGS', 112),
    ]
    if app.is_admin():
        nav.append(('ADMIN', 'ADMIN', 96))
    left = tk.Frame(bar, bg=BG)
    left.pack(side='left', fill='y')
    for label, page, width in nav:
        pill = RoundedPill(left, label, command=lambda p=page: app.show(p),
                           active=app.current_page == page, width=width)
        pill.pack(side='left', padx=(0, 6), pady=7)
        app._profile_first_nav_pills[page] = pill

    right = tk.Frame(bar, bg=BG)
    right.pack(side='right', fill='y')
    app._profile_first_status = tk.Label(right, text='MX BIKES', fg=MUTED, bg=BG,
                                         font=('Segoe UI Semibold', 8))
    app._profile_first_status.pack(side='right', padx=(8, 2), pady=20)

    def refresh_status():
        try:
            text = app.mx_status_label.cget('text')
            fg = app.mx_status_label.cget('fg')
            app._profile_first_status.configure(text=text, fg=fg)
            app.after(1400, refresh_status)
        except Exception:
            pass
    app.after(400, refresh_status)


def _sync_top_nav(app):
    current = getattr(app, 'current_page', 'PROFILE')
    for page, pill in getattr(app, '_profile_first_nav_pills', {}).items():
        try:
            pill.set_active(page == current)
        except Exception:
            pass


def install_profile_first_ui(app):
    if getattr(app, '_profile_first_ui_installed', False):
        return
    app._profile_first_ui_installed = True

    app._profile_overview = types.MethodType(_profile_overview, app)
    app._profile_subnav = types.MethodType(_profile_subnav, app)
    _make_top_nav(app)

    original_show = app.show
    app._profile_first_original_show = original_show

    def wrapped_show(self, name, *args, **kwargs):
        result = original_show(name, *args, **kwargs)
        _sync_top_nav(self)
        return result

    app.show = types.MethodType(wrapped_show, app)
    _sync_top_nav(app)
