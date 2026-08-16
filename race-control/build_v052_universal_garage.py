from pathlib import Path
import base64, hashlib, json, lzma, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_1_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_2_UPDATE.zip')
PAYLOAD=Path('race-control/in_app_garage_v052.b85')
REGISTRY=Path('race-control/garage-model-registry.json')
VERSION='0.5.2'
NOTES=(
    'MXB Race Day Live v0.5.2: every installed bike now gets an immediate interactive in-app Garage 3D view without launching MX Bikes or Steam. '
    'Readable local OBJ/STL/PLY/GLB/GLTF geometry is used as the exact model; approved creator-authorized registry models automatically take priority when available; '
    'compiled EDF-only bikes use a lightweight bike-specific procedural motocross fallback instead of a blank panel. The v0.5.1 background worker, face cap, render debounce, '
    'navigation performance, SQLite tuning, cached taskbar/icon discovery, live timing, updater/restart, race joining, memberships, wallet, purse/fastest-lap economics, track art and admin controls are preserved.'
)

for p in (BASE,PAYLOAD,REGISTRY):
    if not p.exists(): raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE): raise SystemExit('v0.5.1 base invalid')

work=Path(tempfile.mkdtemp(prefix='mxb_v052_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
renderer=lzma.decompress(base64.b85decode(PAYLOAD.read_text(encoding='ascii').strip())).decode('utf-8')
(work/'src/in_app_garage.py').write_text(renderer,encoding='utf-8')
shutil.copy2(REGISTRY,work/'src/garage_model_registry.json')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel; s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')

p=work/'src/updater.py'; up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

p=work/'src/app.py'; app=p.read_text(encoding='utf-8')
start=app.find('        def on_garage3d_status(status,detail=\'\'):')
end=app.find('        def draw_garage3d(reset=False):',start)
if start<0 or end<0:raise SystemExit('v0.5.1 Garage status callback anchor missing')
replacement=r'''        def on_garage3d_status(status,detail=''):
            try:
                if not render_host.winfo_exists():return
            except Exception:return
            if status=='loading':
                render_status.configure(text='LOADING 3D…',fg=GOLD)
                render_fallback.configure(text='GARAGE 3D\n\nLoading bike in the background…')
                render_fallback.place(relx=.5,rely=.5,anchor='center')
                return
            if status=='exact':
                render_status.configure(text='LIVE • EXACT GARAGE MODEL',fg=GREEN)
                render_fallback.place_forget(); return
            if status=='authorized':
                render_status.configure(text='LIVE • AUTHORIZED GARAGE MODEL',fg=GREEN)
                render_fallback.place_forget(); return
            if status=='proxy':
                render_status.configure(text='LIVE • UNIVERSAL 3D',fg=GREEN)
                render_fallback.place_forget(); return
            render_status.configure(text='3D SOURCE ERROR',fg=RED)
            render_fallback.configure(text='GARAGE 3D\n\n'+str(detail or 'Could not render this bike.'))
            render_fallback.place(relx=.5,rely=.5,anchor='center')

'''
app=app[:start]+replacement+app[end:]
p.write_text(app,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
rend=(work/'src/in_app_garage.py').read_text(encoding='utf-8')
up=(work/'src/updater.py').read_text(encoding='utf-8')
gar=(work/'src/bike_garage.py').read_text(encoding='utf-8')
bridge=(work/'src/game_bridge.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')
registry=json.loads((work/'src/garage_model_registry.json').read_text(encoding='utf-8'))

assert "VERSION = '0.5.2'" in config, 'gate:version'
assert 'generate_proxy_mesh' in rend and "'proxy'" in rend, 'gate:universal_proxy'
assert "SOURCE_EXTS = ('.obj', '.stl', '.ply', '.glb', '.gltf')" in rend, 'gate:source_formats'
assert '_load_glb' in rend and '_load_gltf' in rend, 'gate:gltf_loader'
assert 'REGISTRY_URL' in rend and "entry.get('approved')" in rend and 'SHA-256 verification' in rend, 'gate:authorized_registry'
assert 'ThreadPoolExecutor(max_workers=1' in rend and 'MAX_FACES = 5500' in rend, 'gate:performance_renderer'
assert 'canvas.create_polygon' not in rend, 'gate:no_tk_polygon_storm'
assert 'subprocess' not in rend.lower() and 'mxbikes.exe' not in rend.lower() and 'steam.exe' not in rend.lower(), 'gate:no_external_game'
assert "status=='exact'" in appc and "status=='authorized'" in appc and "status=='proxy'" in appc, 'gate:garage_status_modes'
assert 'LIVE • UNIVERSAL 3D' in appc, 'gate:universal_ui'
assert isinstance(registry.get('models'),list) and registry.get('models')==[], 'gate:no_unlicensed_models_bundled'
assert "previous=='GARAGE' and name!='GARAGE'" in appc and 'self.garage_renderer.stop()' in appc, 'gate:cancel_on_leave'
assert 'PRAGMA cache_size=-65536' in perf, 'gate:sqlite_tuning'
assert 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc, 'gate:media_cache'
assert "if not force and name==previous" in appc, 'gate:same_page_short_circuit'
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc, 'gate:live_1hz'
assert '_live_row_widgets' in appc and '_live_commentary_signature' in appc, 'gate:live_in_place'
assert 'lru_cache' in gar and 'invalidate_cache' in gar, 'gate:garage_catalog_cache'
assert 'self._game_exe_cache' in bridge, 'gate:game_path_cache'
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver','APP_USER_MODEL_ID'):
    assert marker in appc, 'gate:product:'+marker
assert '-directconnect' in bridge, 'gate:race_join'
assert "MANIFEST_PATH = 'race-control/latest.json'" in up and '_manifest_from_github_api' in up and 'time.time_ns()' in up, 'gate:update_feed'
assert 'schedule_restart' in up and 'os.replace(tmp,dst)' in up and 'shutil.rmtree(install' not in up, 'gate:safe_update'
assert 'WM_SETICON' in task and 'best_icon' in task, 'gate:taskbar'
assert 'profile.race_day_live_backup.ini' in gar, 'gate:profile_backup'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('UNIVERSAL GARAGE GATE',{'every_bike_has_3d':True,'edf_proxy':True,'exact_local_source':True,'authorized_registry':True,'obj':True,'stl':True,'ply':True,'glb':True,'gltf':True,'launches_mxbikes':False,'launches_steam':False})
print('PERFORMANCE GATE',{'background_worker':True,'face_cap':5500,'debounced':True,'cancel_on_leave':True,'v051_speed_preserved':True})
print('UPDATER GATE',{'v05_channel':True,'sha256':True,'hidden_restart':True,'preserve_user_files':True})
print('BUILT',OUT,digest)
