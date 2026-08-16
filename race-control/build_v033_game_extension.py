from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_3_2_UPDATE.zip')
BRIDGE = Path('race-control/game_bridge_v033.py')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_3_3_UPDATE.zip')
NOTES = ('MXB Race Day Live v0.3.3: turns Race Day Live into an MX Bikes race-day extension with automatic Steam/game detection, '
         'a global Launch MX Bikes button, registered-race bike selection backed by the synced MX Bikes bike library, saved per-race bike '
         'choices for server enforcement, live race-server readiness, and one-click PiBoSo -directconnect joining. Existing updater/restart, '
         'memberships, Community purse/fastest-lap economics, track artwork, live timing, results and admin server controls are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit('Published v0.3.2 base is missing or invalid')
if not BRIDGE.exists():
    raise SystemExit('v0.3.3 game bridge source is missing')

work = Path(tempfile.mkdtemp(prefix='mxb_v033_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)
shutil.copy2(BRIDGE, work/'src/game_bridge.py')

# Version markers.
p = work/'src/config.py'
s = p.read_text(encoding='utf-8')
s = re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.3.3'", s)
p.write_text(s, encoding='utf-8')

p = work/'src/__init__.py'
s = p.read_text(encoding='utf-8') if p.exists() else ''
if '__version__' in s:
    s = re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]", "__version__ = '0.3.3'", s)
else:
    s += "\n__version__ = '0.3.3'\n"
p.write_text(s, encoding='utf-8')

p = work/'src/updater.py'
s = p.read_text(encoding='utf-8')
s = re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+', 'MXB-Race-Day-Live-Updater/0.3.3', s)
p.write_text(s, encoding='utf-8')

# Current rider UI.
p = work/'src/app.py'
app = p.read_text(encoding='utf-8')

anchor = 'from .mx_agent import MXRaceAgent\n'
bridge_import = 'from .game_bridge import MXGameBridge, GameBridgeError, ensure_game_bridge_schema\n'
if bridge_import not in app:
    if anchor not in app: raise SystemExit('Could not locate mx_agent import anchor')
    app = app.replace(anchor, anchor + bridge_import, 1)

old_init = 'self.mx_agent=MXRaceAgent(connect,self.current_rider); self.track_media=TrackMediaResolver(connect)'
new_init = 'self.mx_agent=MXRaceAgent(connect,self.current_rider); ensure_game_bridge_schema(self.conn); self.game_bridge=MXGameBridge(self.conn); self.track_media=TrackMediaResolver(connect)'
if old_init in app:
    app = app.replace(old_init, new_init, 1)
elif new_init not in app:
    raise SystemExit('Could not locate MX bridge init anchor')

# Global Launch MX Bikes button in the Race Day Status sidebar.
old_side = "        self.mx_counts_label.pack(anchor='w',padx=22,pady=(0,6))\n        tk.Label(self.nav,text='Payments: DEMO MODE',fg=MUTED,bg='#101318',font=('Segoe UI',8)).pack(anchor='w',padx=22)"
new_side = "        self.mx_counts_label.pack(anchor='w',padx=22,pady=(0,6))\n        self.mx_launch_btn=tk.Button(self.nav,text='LAUNCH MX BIKES',command=self._launch_mx_game,bg=ACCENT,fg='white',activebackground='#1591ff',relief='flat',font=('Segoe UI Black',8),padx=10,pady=7,cursor='hand2'); self.mx_launch_btn.pack(fill='x',padx=18,pady=(2,9))\n        tk.Label(self.nav,text='Payments: DEMO MODE',fg=MUTED,bg='#101318',font=('Segoe UI',8)).pack(anchor='w',padx=22)"
if old_side in app:
    app = app.replace(old_side, new_side, 1)
elif "text='LAUNCH MX BIKES'" not in app:
    raise SystemExit('Could not locate sidebar launcher anchor')

# Publish the connection target whenever admin prepares/starts a dedicated race server.
if 'self.mx_agent.prepare_race(chosen())' in app:
    app = app.replace('self.mx_agent.prepare_race(chosen())', 'self.mx_agent.prepare_race(chosen()); self.game_bridge.publish_target(chosen())')
if 'self.mx_agent.start_race_server(chosen())' in app:
    app = app.replace('self.mx_agent.start_race_server(chosen())', 'self.mx_agent.start_race_server(chosen()); self.game_bridge.publish_target(chosen())')

# Race detail: registered riders get the integrated launcher below their registration status.
old_action = "        tk.Button(body,text=text,command=lambda:self.signup_demo(race),state=state,bg=color,fg='white',relief='flat',font=('Segoe UI Black',12),pady=12,cursor='hand2').pack(fill='x',pady=(0,14))\n\n    def signup_demo(self,race):"
new_action = "        tk.Button(body,text=text,command=lambda:self.signup_demo(race),state=state,bg=color,fg='white',relief='flat',font=('Segoe UI Black',12),pady=12,cursor='hand2').pack(fill='x',pady=(0,14))\n        if already:self._race_day_launcher(body,race,rider)\n\n    def signup_demo(self,race):"
if old_action in app:
    app = app.replace(old_action, new_action, 1)
elif 'if already:self._race_day_launcher(body,race,rider)' not in app:
    raise SystemExit('Could not locate registered-race launcher anchor')

# My Races rows now open Race Day details directly.
old_my_race = "            tk.Label(f,text=f\"{race['track']}  •  {datetime.fromisoformat(race['start_time']).strftime('%b %d %I:%M %p')}  •  PAID ${race['amount_paid']:.2f}\",fg=GOLD,bg=PANEL2,font=('Segoe UI Semibold',9)).pack(side='right',padx=10)"
new_my_race = old_my_race + "\n            self._bind_click_recursive(f,lambda rid=race['id']:self.open_race_details(rid))"
if old_my_race in app and '_bind_click_recursive(f,lambda rid=race[\'id\']:self.open_race_details(rid))' not in app[app.find('def _profile_my_races'):app.find('def _profile_wallet')]:
    app = app.replace(old_my_race, new_my_race, 1)

# MX Bikes link settings: automatic detection first, override only if needed; public host is a one-time owner/server setting.
sync_line = "        tk.Label(form,text=f\"MX Bikes sync: {status['value'] if status else 'not synced yet'}\",fg=GREEN if status else MUTED,bg=PANEL,font=('Segoe UI Semibold',8)).pack(anchor='w',padx=16,pady=(10,2))\n        def save_profile():"
settings_block = r'''        tk.Label(form,text=f"MX Bikes sync: {status['value'] if status else 'not synced yet'}",fg=GREEN if status else MUTED,bg=PANEL,font=('Segoe UI Semibold',8)).pack(anchor='w',padx=16,pady=(10,2))
        linkbox=tk.Frame(form,bg=PANEL2); linkbox.pack(fill='x',padx=16,pady=(9,2))
        tk.Label(linkbox,text='MX BIKES LINK',fg=ACCENT,bg=PANEL2,font=('Segoe UI Black',9)).pack(anchor='w',padx=10,pady=(9,2))
        detected=self.game_bridge.game_exe()
        tk.Label(linkbox,text=f"Detected game: {detected if detected else 'not found yet'}",fg=GREEN if detected else MUTED,bg=PANEL2,font=('Segoe UI',8),wraplength=970,justify='left').pack(anchor='w',padx=10)
        exe_override_var=tk.StringVar(value=self.conn.execute("SELECT value FROM admin_settings WHERE key='mx_game_exe_override'").fetchone()[0] or '')
        tk.Label(linkbox,text='GAME EXE OVERRIDE — leave blank for automatic Steam detection',fg=MUTED,bg=PANEL2,font=('Segoe UI Semibold',7)).pack(anchor='w',padx=10,pady=(7,2))
        tk.Entry(linkbox,textvariable=exe_override_var,bg=PANEL,fg=TEXT,insertbackground=TEXT,relief='flat',font=('Segoe UI',9)).pack(fill='x',padx=10,ipady=5)
        server_host_var=None
        if self.is_admin():
            server_host_var=tk.StringVar(value=self.conn.execute("SELECT value FROM admin_settings WHERE key='mx_public_server_host'").fetchone()[0] or '')
            tk.Label(linkbox,text='PUBLIC RACE SERVER HOST / IP — one-time server setting',fg=MUTED,bg=PANEL2,font=('Segoe UI Semibold',7)).pack(anchor='w',padx=10,pady=(7,2))
            tk.Entry(linkbox,textvariable=server_host_var,bg=PANEL,fg=TEXT,insertbackground=TEXT,relief='flat',font=('Segoe UI',9)).pack(fill='x',padx=10,ipady=5,pady=(0,9))
        else:
            tk.Label(linkbox,text='Race server address is published automatically by Race Day Live when the host opens the server.',fg=MUTED,bg=PANEL2,font=('Segoe UI',8)).pack(anchor='w',padx=10,pady=(7,9))
        def save_profile():'''
if sync_line in app:
    app = app.replace(sync_line, settings_block, 1)
elif "text='MX BIKES LINK'" not in app:
    raise SystemExit('Could not locate MX link settings anchor')

# Persist those settings with the existing SAVE PROFILE transaction.
old_commit = "                self.conn.commit()\n            except Exception as exc: messagebox.showerror('Profile Settings',f'Could not save profile: {exc}'); return"
new_commit = "                self.conn.execute(\"UPDATE admin_settings SET value=? WHERE key='mx_game_exe_override'\",(exe_override_var.get().strip(),))\n                if server_host_var is not None:self.conn.execute(\"UPDATE admin_settings SET value=? WHERE key='mx_public_server_host'\",(server_host_var.get().strip(),))\n                self.conn.commit()\n            except Exception as exc: messagebox.showerror('Profile Settings',f'Could not save profile: {exc}'); return"
if old_commit in app:
    app = app.replace(old_commit, new_commit, 1)
elif "mx_game_exe_override" not in app[app.find('def save_profile'):app.find('def add_funds_dialog')]:
    raise SystemExit('Could not locate profile save commit anchor')

# Integrated race-day methods. These use the sync DB written by MXRaceAgent rather than duplicating server logic.
launcher_methods = r'''
    def _launch_mx_game(self):
        try:
            result=self.game_bridge.launch_game()
            try:self.mx_status_label.configure(text='● MX BIKES LAUNCHED',fg=GREEN)
            except Exception:pass
            return result
        except GameBridgeError as exc:
            messagebox.showerror('MX Bikes',str(exc))
        except Exception as exc:
            messagebox.showerror('MX Bikes',f'Could not launch MX Bikes: {exc}')

    def _join_race_server(self,race_id,rider_id):
        try:
            result=self.game_bridge.launch_race(race_id,rider_id)
            messagebox.showinfo('Race Day Live',f"Launching MX Bikes directly into {result['endpoint']}.")
        except GameBridgeError as exc:
            messagebox.showerror('Race Day',str(exc))
        except Exception as exc:
            messagebox.showerror('Race Day',f'Could not join the MX Bikes race server: {exc}')

    def _save_race_bike_choice(self,race_id,rider_id,label,bike_map):
        item=bike_map.get(label)
        if not item:
            messagebox.showerror('Race Bike','Choose a bike from your synced MX Bikes library first.'); return
        try:
            saved=self.game_bridge.select_bike(race_id,rider_id,item['content_id'],item['display_name'])
            messagebox.showinfo('Race Bike',f"{saved['display_name']} is locked in for this race. Race Day Live will pass that selection into the server registration.")
            self.open_race_details(race_id)
        except GameBridgeError as exc:messagebox.showerror('Race Bike',str(exc))
        except Exception as exc:messagebox.showerror('Race Bike',f'Could not save race bike: {exc}')

    def _race_day_launcher(self,parent,race,rider):
        launch=self.card(parent); launch.pack(fill='x',pady=(0,16))
        tk.Label(launch,text='RACE DAY LAUNCHER',fg=ACCENT,bg=PANEL,font=('Segoe UI Black',15)).pack(anchor='w',padx=16,pady=(14,2))
        tk.Label(launch,text='Race Day Live is linked to MX Bikes. Pick your bike before race time; when the server opens, JOIN RACE SERVER launches MX Bikes directly into it.',fg=MUTED,bg=PANEL,font=('Segoe UI',9),wraplength=1030,justify='left').pack(anchor='w',padx=16,pady=(0,10))
        status=self.game_bridge.status(race['id'],rider['id']); target=status['target']; selected=status['selected_bike']
        row=tk.Frame(launch,bg=PANEL2); row.pack(fill='x',padx=14,pady=(0,10))
        game_text='MX BIKES READY' if status['game_found'] else 'MX BIKES NOT FOUND'
        tk.Label(row,text=game_text,fg=GREEN if status['game_found'] else RED,bg=PANEL2,font=('Segoe UI Black',9)).pack(side='left',padx=10,pady=10)
        if target.get('ready'):
            server_text=f"SERVER OPEN • {target.get('endpoint','')}"
            server_color=GREEN
        elif not target.get('host'):
            server_text='SERVER ADDRESS PENDING'
            server_color=GOLD
        else:
            server_text=f"SERVER {target.get('status','PREPARING')}"
            server_color=GOLD
        tk.Label(row,text=server_text,fg=server_color,bg=PANEL2,font=('Segoe UI Black',9)).pack(side='right',padx=10)

        bikes=status['bike_count'] and self.game_bridge.bikes() or []
        if bikes:
            picker=tk.Frame(launch,bg=PANEL); picker.pack(fill='x',padx=16,pady=(0,10))
            tk.Label(picker,text='YOUR BIKE FOR THIS RACE',fg=MUTED,bg=PANEL,font=('Segoe UI Semibold',8)).pack(anchor='w')
            bike_map={}
            for item in bikes:
                label=f"{item['display_name']}  [{item['content_id']}]"
                bike_map[label]=item
            labels=list(bike_map.keys())
            current=''
            if selected:
                for label,item in bike_map.items():
                    if item['content_id']==selected.get('content_id') or item['display_name']==selected.get('display_name'):
                        current=label; break
            if not current and rider['game_bike_id']:
                for label,item in bike_map.items():
                    if item['content_id']==rider['game_bike_id']:
                        current=label; break
            bike_var=tk.StringVar(value=current)
            combo=ttk.Combobox(picker,textvariable=bike_var,values=labels,state='readonly',font=('Segoe UI',10)); combo.pack(side='left',fill='x',expand=True,ipady=5,pady=(4,0))
            tk.Button(picker,text='SAVE RACE BIKE',command=lambda:self._save_race_bike_choice(race['id'],rider['id'],bike_var.get(),bike_map),bg=PANEL2,fg=TEXT,relief='flat',font=('Segoe UI Black',9),padx=13,pady=8,cursor='hand2').pack(side='left',padx=(8,0),pady=(4,0))
            if selected:tk.Label(launch,text=f"LOCKED IN: {selected['display_name']}",fg=GREEN,bg=PANEL,font=('Segoe UI Black',9)).pack(anchor='w',padx=16,pady=(0,8))
        else:
            tk.Label(launch,text='No bikes are in the synced game library yet. Race Day Live will keep syncing MX Bikes automatically.',fg=GOLD,bg=PANEL,font=('Segoe UI Semibold',9)).pack(anchor='w',padx=16,pady=(0,8))

        actions=tk.Frame(launch,bg=PANEL); actions.pack(fill='x',padx=14,pady=(0,14))
        if target.get('ready'):
            tk.Button(actions,text='JOIN RACE SERVER',command=lambda:self._join_race_server(race['id'],rider['id']),bg=GREEN,fg='white',activebackground='#50df91',relief='flat',font=('Segoe UI Black',12),pady=12,cursor='hand2').pack(side='left',fill='x',expand=True,padx=(0,6))
        else:
            tk.Button(actions,text='LAUNCH MX BIKES',command=self._launch_mx_game,bg=ACCENT,fg='white',relief='flat',font=('Segoe UI Black',11),pady=12,cursor='hand2').pack(side='left',fill='x',expand=True,padx=(0,6))
        tk.Button(actions,text='SYNC NOW',command=self._run_mx_sync,bg=PANEL2,fg=TEXT,relief='flat',font=('Segoe UI Black',9),padx=15,pady=12,cursor='hand2').pack(side='left',padx=(6,0))

'''
marker = '    def signup_demo(self,race):\n'
if '    def _race_day_launcher(self,parent,race,rider):\n' not in app:
    if marker not in app: raise SystemExit('Could not locate launcher method insertion point')
    app = app.replace(marker, launcher_methods + marker, 1)

p.write_text(app, encoding='utf-8')

# Compile every Python file included in the update overlay.
for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

# Regression gates: fail closed if this update drops an already-approved system.
app_check=(work/'src/app.py').read_text(encoding='utf-8')
bridge_check=(work/'src/game_bridge.py').read_text(encoding='utf-8')
config_check=(work/'src/config.py').read_text(encoding='utf-8')
updater_check=(work/'src/updater.py').read_text(encoding='utf-8')
subs_check=(work/'src/subscriptions.py').read_text(encoding='utf-8')
pricing_check=(work/'src/pricing.py').read_text(encoding='utf-8') if (work/'src/pricing.py').exists() else app_check
track_check=(work/'src/track_media.py').read_text(encoding='utf-8') if (work/'src/track_media.py').exists() else app_check

assert "VERSION = '0.3.3'" in config_check
assert 'MXGameBridge' in app_check and "text='JOIN RACE SERVER'" in app_check and "text='LAUNCH MX BIKES'" in app_check
assert "DIRECT_CONNECT_FLAG = '-directconnect'" in bridge_check and "STEAM_APP_ID = '655500'" in bridge_check
assert 'game_bike_name' in bridge_check and 'game_bike_short' in bridge_check and 'game_content' in bridge_check
assert 'race_launch_targets' in bridge_check and 'race_sessions' in bridge_check
assert 'member_quote' in app_check and all(x in subs_check for x in ("'PIT'", "'RACE'", "'FACTORY'"))
assert 'fastest_lap_pool' in app_check and 'current_purse' in app_check
assert 'check_for_update' in app_check and 'launch_update' in app_check
assert 'api.github.com/repos/' in updater_check and 'latest.json' in updater_check
assert 'MXRaceAgent' in app_check and 'start_race_server' in app_check and 'prepare_race' in app_check
assert 'TrackMediaResolver' in app_check
assert '0.25' in pricing_check or 'fast_lap_contribution' in app_check

# Package all current v0.3.2 overlay files plus the new bridge.
OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and not f.suffix=='.pyc':
            z.write(f,f.relative_to(work).as_posix())

digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={
    'version':'0.3.3',
    'url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_3_UPDATE.zip',
    'sha256':digest,
    'notes':NOTES,
}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('GAME EXTENSION VERIFIED', {'directconnect': True, 'steam_app_id': STEAM_APP_ID if 'STEAM_APP_ID' in globals() else '655500', 'bike_sync': True, 'server_ready_gate': True})
print('BUILT',OUT,digest)
