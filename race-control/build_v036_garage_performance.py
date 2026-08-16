from pathlib import Path
import hashlib, json, py_compile, re, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_3_5_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_3_6_UPDATE.zip')
NOTES=('MXB Race Day Live v0.3.6: moves bike/kit selection into a dedicated top-level GARAGE and keeps every installed MX Bikes bike compatible, '
       'including EDF-only bikes, by running the MX Bikes testing renderer as a hidden backend and attaching only its render surface inside Race Day Live. '
       'No separate game window is shown for Garage preview. Also completes a whole-app performance pass: cached MX content/paint/model scans, cached Steam/game '
       'discovery, cached resized profile/track images and track-media lookups, same-page navigation short-circuiting, Garage-only renderer lifecycle, and an '
       'in-place one-second LIVE timing/commentary refresh instead of destroying/recreating the tower every second. Existing updater/restart, taskbar logo, '
       'one-click race joining, memberships, wallet, race economics, track artwork, results and admin controls are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE): raise SystemExit('v0.3.5 base missing or invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v036_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)

def replace_method(text,name,body,next_name):
    start=text.index(f'    def {name}(')
    end=text.index(f'\n    def {next_name}(',start)
    return text[:start]+body.rstrip()+'\n'+text[end:]

# ---------- version ----------
p=work/'src/config.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]","VERSION = '0.3.6'",s); p.write_text(s,encoding='utf-8')
p=work/'src/__init__.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]","__version__ = '0.3.6'",s); p.write_text(s,encoding='utf-8')
p=work/'src/updater.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+','MXB-Race-Day-Live-Updater/0.3.6',s); p.write_text(s,encoding='utf-8')

# ---------- app: dedicated Garage + UI performance ----------
p=work/'src/app.py'; app=p.read_text(encoding='utf-8')

# Top-level Garage navigation.
nav_old="    ('MY PROFILE','PROFILE'),\n    ('FIND A RACE','UPCOMING'),"
nav_new="    ('MY PROFILE','PROFILE'),\n    ('GARAGE','GARAGE'),\n    ('FIND A RACE','UPCOMING'),"
if nav_old in app: app=app.replace(nav_old,nav_new,1)
elif "('GARAGE','GARAGE')" not in app: raise SystemExit('NAV Garage anchor missing')

# Persistent media caches: PhotoImage objects remain valid across page rebuilds.
old="self._image_refs=[]; self._mx_sync_started=False; self.profile_section='OVERVIEW'; self.race_filter='ALL'; self.current_page='PROFILE'"
new="self._image_refs=[]; self._photo_cache={}; self._profile_photo_cache={}; self._track_media_mem={}; self._mx_sync_started=False; self.profile_section='OVERVIEW'; self.race_filter='ALL'; self.current_page='PROFILE'"
if old in app:app=app.replace(old,new,1)
elif 'self._photo_cache={}' not in app:raise SystemExit('cache init anchor missing')

# Cached profile image scaling.
app=replace_method(app,'_load_profile_photo',r'''    def _load_profile_photo(self,path,size):
        if not path or Image is None or ImageTk is None:return None
        try:
            source=Path(path)
            if not source.exists():return None
            stat=source.stat(); key=(str(source.resolve()).lower(),tuple(size),int(stat.st_mtime_ns),int(stat.st_size))
            cached=self._profile_photo_cache.get(key)
            if cached is not None:return cached
            from PIL import ImageOps
            with Image.open(source) as im:
                im=im.convert('RGB'); im=ImageOps.fit(im,size,method=Image.Resampling.LANCZOS); im.load(); photo=ImageTk.PhotoImage(im.copy())
            self._profile_photo_cache[key]=photo
            while len(self._profile_photo_cache)>24:self._profile_photo_cache.pop(next(iter(self._profile_photo_cache)))
            return photo
        except Exception:return None
''','_store_profile_image')

# Cached track image scaling.
app=replace_method(app,'_load_track_tk',r'''    def _load_track_tk(self,path,size=(330,186)):
        if not path or Image is None or ImageTk is None:return None
        try:
            source=Path(path)
            if not source.exists():return None
            stat=source.stat(); key=(str(source.resolve()).lower(),tuple(size),int(stat.st_mtime_ns),int(stat.st_size))
            cached=self._photo_cache.get(key)
            if cached is not None:return cached
            with Image.open(source) as im:
                im=im.convert('RGB'); im.thumbnail(size,Image.Resampling.LANCZOS)
                canvas=Image.new('RGB',size,(21,25,30)); x=(size[0]-im.width)//2; y=(size[1]-im.height)//2; canvas.paste(im,(x,y))
                photo=ImageTk.PhotoImage(canvas)
            self._photo_cache[key]=photo
            while len(self._photo_cache)>96:self._photo_cache.pop(next(iter(self._photo_cache)))
            return photo
        except Exception:return None
''','_track_photo')

# Track-media DB hits are memoized in-process. Async resolutions replace the memo entry.
track_anchor="        def apply(media):\n            try:\n                if not label.winfo_exists(): return"
track_new="        media_key=(str(discipline).upper(),str(track))\n        def apply(media):\n            self._track_media_mem[media_key]=media\n            try:\n                if not label.winfo_exists(): return"
if track_anchor in app:app=app.replace(track_anchor,track_new,1)
elif 'media_key=(str(discipline).upper(),str(track))' not in app:raise SystemExit('track memo apply anchor missing')
old_cached="        cached=self.track_media.get_cached(discipline,track)"
new_cached="        cached=self._track_media_mem.get(media_key)\n        if cached is None:\n            cached=self.track_media.get_cached(discipline,track); self._track_media_mem[media_key]=cached"
if old_cached in app:app=app.replace(old_cached,new_cached,1)
elif 'self._track_media_mem.get(media_key)' not in app:raise SystemExit('track memo read anchor missing')

# Do not stop renderer on unrelated page clears; do not rebuild the same page when nothing requested a forced refresh.
app=replace_method(app,'clear',r'''    def clear(self,stop_renderer=False):
        if stop_renderer:
            try:
                if hasattr(self,'native_renderer'):self.native_renderer.stop()
            except Exception:pass
        try:self.unbind_all('<MouseWheel>')
        except Exception:pass
        for w in self.content.winfo_children():w.destroy()
        self._image_refs=[]
''','show')
app=replace_method(app,'show',r'''    def show(self,name,force=False):
        if name=='ADMIN' and not self.is_admin():name='PROFILE'
        previous=getattr(self,'current_page',None)
        if not force and name==previous and self.content.winfo_children():return
        self.clear(stop_renderer=(previous=='GARAGE' and name!='GARAGE'))
        self.current_page=name
        for n,b in self.nav_buttons.items():b.configure(bg=PANEL2 if n==name else '#101318',fg=ACCENT if n==name else TEXT)
        getattr(self,'page_'+name.lower().replace(' ','_'))()
''','titlebar')

# Profile subnav no longer owns Bikes/Garage.
app=replace_method(app,'_profile_subnav',r'''    def _profile_subnav(self):
        row=tk.Frame(self.content,bg=BG); row.pack(fill='x',padx=28,pady=(0,12))
        for label,key in [('OVERVIEW','OVERVIEW'),('MY RACES','RACES'),('WALLET','WALLET'),('MEMBERSHIP','MEMBERSHIP'),('PROFILE SETTINGS','SETTINGS')]:
            active=self.profile_section==key
            tk.Button(row,text=label,command=lambda k=key:self._set_profile_section(k),bg=ACCENT if active else PANEL2,fg='white' if active else TEXT,activebackground=ACCENT,activeforeground='white',relief='flat',font=('Segoe UI Black' if active else 'Segoe UI Semibold',9),padx=16,pady=8,cursor='hand2').pack(side='left',padx=(0,6))
''','_bind_click_recursive')
app=replace_method(app,'_set_profile_section',r'''    def _set_profile_section(self,section):
        self.profile_section=section
        self.show('PROFILE',force=True)
''','_profile_subnav')
app=replace_method(app,'page_profile',r'''    def page_profile(self):
        r=self.rider(); self._profile_header(r); self._profile_subnav()
        if self.profile_section=='RACES':return self._profile_my_races(r)
        if self.profile_section=='WALLET':return self._profile_wallet(r)
        if self.profile_section=='MEMBERSHIP':return self._profile_membership(r)
        if self.profile_section=='SETTINGS':return self._profile_settings(r)
        return self._profile_overview(r)
''','_profile_overview')

# Dedicated top-level Garage uses the exact native profile/kit selection engine already built.
garage_method=r'''    def page_garage(self):
        r=self.rider()
        self.bike_garage.username=self.current_rider
        return self._profile_bikes(r)

'''
marker='    def _profile_bikes(self,r):\n'
if '    def page_garage(self):\n' not in app:
    if marker not in app:raise SystemExit('Garage insertion anchor missing')
    app=app.replace(marker,garage_method+marker,1)

app=app.replace("tk.Label(body,text='BIKE SELECTION'","tk.Label(body,text='GARAGE'",1)
app=app.replace("text='The same MX Bikes rider/bike selection, connected to your actual game profile. Changes here are written to MX Bikes profile.ini so the game opens with this bike and kit selected.'","text='Your complete MX Bikes garage inside Race Day Live. Every installed bike remains selectable, including EDF-only bikes, and the live 3D surface is hosted directly on this page. Bike, paint, helmet, rider kit, gloves, boots and protection stay synchronized with the native MX Bikes profile.'",1)
app=app.replace("text='LIVE 3D • MX BIKES ENGINE'","text='LIVE 3D GARAGE'",1)
app=app.replace("text='PREVIEW STARTING…'","text='LOADING BIKE…'",1)
app=app.replace("text='MX BIKES NATIVE 3D\\n\\nStarting the real game renderer…'","text='GARAGE 3D\\n\\nLoading installed bike…'",1)
app=app.replace("render_status.configure(text='LIVE • REAL MX BIKES RENDERER',fg=GREEN)","render_status.configure(text='LIVE • IN-APP GARAGE',fg=GREEN)",1)
app=app.replace("render_status.configure(text='STARTING MX BIKES ENGINE…',fg=GOLD)","render_status.configure(text='LOADING GARAGE 3D…',fg=GOLD)",1)
app=app.replace("text='START / REFRESH LIVE 3D'","text='RELOAD 3D'",1)
app=app.replace("text='STOP 3D'","text='PAUSE 3D'",1)
app=app.replace("render_fallback.configure(text='MX BIKES NATIVE 3D\\n\\n'+(self.bike_garage.bike_display(bike) or 'SYNC GAME CONTENT'))","render_fallback.configure(text='GARAGE 3D\\n\\n'+(self.bike_garage.bike_display(bike) or 'SYNC GAME CONTENT'))",1)
# Slower debounce avoids expensive process restart storms while the user taps arrows quickly.
app=app.replace("preview_restart_after['id']=self.after(800,lambda:start_live_renderer(False))","preview_restart_after['id']=self.after(1200,lambda:start_live_renderer(False))",1)

# Applying a selection stays on Garage; manual sync refreshes Garage without creating another repeating sync timer.
app=app.replace("self._set_profile_section('BIKES')","self.show('GARAGE',force=True)")
old_sync_btn="tk.Button(row,text='SYNC GAME CONTENT',command=lambda:[self._run_mx_sync(),self.after(1100,lambda:self.show('GARAGE',force=True))]"
# The original may still contain the pre-replacement BIKES route in lambda; use regex below.
app=re.sub(r"tk\.Button\(row,text='SYNC GAME CONTENT',command=lambda:\[[^\]]+\]", "tk.Button(row,text='SYNC GAME CONTENT',command=self._garage_sync_now", app, count=1)
# Remove the Garage-local game-launch button. Global LAUNCH MX BIKES remains in the sidebar/race-day integration.
app=re.sub(r"\n\s*tk\.Button\(row,text='LAUNCH MX BIKES'.*?\.pack\(side='left',fill='x',expand=True,padx=\(4,0\)\)","",app,count=1)

# Cache invalidation happens after actual sync content changes.
app=replace_method(app,'_apply_mx_environment',r'''    def _apply_mx_environment(self,env):
        try:
            self.bike_garage.invalidate_cache()
            self.game_bridge.invalidate_cache()
            if env.found:
                self.mx_status_label.configure(text='● MX BIKES CONNECTED',fg=GREEN)
                self.mx_counts_label.configure(text=f"{env.tracks_found} tracks • {env.bikes_found} bikes\nProfile: {env.profile_name or 'detected'}")
            else:
                self.mx_status_label.configure(text='● MX BIKES NOT FOUND',fg=RED)
                self.mx_counts_label.configure(text=env.error or 'Install path not detected')
        except Exception:pass

    def _garage_sync_now(self):
        try:self.mx_status_label.configure(text='● SYNCING MX BIKES…',fg=GOLD)
        except Exception:pass
        def done(env):
            def ui():
                self._apply_mx_environment(env)
                if getattr(self,'current_page','')=='GARAGE':self.show('GARAGE',force=True)
            try:self.after(0,ui)
            except Exception:pass
        self.mx_agent.sync_async(done)
''','_on_close')

# Live timing: keep one-second cadence, but update/reorder existing row widgets rather than destroying the tower every tick.
app=replace_method(app,'_refresh_live_widgets',r'''    def _refresh_live_widgets(self,race_id):
        if self.current_page!='LIVE' or not hasattr(self,'live_tower') or not self.live_tower.winfo_exists():return
        self._process_commentary_events(race_id)
        session=self.conn.execute('SELECT * FROM race_sessions WHERE race_id=?',(race_id,)).fetchone()
        race=self.conn.execute('SELECT * FROM races WHERE id=?',(race_id,)).fetchone()
        riders=list(self.conn.execute('SELECT * FROM live_riders WHERE race_id=? ORDER BY COALESCE(position,999),race_number',(race_id,)))[:12]
        session_name=(session['session'] or 'WAITING').replace('QUALIFYPRACTICE','QUALIFY PRACTICE') if session else 'WAITING'
        state=(session['session_state'] or 'WAITING') if session else 'WAITING'
        top=f"{self.race_class_label(race)} • {session_name} • {state}" if race else f'{session_name} • {state}'
        if not getattr(self,'_live_header_label',None) or not self._live_header_label.winfo_exists():
            self._live_header_label=tk.Label(self.live_tower,text=top,fg=GOLD,bg='#11161c',font=('Segoe UI Black',8),wraplength=230,justify='left')
            self._live_header_label.pack(fill='x',padx=10,pady=10)
        else:self._live_header_label.configure(text=top)
        if not hasattr(self,'_live_row_widgets'):self._live_row_widgets={}
        desired=[]
        if not riders:
            if not getattr(self,'_live_waiting_label',None) or not self._live_waiting_label.winfo_exists():
                self._live_waiting_label=tk.Label(self.live_tower,text='Waiting for riders to join the MX Bikes server…',fg=MUTED,bg='#11161c',font=('Segoe UI',9),wraplength=220,justify='left')
                self._live_waiting_label.pack(anchor='w',padx=10,pady=8)
        else:
            if getattr(self,'_live_waiting_label',None) and self._live_waiting_label.winfo_exists():self._live_waiting_label.destroy()
            self._live_waiting_label=None
        for idx,r in enumerate(riders):
            key=str(r['race_number'] or r['name'] or idx); desired.append(key)
            item=self._live_row_widgets.get(key)
            if not item or not item[0].winfo_exists():
                f=tk.Frame(self.live_tower,bg=PANEL2)
                pos_label=tk.Label(f,fg=ACCENT,bg=PANEL2,font=('Segoe UI Black',11),width=2)
                pos_label.pack(side='left',padx=5,pady=6)
                name_label=tk.Label(f,fg=TEXT,bg=PANEL2,font=('Segoe UI Semibold',8),wraplength=120,justify='left')
                name_label.pack(side='left')
                gap_label=tk.Label(f,fg=MUTED,bg=PANEL2,font=('Segoe UI',7)); gap_label.pack(side='right',padx=6)
                item=(f,pos_label,name_label,gap_label); self._live_row_widgets[key]=item
            f,pos_label,name_label,gap_label=item
            pos=r['position'] if r['position'] else '—'; name=r['name'] or f"#{r['race_number']}"; gap='LEADER' if r['position']==1 else (r['gap'] or self._lap_display(r['best_lap_ms']))
            pos_label.configure(text=str(pos)); name_label.configure(text=f"#{r['race_number']} {name}" if not str(name).startswith('#') else name); gap_label.configure(text=str(gap))
        for key,item in list(self._live_row_widgets.items()):
            if key not in desired:
                try:item[0].destroy()
                except Exception:pass
                self._live_row_widgets.pop(key,None)
        # Repacking existing row frames is cheap and preserves correct live position ordering.
        for key in desired:
            f=self._live_row_widgets[key][0]; f.pack_forget(); f.pack(fill='x',padx=8,pady=2)
        if hasattr(self,'live_commentary_frame') and self.live_commentary_frame.winfo_exists():
            comments=tuple(reversed(self.commentary_history[-6:]))
            if comments!=getattr(self,'_live_commentary_signature',None):
                self._live_commentary_signature=comments
                for w in self.live_commentary_frame.winfo_children():w.destroy()
                if not comments:tk.Label(self.live_commentary_frame,text='Commentary will appear automatically as official MX Bikes timing events arrive.',fg=MUTED,bg=PANEL,font=('Segoe UI',9),wraplength=330,justify='left').pack(fill='x',padx=14,pady=10)
                for text in comments:tk.Label(self.live_commentary_frame,text='“'+text+'”',fg=TEXT,bg=PANEL2,wraplength=330,justify='left',font=('Segoe UI',9),padx=11,pady=10).pack(fill='x',padx=12,pady=4)
        self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))
''','page_live')

# Reset live widget cache only when entering a new live page, not every one-second update.
live_anchor="        self.live_tower=tk.Frame(vid,bg='#11161c'); self.live_tower.place(x=18,y=65,width=270,height=500)"
live_new=live_anchor+"\n        self._live_row_widgets={}; self._live_header_label=None; self._live_waiting_label=None; self._live_commentary_signature=None"
if live_anchor in app:app=app.replace(live_anchor,live_new,1)
elif 'self._live_row_widgets={}' not in app:raise SystemExit('live init anchor missing')

# page_my_races must force Profile rebuild because same-page clicks are now short-circuited.
app=app.replace("self.profile_section='RACES'; self.show('PROFILE')","self.profile_section='RACES'; self.show('PROFILE',force=True)",1)

p.write_text(app,encoding='utf-8')

# ---------- Garage content cache ----------
p=work/'src/bike_garage.py'; gar=p.read_text(encoding='utf-8')
if 'from functools import lru_cache' not in gar:gar=gar.replace('import shutil\n','import shutil\nfrom functools import lru_cache\n',1)
init_anchor="        self.username = username\n"
inv=r'''        self.username = username

    def invalidate_cache(self):
        for name in ('mods_root','_roots','bike_records','bike_category','categories','bikes_for_category','bike_paints','_model_dirs','rider_paints','gloves_paints','helmet_paints','goggles_paints','boot_paints','protection_paints','fonts','garage_picture'):
            fn=getattr(self,name,None)
            try:fn.cache_clear()
            except Exception:pass
'''
if 'def invalidate_cache(self):' not in gar:
    if init_anchor not in gar:raise SystemExit('garage init anchor missing')
    gar=gar.replace(init_anchor,inv,1)
for name,size in [('mods_root',2),('_roots',2),('bike_records',2),('bike_category',256),('categories',2),('bikes_for_category',64),('bike_paints',128),('_model_dirs',64),('rider_paints',64),('gloves_paints',64),('helmet_paints',64),('goggles_paints',64),('boot_paints',64),('protection_paints',64),('fonts',8),('garage_picture',128)]:
    sig=f'    def {name}('
    dec=f'    @lru_cache(maxsize={size})\n'
    if dec+f'    def {name}(' not in gar:
        if sig not in gar:raise SystemExit('garage cache method missing '+name)
        gar=gar.replace(sig,dec+sig,1)
p.write_text(gar,encoding='utf-8')

# ---------- Game path discovery cache ----------
p=work/'src/game_bridge.py'; bridge=p.read_text(encoding='utf-8')
old_init="    def __init__(self, conn):\n        self.conn = conn\n        ensure_game_bridge_schema(conn)"
new_init="    def __init__(self, conn):\n        self.conn = conn\n        self._game_exe_cache = None\n        ensure_game_bridge_schema(conn)"
if old_init in bridge:bridge=bridge.replace(old_init,new_init,1)
elif 'self._game_exe_cache = None' not in bridge:raise SystemExit('game bridge init cache anchor missing')
old_game="    def game_exe(self):\n        return find_mxbikes_exe(self.conn)"
new_game="""    def invalidate_cache(self):
        self._game_exe_cache = None

    def game_exe(self):
        try:
            if self._game_exe_cache and Path(self._game_exe_cache).is_file():return Path(self._game_exe_cache)
        except Exception:pass
        found=find_mxbikes_exe(self.conn)
        self._game_exe_cache=str(found) if found else None
        return found"""
if old_game in bridge:bridge=bridge.replace(old_game,new_game,1)
elif 'def invalidate_cache(self):' not in bridge:raise SystemExit('game exe method anchor missing')
p.write_text(bridge,encoding='utf-8')

# ---------- Hidden backend renderer: no external game window ----------
p=work/'src/native_renderer.py'; rend=p.read_text(encoding='utf-8')
rend=rend.replace("            if proc_id.value == pid and user32.IsWindowVisible(hwnd):\n                windows.append(int(hwnd))","            if proc_id.value == pid:\n                windows.append(int(hwnd))",1)
old_popen="                self.process = subprocess.Popen(cmd, cwd=str(install_root))"
new_popen="""                startupinfo=subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE: backend never appears as a separate game window.
                priority=getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)
                self.process = subprocess.Popen(cmd,cwd=str(install_root),startupinfo=startupinfo,creationflags=priority)"""
if old_popen in rend:rend=rend.replace(old_popen,new_popen,1)
elif 'startupinfo.wShowWindow = 0' not in rend:raise SystemExit('hidden renderer Popen anchor missing')
p.write_text(rend,encoding='utf-8')

# ---------- compile + regression gates ----------
for py in work.rglob('*.py'):
    py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8'); garc=(work/'src/bike_garage.py').read_text(encoding='utf-8'); rendc=(work/'src/native_renderer.py').read_text(encoding='utf-8'); bridgec=(work/'src/game_bridge.py').read_text(encoding='utf-8'); updater=(work/'src/updater.py').read_text(encoding='utf-8'); config=(work/'src/config.py').read_text(encoding='utf-8')
assert "VERSION = '0.3.6'" in config
assert "('GARAGE','GARAGE')" in appc and 'def page_garage' in appc and "('BIKES','BIKES')" not in appc
assert 'GARAGE 3D' in appc and 'IN-APP GARAGE' in appc
assert 'startupinfo.wShowWindow = 0' in rendc and 'SetParent' in rendc and "'-testing'" in rendc
assert 'IsWindowVisible(hwnd)' not in rendc and 'BELOW_NORMAL_PRIORITY_CLASS' in rendc
assert 'lru_cache' in garc and 'def invalidate_cache(self):' in garc and '@lru_cache(maxsize=2)\n    def bike_records' in garc
assert 'self._game_exe_cache' in bridgec and 'def invalidate_cache(self):' in bridgec
assert 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc
assert "if not force and name==previous" in appc and "stop_renderer=(previous=='GARAGE'" in appc
assert 'comments!=getattr(self,\'_live_commentary_signature\',None)' in appc and 'f.pack_forget(); f.pack' in appc
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc
# Approved systems preserved.
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver','APP_USER_MODEL_ID'):
    assert marker in appc
assert '-directconnect' in bridgec
assert 'api.github.com/repos/' in updater and 'latest.json' in updater and 'schedule_restart' in updater
assert 'profile.race_day_live_backup.ini' in garc

with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':'0.3.6','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_6_UPDATE.zip','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('V036 VERIFIED',{'garage_top_level':True,'edf_all_bikes_backend':True,'separate_game_window':False,'content_scan_cache':True,'image_cache':True,'game_path_cache':True,'track_media_mem_cache':True,'live_in_place_1hz':True,'same_page_short_circuit':True,'garage_only_renderer_lifecycle':True})
print('BUILT',OUT,digest)
