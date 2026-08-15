from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_2_7_UPDATE.zip')
PATCH = Path('race-control/releases/MXB_Race_Day_Live_v0_2_8_UPDATE.zip')
OUT = PATCH
NOTES = ('MXB Race Day Live v0.2.8: complete update package containing the working live updater and automatic restart path from v0.2.7, the corrected Find a Race track-image mapping and stale-image cache reset, plus a fix that always re-enables the UPDATE button after an update error.')

for p in (BASE, PATCH):
    if not p.exists() or not zipfile.is_zipfile(p):
        raise SystemExit(f'Missing or invalid ZIP: {p}')

work = Path(tempfile.mkdtemp(prefix='mxb_v028_complete_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

with zipfile.ZipFile(PATCH) as z:
    for rel in ('src/config.py', 'src/track_media.py'):
        if rel not in z.namelist():
            raise SystemExit(f'Patch package missing {rel}')
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(rel))

# Keep all version markers aligned.
cfg = work / 'src/config.py'
s = cfg.read_text(encoding='utf-8')
s = re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.2.8'", s)
cfg.write_text(s, encoding='utf-8')

init = work / 'src/__init__.py'
if init.exists():
    s = init.read_text(encoding='utf-8')
    s = re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]", "__version__ = '0.2.8'", s)
    init.write_text(s, encoding='utf-8')
else:
    init.write_text("__version__ = '0.2.8'\n", encoding='utf-8')

# Fix the failure path that could leave UPDATE disabled forever after a bad package.
app_path = work / 'src/app.py'
app = app_path.read_text(encoding='utf-8')
old_error = "            except Exception as e:self.after(0,lambda:(self.update_btn.configure(state='normal',text='UPDATE'),messagebox.showerror('Update Failed',str(e))))"
new_error = "            except Exception as e:\n                msg=str(e)\n                self.after(0,lambda msg=msg:(self.update_btn.configure(state='normal',text='UPDATE'),messagebox.showerror('Update Failed',msg)))"
if old_error not in app:
    raise SystemExit('Expected UPDATE error-handler line was not found')
app = app.replace(old_error, new_error, 1)
app_path.write_text(app, encoding='utf-8')

# Match the updater's real package requirements, then verify our additional files.
required = [
    'app.py', 'src/app.py', 'src/config.py', 'src/updater.py',
    'src/track_media.py', 'Start MXB Race Day Live.vbs'
]
for rel in required:
    if not (work / rel).exists():
        raise SystemExit(f'Complete update is missing {rel}')

# Regression checks for the exact failures seen in v0.2.8.
up = (work / 'src/updater.py').read_text(encoding='utf-8')
if '_manifest_from_github_api' not in up:
    raise SystemExit('Live GitHub API update checker missing')
if 'schedule_restart' not in up:
    raise SystemExit('Automatic restart watchdog missing')
app = (work / 'src/app.py').read_text(encoding='utf-8')
if 'def do_update' not in app or 'check_for_update()' not in app or 'launch_update(z)' not in app:
    raise SystemExit('In-app UPDATE button path missing')
if 'lambda msg=msg' not in app:
    raise SystemExit('UPDATE button recovery fix missing')
tm = (work / 'src/track_media.py').read_text(encoding='utf-8')
for marker in ('DIRECT_TRACK_SOURCES', 'Millville', 'RedBud', 'Pala', 'Anaheim', 'San Diego', 'TRACK_MEDIA_CACHE_EPOCH'):
    if marker not in tm:
        raise SystemExit(f'Track-image fix marker missing: {marker}')

for rel in ('app.py','src/app.py','src/config.py','src/updater.py','src/track_media.py'):
    py_compile.compile(str(work / rel), doraise=True)

new_zip = OUT.with_suffix('.fixed.tmp.zip')
with zipfile.ZipFile(new_zip, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(work.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            z.write(p, p.relative_to(work).as_posix())

with zipfile.ZipFile(new_zip) as z:
    names = set(z.namelist())
    missing = [rel for rel in required if rel not in names]
    if missing:
        raise SystemExit('Final ZIP incomplete: ' + ', '.join(missing))
    if 'src/__init__.py' not in names:
        raise SystemExit('Final ZIP missing generated version marker')

shutil.move(str(new_zip), str(OUT))
digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest = {
    'version': '0.2.8',
    'url': 'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_2_8_UPDATE.zip',
    'sha256': digest,
    'notes': NOTES,
}
Path('race-control/latest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print('Rebuilt complete v0.2.8:', OUT)
print('sha256:', digest)
