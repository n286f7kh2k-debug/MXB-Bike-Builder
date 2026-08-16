from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_3_3_UPDATE.zip')
GARAGE=Path('race-control/bike_garage_v034.py')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_3_4_UPDATE.zip')
NOTES=('MXB Race Day Live v0.3.4: adds a native Profile > Bikes garage modeled on the MX Bikes Bike Selection screen. '
       'It reads the rider’s actual MX Bikes profile and mod folders, cycles the same Bike/Head/Torso/Legs selections, writes the native '
       'profile.ini selection fields with a safety backup, uses synced/custom bikes and .pnt gear paints, and keeps race-bike selection aligned. '
       'Also assigns a stable Windows AppUserModelID and the Race Day Live icon to the window/taskbar. v0.3.3 one-click game/server launch '
       'and all existing updater, membership, wallet, race economics, track media, live timing, results and admin controls are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('v0.3.3 base missing or invalid')
if not GARAGE.exists():raise SystemExit('bike garage source missing')
work=Path(tempfile.mkdtemp(prefix='mxb_v034_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(GARAGE,work/'src/bike_garage.py')

# Version markers.
p=work/'src/config.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]","VERSION = '0.3.4'",s); p.write_text(s,encoding='utf-8')
p=work/'src/__init__.py'; s=p.read_text(encoding='utf-8') if p.exists() else ''; s=re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]","__version__ = '0.3.4'",s) if '__version__' in s else s+"\n__version__ = '0.3.4'\n"; p.write_text(s,encoding='utf-8')
p=work/'src/updater.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+','MXB-Race-Day-Live-Updater/0.3.4',s); p.write_text(s,encoding='utf-8')

p=work/'src/app.py'; app=p.read_text(encoding='utf-8')

# Stable Windows app identity must be set before Tk creates the top-level window.
identity="""
APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'
try:
    if os.name=='nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
except Exception:
    pass
"""
if "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'" not in app:
    marker="NAV = [\n"
    if marker not in app:raise SystemExit('NAV anchor missing for Windows identity')
    app=app.replace(marker,identity+'\n'+marker,1)

# Native garage bridge import/init.
anchor='from .game_bridge import MXGameBridge, GameBridgeError, ensure_game_bridge_schema\n'
imp='from .bike_garage import MXBikeGarage, BikeGarageError\n'
if imp not in app:
    if anchor not in app:raise SystemExit('game bridge import missing')
    app=app.replace(anchor,anchor+imp,1)
old="self.mx_agent=MXRaceAgent(connect,self.current_rider); ensure_game_bridge_schema(self.conn); self.game_bridge=MXGameBridge(self.conn); self.track_media=TrackMediaResolver(connect)"
new="self.mx_agent=MXRaceAgent(connect,self.current_rider); ensure_game_bridge_schema(self.conn); self.game_bridge=MXGameBridge(self.conn); self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.track_media=TrackMediaResolver(connect)"
if old in app:app=app.replace(old,new,1)
elif 'self.bike_garage=MXBikeGarage' not in app:raise SystemExit('init bridge anchor missing')

# Taskbar/window icon: explicit AppUserModelID + window iconphoto + ICO.
old_icon="        try:self.iconbitmap(os.path.join(os.path.dirname(os.path.dirname(__file__)),'assets','mxb_race_day_live.ico'))\n        except Exception:pass"
new_icon="""        try:
            icon_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),'assets','mxb_race_day_live.ico')
            self.iconbitmap(default=icon_path)
            if Image is not None and ImageTk is not None:
                with Image.open(icon_path) as icon_im:
                    icon_im=icon_im.convert('RGBA'); icon_im.thumbnail((256,256),Image.Resampling.LANCZOS)
                    self._taskbar_icon=ImageTk.PhotoImage(icon_im.copy())
                self.iconphoto(True,self._taskbar_icon)
        except Exception:pass"""
if old_icon in app:app=app.replace(old_icon,new_icon,1)
elif 'self.iconphoto(True,self._taskbar_icon)' not in app:raise SystemExit('icon anchor missing')

# Profile subnav + route.
old_nav="for label,key in [('OVERVIEW','OVERVIEW'),('MY RACES','RACES'),('WALLET','WALLET'),('MEMBERSHIP','MEMBERSHIP'),('PROFILE SETTINGS','SETTINGS')]:"
new_nav="for label,key in [('OVERVIEW','OVERVIEW'),('MY RACES','RACES'),('BIKES','BIKES'),('WALLET','WALLET'),('MEMBERSHIP','MEMBERSHIP'),('PROFILE SETTINGS','SETTINGS')]:"
if old_nav in app:app=app.replace(old_nav,new_nav,1)
elif "('BIKES','BIKES')" not in app:raise SystemExit('profile subnav anchor missing')
route="        if self.profile_section=='RACES': return self._profile_my_races(r)\n"
if "self.profile_section=='BIKES'" not in app:
    if route not in app:raise SystemExit('profile route anchor missing')
    app=app.replace(route,route+"        if self.profile_section=='BIKES': return self._profile_bikes(r)\n",1)

# Keep garage username aligned when Profile Settings renames the rider.
rename="            self.current_rider=name; self.mx_agent.current_username=name"
rename_new="            self.current_rider=name; self.mx_agent.current_username=name; self.bike_garage.username=name"
if rename in app:app=app.replace(rename,rename_new,1)

# MX Bikes-like Bike Selection page: Bike, Head, Torso, Legs in the same order with arrow cycling.
method=r'''
    def _profile_bikes(self,r):
        body=self._scrollable(self.content,pady=(0,24))
        tk.Label(body,text='BIKE SELECTION',fg=TEXT,bg=BG,font=('Segoe UI Black',22,'italic')).pack(anchor='w',pady=(4,2))
        tk.Label(body,text='The same MX Bikes rider/bike selection, connected to your actual game profile. Changes here are written to MX Bikes profile.ini so the game opens with this bike and kit selected.',fg=MUTED,bg=BG,font=('Segoe UI',10),wraplength=1080,justify='left').pack(anchor='w',pady=(0,12))
        self.bike_garage.username=self.current_rider
        diag=self.bike_garage.diagnostics(); current=self.bike_garage.read_selection(); records=self.bike_garage.bike_records()
        by_id={x['id']:x for x in records}
        if current.get('bikeid') and current['bikeid'] in by_id:category=by_id[current['bikeid']]['category']
        else:category=(records[0]['category'] if records else 'OTHER')
        state=dict(current); state['category']=category
        if not state.get('rider'):state['rider']='default_mx'
        if not state.get('helmet'):state['helmet']='default'
        if not state.get('boots'):state['boots']='default'
        if not state.get('protection'):state['protection']='default'

        shell=tk.Frame(body,bg=BG); shell.pack(fill='x')
        left=self.card(shell); left.pack(side='left',fill='y',padx=(0,8)); left.configure(width=535); left.pack_propagate(False)
        right=self.card(shell); right.pack(side='left',fill='both',expand=True,padx=(8,0))
        selector_labels={}; selector_values={}

        def values(key):
            if key=='category':vals=self.bike_garage.categories()
            elif key=='bikeid':vals=[x['id'] for x in self.bike_garage.bikes_for_category(state.get('category'))]
            elif key=='paint':vals=self.bike_garage.bike_paints(state.get('bikeid',''))
            elif key=='bike_font':vals=self.bike_garage.fonts('bike')
            elif key=='helmet':vals=self.bike_garage.helmet_models()
            elif key=='helmet_paint':vals=self.bike_garage.helmet_paints(state.get('helmet','default'))
            elif key=='goggles_paint':vals=self.bike_garage.goggles_paints(state.get('helmet','default'))
            elif key=='helmet_cam':vals=self.bike_garage.helmet_cams()
            elif key=='rider':vals=self.bike_garage.rider_models()
            elif key=='suit_paint':vals=self.bike_garage.rider_paints(state.get('rider','default_mx'))
            elif key=='suit_font':vals=self.bike_garage.fonts('rider')
            elif key=='gloves_paint':vals=self.bike_garage.gloves_paints(state.get('rider','default_mx'))
            elif key=='protection':vals=self.bike_garage.protection_models()
            elif key=='protection_paint':vals=self.bike_garage.protection_paints(state.get('protection','default'))
            elif key=='boots':vals=self.bike_garage.boot_models()
            elif key=='boots_paint':vals=self.bike_garage.boot_paints(state.get('boots','default'))
            else:vals=['']
            cur=str(state.get(key,'') or '')
            vals=list(vals or [])
            if cur not in vals:vals=[cur]+vals
            if not vals:vals=['']
            return vals

        def display(key,value):
            value=str(value or '')
            if key=='bikeid':return self.bike_garage.bike_display(value) or '—'
            if not value or value.lower()=='none':return '-None-'
            return value

        def normalize_dependents(changed):
            deps={
                'category':['bikeid','paint'], 'bikeid':['paint'],
                'helmet':['helmet_paint','goggles_paint'],
                'rider':['suit_paint','gloves_paint'],
                'protection':['protection_paint'], 'boots':['boots_paint']}
            for dep in deps.get(changed,[]):
                vals=values(dep)
                if str(state.get(dep,'') or '') not in vals:state[dep]=vals[0] if vals else ''
            if changed=='bikeid':
                rec=next((x for x in records if x['id']==state.get('bikeid')),None)
                if rec:state['category']=rec['category']

        preview_image=tk.Label(right,text='',fg=TEXT,bg='#0f1216',font=('Segoe UI Black',18),justify='center')
        preview_image.pack(fill='x',padx=14,pady=(14,8),ipady=30)
        preview_title=tk.Label(right,text='',fg=TEXT,bg=PANEL,font=('Segoe UI Black',18))
        preview_title.pack(anchor='w',padx=16,pady=(4,1))
        preview_meta=tk.Label(right,text='',fg=ACCENT,bg=PANEL,font=('Segoe UI Black',10),justify='left')
        preview_meta.pack(anchor='w',padx=16)
        preview_gear=tk.Label(right,text='',fg=MUTED,bg=PANEL,font=('Segoe UI Semibold',9),justify='left',wraplength=550)
        preview_gear.pack(anchor='w',padx=16,pady=(8,12))

        def refresh_preview():
            bike=state.get('bikeid',''); preview_title.configure(text=self.bike_garage.bike_display(bike) or 'NO BIKE DETECTED')
            preview_meta.configure(text=f"{state.get('category','OTHER')}  •  Paint: {display('paint',state.get('paint'))}  •  Bike font: {display('bike_font',state.get('bike_font'))}")
            preview_gear.configure(text=(f"Helmet: {display('helmet',state.get('helmet'))} / {display('helmet_paint',state.get('helmet_paint'))}\n"
                                         f"Rider: {display('rider',state.get('rider'))} / {display('suit_paint',state.get('suit_paint'))} / Gloves: {display('gloves_paint',state.get('gloves_paint'))}\n"
                                         f"Boots: {display('boots',state.get('boots'))} / {display('boots_paint',state.get('boots_paint'))}  •  Protection: {display('protection',state.get('protection'))}"))
            pic=self.bike_garage.garage_picture(bike)
            photo=self._load_track_tk(str(pic),(570,330)) if pic else None
            if photo:preview_image.configure(image=photo,text='')
            else:preview_image.configure(image='',text='MX BIKES\nBIKE SELECTION\n\n'+(self.bike_garage.bike_display(bike) or 'SYNC GAME CONTENT'))

        def refresh_all():
            for key,label in selector_labels.items():label.configure(text=display(key,state.get(key,'')))
            refresh_preview()

        def cycle(key,step):
            vals=values(key); cur=str(state.get(key,'') or '')
            try:i=vals.index(cur)
            except ValueError:i=0
            state[key]=vals[(i+step)%len(vals)]
            normalize_dependents(key); refresh_all()

        def group(title,rows):
            box=tk.Frame(left,bg=PANEL); box.pack(fill='x',padx=12,pady=(10,0))
            tk.Label(box,text=title,fg=TEXT,bg=PANEL,font=('Segoe UI Black',11)).pack(anchor='w',pady=(0,5))
            for label_text,key in rows:
                row=tk.Frame(box,bg=PANEL2,height=34); row.pack(fill='x',pady=2); row.pack_propagate(False)
                tk.Label(row,text=label_text,fg=MUTED,bg=PANEL2,font=('Segoe UI Semibold',8),width=17,anchor='w').pack(side='left',padx=(9,2))
                tk.Button(row,text='◀',command=lambda k=key:cycle(k,-1),bg=PANEL2,fg=TEXT,activebackground='#2d3944',activeforeground='white',relief='flat',font=('Segoe UI Black',9),width=3,cursor='hand2').pack(side='left')
                val=tk.Label(row,text='',fg=TEXT,bg='#20262d',font=('Segoe UI Semibold',9),anchor='center'); val.pack(side='left',fill='both',expand=True,padx=3); selector_labels[key]=val
                tk.Button(row,text='▶',command=lambda k=key:cycle(k,1),bg=PANEL2,fg=TEXT,activebackground='#2d3944',activeforeground='white',relief='flat',font=('Segoe UI Black',9),width=3,cursor='hand2').pack(side='left',padx=(0,5))
            return box

        group('BIKE',[('Category','category'),('Bike','bikeid'),('Paint','paint'),('Bike Font','bike_font')])
        group('HEAD',[('Helmet','helmet'),('Helmet Paint','helmet_paint'),('Goggles Paint','goggles_paint'),('Helmet Cam','helmet_cam')])
        group('TORSO',[('Rider','rider'),('Rider Gear','suit_paint'),('Rider Font','suit_font'),('Gloves Paint','gloves_paint'),('Protection','protection'),('Protection Paint','protection_paint')])
        group('LEGS',[('Boots','boots'),('Boots Paint','boots_paint')])

        pathbox=tk.Frame(right,bg=PANEL2); pathbox.pack(fill='x',padx=14,pady=(0,10))
        tk.Label(pathbox,text=f"MX Bikes profile: {diag.get('profile') or 'not detected'}",fg=GREEN if diag.get('profile_ini') else GOLD,bg=PANEL2,font=('Segoe UI Black',9)).pack(anchor='w',padx=10,pady=(9,1))
        tk.Label(pathbox,text=f"{diag.get('profile_ini') or 'Launch MX Bikes once and sync to create/detect profile.ini'}",fg=MUTED,bg=PANEL2,font=('Segoe UI',8),wraplength=560,justify='left').pack(anchor='w',padx=10,pady=(0,3))
        tk.Label(pathbox,text=f"{diag.get('bikes',0)} bikes detected  •  Mods: {diag.get('mods_root','')}",fg=MUTED,bg=PANEL2,font=('Segoe UI',8),wraplength=560,justify='left').pack(anchor='w',padx=10,pady=(0,9))

        def apply_game_profile():
            payload={k:v for k,v in state.items() if k in self.bike_garage.PROFILE_KEYS}
            payload['race_number']=str(r['number'] or current.get('race_number') or '')
            try:
                path=self.bike_garage.apply_selection(payload)
                messagebox.showinfo('MX Bikes Bike Selection',f"Applied directly to MX Bikes profile:\n{path}\n\nYour original profile.ini was backed up the first time Race Day Live changed it.")
                self._set_profile_section('BIKES')
            except BikeGarageError as exc:messagebox.showerror('MX Bikes Bike Selection',str(exc))
            except Exception as exc:messagebox.showerror('MX Bikes Bike Selection',f'Could not apply the selection: {exc}')

        actions=tk.Frame(right,bg=PANEL); actions.pack(fill='x',padx=14,pady=(0,14))
        tk.Button(actions,text='APPLY TO MX BIKES',command=apply_game_profile,bg=GREEN,fg='white',relief='flat',font=('Segoe UI Black',11),pady=11,cursor='hand2').pack(fill='x',pady=(0,7))
        row=tk.Frame(actions,bg=PANEL); row.pack(fill='x')
        tk.Button(row,text='READ CURRENT GAME SELECTION',command=lambda:self._set_profile_section('BIKES'),bg=PANEL2,fg=TEXT,relief='flat',font=('Segoe UI Black',9),pady=9,cursor='hand2').pack(side='left',fill='x',expand=True,padx=(0,4))
        tk.Button(row,text='SYNC GAME CONTENT',command=lambda:[self._run_mx_sync(),self.after(1100,lambda:self._set_profile_section('BIKES'))],bg=PANEL2,fg=TEXT,relief='flat',font=('Segoe UI Black',9),pady=9,cursor='hand2').pack(side='left',fill='x',expand=True,padx=4)
        tk.Button(row,text='LAUNCH MX BIKES',command=self._launch_mx_game,bg=ACCENT,fg='white',relief='flat',font=('Segoe UI Black',9),pady=9,cursor='hand2').pack(side='left',fill='x',expand=True,padx=(4,0))
        tk.Label(right,text='Race Day Live uses MX Bikes native profile values. If a custom model or paint is installed in the correct MX Bikes mod folder, it appears here automatically after sync/reload.',fg=MUTED,bg=PANEL,font=('Segoe UI',8),wraplength=570,justify='left').pack(anchor='w',padx=16,pady=(0,14))
        refresh_all()

'''
insert='    def _profile_settings(self,r):\n'
if '    def _profile_bikes(self,r):\n' not in app:
    if insert not in app:raise SystemExit('profile settings insertion anchor missing')
    app=app.replace(insert,method+insert,1)

p.write_text(app,encoding='utf-8')

# Compile and regression gates.
for py in work.rglob('*.py'):
    py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
garc=(work/'src/bike_garage.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')
updater=(work/'src/updater.py').read_text(encoding='utf-8')
assert "VERSION = '0.3.4'" in config
assert "('BIKES','BIKES')" in appc and "def _profile_bikes" in appc
for label in ('BIKE','HEAD','TORSO','LEGS','APPLY TO MX BIKES','READ CURRENT GAME SELECTION','LAUNCH MX BIKES'):
    assert label in appc
for key in ('bikeid','paint','bike_font','rider','helmet','helmet_paint','goggles_paint','helmet_cam','suit_paint','suit_font','boots','boots_paint','gloves_paint','protection','protection_paint'):
    assert key in garc
assert 'profile.race_day_live_backup.ini' in garc and 'global.ini' in garc and "'.pnt'" in garc
assert "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'" in appc and 'SetCurrentProcessExplicitAppUserModelID' in appc and 'iconphoto(True,self._taskbar_icon)' in appc
assert 'MXGameBridge' in appc and 'JOIN RACE SERVER' in appc and '-directconnect' in (work/'src/game_bridge.py').read_text(encoding='utf-8')
assert 'member_quote' in appc and 'fastest_lap_pool' in appc and 'current_purse' in appc and 'TrackMediaResolver' in appc
assert 'api.github.com/repos/' in updater and 'latest.json' in updater

with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':'0.3.4','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_4_UPDATE.zip','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('PROFILE BIKES VERIFIED',{'native_profile_fields':15,'groups':['BIKE','HEAD','TORSO','LEGS'],'profile_backup':True,'custom_pnt_scan':True,'taskbar_app_id':True,'taskbar_iconphoto':True})
print('BUILT',OUT,digest)
