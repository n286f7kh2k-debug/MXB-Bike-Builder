from pathlib import Path
import hashlib, json, tempfile, zipfile, py_compile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_2_6_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_2_7_UPDATE.zip')
NOTES = ('MXB Race Day Live v0.2.7: fixes automatic restart after an in-app update, '
         'adds a delayed Windows launcher and detached restart watchdog, and closes the GUI cleanly on the main thread.')

if not BASE.exists():
    raise SystemExit(f'Base release missing: {BASE}')

work = Path(tempfile.mkdtemp(prefix='mxbv027_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

p = work / 'src/config.py'
s = p.read_text(encoding='utf-8')
assert "VERSION = '0.2.6'" in s
p.write_text(s.replace("VERSION = '0.2.6'", "VERSION = '0.2.7'"), encoding='utf-8')

p = work / 'src/app.py'
s = p.read_text(encoding='utf-8')
old = '''                self.after(0,lambda:self.update_btn.configure(text=f"DOWNLOADING {m['version']}…")); z=download_update(m); self.after(0,lambda:self.update_btn.configure(text='RESTARTING…')); launch_update(z); self.after(500,self.destroy)'''
new = '''                self.after(0,lambda:self.update_btn.configure(text=f"DOWNLOADING {m['version']}…"))
                z=download_update(m)
                launch_update(z)
                def close_for_update():
                    try:self.update_btn.configure(text='INSTALLING & RESTARTING…')
                    except Exception:pass
                    self.after(300,self._on_close)
                self.after(0,close_for_update)'''
assert old in s
p.write_text(s.replace(old, new), encoding='utf-8')

p = work / 'src/updater.py'
s = p.read_text(encoding='utf-8')
s = s.replace("'User-Agent': 'MXB-Race-Day-Live-Updater/0.2.5'", "'User-Agent': 'MXB-Race-Day-Live-Updater/0.2.7'")
s = s.replace("'User-Agent': 'MXB-Race-Day-Live-Updater/0.2.6'", "'User-Agent': 'MXB-Race-Day-Live-Updater/0.2.7'")
old_restart = '''def restart():
    vbs = INSTALL / 'Start MXB Race Day Live.vbs'
    legacy_vbs = INSTALL / 'Start MXB Race Control.vbs'
    app = INSTALL / 'app.py'
    if os.name == 'nt' and vbs.exists():
        subprocess.Popen(['wscript.exe', str(vbs)], cwd=str(INSTALL), creationflags=CREATE_NO_WINDOW, close_fds=True)
        L('Restarted with hidden VBS launcher')
        return
    if os.name == 'nt' and legacy_vbs.exists():
        subprocess.Popen(['wscript.exe', str(legacy_vbs)], cwd=str(INSTALL), creationflags=CREATE_NO_WINDOW, close_fds=True)
        L('Restarted with legacy hidden VBS launcher')
        return
    py = Path(PYTHON)
    if os.name == 'nt' and py.name.lower() == 'python.exe':
        pyw = py.with_name('pythonw.exe')
        if pyw.exists():
            py = pyw
    subprocess.Popen([str(py), str(app)], cwd=str(INSTALL), creationflags=CREATE_NO_WINDOW, close_fds=True)
    L('Restarted directly with ' + str(py))
'''
new_restart = '''def schedule_restart():
    """Start a detached watchdog which relaunches after this updater has exited."""
    watchdog = Path(tempfile.gettempdir()) / 'mxb_race_day_live_restart_watchdog.py'
    watchdog_code = r"""import os, subprocess, sys, time, traceback
from pathlib import Path
INSTALL = Path(sys.argv[1]); LOG = Path(sys.argv[2]); PYTHON = sys.argv[3]
def L(msg):
    try:
        with LOG.open('a', encoding='utf-8') as f: f.write(time.strftime('%Y-%m-%dT%H:%M:%S') + ' restart-watchdog ' + str(msg) + '\\n')
    except Exception: pass
def popen(args):
    flags = (0x08000000 | 0x00000200 | 0x00000008) if os.name == 'nt' else 0
    try: return subprocess.Popen(args, cwd=str(INSTALL), creationflags=flags, close_fds=True)
    except Exception as exc:
        L('Detached launch failed: ' + repr(exc))
        return subprocess.Popen(args, cwd=str(INSTALL), creationflags=(0x08000000 if os.name == 'nt' else 0), close_fds=True)
try:
    time.sleep(1.8)
    vbs = INSTALL / 'Start MXB Race Day Live.vbs'
    if os.name == 'nt' and vbs.exists(): popen(['wscript.exe', str(vbs)]); L('Launched VBS'); raise SystemExit(0)
    app = INSTALL / 'app.py'; py = INSTALL / '.venv' / 'Scripts' / 'pythonw.exe'
    if not py.exists(): py = Path(PYTHON)
    popen([str(py), str(app)]); L('Launched app directly')
except SystemExit: raise
except Exception: L('RESTART WATCHDOG FAILED\\n' + traceback.format_exc())
"""
    watchdog.write_text(watchdog_code, encoding='utf-8')
    flags = (0x08000000 | 0x00000200 | 0x00000008) if os.name == 'nt' else 0
    try:
        subprocess.Popen([PYTHON, str(watchdog), str(INSTALL), str(LOG), PYTHON], cwd=str(INSTALL), creationflags=flags, close_fds=True)
        L('Detached restart watchdog scheduled')
    except Exception as exc:
        L('Watchdog failed; VBS fallback: ' + repr(exc))
        vbs = INSTALL / 'Start MXB Race Day Live.vbs'
        if os.name == 'nt' and vbs.exists(): subprocess.Popen(['wscript.exe', str(vbs)], cwd=str(INSTALL), creationflags=CREATE_NO_WINDOW, close_fds=True)
        else: subprocess.Popen([PYTHON, str(INSTALL / 'app.py')], cwd=str(INSTALL), creationflags=CREATE_NO_WINDOW, close_fds=True)
'''
assert old_restart in s
s = s.replace(old_restart, new_restart)
s = s.replace("    restart()\n    L('Update completed')", "    schedule_restart()\n    L('Update completed; restart scheduled')")
flags_old = "    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n    try:\n"
flags_new = "    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n    if os.name == 'nt': flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)\n    try:\n"
assert flags_old in s
s = s.replace(flags_old, flags_new, 1)
p.write_text(s, encoding='utf-8')

vbs = r'''Option Explicit
On Error Resume Next
Dim shell, fso, root, pyw, pye, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
WScript.Sleep 1800
pyw = root & "\.venv\Scripts\pythonw.exe"
pye = root & "\.venv\Scripts\python.exe"
If fso.FileExists(pyw) Then
  Err.Clear
  cmd = Chr(34) & pyw & Chr(34) & " " & Chr(34) & root & "\app.py" & Chr(34)
  shell.Run cmd, 0, False
  If Err.Number = 0 Then WScript.Quit 0
End If
If fso.FileExists(pye) Then
  Err.Clear
  cmd = Chr(34) & pye & Chr(34) & " " & Chr(34) & root & "\app.py" & Chr(34)
  shell.Run cmd, 0, False
  If Err.Number = 0 Then WScript.Quit 0
End If
'''
(work / 'Start MXB Race Day Live.vbs').write_text(vbs, encoding='utf-8')
(work / 'run_windows.bat').write_text('@echo off\ncd /d "%~dp0"\nstart "" /b wscript.exe "Start MXB Race Day Live.vbs"\nexit /b 0\n', encoding='utf-8')

for rel in ['app.py', 'src/app.py', 'src/config.py', 'src/updater.py', 'src/track_media.py']:
    py_compile.compile(str(work / rel), doraise=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts:
            z.write(f, f.relative_to(work).as_posix())

with zipfile.ZipFile(OUT) as z:
    names = set(z.namelist())
    for required in ['app.py', 'src/app.py', 'src/config.py', 'src/updater.py', 'Start MXB Race Day Live.vbs']:
        assert required in names

digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest = {
    'version': '0.2.7',
    'url': 'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_2_7_UPDATE.zip',
    'sha256': digest,
    'notes': NOTES,
}
Path('race-control/latest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print('Built', OUT, digest)
