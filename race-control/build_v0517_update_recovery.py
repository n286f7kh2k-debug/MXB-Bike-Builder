from pathlib import Path
import hashlib
import json
import py_compile
import re
import tempfile
import zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_5_16_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_17_UPDATE.zip')
VERSION = '0.5.17'
NOTES = (
    'MXB Race Day Live v0.5.17 is a lean updater-recovery release for users whose v0.5.16 Tracks update did not complete. '
    'It re-forces the Tracks route and top-navigation install even on a partially updated v0.5.16 copy, preserves the verified MXB-Shop track image/direct-link mappings, '
    'and ships as a small hot-update package instead of re-downloading the large Windows binary payload. '
    'The updater itself is also hardened for future releases with multiple GitHub binary download routes, longer timeouts, SHA-256 verification on every route and clearer combined download errors.'
)

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit('v0.5.16 base missing/invalid')

work = Path(tempfile.mkdtemp(prefix='mxb_v0517_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

for rel, var in [('src/config.py', 'VERSION'), ('src/__init__.py', '__version__')]:
    p = work / rel
    text = p.read_text(encoding='utf-8')
    text, n = re.subn(
        rf"{var}\s*=\s*['\"][^'\"]+['\"]",
        f"{var} = '{VERSION}'",
        text,
        count=1,
    )
    if n != 1:
        raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(text, encoding='utf-8')

# Force the Tracks hot-install hook to execute again for recovery from a partial 0.5.16 refresh.
p = work / 'src' / 'app.py'
app = p.read_text(encoding='utf-8')
if "str(target_version).strip()=='0.5.16'" in app:
    app = app.replace("str(target_version).strip()=='0.5.16'", "str(target_version).strip()=='0.5.17'", 1)
if 'v0.5.16 Tracks install' in app:
    app = app.replace('v0.5.16 Tracks install', 'v0.5.17 Tracks recovery install', 1)
if 'install_tracks_ui(self)' not in app:
    raise SystemExit('cold Tracks install hook missing')
if 'v0.5.17 Tracks recovery install' not in app:
    raise SystemExit('hot Tracks recovery hook missing')
p.write_text(app, encoding='utf-8')

# Make the UI installer run again on 0.5.17 instead of treating a partial 0.5.16 install as complete.
p = work / 'src' / 'tracks_ui.py'
tracks = p.read_text(encoding='utf-8')
tracks = tracks.replace("getattr(app, '_tracks_ui_version', '') == '0.5.16'", "getattr(app, '_tracks_ui_version', '') == '0.5.17'")
tracks = tracks.replace("app._tracks_ui_version = '0.5.16'", "app._tracks_ui_version = '0.5.17'")
p.write_text(tracks, encoding='utf-8')

# Harden future updater downloads. The current 0.5.15/0.5.16 client only needs this small package once;
# after 0.5.17 is installed it gains multiple GitHub binary routes automatically.
p = work / 'src' / 'updater.py'
up = p.read_text(encoding='utf-8')
up = re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+', f'MXB-Race-Day-Live-Updater/{VERSION}', up)
start = up.find('def download_update(manifest):')
end = up.find('\n\ndef _install_root():', start)
if start < 0 or end < 0:
    raise SystemExit('download_update anchors missing')
new_download = r'''def download_update(manifest):
    manifest = _normalize_manifest(manifest)
    filename = Path(str(manifest['url']).split('?', 1)[0]).name or f"MXB_Race_Day_Live_v{manifest['version'].replace('.', '_')}_UPDATE.zip"
    out = Path(tempfile.gettempdir()) / filename
    tmp = out.with_suffix(out.suffix + '.part')
    expected = manifest.get('sha256') or ''

    candidates = [(manifest['url'], 'application/octet-stream')]
    if filename:
        candidates.append((
            f'https://github.com/{REPO}/raw/refs/heads/{BRANCH}/race-control/releases/{filename}',
            'application/octet-stream',
        ))
        candidates.append((
            f'https://api.github.com/repos/{REPO}/contents/race-control/releases/{filename}?ref={BRANCH}',
            'application/vnd.github.raw+json',
        ))

    errors = []
    for base_url, accept in candidates:
        tmp.unlink(missing_ok=True)
        h = hashlib.sha256()
        try:
            sep = '&' if '?' in base_url else '?'
            url = f'{base_url}{sep}_mxb={time.time_ns()}'
            req = urllib.request.Request(url, headers={
                'User-Agent': USER_AGENT,
                'Accept': accept,
                'Cache-Control': 'no-cache, no-store, max-age=0',
                'Pragma': 'no-cache',
            })
            with urllib.request.urlopen(req, timeout=120) as src, tmp.open('wb') as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    h.update(chunk)
            digest = h.hexdigest()
            if expected and digest.lower() != expected.lower():
                raise RuntimeError(f'SHA-256 mismatch: expected {expected}, got {digest}')
            if not zipfile.is_zipfile(tmp):
                raise RuntimeError('downloaded payload is not a ZIP package')
            os.replace(tmp, out)
            return out
        except Exception as exc:
            errors.append(f'{base_url}: {exc}')
            tmp.unlink(missing_ok=True)

    raise RuntimeError('Update download failed on every GitHub route. ' + ' | '.join(errors))
'''
up = up[:start] + new_download + up[end:]
p.write_text(up, encoding='utf-8')

# Keep the cache epoch explicit so stale/wrong track thumbnails cannot survive the recovery update.
p = work / 'src' / 'track_media.py'
media = p.read_text(encoding='utf-8')
media, n = re.subn(
    r"TRACK_MEDIA_CACHE_EPOCH\s*=\s*['\"][^'\"]+['\"]",
    "TRACK_MEDIA_CACHE_EPOCH = 'v0517-tracks-recovery'",
    media,
    count=1,
)
if n != 1:
    raise SystemExit('track cache epoch anchor missing')
p.write_text(media, encoding='utf-8')

required = [
    'app.py',
    'src/app.py',
    'src/config.py',
    'src/updater.py',
    'src/__init__.py',
    'src/profile_first_ui.py',
    'src/tracks_ui.py',
    'src/track_media.py',
]
for rel in required:
    if not (work / rel).is_file():
        raise SystemExit(f'lean recovery missing {rel}')

for rel in required:
    if rel.endswith('.py'):
        py_compile.compile(str(work / rel), doraise=True)

app = (work / 'src/app.py').read_text(encoding='utf-8')
tracks = (work / 'src/tracks_ui.py').read_text(encoding='utf-8')
profile = (work / 'src/profile_first_ui.py').read_text(encoding='utf-8')
media = (work / 'src/track_media.py').read_text(encoding='utf-8')
up = (work / 'src/updater.py').read_text(encoding='utf-8')
assert "VERSION = '0.5.17'" in (work / 'src/config.py').read_text(encoding='utf-8'), 'gate:version'
assert 'v0.5.17 Tracks recovery install' in app, 'gate:forced_hot_tracks_reinstall'
assert "app._tracks_ui_version = '0.5.17'" in tracks, 'gate:tracks_installer_generation'
assert "('TRACKS', 'TRACKS', 92)" in profile, 'gate:tracks_top_nav'
assert "TRACK_MEDIA_CACHE_EPOCH = 'v0517-tracks-recovery'" in media, 'gate:cache_refresh'
assert 'application/vnd.github.raw+json' in up and 'timeout=120' in up, 'gate:multi_route_updater'
assert "Update download failed on every GitHub route" in up, 'gate:clear_download_failure'
for venue in ('Millville Club', 'RedBud Club', 'Fox Raceway', 'Anaheim Stadium', 'San Diego Stadium'):
    assert venue in media, 'gate:verified_track:'+venue

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel in required:
        z.write(work / rel, rel)

digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest = {
    'version': VERSION,
    'url': f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}',
    'sha256': digest,
    'notes': NOTES,
}
Path('race-control/latest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print('RECOVERY UPDATE GATE', {
    'version': VERSION,
    'lean_files': len(required),
    'forced_tracks_reinstall': True,
    'multi_route_future_downloads': True,
})
print('BUILT', OUT, OUT.stat().st_size, digest)
