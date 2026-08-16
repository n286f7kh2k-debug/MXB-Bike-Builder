from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_5_12_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_13_UPDATE.zip')
UI = Path('race-control/profile_ui_v0513.py')
WININT = Path('race-control/windows_integration_v0513.py')
TASKBAR = Path('race-control/windows_taskbar_v0513.py')
LAUNCHER_SRC = Path('race-control/launcher/rdl_launcher.py')
LAUNCHER = Path('race-control/staging/MXB Race Day Live.exe')
ICON = Path('race-control/staging/rdl-launcher.ico')
VERSION = '0.5.13'
NOTES = (
    'MXB Race Day Live v0.5.13 refines the profile-first interface into a focused race-night layout inspired by the supplied direction without copying it or adding unnecessary dashboard clutter. '
    'The rider profile remains the landing page with the existing banner/avatar identity, a compact career strip, My Races, next-race and latest-result panels. Primary navigation is limited to Profile, Find a Race, Championships, Garage, Live and Results; Wallet, Rankings, Profile Settings, Membership, MX Bikes tools, updates and Admin are moved into a compact MENU dropdown. '
    'Windows identity is also reworked at the process level: MXB Race Day Live.exe now hosts the application in-process instead of spawning pythonw.exe, the custom icon is embedded directly into the branded executable, desktop/existing pinned links target that executable and use its embedded icon, and the old explicit Python-era AppUserModelID override is removed. The v0.5.13 update performs a one-time relaunch into the new branded host after installation.'
)

for p in (BASE, UI, WININT, TASKBAR, LAUNCHER_SRC, LAUNCHER, ICON):
    if not p.exists():
        raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):
    raise SystemExit('v0.5.12 base missing/invalid')
if LAUNCHER.read_bytes()[:2] != b'MZ':
    raise SystemExit('branded native host is not a Windows PE executable')

work = Path(tempfile.mkdtemp(prefix='mxb_v0513_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

# Version all installed Python metadata.
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

# Replace presentation and Windows shell/process integration only; preserve all services/features.
shutil.copy2(UI, work / 'src' / 'profile_first_ui.py')
shutil.copy2(WININT, work / 'src' / 'windows_integration.py')
shutil.copy2(TASKBAR, work / 'src' / 'windows_taskbar.py')
(work / 'assets' / 'bin').mkdir(parents=True, exist_ok=True)
shutil.copy2(LAUNCHER, work / 'assets' / 'bin' / 'MXB Race Day Live.exe')
(work / 'assets').mkdir(parents=True, exist_ok=True)
shutil.copy2(ICON, work / 'assets' / 'mxb_race_day_live.ico')

# Shift the shared widgets/screens toward the same restrained deep-navy/cyan race theme.
p = work / 'src' / 'app.py'
app = p.read_text(encoding='utf-8')
app, n1 = re.subn(
    r"BG='#[0-9a-fA-F]{6}';\s*PANEL='#[0-9a-fA-F]{6}';\s*PANEL2='#[0-9a-fA-F]{6}';\s*TEXT='#[0-9a-fA-F]{6}';\s*MUTED='#[0-9a-fA-F]{6}'",
    "BG='#04101b'; PANEL='#071a29'; PANEL2='#0a2235'; TEXT='#f2f7fb'; MUTED='#88a5ba'",
    app, count=1,
)
app, n2 = re.subn(
    r"ACCENT='#[0-9a-fA-F]{6}';\s*GOLD='#[0-9a-fA-F]{6}';\s*GREEN='#[0-9a-fA-F]{6}';\s*RED='#[0-9a-fA-F]{6}';\s*LINE='#[0-9a-fA-F]{6}';\s*BLUE='#[0-9a-fA-F]{6}'",
    "ACCENT='#079cff'; GOLD='#f4c542'; GREEN='#2bd672'; RED='#ff5964'; LINE='#155273'; BLUE='#079cff'",
    app, count=1,
)
if n1 != 1 or n2 != 1:
    raise SystemExit('shared app palette anchors missing')

# Retire the old process AppUserModelID override. The real executable path now owns shell identity.
app, n = re.subn(
    r"APP_USER_MODEL_ID\s*=\s*['\"][^'\"]*['\"]\s*\ntry:\s*\n\s*if os\.name==['\"]nt['\"]:\s*\n\s*import ctypes\s*\n\s*ctypes\.windll\.shell32\.SetCurrentProcessExplicitAppUserModelID\(APP_USER_MODEL_ID\)\s*\nexcept Exception:\s*\n\s*pass",
    "APP_USER_MODEL_ID=''",
    app, count=1, flags=re.S,
)
if n != 1 and 'SetCurrentProcessExplicitAppUserModelID' in app:
    raise SystemExit('could not retire explicit process AppUserModelID')

# Keep the compact UI installer already wired by v0.5.12, and refresh shell links on startup.
install_anchor = '        install_profile_first_ui(self)\n'
if install_anchor not in app:
    raise SystemExit('profile UI installer anchor missing')
if 'v0.5.13 shell target refresh' not in app:
    app = app.replace(
        install_anchor,
        install_anchor +
        "        # v0.5.13 shell target refresh: pins/desktop target the branded host executable.\n"
        "        try:\n"
        "            from .windows_integration import ensure_desktop_shortcut as _rdl_shortcut\n"
        "            self.after(500,lambda:_rdl_shortcut(Path(__file__).resolve().parent.parent))\n"
        "        except Exception:pass\n",
        1,
    )

# One-time transition: v0.5.12 is still owned by pythonw. After hot install, let the
# normal hot refresh finish, then automatically reopen under the new branded in-process host.
hot_anchor = '    def _after_hot_reload(self,target_version,snapshot):\n'
if hot_anchor not in app:
    raise SystemExit('hot reload lifecycle anchor missing')
if 'v0.5.13 native host transition' not in app:
    transition = (
        hot_anchor +
        "        # v0.5.13 native host transition: eliminate the pythonw-owned app window.\n"
        "        if str(target_version).strip()=='0.5.13':\n"
        "            try:\n"
        "                from .windows_integration import ensure_desktop_shortcut as _rdl_link, restart_into_native_host as _rdl_restart\n"
        "                _rdl_root=Path(__file__).resolve().parent.parent\n"
        "                _rdl_link(_rdl_root)\n"
        "                self.after(1400,lambda r=_rdl_root:_rdl_restart(r,self,50))\n"
        "            except Exception:pass\n"
    )
    app = app.replace(hot_anchor, transition, 1)

p.write_text(app, encoding='utf-8')

# Syntax-check the complete release tree.
for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

app = (work / 'src' / 'app.py').read_text(encoding='utf-8')
ui = (work / 'src' / 'profile_first_ui.py').read_text(encoding='utf-8')
wint = (work / 'src' / 'windows_integration.py').read_text(encoding='utf-8')
task = (work / 'src' / 'windows_taskbar.py').read_text(encoding='utf-8')
launch_src = LAUNCHER_SRC.read_text(encoding='utf-8')

# Release gates: visual simplification + feature routing + native Windows ownership.
assert "VERSION = '0.5.13'" in (work / 'src' / 'config.py').read_text(encoding='utf-8'), 'gate:version'
assert "app.nav.pack_forget()" in ui and "app.update_btn.pack_forget()" in ui, 'gate:old_clutter_hidden'
assert "('PROFILE', 'PROFILE'" in ui and "('FIND A RACE', 'UPCOMING'" in ui, 'gate:primary_navigation'
primary = ui[ui.find('primary = ['):ui.find('left = tk.Frame', ui.find('primary = ['))]
for hidden in ('SETTINGS', 'MEMBERSHIP', 'ADMIN', 'WALLET', 'RANKINGS'):
    assert hidden not in primary, 'gate:hidden_from_primary:'+hidden
for menu_item in ('Profile Settings', 'Wallet', 'Rankings', 'Check for Updates', 'Admin Control'):
    assert menu_item in ui, 'gate:dropdown:'+menu_item
assert 'MY RACES' in ui and 'NEXT REGISTERED RACE' in ui and 'LATEST RESULT' in ui, 'gate:focused_profile'
for route in ("show('UPCOMING')", "show('CHAMPIONSHIPS')", "show('GARAGE')", "show('LIVE')", "show('RESULTS')"):
    assert route in ui, 'gate:route:'+route
assert 'runpy.run_path' in launch_src, 'gate:in_process_host'
assert 'subprocess.Popen' not in launch_src, 'gate:no_python_handoff'
assert 'SetCurrentProcessExplicitAppUserModelID' not in app, 'gate:no_app_appid_override'
assert 'SetCurrentProcessExplicitAppUserModelID' not in task, 'gate:no_taskbar_appid_override'
assert "$s.IconLocation='" in wint and "_ps_quote(str(launcher))" in wint, 'gate:pin_uses_embedded_exe_icon'
assert 'restart_into_native_host' in wint and 'v0.5.13 native host transition' in app, 'gate:auto_native_transition'
assert (work / 'assets' / 'bin' / 'MXB Race Day Live.exe').read_bytes()[:2] == b'MZ', 'gate:branded_host_payload'

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
print('UI GATE', {'profile_landing': True, 'focused_race_layout': True, 'secondary_tools_in_menu': True})
print('WINDOWS GATE', {'python_handoff': False, 'native_host': True, 'embedded_pin_icon': True, 'explicit_appid_override': False})
print('BUILT', OUT, digest)
