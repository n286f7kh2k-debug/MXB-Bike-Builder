from pathlib import Path
import hashlib
import json
import py_compile
import re
import shutil
import tempfile
import zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_5_15_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_16_UPDATE.zip')
TRACKS_UI = Path('race-control/tracks_ui_v0516.py')
LAUNCHER = Path('race-control/staging/MXB Race Day Live.exe')
ICON = Path('race-control/staging/rdl-launcher.ico')
VERSION = '0.5.16'
NOTES = (
    'MXB Race Day Live v0.5.16 adds a dedicated Tracks section to the race-night top navigation. '
    'The new track library uses the same pinned MXB-Shop TrackMediaResolver mappings already used by Race Day Live, '
    'so each card shows the verified matching track artwork and opens the exact MXB-Shop release page instead of a search result or fuzzy match. '
    'The initial library includes Spring Creek/Millville, Buchanan/RedBud, Pala/Fox Raceway, Anaheim 1 and San Diego, '
    'with Race Day Live aliases shown on each card. Track media cache is refreshed for this release to prevent stale thumbnails. '
    'The v0.5.15 branded Windows process identity, hot updater, profile-first UI, Garage, race, wallet, live, results, championships and admin features are preserved.'
)

for p in (BASE, TRACKS_UI):
    if not p.exists():
        raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):
    raise SystemExit('v0.5.15 base missing/invalid')

work = Path(tempfile.mkdtemp(prefix='mxb_v0516_'))
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

p = work / 'src' / 'updater.py'
updater = p.read_text(encoding='utf-8')
updater = re.sub(
    r'MXB-Race-Day-Live-Updater/[0-9.]+',
    f'MXB-Race-Day-Live-Updater/{VERSION}',
    updater,
)
p.write_text(updater, encoding='utf-8')

shutil.copy2(TRACKS_UI, work / 'src' / 'tracks_ui.py')

p = work / 'src' / 'profile_first_ui.py'
profile_ui = p.read_text(encoding='utf-8')
tracks_nav = "        ('TRACKS', 'TRACKS', 92),\n"
if tracks_nav not in profile_ui:
    anchor = "        ('FIND A RACE', 'UPCOMING', 126),\n"
    if anchor not in profile_ui:
        raise SystemExit('top navigation FIND A RACE anchor missing in profile_first_ui.py')
    profile_ui = profile_ui.replace(anchor, anchor + tracks_nav, 1)
p.write_text(profile_ui, encoding='utf-8')

p = work / 'src' / 'app.py'
app = p.read_text(encoding='utf-8')

cold_anchor = '        install_profile_first_ui(self)\n'
cold_install = (
    "        from .tracks_ui import install_tracks_ui\n"
    "        install_tracks_ui(self)\n"
)
if cold_install not in app:
    if cold_anchor not in app:
        raise SystemExit('profile-first startup install anchor missing in src/app.py')
    app = app.replace(cold_anchor, cold_anchor + cold_install, 1)

hot_anchor = '    def _after_hot_reload(self,target_version,snapshot):\n'
hot_install = '''        # v0.5.16 Tracks install: bind the new route into this already-running window
        # and rebuild the compact nav so TRACKS appears immediately after hot update.
        if str(target_version).strip()=='0.5.16':
            try:
                from .tracks_ui import install_tracks_ui as _install_tracks_ui
                from .profile_first_ui import _make_top_nav as _rebuild_tracks_nav, _sync_top_nav as _sync_tracks_nav
                _install_tracks_ui(self)
                _rebuild_tracks_nav(self)
                _sync_tracks_nav(self)
            except Exception:
                pass
'''
if 'v0.5.16 Tracks install' not in app:
    if hot_anchor not in app:
        raise SystemExit('hot-refresh lifecycle anchor missing in src/app.py')
    app = app.replace(hot_anchor, hot_anchor + hot_install, 1)

p.write_text(app, encoding='utf-8')

p = work / 'src' / 'track_media.py'
track_media = p.read_text(encoding='utf-8')
if 'TRACK_MEDIA_CACHE_EPOCH' not in track_media:
    raise SystemExit('track media cache epoch missing')
track_media, n = re.subn(
    r"TRACK_MEDIA_CACHE_EPOCH\s*=\s*['\"][^'\"]+['\"]",
    "TRACK_MEDIA_CACHE_EPOCH = 'v0516-tracks-section-verified-pins'",
    track_media,
    count=1,
)
if n != 1:
    raise SystemExit('track media cache epoch replacement failed')
p.write_text(track_media, encoding='utf-8')

if LAUNCHER.is_file():
    if LAUNCHER.read_bytes()[:2] != b'MZ':
        raise SystemExit('staged MXB Race Day Live host is not a Windows PE executable')
    (work / 'assets' / 'bin').mkdir(parents=True, exist_ok=True)
    shutil.copy2(LAUNCHER, work / 'assets' / 'bin' / 'MXB Race Day Live.exe')
if ICON.is_file():
    (work / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ICON, work / 'assets' / 'mxb_race_day_live.ico')

for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

app = (work / 'src' / 'app.py').read_text(encoding='utf-8')
profile_ui = (work / 'src' / 'profile_first_ui.py').read_text(encoding='utf-8')
tracks_ui = (work / 'src' / 'tracks_ui.py').read_text(encoding='utf-8')
track_media = (work / 'src' / 'track_media.py').read_text(encoding='utf-8')
updater = (work / 'src' / 'updater.py').read_text(encoding='utf-8')

assert f"VERSION = '{VERSION}'" in (work / 'src' / 'config.py').read_text(encoding='utf-8'), 'gate:version'
assert "('TRACKS', 'TRACKS', 92)" in profile_ui, 'gate:tracks_nav'
assert 'install_tracks_ui(self)' in app, 'gate:cold_tracks_install'
assert 'v0.5.16 Tracks install' in app, 'gate:hot_tracks_install'
assert 'def _page_tracks(' in tracks_ui and 'def install_tracks_ui(' in tracks_ui, 'gate:tracks_route'
assert 'self._track_photo(' in tracks_ui, 'gate:existing_track_media_pipeline'
assert "TRACK_MEDIA_CACHE_EPOCH = 'v0516-tracks-section-verified-pins'" in track_media, 'gate:fresh_track_cache'

source_urls = (
    'https://mxbikes-shop.com/downloads/2024-arlmx-rd7-millville/',
    'https://mxbikes-shop.com/downloads/2025-arlmx-rd6-buchanan/',
    'https://mxbikes-shop.com/downloads/2025-arlmx-rd1-pala/',
    'https://mxbikes-shop.com/downloads/2025-fxr-arl-supercross-series-presented-by-motooption-round-1/',
    'https://www.mxbikes-shop.com/downloads/2023-arl-sx-round-02-san-diego/',
)
for url in source_urls:
    assert url in tracks_ui, 'gate:tracks_card_link:' + url
    assert url in track_media, 'gate:resolver_source_link:' + url

for alias in ('Millville Club', 'Spring Creek', 'RedBud Club', 'Fox Raceway', 'Anaheim Stadium', 'San Diego Stadium'):
    assert alias in track_media, 'gate:resolver_alias:' + alias

for image_marker in (
    'track_image_millville_1200x1200',
    'wp-content/uploads/2025/07/track_image-2.jpg',
    'wp-content/uploads/2025/05/track_image-3.jpg',
    'wp-content/uploads/2025/01/track_image.jpg',
    'wp-content/uploads/2023/01/thumbnailfinal-copie-1.png',
):
    assert image_marker in track_media, 'gate:verified_image:' + image_marker

assert 'mxb-mods.com' not in track_media and 'mymxb.com' not in track_media, 'gate:no_mirror_guessing'
assert '_manifest_from_github_api' in updater and 'schedule_restart' in updater, 'gate:updater_preserved'
assert 'install_profile_first_ui(self)' in app, 'gate:profile_ui_preserved'

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

print('TRACKS GATE', {
    'tracks_nav': True,
    'verified_mxb_shop_links': len(source_urls),
    'existing_track_media_pipeline': True,
    'cache_refresh': True,
    'mirror_guessing': False,
    'hot_update_route_install': True,
})
print('BUILT', OUT, digest)
