from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_5_13_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_14_UPDATE.zip')
WININT = Path('race-control/windows_integration_v0511.py')
TASKBAR = Path('race-control/windows_taskbar_v056.py')
LAUNCHER_SRC = Path('race-control/launcher/rdl_launcher.py')
LAUNCHER = Path('race-control/staging/MXB Race Day Live.exe')
ICON = Path('race-control/staging/rdl-launcher.ico')
VERSION = '0.5.14'
NOTES = (
    'MXB Race Day Live v0.5.14 is a startup recovery release for the v0.5.13 host regression. '
    'It preserves the v0.5.13 profile-first race-night UI and all app data/features, but restores the last known-good external pythonw launch model so cold launches work again. '
    'The recovery launcher strips inherited PyInstaller _PYI_/PYINSTALLER environment state before starting the app runtime, preventing the parent-process executable security validation failure seen immediately after v0.5.13. '
    'The in-process host that produced the tkinter ttk/messagebox/filedialog import failure is removed. Stable AppUserModelID/window icon handling from the earlier working shell integration is restored. '
    'Garage/model rendering changes are intentionally not included in this emergency recovery release.'
)

for p in (BASE, WININT, TASKBAR, LAUNCHER_SRC, LAUNCHER, ICON):
    if not p.exists():
        raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):
    raise SystemExit('v0.5.13 base missing/invalid')
if LAUNCHER.read_bytes()[:2] != b'MZ':
    raise SystemExit('recovery launcher is not a Windows PE executable')

work = Path(tempfile.mkdtemp(prefix='mxb_v0514_recovery_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

for rel, var in [('src/config.py', 'VERSION'), ('src/__init__.py', '__version__')]:
    p = work / rel
    text = p.read_text(encoding='utf-8')
    text, n = re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]", f"{var} = '{VERSION}'", text, count=1)
    if n != 1:
        raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(text, encoding='utf-8')

p = work / 'src' / 'updater.py'
text = p.read_text(encoding='utf-8')
text = re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+', f'MXB-Race-Day-Live-Updater/{VERSION}', text)
p.write_text(text, encoding='utf-8')

# Keep the v0.5.13 UI/features; replace only the broken Windows host/shell layer.
shutil.copy2(WININT, work / 'src' / 'windows_integration.py')
shutil.copy2(TASKBAR, work / 'src' / 'windows_taskbar.py')
(work / 'assets' / 'bin').mkdir(parents=True, exist_ok=True)
shutil.copy2(LAUNCHER, work / 'assets' / 'bin' / 'MXB Race Day Live.exe')
(work / 'assets').mkdir(parents=True, exist_ok=True)
shutil.copy2(ICON, work / 'assets' / 'mxb_race_day_live.ico')

# Retire the v0.5.13 automatic native-host transition. It is no longer part of the design.
p = work / 'src' / 'app.py'
app = p.read_text(encoding='utf-8')
app = app.replace("        # v0.5.13 native host transition: eliminate the pythonw-owned app window.\n        if str(target_version).strip()=='0.5.13':\n            try:\n                from .windows_integration import ensure_desktop_shortcut as _rdl_link, restart_into_native_host as _rdl_restart\n                _rdl_root=Path(__file__).resolve().parent.parent\n                _rdl_link(_rdl_root)\n                self.after(1400,lambda r=_rdl_root:_rdl_restart(r,self,50))\n            except Exception:pass\n", '', 1)
# Restore stable process AppUserModelID for the pythonw-owned Tk process.
app = re.sub(r"APP_USER_MODEL_ID\s*=\s*['\"][^'\"]*['\"]", "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'", app, count=1)
p.write_text(app, encoding='utf-8')

for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

launch_src = LAUNCHER_SRC.read_text(encoding='utf-8')
app = (work / 'src' / 'app.py').read_text(encoding='utf-8')
wint = (work / 'src' / 'windows_integration.py').read_text(encoding='utf-8')
task = (work / 'src' / 'windows_taskbar.py').read_text(encoding='utf-8')
ui = (work / 'src' / 'profile_first_ui.py').read_text(encoding='utf-8')

assert "VERSION = '0.5.14'" in (work / 'src' / 'config.py').read_text(encoding='utf-8'), 'gate:version'
assert 'subprocess.Popen' in launch_src and 'runpy.run_path' not in launch_src, 'gate:external_runtime_launcher'
assert "key.startswith('_PYI_')" in launch_src and "key.startswith('PYINSTALLER_')" in launch_src, 'gate:pyinstaller_env_cleanup'
assert 'import tkinter' not in launch_src, 'gate:no_frozen_tk_host'
assert 'restart_into_native_host' not in wint, 'gate:no_native_host_restart'
assert "APP_ID='MXBRaceDayLive.Desktop'" in wint and "APP_ID='MXBRaceDayLive.Desktop'" in task, 'gate:stable_app_id'
assert "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'" in app, 'gate:app_id_restored'
assert 'v0.5.13 native host transition' not in app, 'gate:bad_transition_removed'
assert "('FIND A RACE', 'UPCOMING'" in ui and 'MY RACES' in ui, 'gate:v0513_ui_preserved'
assert (work / 'assets' / 'bin' / 'MXB Race Day Live.exe').read_bytes()[:2] == b'MZ', 'gate:launcher_payload'

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc':
            z.write(f, f.relative_to(work).as_posix())

digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest = {
    'version': VERSION,
    'url': f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}',
    'sha256': digest,
    'notes': NOTES,
}
Path('race-control/latest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
LAUNCHER.unlink(missing_ok=True)
Path('race-control/staging/mxb_asset_decoder.exe').unlink(missing_ok=True)
ICON.unlink(missing_ok=True)
print('STARTUP RECOVERY GATE', {
    'external_python_runtime': True,
    'pyinstaller_parent_state_cleared': True,
    'frozen_tk_host': False,
    'v0513_ui_preserved': True,
})
print('BUILT', OUT, digest)
