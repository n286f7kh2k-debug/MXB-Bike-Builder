from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_2_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_3_UPDATE.zip')
WININT=Path('race-control/windows_integration_v053.py')
TASKBAR=Path('race-control/windows_taskbar_v053.py')
VERSION='0.5.3'
NOTES=(
    'MXB Race Day Live v0.5.3: fixes Windows taskbar identity at the launcher and HWND levels. The desktop shortcut is migrated from WScript/VBS primary launching to direct pythonw/app.py launching while preserving its configured IconLocation; icon resource indexes are preserved; EXE/DLL icon resources are loaded with ExtractIconExW; Explorer shortcut icons are a fallback; the process AppUserModelID is set before the Tk app imports; and WM_SETICON/class icons are applied to the actual top-level window. v0.5.2 universal Garage, v0.5.1 performance fixes, updater/restart, race joining, memberships, wallet, purse/fastest-lap economics, track art, live timing and admin controls are preserved.'
)

for p in (BASE,WININT,TASKBAR):
    if not p.exists(): raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE): raise SystemExit('v0.5.2 base invalid')

work=Path(tempfile.mkdtemp(prefix='mxb_v053_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(WININT,work/'src/windows_integration.py')
shutil.copy2(TASKBAR,work/'src/windows_taskbar.py')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel; s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')

p=work/'src/updater.py'; up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

p=work/'src/app.py'; app=p.read_text(encoding='utf-8')
app,n=re.subn(r"APP_USER_MODEL_ID\s*=\s*['\"]MXBRaceDayLive\.Desktop(?:\.v\d+)?['\"]",
              "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v4'",app,count=1)
if n!=1 and "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v4'" not in app:
    raise SystemExit('AppUserModelID anchor missing')
p.write_text(app,encoding='utf-8')

p=work/'app.py'; root=p.read_text(encoding='utf-8')
startup=r'''# MXB Race Day Live Windows shell identity: must run before Tk creates the taskbar button.
try:
    from pathlib import Path as _RDLPath
    from src.windows_taskbar import set_process_app_id as _rdl_set_process_app_id
    from src.windows_integration import ensure_desktop_shortcut as _rdl_ensure_desktop_shortcut
    _rdl_set_process_app_id()
    _rdl_ensure_desktop_shortcut(_RDLPath(__file__).resolve().parent)
except Exception:
    pass

'''
if '_rdl_set_process_app_id' not in root:
    root=startup+root
p.write_text(root,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)

appc=(work/'src/app.py').read_text(encoding='utf-8')
rootc=(work/'app.py').read_text(encoding='utf-8')
wint=(work/'src/windows_integration.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
rend=(work/'src/in_app_garage.py').read_text(encoding='utf-8')
up=(work/'src/updater.py').read_text(encoding='utf-8')
gar=(work/'src/bike_garage.py').read_text(encoding='utf-8')
bridge=(work/'src/game_bridge.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')

assert "VERSION = '0.5.3'" in config, 'gate:version'
assert "APP_ID='MXBRaceDayLive.Desktop.v4'" in wint, 'gate:integration_app_id_v4'
assert "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v4'" in appc, 'gate:app_id_v4'
assert 'shortcut_icon_spec' in wint and "get('icon')" in wint, 'gate:preserve_iconlocation_index'
assert "root/'.venv'/'Scripts'/'pythonw.exe'" in wint and 'root / "app.py"' in wint, 'gate:direct_pythonw_launcher'
assert "'wscript.exe'" in wint and 'Start MXB Race Day Live.vbs' in wint, 'gate:wscript_fallback_only'
assert '_rdl_set_process_app_id()' in rootc and '_rdl_ensure_desktop_shortcut' in rootc, 'gate:identity_before_tk'
assert 'ExtractIconExW' in task and '_split_spec' in task, 'gate:exe_dll_icon_resource'
assert 'SHGetFileInfoW' in task and '_load_from_shortcut' in task, 'gate:explorer_shortcut_fallback'
for marker in ('WM_SETICON','ICON_BIG','ICON_SMALL','SetClassLongPtrW','RedrawWindow','SetCurrentProcessExplicitAppUserModelID'):
    assert marker in task, 'gate:hwnd:'+marker
assert 'apply_taskbar_identity' in appc and '_apply_windows_taskbar_icon' in appc, 'gate:hwnd_apply_from_app'
assert "self.bind('<Map>'" in appc or "bind('<Map>'" in appc, 'gate:map_reapply'

assert 'generate_proxy_mesh' in rend and "'proxy'" in rend, 'gate:universal_garage'
assert all(ext in rend for ext in ("'.obj'","'.stl'","'.ply'","'.glb'","'.gltf'")), 'gate:garage_formats'
assert 'ThreadPoolExecutor(max_workers=1' in rend and 'MAX_FACES = 5500' in rend, 'gate:garage_perf'
assert 'subprocess' not in rend.lower() and 'mxbikes.exe' not in rend.lower() and 'steam.exe' not in rend.lower(), 'gate:no_game_from_garage'
assert "status=='proxy'" in appc and 'LIVE • UNIVERSAL 3D' in appc, 'gate:garage_ui'
assert "previous=='GARAGE' and name!='GARAGE'" in appc and 'self.garage_renderer.stop()' in appc, 'gate:cancel_garage_on_leave'
assert 'PRAGMA cache_size=-65536' in perf, 'gate:sqlite_perf'
assert 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc, 'gate:media_caches'
assert "if not force and name==previous" in appc, 'gate:navigation_short_circuit'
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc, 'gate:live_1hz'
assert '_live_row_widgets' in appc and '_live_commentary_signature' in appc, 'gate:live_in_place'
assert 'lru_cache' in gar and 'invalidate_cache' in gar, 'gate:garage_catalog_cache'
assert 'self._game_exe_cache' in bridge, 'gate:game_path_cache'

for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver'):
    assert marker in appc, 'gate:product:'+marker
assert '-directconnect' in bridge, 'gate:race_join'
assert "MANIFEST_PATH = 'race-control/latest.json'" in up and '_manifest_from_github_api' in up and 'time.time_ns()' in up, 'gate:update_feed'
assert 'schedule_restart' in up and 'os.replace(tmp,dst)' in up and 'shutil.rmtree(install' not in up, 'gate:safe_update'
assert 'profile.race_day_live_backup.ini' in gar, 'gate:profile_backup'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('TASKBAR GATE',{'app_id_before_tk':True,'direct_pythonw_shortcut':True,'preserve_icon_resource_index':True,'extract_exe_dll_icon':True,'explorer_shortcut_fallback':True,'wm_seticon_big_small':True,'class_icons':True,'map_reapply':True})
print('GARAGE/PERF GATE',{'universal_3d_preserved':True,'no_game_launch':True,'background_worker':True,'cancel_on_leave':True,'v051_speed_preserved':True})
print('UPDATER GATE',{'v05_channel':True,'sha256':True,'hidden_restart':True,'preserve_user_files':True})
print('BUILT',OUT,digest)
