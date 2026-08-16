from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_5_14_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_15_UPDATE.zip')
WININT_BASE = Path('race-control/windows_integration_v0513.py')
TASKBAR = Path('race-control/windows_taskbar_v0513.py')
NATIVE_SRC = Path('race-control/launcher/rdl_native_host.py')
LAUNCHER = Path('race-control/staging/MXB Race Day Live.exe')
ICON = Path('race-control/staging/rdl-launcher.ico')
VERSION = '0.5.15'
NOTES = (
    'MXB Race Day Live v0.5.15 restores the branded Windows process identity without reintroducing the v0.5.13 startup regression. '
    'MXB Race Day Live.exe again owns the running Tk application so taskbar right-click identity no longer comes from pythonw.exe. '
    'The native host now explicitly bundles tkinter ttk, messagebox, filedialog, colorchooser, simpledialog, font and scrolledtext plus the Pillow UI modules, and the Windows build runs a frozen-host smoke test before publication. '
    'Desktop and existing pinned shortcuts are retargeted to the branded EXE, use the permanent Race Day Live icon, and refresh the Explorer icon cache. '
    'Native-host restarts now strip inherited PyInstaller state so future executable swaps do not trigger the parent-process executable security validation error. '
    'This release is intentionally limited to Windows startup/taskbar identity; Garage model, rider skin and performance fixes remain queued separately.'
)

for p in (BASE, WININT_BASE, TASKBAR, NATIVE_SRC, LAUNCHER, ICON):
    if not p.exists():
        raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):
    raise SystemExit('v0.5.14 base missing/invalid')
if LAUNCHER.read_bytes()[:2] != b'MZ':
    raise SystemExit('branded native host is not a Windows PE executable')

work = Path(tempfile.mkdtemp(prefix='mxb_v0515_'))
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

# Start from the native-host shell integration, then harden restarts and icon persistence.
wint = WININT_BASE.read_text(encoding='utf-8')
if 'def _clean_launch_env(' not in wint:
    anchor = 'def restart_into_native_host(root, tk_root=None, delay_ms=700):\n'
    if anchor not in wint:
        raise SystemExit('native restart anchor missing')
    clean = '''def _clean_launch_env():
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith('_PYI_') or key.startswith('PYINSTALLER_'):
            env.pop(key, None)
    return env


'''
    wint = wint.replace(anchor, clean + anchor, 1)

# Permanent ICO for shortcuts/pins; the EXE also embeds the same icon.
old = "    ps = (\n        \"$w=New-Object -ComObject WScript.Shell;\""
if old not in wint:
    raise SystemExit('shortcut writer anchor missing')
wint = wint.replace(
    old,
    "    icon_source = packaged_icon(root) or str(launcher)\n    ps = (\n        \"$w=New-Object -ComObject WScript.Shell;\"",
    1,
)
wint = wint.replace(
    '"$s.IconLocation=\'" + _ps_quote(str(launcher)) + ",0\';"',
    '"$s.IconLocation=\'" + _ps_quote(icon_source) + ",0\';"',
    1,
)

# Every process that can launch the next PyInstaller host receives a clean environment.
wint = wint.replace(
    "                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),\n                )",
    "                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),\n                    env=_clean_launch_env(),\n                )",
    1,
)
wint = wint.replace(
    "                subprocess.Popen([str(launcher)], cwd=str(root),\n                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))",
    "                subprocess.Popen([str(launcher)], cwd=str(root),\n                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),\n                                 env=_clean_launch_env())",
    1,
)

# Stronger Explorer icon refresh after retargeting a pin.
show = "            subprocess.run([exe, '-show'], timeout=3,\n                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)"
if show in wint:
    wint = wint.replace(
        show,
        "            subprocess.run([exe, '-ClearIconCache'], timeout=3, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)\n            subprocess.run([exe, '-show'], timeout=3,\n                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)",
        1,
    )
(work / 'src' / 'windows_integration.py').write_text(wint, encoding='utf-8')
shutil.copy2(TASKBAR, work / 'src' / 'windows_taskbar.py')
(work / 'assets' / 'bin').mkdir(parents=True, exist_ok=True)
shutil.copy2(LAUNCHER, work / 'assets' / 'bin' / 'MXB Race Day Live.exe')
(work / 'assets').mkdir(parents=True, exist_ok=True)
shutil.copy2(ICON, work / 'assets' / 'mxb_race_day_live.ico')

# Keep the stable v0.5.14 app/UI.  After hot-install, replace the dormant root
# launcher while pythonw still owns this one session, and repair all known links.
p = work / 'src' / 'app.py'
app = p.read_text(encoding='utf-8')
hot_anchor = '    def _after_hot_reload(self,target_version,snapshot):\n'
if hot_anchor not in app:
    raise SystemExit('hot reload lifecycle anchor missing')
if 'v0.5.15 native identity install' not in app:
    app = app.replace(
        hot_anchor,
        hot_anchor +
        "        # v0.5.15 native identity install: current v0.5.14 session is pythonw-owned,\n"
        "        # so the branded root EXE can be replaced safely without forcing a restart.\n"
        "        if str(target_version).strip()=='0.5.15':\n"
        "            try:\n"
        "                from .windows_integration import ensure_desktop_shortcut as _rdl_link\n"
        "                _rdl_root=Path(__file__).resolve().parent.parent\n"
        "                self.after(500,lambda r=_rdl_root:_rdl_link(r))\n"
        "            except Exception:pass\n",
        1,
    )
install_anchor = '        install_profile_first_ui(self)\n'
if install_anchor in app and 'v0.5.15 startup shell repair' not in app:
    app = app.replace(
        install_anchor,
        install_anchor +
        "        # v0.5.15 startup shell repair: keep desktop/pins on the branded executable.\n"
        "        try:\n"
        "            from .windows_integration import ensure_desktop_shortcut as _rdl_shortcut\n"
        "            self.after(700,lambda:_rdl_shortcut(Path(__file__).resolve().parent.parent))\n"
        "        except Exception:pass\n",
        1,
    )
p.write_text(app, encoding='utf-8')

for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

app = (work / 'src' / 'app.py').read_text(encoding='utf-8')
wint = (work / 'src' / 'windows_integration.py').read_text(encoding='utf-8')
task = (work / 'src' / 'windows_taskbar.py').read_text(encoding='utf-8')
native = NATIVE_SRC.read_text(encoding='utf-8')

assert "VERSION = '0.5.15'" in (work / 'src' / 'config.py').read_text(encoding='utf-8'), 'gate:version'
assert 'runpy.run_path' in native and 'subprocess.Popen' not in native, 'gate:branded_process_owns_ui'
for required in ('ttk', 'messagebox', 'filedialog', 'colorchooser', 'simpledialog', 'scrolledtext', 'ImageTk'):
    assert required in native, 'gate:native_ui_import:'+required
assert 'SMOKE_ARG' in native and '_smoke_test' in native, 'gate:frozen_host_smoke_test'
assert "key.startswith('_PYI_')" in wint and "key.startswith('PYINSTALLER_')" in wint, 'gate:clean_pyinstaller_env'
assert 'env=_clean_launch_env()' in wint, 'gate:clean_native_restart'
assert 'icon_source = packaged_icon(root) or str(launcher)' in wint, 'gate:permanent_pin_icon'
assert '_migrate_pinned_shortcuts' in wint and 'ensure_desktop_shortcut' in wint, 'gate:pin_migration'
assert 'v0.5.15 native identity install' in app, 'gate:hot_install_shell_repair'
assert 'v0.5.15 startup shell repair' in app, 'gate:cold_start_shell_repair'
assert 'SetCurrentProcessExplicitAppUserModelID' not in task, 'gate:window_does_not_override_host_identity'
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
print('WINDOWS IDENTITY GATE', {
    'branded_process_owns_ui': True,
    'tkinter_submodules_bundled': True,
    'frozen_host_smoke_test': True,
    'pyinstaller_restart_env_clean': True,
    'permanent_pin_icon': True,
})
print('BUILT', OUT, digest)
