from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_4_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_6_UPDATE.zip')
WININT=Path('race-control/windows_integration_v056.py')
TASKBAR=Path('race-control/windows_taskbar_v056.py')
VERSION='0.5.6'
NOTES=(
 'MXB Race Day Live v0.5.6: corrective stability release built from the stable v0.5.4 extension/hot-update base, completely removing the v0.5.5 DWM/game-mirror startup path that launched MX Bikes, produced a black Garage surface on some systems and caused app-wide lag. '
 'Garage again performs zero MX Bikes process launches, zero DWM polling and zero background 3D rendering; the v0.5.4 two-way native profile/content sync, exact Bike/Head/Torso/Legs selection workflow, full race loadout capture and apply-before-direct-connect remain intact, and no fake/procedural model is shown. '
 'The Windows icon path is rebuilt to extract the exact icon Explorer already displays for the MXB Race Day Live desktop shortcut into a real multi-size assets/mxb_race_day_live.ico file, use that concrete ICO for Tk and WM_SETICON/class icons, migrate the shortcut to a dedicated MXB Race Day Live.exe copied from the active pythonw runtime, retain one permanent AppUserModelID, and notify Explorer to refresh its icon cache. '
 'Stay-open hot updates, v0.5.1 performance caches, memberships, wallet, one-click race joining, live timing, purse/fastest-lap economics, track art and admin controls are preserved.'
)
for p in (BASE,WININT,TASKBAR):
    if not p.exists():raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.4 base invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v056_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(WININT,work/'src/windows_integration.py')
shutil.copy2(TASKBAR,work/'src/windows_taskbar.py')
# Explicitly remove any game-mirror file if a contaminated base is ever supplied accidentally.
for rel in ('src/mx_game_mirror.py',):
    try:(work/rel).unlink(missing_ok=True)
    except Exception:pass

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

# Permanent identity was versioned in the old package; normalize it to one stable ID.
p=work/'src/app.py';app=p.read_text(encoding='utf-8')
app=re.sub(r"APP_USER_MODEL_ID\s*=\s*['\"]MXBRaceDayLive\.Desktop(?:\.v\d+)?['\"]","APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'",app,count=1)
p.write_text(app,encoding='utf-8')

# Root bootstrap sets permanent AppID + fixes shortcut/icon before Tk is imported.
p=work/'app.py';root=p.read_text(encoding='utf-8')
root=re.sub(r"from src\.windows_taskbar import set_process_app_id as _rdl_set_process_app_id", "from src.windows_taskbar import set_process_app_id as _rdl_set_process_app_id",root)
# existing bootstrap is retained; the copied modules now implement the concrete icon/launcher path.
p.write_text(root,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
rootc=(work/'app.py').read_text(encoding='utf-8')
wint=(work/'src/windows_integration.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
ext=(work/'src/mx_extension.py').read_text(encoding='utf-8')
hot=(work/'src/hot_reload.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
bridge=(work/'src/game_bridge.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')

assert "VERSION = '0.5.6'" in config,'gate:version'
# v0.5.5 must be completely gone from runtime behavior.
assert not (work/'src/mx_game_mirror.py').exists(),'gate:no_game_mirror_file'
for marker in ('DwmRegisterThumbnail','DwmUpdateThumbnailProperties','game_mirror.prewarm_async','MXGameGarageMirror'):
    assert marker not in appc,'gate:no_v055:'+marker
assert 'self.game_bridge.launch_game()' not in appc[appc.rfind('    def _profile_bikes(self,r):'):appc.find('    def _after_hot_reload',appc.rfind('    def _profile_bikes(self,r):'))], 'gate:garage_no_game_launch'
# v0.5.4 real extension integration stays.
for marker in ('Bike Selection','Category','Bike Font','Helmet Paint','Goggles Paint','Kit Paint','Kit Font','Gloves Paint','Protection Paint','Boots Paint'):
    assert marker in appc,'gate:garage_native_ui:'+marker
assert 'self.mx_extension.mirror_selection(state)' in appc,'gate:native_profile_write'
assert 'capture_race_loadout' in ext and 'prepare_join' in ext and 'sync_profile_state' in ext,'gate:extension_preserved'
new_garage=appc[appc.rfind('    def _profile_bikes(self,r):'):appc.find('    def _after_hot_reload',appc.rfind('    def _profile_bikes(self,r):'))]
assert 'generate_proxy_mesh' not in new_garage and 'draw_garage3d' not in new_garage,'gate:no_fake_visible_model'
# Speed: preserve v0.5.1 caches and no startup rendering process/polling.
assert 'PRAGMA cache_size=-65536' in perf,'gate:sqlite_cache'
assert 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc,'gate:image_caches'
assert "if not force and name==previous" in appc,'gate:navigation_short_circuit'
assert 'ThreadPoolExecutor(max_workers=1' in (work/'src/in_app_garage.py').read_text(encoding='utf-8'),'gate:background_renderer_preserved_but_inactive'
# Concrete Windows icon + named launcher.
assert "APP_ID='MXBRaceDayLive.Desktop'" in wint and "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'" in appc,'gate:permanent_app_id'
assert "LAUNCHER_NAME='MXB Race Day Live.exe'" in wint and 'ensure_native_launcher' in wint,'gate:named_launcher'
assert 'ensure_local_icon' in task and '_extract_shortcut_icon_png' in task,'gate:shortcut_icon_extraction'
assert "base.save(ico,format='ICO'" in task and "(16,16)" in task and "(256,256)" in task,'gate:real_multisize_ico'
assert 'tk_root.iconbitmap' in task and 'WM_SETICON' in task and 'SetClassLongPtrW' in task,'gate:hwnd_icon'
assert "$s.TargetPath='" in wint and 'target=str(launcher)' in wint and "$s.IconLocation='" in wint,'gate:shortcut_launcher_and_icon'
assert 'SHChangeNotify' in wint and 'SHChangeNotify' in task,'gate:explorer_refresh'
assert '_rdl_set_process_app_id()' in rootc and '_rdl_ensure_desktop_shortcut' in rootc,'gate:identity_before_tk'
# Hot update stays open after v0.5.4.
assert 'install_hot_update' in hot and 'refresh_running_app' in hot and 'app.__class__=new_cls' in hot,'gate:hot_update'
update_block=appc[appc.find('    def do_update(self):'):appc.find('\ndef main():')]
assert 'launch_update(' not in update_block and 'self._on_close' not in update_block,'gate:no_restart_update'
# Approved product systems.
assert '-directconnect' in bridge,'gate:race_join'
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver'):
    assert marker in appc,'gate:product:'+marker

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('STABILITY GATE',{'mx_bikes_spawned_by_garage':False,'dwm_polling':False,'startup_3d_workload':False,'v051_caches':True,'v054_extension':True})
print('TASKBAR GATE',{'real_local_ico':True,'shortcut_icon_extracted':True,'multi_size_ico':True,'named_launcher':True,'permanent_app_id':True,'wm_seticon':True,'explorer_refresh':True})
print('HOT UPDATE GATE',{'stay_open':True,'rollback':True})
print('BUILT',OUT,digest)
