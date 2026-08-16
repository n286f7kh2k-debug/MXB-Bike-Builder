from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

SHORTCUT_NAME = 'MXB Race Day Live.lnk'
LAUNCHER_NAME = 'MXB Race Day Live.exe'
RUNTIME_FILE = 'rdl_runtime.txt'
_cache_lock = threading.Lock()
_shortcut_cache = None
_info_cache = None


def desktop_dirs():
    roots = []
    for key in ('USERPROFILE', 'ONEDRIVE', 'OneDriveConsumer', 'OneDriveCommercial', 'PUBLIC'):
        raw = os.environ.get(key)
        if raw:
            roots.append(Path(raw) / 'Desktop')
    try:
        roots.append(Path.home() / 'Desktop')
    except Exception:
        pass
    out, seen = [], set()
    for p in roots:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def find_shortcut(refresh=False):
    global _shortcut_cache
    with _cache_lock:
        if not refresh and _shortcut_cache:
            p = Path(_shortcut_cache)
            if p.is_file():
                return p
    found = None
    for root in desktop_dirs():
        p = root / SHORTCUT_NAME
        if p.is_file():
            found = p
            break
        try:
            matches = sorted(root.glob('*MXB*Race*Day*Live*.lnk')) if root.is_dir() else []
            if matches:
                found = matches[0]
                break
        except Exception:
            pass
    with _cache_lock:
        _shortcut_cache = str(found) if found else ''
    return found


def _ps_quote(value):
    return str(value).replace("'", "''")


def _read_shortcut(shortcut):
    if os.name != 'nt':
        return {}
    shortcut = Path(shortcut or '')
    if not shortcut.is_file():
        return {}
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + _ps_quote(shortcut) + "');"
        "$o=[ordered]@{target=$s.TargetPath;arguments=$s.Arguments;working=$s.WorkingDirectory;icon=$s.IconLocation};"
        "$o|ConvertTo-Json -Compress"
    )
    try:
        cp = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        import json
        return json.loads((cp.stdout or '{}').strip() or '{}')
    except Exception:
        return {}


def shortcut_info(shortcut=None, refresh=False):
    global _info_cache
    if os.name != 'nt':
        return {}
    shortcut = Path(shortcut or find_shortcut(refresh=refresh) or '')
    if not shortcut.is_file():
        return {}
    use_cache = shortcut == find_shortcut()
    if use_cache:
        with _cache_lock:
            if not refresh and isinstance(_info_cache, dict) and _info_cache:
                return dict(_info_cache)
    info = _read_shortcut(shortcut)
    if use_cache:
        with _cache_lock:
            _info_cache = dict(info)
    return info


def shortcut_icon_spec(shortcut=None, refresh=False):
    return str(shortcut_info(shortcut, refresh).get('icon') or '').strip().strip('"')


def _pythonw_source(root):
    root = Path(root).resolve()
    candidates = [root / '.venv' / 'Scripts' / 'pythonw.exe']
    try:
        candidates.append(Path(sys.executable).with_name('pythonw.exe'))
    except Exception:
        pass
    for p in candidates:
        try:
            if p.is_file():
                return p.resolve()
        except Exception:
            pass
    return None


def packaged_launcher(root):
    p = Path(root).resolve() / 'assets' / 'bin' / LAUNCHER_NAME
    return p if p.is_file() else None


def native_launcher_path(root):
    p = Path(root).resolve() / LAUNCHER_NAME
    return p if p.is_file() else None


def running_native_host(root):
    try:
        root = Path(root).resolve()
        return Path(sys.executable).resolve() == (root / LAUNCHER_NAME).resolve()
    except Exception:
        return False


def _same_file(a, b):
    try:
        a, b = Path(a), Path(b)
        if not a.is_file() or not b.is_file() or a.stat().st_size != b.stat().st_size:
            return False
        def digest(p):
            h = hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
            return h.digest()
        return digest(a) == digest(b)
    except Exception:
        return False


def _write_runtime_hint(root):
    root = Path(root).resolve()
    runtime = _pythonw_source(root)
    if not runtime:
        return None
    hint = root / 'assets' / 'bin' / RUNTIME_FILE
    hint.parent.mkdir(parents=True, exist_ok=True)
    try:
        try:
            value = str(runtime.relative_to(root)).replace('/', '\\')
        except Exception:
            value = str(runtime)
        tmp = hint.with_suffix('.tmp')
        tmp.write_text(value + '\n', encoding='utf-8')
        os.replace(tmp, hint)
    except Exception:
        return None
    return hint


def ensure_native_launcher(root):
    """Install/stage the branded in-process host; never copy or rename pythonw.exe."""
    if os.name != 'nt':
        return None
    root = Path(root).resolve()
    src = packaged_launcher(root)
    dst = root / LAUNCHER_NAME
    pending = dst.with_name(dst.name + '.rdlnew')
    _write_runtime_hint(root)
    if not src:
        return dst if dst.is_file() else None
    try:
        if _same_file(src, dst):
            pending.unlink(missing_ok=True)
            return dst
        # A running EXE cannot replace itself. Stage it; restart_into_native_host
        # will swap it after this process exits.
        if running_native_host(root):
            shutil.copy2(src, pending)
            return dst
        tmp = dst.with_name(dst.name + '.rdltmp')
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
        pending.unlink(missing_ok=True)
        # Retire only the old app-named copy that previous builds put beside pythonw.
        runtime = _pythonw_source(root)
        if runtime:
            legacy = runtime.with_name(LAUNCHER_NAME)
            if legacy.is_file() and legacy.resolve() != dst.resolve():
                try:
                    legacy.unlink()
                except Exception:
                    pass
        return dst
    except Exception:
        return dst if dst.is_file() else None


def packaged_icon(root):
    p = Path(root).resolve() / 'assets' / 'mxb_race_day_live.ico'
    return str(p) if p.is_file() else ''


def best_icon(root, refresh=False):
    # Explorer should use the icon embedded in the branded EXE for shortcuts/pins.
    launcher = native_launcher_path(root)
    if launcher:
        return str(launcher)
    return packaged_icon(root) or shortcut_icon_spec(refresh=refresh)


def _write_shortcut(shortcut, root, launcher):
    shortcut = Path(shortcut)
    root = Path(root).resolve()
    launcher = Path(launcher).resolve()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        "$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('" + _ps_quote(shortcut) + "');"
        "$s.TargetPath='" + _ps_quote(launcher) + "';"
        "$s.Arguments='';"
        "$s.WorkingDirectory='" + _ps_quote(root) + "';"
        "$s.Description='MXB Race Day Live';"
        "$s.IconLocation='" + _ps_quote(str(launcher)) + ",0';"
        "$s.Save()"
    )
    try:
        subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
            timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False,
        )
        return shortcut.is_file()
    except Exception:
        return False


def _pinned_dirs():
    raw = os.environ.get('APPDATA', '')
    if not raw:
        return []
    base = Path(raw) / 'Microsoft' / 'Internet Explorer' / 'Quick Launch' / 'User Pinned'
    return [base / 'TaskBar', base / 'StartMenu']


def _is_our_shortcut(path, root):
    path = Path(path)
    if 'mxb race day live' in path.stem.lower():
        return True
    info = _read_shortcut(path)
    target = str(info.get('target') or '').lower()
    args = str(info.get('arguments') or '').lower()
    if Path(target).name.lower() == LAUNCHER_NAME.lower():
        return True
    app_py = str((Path(root).resolve() / 'app.py')).lower()
    return app_py in args and Path(target).name.lower() in ('python.exe', 'pythonw.exe')


def _migrate_pinned_shortcuts(root, launcher):
    changed = 0
    for folder in _pinned_dirs():
        try:
            links = list(folder.glob('*.lnk')) if folder.is_dir() else []
        except Exception:
            links = []
        for link in links:
            try:
                if _is_our_shortcut(link, root) and _write_shortcut(link, root, launcher):
                    changed += 1
            except Exception:
                pass
    return changed


def _refresh_shell():
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass
    try:
        exe = shutil.which('ie4uinit.exe')
        if exe:
            subprocess.run([exe, '-show'], timeout=3,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)
    except Exception:
        pass


def ensure_desktop_shortcut(root):
    """Retarget desktop/existing pinned links to the real branded EXE and its embedded icon."""
    if os.name != 'nt':
        return None
    global _shortcut_cache, _info_cache
    root = Path(root).resolve()
    launcher = ensure_native_launcher(root)
    if not launcher:
        return None
    shortcut = find_shortcut() or next(
        (d / SHORTCUT_NAME for d in desktop_dirs() if d.is_dir() and 'public' not in str(d).lower()),
        Path.home() / 'Desktop' / SHORTCUT_NAME,
    )
    _write_shortcut(shortcut, root, launcher)
    _migrate_pinned_shortcuts(root, launcher)
    with _cache_lock:
        _shortcut_cache = str(shortcut)
        _info_cache = None
    _refresh_shell()
    return shortcut


def restart_into_native_host(root, tk_root=None, delay_ms=700):
    """Restart once into the branded host, swapping a staged host after exit if needed."""
    if os.name != 'nt':
        return False
    root = Path(root).resolve()
    launcher = ensure_native_launcher(root)
    if not launcher:
        return False
    pending = launcher.with_name(launcher.name + '.rdlnew')
    pid = os.getpid()

    def launch_now():
        try:
            if pending.is_file() and running_native_host(root):
                ps = (
                    f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue;"
                    "if($p){$p.WaitForExit()};"
                    f"Move-Item -LiteralPath '{_ps_quote(pending)}' -Destination '{_ps_quote(launcher)}' -Force;"
                    f"Start-Process -FilePath '{_ps_quote(launcher)}' -WorkingDirectory '{_ps_quote(root)}'"
                )
                subprocess.Popen(
                    ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            else:
                subprocess.Popen([str(launcher)], cwd=str(root),
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                if tk_root is not None:
                    tk_root.destroy()
            except Exception:
                pass
            return True
        except Exception:
            return False

    if tk_root is not None:
        try:
            tk_root.after(max(50, int(delay_ms)), launch_now)
            return True
        except Exception:
            pass
    return launch_now()
