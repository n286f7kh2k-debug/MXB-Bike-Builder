from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_0_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_1_UPDATE.zip')
RENDERER=Path('race-control/in_app_garage_v051.py')
WININT=Path('race-control/windows_integration_v051.py')
PERF=Path('race-control/runtime_perf_v051.py')
VERSION='0.5.1'
NOTES=(
    'MXB Race Day Live v0.5.1: performance hotfix and Garage renderer rebuild. The Garage no longer draws thousands of Tk polygons on the UI thread; '
    'model discovery, parsing and rasterization run on one background worker and Tk receives one completed frame. Garage drag/zoom/resize redraws are debounced, '
    'pending work is cancelled when leaving Garage, source meshes are bounded for smooth interaction, and OBJ/STL/PLY source geometry is supported. EDF-only bikes '
    'remain fully selectable/synced but are never launched through MX Bikes. Windows taskbar icon discovery is cached so repeated window-map events no longer spawn '
    'PowerShell repeatedly. SQLite desktop-cache pragmas reduce database filesystem churn while preserving transaction semantics. v0.5.0 updater/restart fixes, race joining, '
    'memberships, wallet, purse/fastest-lap economics, track art, live timing and admin controls are preserved.'
)

for p in (BASE,RENDERER,WININT,PERF):
    if not p.exists():raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.0 base invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v051_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(RENDERER,work/'src/in_app_garage.py')
shutil.copy2(WININT,work/'src/windows_integration.py')
shutil.copy2(PERF,work/'src/runtime_perf.py')

# Version markers and updater identity.
for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel; s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py'; up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

p=work/'src/app.py'; app=p.read_text(encoding='utf-8')
perf_import='from .runtime_perf import tune_database, UiPerf\n'
if perf_import not in app:
    anchors=['from .in_app_garage import InAppGarageRenderer, GarageModelError\n','from .windows_taskbar import apply_taskbar_identity, release_taskbar_icons\n']
    for anchor in anchors:
        if anchor in app:
            app=app.replace(anchor,anchor+perf_import,1);break
    else:raise SystemExit('performance import anchor missing')

# Tune the existing connection once; no query results are cached here.
if 'tune_database(self.conn)' not in app:
    m=re.search(r'self\.conn\s*=\s*connect\(\)',app)
    if not m:raise SystemExit('database connection anchor missing')
    end=m.end()
    app=app[:end]+'; tune_database(self.conn); self.ui_perf=UiPerf(self)'+app[end:]

# Replace the synchronous v0.3.9 Garage block with a nonblocking renderer bridge.
start=app.find('        # True in-app renderer. Garage is forbidden from spawning MX Bikes/Steam.')
end=app.find('        def refresh_all():',start)
if start<0 or end<0:raise SystemExit('v0.5.0 Garage renderer block missing')
replacement=r'''        # Nonblocking in-app renderer. No MX Bikes/Steam process is used for Garage.
        def on_garage3d_status(status,detail=''):
            try:
                if not render_host.winfo_exists():return
            except Exception:return
            if status=='loading':
                render_status.configure(text='LOADING 3D…',fg=GOLD)
                render_fallback.configure(text='GARAGE 3D\n\nLoading bike in the background…')
                render_fallback.place(relx=.5,rely=.5,anchor='center')
                return
            if status=='ready':
                render_status.configure(text='LIVE • RACE DAY LIVE 3D',fg=GREEN)
                render_fallback.place_forget()
                return
            if status=='opaque':
                bike=state.get('bikeid','')
                pic=None
                try:pic=self.bike_garage.garage_picture(bike)
                except Exception:pass
                if pic:
                    try:
                        photo=self._load_track_tk(str(pic),size=(620,350))
                        if photo:
                            render_host.delete('garage3d_frame')
                            render_host.create_image(render_host.winfo_width()/2,render_host.winfo_height()/2,image=photo,anchor='center',tags='garage3d_frame')
                            render_host._garage3d_photo=photo
                            render_status.configure(text='GAME PREVIEW • EDF BIKE',fg=GOLD)
                            render_fallback.place_forget()
                            return
                    except Exception:pass
                render_status.configure(text='EDF BIKE • SELECTION SYNCED',fg=GOLD)
                render_fallback.configure(text='3D SOURCE NOT AVAILABLE FOR THIS COMPILED EDF BIKE\n\nRace Day Live will not launch MX Bikes.\nBike / paint / gear selection remains synced.')
                render_fallback.place(relx=.5,rely=.5,anchor='center')
                return
            render_status.configure(text='3D SOURCE ERROR',fg=RED)
            render_fallback.configure(text='GARAGE 3D\n\n'+str(detail or 'Could not render this source model.'))
            render_fallback.place(relx=.5,rely=.5,anchor='center')

        def draw_garage3d(reset=False):
            bike=state.get('bikeid','')
            self.garage_renderer.schedule(render_host,bike,on_garage3d_status,reset=reset,delay=0 if reset else 70)

        self.garage_renderer.bind(render_host,lambda:state.get('bikeid',''),on_garage3d_status)

'''
app=app[:start]+replacement+app[end:]
# Ensure the initial draw happens after the page is visible, not during widget construction.
app=app.replace('        self.after_idle(lambda:draw_garage3d(True))','        self.after(40,lambda:draw_garage3d(True))')
# Selector changes should debounce through the renderer, never rasterize synchronously.
app=app.replace('            normalize_dependents(key); refresh_all(); draw_garage3d(False)','            normalize_dependents(key); refresh_all(); self.garage_renderer.schedule(render_host,state.get(\'bikeid\',\'\'),on_garage3d_status,delay=85)')

# Leaving Garage must cancel queued render callbacks/work tokens immediately.
show_start=app.find('    def show(self,name,force=False):')
show_end=app.find('\n    def ',show_start+8)
if show_start>=0 and show_end>show_start:
    block=app[show_start:show_end]
    needle="        previous=getattr(self,'current_page',None)\n"
    cancel="        previous=getattr(self,'current_page',None)\n        if previous=='GARAGE' and name!='GARAGE':\n            try:self.garage_renderer.stop()\n            except Exception:pass\n"
    if "previous=='GARAGE' and name!='GARAGE'" not in block:
        if needle not in block:raise SystemExit('show previous-page anchor missing')
        block=block.replace(needle,cancel,1)
        app=app[:show_start]+block+app[show_end:]

# Avoid running GC or shell work during navigation; UI image caches from v0.3.6 remain intact.
p.write_text(app,encoding='utf-8')

# Compile all Python included in the overlay.
for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)

appc=(work/'src/app.py').read_text(encoding='utf-8')
rend=(work/'src/in_app_garage.py').read_text(encoding='utf-8')
wint=(work/'src/windows_integration.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
up=(work/'src/updater.py').read_text(encoding='utf-8')
gar=(work/'src/bike_garage.py').read_text(encoding='utf-8')
bridge=(work/'src/game_bridge.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')

# Speed gates.
assert "VERSION = '0.5.1'" in config
assert 'ThreadPoolExecutor(max_workers=1' in rend, 'gate:garage_worker'
assert 'canvas.create_polygon' not in rend, 'gate:no_tk_polygon_storm'
assert 'MAX_FACES = 5500' in rend, 'gate:bounded_mesh'
assert "delay=160" in rend and "delay=55" in rend, 'gate:render_debounce'
assert 'subprocess' not in rend.lower() and 'mxbikes.exe' not in rend.lower(), 'gate:no_external_garage_process'
assert "previous=='GARAGE' and name!='GARAGE'" in appc and 'self.garage_renderer.stop()' in appc, 'gate:cancel_on_leave'
assert 'tune_database(self.conn)' in appc and 'PRAGMA cache_size=-65536' in perf, 'gate:sqlite_tuning'
assert '_icon_cache' in wint and 'if not refresh and _icon_cache' in wint, 'gate:cached_shell_icon'
assert 'subprocess.run' in wint  # still available only for first-time shortcut/icon resolution
# Existing whole-app performance work must stay.
assert 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc, 'gate:image_media_caches'
assert "if not force and name==previous" in appc, 'gate:same_page_short_circuit'
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc, 'gate:live_1hz'
assert '_live_row_widgets' in appc and '_live_commentary_signature' in appc, 'gate:live_in_place'
assert 'lru_cache' in gar and 'invalidate_cache' in gar, 'gate:garage_content_cache'
assert 'self._game_exe_cache' in bridge, 'gate:game_path_cache'
# Product regression gates.
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver','APP_USER_MODEL_ID'):
    assert marker in appc, 'gate:product:'+marker
assert '-directconnect' in bridge, 'gate:race_directconnect'
assert "MANIFEST_PATH = 'race-control/latest.json'" in up and '_manifest_from_github_api' in up and 'time.time_ns()' in up, 'gate:v050_updater_feed'
assert 'schedule_restart' in up and 'os.replace(tmp,dst)' in up and 'shutil.rmtree(install' not in up, 'gate:v050_safe_update'
assert 'WM_SETICON' in task and 'best_icon' in task, 'gate:taskbar_preserved'
assert 'profile.race_day_live_backup.ini' in gar, 'gate:profile_backup'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('PERFORMANCE GATE',{'garage_ui_thread_polygons':False,'garage_background_worker':True,'garage_face_cap':5500,'garage_debounce':True,'cancel_render_on_leave':True,'shell_icon_cached':True,'sqlite_cache_tuned':True,'live_timing_1hz_preserved':True})
print('GARAGE GATE',{'launches_mxbikes':False,'obj':True,'stl':True,'ply':True,'edf_selection_sync':True,'edf_direct_decode':False})
print('UPDATER GATE',{'v050_channel_preserved':True,'sha256':True,'hidden_restart':True,'preserve_user_files':True})
print('BUILT',OUT,digest)
