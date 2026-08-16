from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_3_9_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_0_UPDATE.zip')
VERSION = '0.5.0'
NOTES = (
    'MXB Race Day Live v0.5.0: unifies the in-app updater onto the Race Day Live channel, '
    'moves the version above the legacy MXB Bike Builder 0.4.x line so updates can no longer be '
    'blocked by the old product version, bypasses stale GitHub manifest caching, verifies SHA-256 '
    'before install, installs without deleting rider/settings data, and restarts through the hidden '
    'Windows launcher. Existing Race Day Live features from v0.3.9 are preserved.'
)

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit(f'Missing/invalid base release: {BASE}')

work = Path(tempfile.mkdtemp(prefix='mxb_v050_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

for rel, pattern, replacement in (
    ('src/config.py', r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.5.0'"),
    ('src/__init__.py', r"__version__\s*=\s*['\"][^'\"]+['\"]", "__version__ = '0.5.0'"),
):
    p = work / rel
    if not p.exists():
        raise SystemExit(f'Missing {rel}')
    s = p.read_text(encoding='utf-8')
    s2, count = re.subn(pattern, replacement, s, count=1)
    if count != 1:
        raise SystemExit(f'Could not bump version in {rel}')
    p.write_text(s2, encoding='utf-8')

updater = r"""from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from .config import VERSION

REPO = 'n286f7kh2k-debug/MXB-Bike-Builder'
BRANCH = 'main'
MANIFEST_PATH = 'race-control/latest.json'
MANIFEST_API = f'https://api.github.com/repos/{REPO}/contents/{MANIFEST_PATH}'
MANIFEST_RAW = f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{MANIFEST_PATH}'
USER_AGENT = f'MXB-Race-Day-Live-Updater/{VERSION}'


def _version_tuple(value):
    parts = []
    for piece in str(value or '').strip().lstrip('vV').split('.'):
        digits = ''.join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def _request(url, timeout=20):
    sep = '&' if '?' in url else '?'
    busted = f'{url}{sep}_mxb={time.time_ns()}'
    req = urllib.request.Request(
        busted,
        headers={
            'User-Agent': USER_AGENT,
            'Accept': 'application/vnd.github+json, application/json;q=0.9, */*;q=0.1',
            'Cache-Control': 'no-cache, no-store, max-age=0',
            'Pragma': 'no-cache',
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def _normalize_manifest(data):
    if not isinstance(data, dict):
        raise RuntimeError('Update feed returned an invalid manifest.')
    version = str(data.get('version') or '').strip().lstrip('vV')
    url = str(data.get('url') or '').strip()
    sha256 = str(data.get('sha256') or '').strip().lower()
    notes = str(data.get('notes') or '').strip()
    if not version or not url:
        raise RuntimeError('Update manifest is missing version or download URL.')
    if sha256 and (len(sha256) != 64 or any(c not in '0123456789abcdef' for c in sha256)):
        raise RuntimeError('Update manifest contains an invalid SHA-256 value.')
    return {'version': version, 'url': url, 'sha256': sha256, 'notes': notes}


def _manifest_from_github_api():
    with _request(f'{MANIFEST_API}?ref={BRANCH}', timeout=20) as r:
        payload = json.loads(r.read().decode('utf-8'))
    encoded = str(payload.get('content') or '').replace('\n', '')
    if not encoded:
        raise RuntimeError('GitHub update feed did not contain manifest data.')
    raw = base64.b64decode(encoded).decode('utf-8-sig')
    return _normalize_manifest(json.loads(raw))


def _manifest_from_raw():
    with _request(MANIFEST_RAW, timeout=20) as r:
        return _normalize_manifest(json.loads(r.read().decode('utf-8-sig')))


def _get_manifest():
    errors = []
    for loader in (_manifest_from_github_api, _manifest_from_raw):
        try:
            return loader()
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError('Could not refresh the Race Day Live update feed. ' + ' | '.join(errors))


def check_for_update(current_version=None):
    current = str(current_version or VERSION).strip().lstrip('vV')
    manifest = _get_manifest()
    manifest['current_version'] = current
    manifest['available'] = _version_tuple(manifest['version']) > _version_tuple(current)
    return manifest


def download_update(manifest):
    manifest = _normalize_manifest(manifest)
    out = Path(tempfile.gettempdir()) / f"MXB_Race_Day_Live_v{manifest['version'].replace('.', '_')}_UPDATE.zip"
    tmp = out.with_suffix(out.suffix + '.part')
    tmp.unlink(missing_ok=True)
    h = hashlib.sha256()
    try:
        with _request(manifest['url'], timeout=60) as src, tmp.open('wb') as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                h.update(chunk)
        digest = h.hexdigest()
        expected = manifest.get('sha256') or ''
        if expected and digest.lower() != expected.lower():
            raise RuntimeError(f'Update download failed SHA-256 verification. Expected {expected}, got {digest}.')
        if not zipfile.is_zipfile(tmp):
            raise RuntimeError('Downloaded update is not a valid ZIP package.')
        os.replace(tmp, out)
        return out
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _install_root():
    return Path(__file__).resolve().parent.parent


def schedule_restart(update_zip, install_dir=None, wait_pid=None):
    update_zip = Path(update_zip).resolve()
    install_dir = Path(install_dir or _install_root()).resolve()
    wait_pid = int(wait_pid or os.getpid())
    if not update_zip.exists() or not zipfile.is_zipfile(update_zip):
        raise RuntimeError('Update package disappeared before install could start.')

    script = Path(tempfile.gettempdir()) / 'mxb_race_day_live_apply_update.py'
    code = '''import os, shutil, subprocess, sys, tempfile, time, zipfile\nfrom pathlib import Path\nzip_path=Path(sys.argv[1]).resolve()\ninstall=Path(sys.argv[2]).resolve()\npid=int(sys.argv[3])\nfor _ in range(240):\n    try:\n        os.kill(pid,0)\n        time.sleep(0.25)\n    except OSError:\n        break\nwork=Path(tempfile.mkdtemp(prefix="mxb_rdl_apply_"))\ntry:\n    with zipfile.ZipFile(zip_path) as z:z.extractall(work)\n    for src in sorted(work.rglob("*")):\n        rel=src.relative_to(work)\n        dst=install/rel\n        if src.is_dir():\n            dst.mkdir(parents=True,exist_ok=True)\n            continue\n        dst.parent.mkdir(parents=True,exist_ok=True)\n        tmp=dst.with_name(dst.name+".mxbnew")\n        try:\n            shutil.copy2(src,tmp)\n            os.replace(tmp,dst)\n        finally:\n            try:tmp.unlink(missing_ok=True)\n            except Exception:pass\n    vbs=install/"Start MXB Race Day Live.vbs"\n    if vbs.exists():\n        subprocess.Popen(["wscript.exe",str(vbs)],cwd=str(install),creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))\n    else:\n        app=install/"app.py"\n        py=Path(sys.executable)\n        pythonw=py.with_name("pythonw.exe")\n        subprocess.Popen([str(pythonw if pythonw.exists() else py),str(app)],cwd=str(install),creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))\nfinally:\n    shutil.rmtree(work,ignore_errors=True)\n    try:zip_path.unlink(missing_ok=True)\n    except Exception:pass\n'''
    script.write_text(code, encoding='utf-8')
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    runner = str(pythonw if pythonw.exists() else Path(sys.executable))
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(
        [runner, str(script), str(update_zip), str(install_dir), str(wait_pid)],
        cwd=str(install_dir),
        creationflags=flags,
        close_fds=True,
    )
    return script


def launch_update(update_zip):
    return schedule_restart(update_zip)
"""

up_path = work / 'src/updater.py'
if not up_path.exists():
    raise SystemExit('Base release is missing src/updater.py')
up_path.write_text(updater, encoding='utf-8')

app_path = work / 'src/app.py'
app = app_path.read_text(encoding='utf-8')
if 'def do_update(self):' not in app or 'check_for_update' not in app or 'launch_update(z)' not in app:
    raise SystemExit('v0.5.0 updater UI anchors missing')
app = app.replace('MXB-Race-Day-Live-Updater/0.3.9', 'MXB-Race-Day-Live-Updater/0.5.0')
app_path.write_text(app, encoding='utf-8')

required = ['app.py','src/app.py','src/config.py','src/updater.py','src/__init__.py','Start MXB Race Day Live.vbs']
for rel in required:
    if not (work / rel).exists():
        raise SystemExit(f'Final update missing {rel}')

up = up_path.read_text(encoding='utf-8')
app = app_path.read_text(encoding='utf-8')
assert "MANIFEST_PATH = 'race-control/latest.json'" in up
assert '_manifest_from_github_api' in up and '_manifest_from_raw' in up
assert 'time.time_ns()' in up and 'Cache-Control' in up
assert 'check_for_update' in up and 'download_update' in up and 'launch_update' in up
assert 'schedule_restart' in up and 'os.replace(tmp,dst)' in up
assert 'shutil.rmtree(install' not in up
assert 'def do_update(self):' in app and 'launch_update(z)' in app
assert "VERSION = '0.5.0'" in (work/'src/config.py').read_text(encoding='utf-8')
assert "__version__ = '0.5.0'" in (work/'src/__init__.py').read_text(encoding='utf-8')

for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

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
print('UPDATER GATE', {'canonical_manifest': 'race-control/latest.json', 'version': VERSION, 'preserve_user_files': True, 'hidden_restart': True})
print('BUILT', OUT, digest)
