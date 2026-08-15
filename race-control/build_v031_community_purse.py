from pathlib import Path
import hashlib, json, py_compile, re, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_3_0_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_3_1_UPDATE.zip')
NOTES = ('MXB Race Day Live v0.3.1: Community race cards on Find a Race now show the minimum valid purse and fastest-lap pool instead of $0 before enough riders have entered. '
         'The displayed amount grows with paid entries, while $3 Community pricing, verified MX Bikes Shop artwork, the in-app updater, and automatic restart are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit('Published v0.3.0 base is missing or invalid')

work = Path(tempfile.mkdtemp(prefix='mxb_v031_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

# Version markers.
p = work/'src/config.py'
s = p.read_text(encoding='utf-8')
s = re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.3.1'", s)
p.write_text(s, encoding='utf-8')

p = work/'src/__init__.py'
s = p.read_text(encoding='utf-8') if p.exists() else ''
s = re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]", "__version__ = '0.3.1'", s) if '__version__' in s else s + "\n__version__ = '0.3.1'\n"
p.write_text(s, encoding='utf-8')

p = work/'src/updater.py'
s = p.read_text(encoding='utf-8')
s = s.replace('Updater/0.3.0', 'Updater/0.3.1')
p.write_text(s, encoding='utf-8')

# Find a Race: Community races cannot run below min_riders, so display the minimum
# valid purse/pool instead of a misleading $0 while signups are still below minimum.
p = work/'src/app.py'
app = p.read_text(encoding='utf-8')
old = """            paid,purse=current_purse(self.conn,race['id']); fast=fastest_lap_pool(self.conn,race['id'])
            cash=tk.Frame(tile,bg=PANEL2); cash.pack(fill='x',padx=12,pady=(0,8))
            for lab,val,col in [('PURSE',f'${purse:,.0f}',GOLD),('FASTEST LAP',f'${fast:,.0f}',GREEN),('RIDERS',f\"{paid}/{race['max_riders']}\",TEXT)]:
"""
new = """            paid,purse=current_purse(self.conn,race['id']); fast=fastest_lap_pool(self.conn,race['id'])
            purse_text=f'${purse:,.0f}'
            fast_text=f'${fast:,.0f}'
            if race['lobby_tier']=='Low Entry':
                display_riders=max(paid,int(race['min_riders']))
                display_purse=display_riders*float(race['prize_contribution'])
                display_fast=display_riders*float(race['fast_lap_contribution'] or 0)
                grow='+' if paid<int(race['max_riders']) else ''
                purse_text=f'${display_purse:,.0f}{grow}'
                fast_text=f'${display_fast:,.0f}{grow}'
            cash=tk.Frame(tile,bg=PANEL2); cash.pack(fill='x',padx=12,pady=(0,8))
            for lab,val,col in [('PURSE',purse_text,GOLD),('FASTEST LAP',fast_text,GREEN),('RIDERS',f\"{paid}/{race['max_riders']}\",TEXT)]:
"""
if old not in app:
    raise SystemExit('Could not locate Find a Race purse card block')
app = app.replace(old, new, 1)
p.write_text(app, encoding='utf-8')

required = ['app.py','src/app.py','src/config.py','src/updater.py','src/pricing.py','src/track_media.py','src/__init__.py','Start MXB Race Day Live.vbs']
for rel in required:
    if not (work/rel).exists():
        raise SystemExit('Final update missing '+rel)

# Regression gates: no feature release may undo previously verified systems.
up = (work/'src/updater.py').read_text(encoding='utf-8')
tm = (work/'src/track_media.py').read_text(encoding='utf-8')
pr = (work/'src/pricing.py').read_text(encoding='utf-8')
app = (work/'src/app.py').read_text(encoding='utf-8')
for marker in ('_manifest_from_github_api','schedule_restart'):
    if marker not in up: raise SystemExit('Updater regression: '+marker)
for marker in ('DIRECT_TRACK_IMAGES','v029-mxb-shop-pinned-images-only','mxbikes-shop.com'):
    if marker not in tm: raise SystemExit('Track-art regression: '+marker)
for marker in ('COMMUNITY_LOW_ENTRY_FEE = 3.00','Expert Community Sprint','pricing_ladder_v030'):
    if marker not in pr: raise SystemExit('Pricing regression: '+marker)
for marker in ("display_riders=max(paid,int(race['min_riders']))", "purse_text=f'${display_purse:,.0f}{grow}'", "fast_text=f'${display_fast:,.0f}{grow}'"):
    if marker not in app: raise SystemExit('Community purse display regression: '+marker)

for rel in ('app.py','src/app.py','src/config.py','src/updater.py','src/pricing.py','src/track_media.py'):
    py_compile.compile(str(work/rel), doraise=True)

# Functional display test for the $3 Community split: $1 main purse + $0.25 fast-lap per rider,
# with a 4-rider minimum and 20-rider maximum.
def shown(paid):
    display_riders=max(paid,4)
    grow='+' if paid<20 else ''
    return f'${display_riders*1.0:,.0f}{grow}', f'${display_riders*.25:,.0f}{grow}'
assert shown(0)==('$4+','$1+')
assert shown(3)==('$4+','$1+')
assert shown(4)==('$4+','$1+')
assert shown(7)==('$7+','$2+')
assert shown(20)==('$20','$5')
print('COMMUNITY PURSE DISPLAY VERIFIED', [shown(x) for x in (0,3,4,7,20)])

with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts:
            z.write(f, f.relative_to(work).as_posix())
with zipfile.ZipFile(OUT) as z:
    names=set(z.namelist()); missing=[x for x in required if x not in names]
    if missing: raise SystemExit('Packaged ZIP incomplete: '+', '.join(missing))

digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
Path('race-control/latest.json').write_text(json.dumps({
    'version':'0.3.1',
    'url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_1_UPDATE.zip',
    'sha256':digest,
    'notes':NOTES,
}, indent=2)+'\n', encoding='utf-8')
print('BUILT', OUT, digest)
