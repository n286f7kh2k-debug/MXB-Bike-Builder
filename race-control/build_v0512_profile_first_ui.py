from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_5_11_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_5_12_UPDATE.zip')
UI = Path('race-control/profile_ui_v0512.py')
LAUNCHER = Path('race-control/staging/MXB Race Day Live.exe')
VERSION = '0.5.12'
NOTES = (
    'MXB Race Day Live v0.5.12 introduces a profile-first Rider Hub interface while preserving the existing race, wallet, Garage, live broadcast, results, championships, rankings, membership and admin functionality. '
    'The rider profile is the landing page, the old always-visible left sidebar is replaced by a compact rounded top navigation bar, and the profile overview now uses large rounded-outline one-click sections for Find a Race, My Races, Garage, Wallet, Live, Results, Championships, Rankings, Profile Settings, Membership, MX Bikes sync and Admin Control when available. '
    'Profile photo, banner, skill status, etiquette, rider statistics, race snapshot and existing profile subpages remain connected to the same underlying data and actions.'
)

for p in (BASE, UI, LAUNCHER):
    if not p.exists():
        raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):
    raise SystemExit('v0.5.11 base missing/invalid')
if LAUNCHER.read_bytes()[:2] != b'MZ':
    raise SystemExit('branded launcher is not a Windows PE executable')

work = Path(tempfile.mkdtemp(prefix='mxb_v0512_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

for rel, var in [('src/config.py', 'VERSION'), ('src/__init__.py', '__version__')]:
    p = work / rel
    s = p.read_text(encoding='utf-8')
    s2, n = re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]", f"{var} = '{VERSION}'", s, count=1)
    if n != 1:
        raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2, encoding='utf-8')

p = work / 'src' / 'updater.py'
up = p.read_text(encoding='utf-8')
up = re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+', f'MXB-Race-Day-Live-Updater/{VERSION}', up)
p.write_text(up, encoding='utf-8')

# Preserve the v0.5.11 launcher/taskbar and real MX Bikes viewer fixes.
(work / 'assets' / 'bin').mkdir(parents=True, exist_ok=True)
shutil.copy2(LAUNCHER, work / 'assets' / 'bin' / 'MXB Race Day Live.exe')
shutil.copy2(UI, work / 'src' / 'profile_first_ui.py')

p = work / 'src' / 'app.py'
app = p.read_text(encoding='utf-8')
if 'install_profile_first_ui(self)' not in app:
    old = "self._styles(); self._layout(); self.show('PROFILE')"
    new = (
        "self._styles(); self._layout()\n"
        "        from .profile_first_ui import install_profile_first_ui\n"
        "        install_profile_first_ui(self)\n"
        "        self.show('PROFILE')"
    )
    if old not in app:
        pattern = r"self\._styles\(\);\s*self\._layout\(\);\s*self\.show\(['\"]PROFILE['\"]\)"
        app, n = re.subn(pattern, new, app, count=1)
        if n != 1:
            raise SystemExit('profile-first UI install anchor missing in src/app.py')
    else:
        app = app.replace(old, new, 1)
p.write_text(app, encoding='utf-8')

for py in work.rglob('*.py'):
    py_compile.compile(str(py), doraise=True)

app = (work / 'src' / 'app.py').read_text(encoding='utf-8')
ui = (work / 'src' / 'profile_first_ui.py').read_text(encoding='utf-8')
assert "VERSION = '0.5.12'" in (work / 'src' / 'config.py').read_text(encoding='utf-8'), 'gate:version'
assert 'install_profile_first_ui(self)' in app, 'gate:ui_install'
assert 'class RoundedTile' in ui and 'class RoundedPill' in ui, 'gate:rounded_components'
assert "app.nav.pack_forget()" in ui, 'gate:left_nav_retired'
assert "app.content.pack(side='top', fill='both', expand=True)" in ui, 'gate:expanded_content'
for target in ('UPCOMING', 'GARAGE', 'LIVE', 'RESULTS', 'CHAMPIONSHIPS', 'RANKINGS'):
    assert f"self.show('{target}')" in ui, f'gate:route:{target}'
for section in ('RACES', 'WALLET', 'SETTINGS'):
    assert f"self._set_profile_section('{section}')" in ui, f'gate:profile_section:{section}'
assert 'MEMBERSHIP' in ui and 'ADMIN CONTROL' in ui and 'SYNC MX BIKES' in ui, 'gate:retained_features'
assert 'NEXT ELIGIBLE RACE' in ui and 'LATEST RESULT' in ui, 'gate:profile_snapshot'
assert (work / 'assets' / 'bin' / 'MXB Race Day Live.exe').read_bytes()[:2] == b'MZ', 'gate:launcher_preserved'

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
Path('race-control/staging/rdl-launcher.ico').unlink(missing_ok=True)
print('UI GATE', {
    'profile_landing': True,
    'left_sidebar': False,
    'rounded_top_nav': True,
    'rounded_profile_tiles': True,
    'existing_routes_preserved': True,
})
print('BUILT', OUT, digest)
