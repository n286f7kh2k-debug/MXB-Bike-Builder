from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

APP_NAME = 'MXB Race Day Live'
LATEST_URL = 'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/latest.json'
MIN_RECOVERY_VERSION = (0, 5, 14)


def _msg(text: str, title: str = APP_NAME, error: bool = False) -> None:
    try:
        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(None, str(text), str(title), flags)
    except Exception:
        pass


def _version_tuple(value: str):
    out = []
    for part in str(value or '').strip().split('.'):
        try:
            out.append(int(part))
        except Exception:
            out.append(0)
    return tuple((out + [0, 0, 0])[:3])


def _valid_install(root: Path) -> bool:
    root = Path(root)
    return (root / 'app.py').is_file() and (root / 'src' / 'app.py').is_file()


def _candidate_score(root: Path) -> tuple:
    text = str(root).lower()
    score = 0
    if 'mxb_race_day_live' in text or 'mxb race day live' in text:
        score += 100
    if (root / 'MXB Race Day Live.exe').is_file():
        score += 60
    if (root / 'assets' / 'bin' / 'MXB Race Day Live.exe').is_file():
        score += 30
    try:
        stamp = max((root / 'app.py').stat().st_mtime, (root / 'src' / 'app.py').stat().st_mtime)
    except Exception:
        stamp = 0
    return score, stamp, -len(str(root))


def _search_roots():
    home = Path.home()
    starts = [Path.cwd(), Path(sys.executable).resolve().parent, home / 'Desktop', home / 'Documents']
    seen = set()
    candidates = []
    for start in starts:
        try:
            start = start.resolve()
        except Exception:
            continue
        key = str(start).lower()
        if key in seen:
            continue
        seen.add(key)
        if _valid_install(start):
            candidates.append(start)
            continue
        if not start.is_dir():
            continue
        # Keep recovery fast: only inspect directories that look like Race Day Live installs.
        try:
            for p in start.rglob('app.py'):
                parent = p.parent
                if len(parent.relative_to(start).parts) > 7:
                    continue
                if _valid_install(parent):
                    candidates.append(parent)
        except Exception:
            pass
    unique = {}
    for p in candidates:
        try:
            unique[str(p.resolve()).lower()] = p.resolve()
        except Exception:
            pass
    return sorted(unique.values(), key=_candidate_score, reverse=True)


def _pick_folder() -> Path | None:
    ps = r'''
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.FolderBrowserDialog
$f.Description = 'Select your MXB Race Day Live app folder (the folder containing app.py)'
$f.ShowNewFolderButton = $false
if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }
'''
    try:
        cp = subprocess.run(
            ['powershell.exe', '-NoProfile', '-STA', '-Command', ps],
            capture_output=True, text=True, timeout=120,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        value = (cp.stdout or '').strip().splitlines()
        if value:
            p = Path(value[-1].strip())
            return p if _valid_install(p) else None
    except Exception:
        pass
    return None


def _locate_install() -> Path:
    found = _search_roots()
    if len(found) == 1:
        return found[0]
    if found:
        best = found[0]
        # If one candidate is clearly stronger than the rest, use it without bothering the user.
        if len(found) == 1 or _candidate_score(best)[0] > _candidate_score(found[1])[0]:
            return best
    picked = _pick_folder()
    if picked:
        return picked.resolve()
    if found:
        return found[0]
    raise RuntimeError('Could not find the MXB Race Day Live install folder. Run Recovery again and select the folder that contains app.py.')


def _download(url: str, out: Path) -> None:
    req = urllib.request.Request(url, headers={'User-Agent': 'MXB-Race-Day-Live-Recovery/0.5.14'})
    with urllib.request.urlopen(req, timeout=180) as response, out.open('wb') as f:
        shutil.copyfileobj(response, f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _safe_rel(name: str) -> Path:
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts:
        raise RuntimeError(f'Unsafe file in recovery package: {name}')
    return rel


def _apply_update(install: Path, package: Path) -> Path:
    if not zipfile.is_zipfile(package):
        raise RuntimeError('Downloaded recovery package is not a valid ZIP file.')
    stage = Path(tempfile.mkdtemp(prefix='mxb_rdl_recovery_stage_'))
    backup = Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()) / APP_NAME / 'recovery_backups' / datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        with zipfile.ZipFile(package) as z:
            for info in z.infolist():
                _safe_rel(info.filename)
            z.extractall(stage)
        for required in ('app.py', 'src/app.py', 'src/config.py', 'assets/bin/MXB Race Day Live.exe'):
            if not (stage / required).is_file():
                raise RuntimeError(f'Recovery package is incomplete: missing {required}')
        files = [p for p in stage.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
        for src in files:
            rel = src.relative_to(stage)
            dst = install / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_file():
                save = backup / rel
                save.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(dst, save)
                except Exception:
                    pass
            tmp = dst.with_name(dst.name + '.rdlrecover')
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
        # The packaged launcher lives in assets/bin; copy it to the stable root executable too.
        launcher_src = install / 'assets' / 'bin' / 'MXB Race Day Live.exe'
        launcher_dst = install / 'MXB Race Day Live.exe'
        tmp = launcher_dst.with_name(launcher_dst.name + '.rdlrecover')
        shutil.copy2(launcher_src, tmp)
        os.replace(tmp, launcher_dst)
        return launcher_dst
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _launch(install: Path, launcher: Path) -> None:
    env = dict(os.environ)
    for key in tuple(env):
        if key.startswith('_PYI_') or key.startswith('PYINSTALLER_'):
            env.pop(key, None)
    subprocess.Popen(
        [str(launcher)], cwd=str(install), env=env,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), close_fds=True,
    )


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix='mxb_rdl_recovery_'))
    try:
        install = _locate_install()
        manifest_path = work / 'latest.json'
        _download(LATEST_URL, manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        version = str(manifest.get('version') or '').strip()
        if _version_tuple(version) < MIN_RECOVERY_VERSION:
            raise RuntimeError(f'The recovery feed is not ready yet (found v{version or "unknown"}).')
        url = str(manifest.get('url') or '').strip()
        expected = str(manifest.get('sha256') or '').strip().lower()
        if not url or not expected:
            raise RuntimeError('Recovery feed is missing its download URL or checksum.')
        package = work / 'update.zip'
        _download(url, package)
        actual = _sha256(package)
        if actual != expected:
            raise RuntimeError(f'Recovery download failed checksum validation. Expected {expected}, got {actual}.')
        launcher = _apply_update(install, package)
        _launch(install, launcher)
        _msg(f'MXB Race Day Live was repaired to v{version}.\n\nThe app is starting now.', 'MXB Race Day Live Recovery')
        return 0
    except Exception as exc:
        _msg(f'Recovery could not finish.\n\n{exc}', 'MXB Race Day Live Recovery', True)
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main())
