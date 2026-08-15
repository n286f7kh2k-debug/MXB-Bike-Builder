from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_2_9_UPDATE.zip')
PRICING = Path('race-control/pricing_v030.py')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_3_0_UPDATE.zip')
NOTES = ('MXB Race Day Live v0.3.0: Low Entry races are now $3 at every skill level so riders can race for only a few dollars, '
         'while Cash and Premier races keep their higher stakes. Existing installs migrate automatically without duplicate race cards, '
         'and the verified MX Bikes Shop artwork plus the working updater/restart path are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit('Published v0.2.9 base is missing or invalid')
if not PRICING.exists():
    raise SystemExit('Pricing migration module is missing')

work=Path(tempfile.mkdtemp(prefix='mxb_v030_'))
with zipfile.ZipFile(BASE) as z: z.extractall(work)
shutil.copy2(PRICING, work/'src/pricing.py')

# Version.
p=work/'src/config.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.3.0'", s); p.write_text(s,encoding='utf-8')
p=work/'src/__init__.py'; s=p.read_text(encoding='utf-8') if p.exists() else ''; s=re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]", "__version__ = '0.3.0'", s) if '__version__' in s else s+"\n__version__ = '0.3.0'\n"; p.write_text(s,encoding='utf-8')

# Hook the migration immediately after the existing database connection is opened.
p=work/'src/app.py'; app=p.read_text(encoding='utf-8')
import_line='from .pricing import apply_low_entry_pricing\n'
if import_line not in app:
    anchor='from .track_media import TrackMediaResolver\n'
    if anchor not in app: raise SystemExit('Could not locate pricing import anchor')
    app=app.replace(anchor, anchor+import_line, 1)
old="super().__init__(); seed(); self.conn=connect(); self.settings=load_settings(); self.current_rider='Welchy'"
new="super().__init__(); seed(); self.conn=connect(); apply_low_entry_pricing(self.conn); self.settings=load_settings(); self.current_rider='Welchy'"
if old not in app and new not in app: raise SystemExit('Could not locate startup pricing hook')
app=app.replace(old,new,1)
app=app.replace('Pick the stakes you want. Your eligible classes are prioritized automatically.','Pick the stakes you want. Low Entry races are just $3 at every skill level; higher-stakes Cash and Premier races are still available.')
old_ladder="data=[('Rookie','Low Entry','$5'),('Rookie','Open','$10'),('Amateur','Low Entry','$8'),('Amateur','Premier','$35'),('Expert','Low Entry','$12'),('Expert','Cash','$25–30'),('Expert','Premier','$50+'),('Pro','Low Entry','$20'),('Pro','Cash','$50+'),('Pro','Premier','$100+')]"
new_ladder="data=[('Rookie','Low Entry','$3'),('Rookie','Open','$10'),('Amateur','Low Entry','$3'),('Amateur','Premier','$35'),('Expert','Low Entry','$3'),('Expert','Cash','$25–30'),('Expert','Premier','$50+'),('Pro','Low Entry','$3'),('Pro','Cash','$50+'),('Pro','Premier','$100+')]"
if old_ladder not in app and new_ladder not in app: raise SystemExit('Could not locate admin pricing ladder')
app=app.replace(old_ladder,new_ladder)
p.write_text(app,encoding='utf-8')

required=['app.py','src/app.py','src/config.py','src/updater.py','src/pricing.py','src/track_media.py','src/__init__.py','Start MXB Race Day Live.vbs']
for rel in required:
    if not (work/rel).exists(): raise SystemExit('Final update missing '+rel)

# Preserve the pieces we already fixed. Feature releases fail if these regress.
up=(work/'src/updater.py').read_text(encoding='utf-8')
tm=(work/'src/track_media.py').read_text(encoding='utf-8')
pr=(work/'src/pricing.py').read_text(encoding='utf-8')
app=(work/'src/app.py').read_text(encoding='utf-8')
for marker in ('_manifest_from_github_api','schedule_restart'):
    if marker not in up: raise SystemExit('Updater regression: '+marker)
for marker in ('DIRECT_TRACK_IMAGES','v029-mxb-shop-pinned-images-only','mxbikes-shop.com'):
    if marker not in tm: raise SystemExit('Track-art regression: '+marker)
for marker in ('COMMUNITY_LOW_ENTRY_FEE = 3.00','Expert $12 Sprint','Expert Community Sprint','pricing_ladder_v030'):
    if marker not in pr: raise SystemExit('Pricing regression: '+marker)
if 'apply_low_entry_pricing(self.conn)' not in app or "('Expert','Low Entry','$3')" not in app:
    raise SystemExit('Pricing UI/startup hook missing')

for rel in ('app.py','src/app.py','src/config.py','src/updater.py','src/pricing.py','src/track_media.py'):
    py_compile.compile(str(work/rel),doraise=True)

# Functional migration test against the real race-table shape: one old row per class,
# then simulate a second startup where old seed() recreates those legacy names.
import sqlite3
c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
c.executescript('''CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE races(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,skill_class TEXT,lobby_tier TEXT,status TEXT,entry_fee REAL,prize_contribution REAL,fast_lap_contribution REAL,platform_fee REAL); CREATE TABLE registrations(id INTEGER PRIMARY KEY,race_id INTEGER,payment_status TEXT);''')
old=[('Rookie $5 Gate Drop','Rookie',5,2,.5,2.5),('Amateur $8 Gate Drop','Amateur',8,3.5,.5,4),('Expert $12 Sprint','Expert',12,5.5,.75,5.75),('Pro $20 Warm-Up','Pro',20,9.5,1.5,9)]
for name,skill,fee,main,fast,plat in old: c.execute("INSERT INTO races(name,skill_class,lobby_tier,status,entry_fee,prize_contribution,fast_lap_contribution,platform_fee) VALUES(?,?,'Low Entry','REGISTRATION',?,?,?,?)",(name,skill,fee,main,fast,plat))
ns={}; exec(compile(pr,'pricing.py','exec'),ns); ns['apply_low_entry_pricing'](c)
rows=list(c.execute("SELECT * FROM races ORDER BY skill_class")); assert len(rows)==4 and all(r['entry_fee']==3 for r in rows) and all('Community' in r['name'] for r in rows)
# Simulate old seed recreating four legacy rows, then cleanup again.
for name,skill,fee,main,fast,plat in old: c.execute("INSERT INTO races(name,skill_class,lobby_tier,status,entry_fee,prize_contribution,fast_lap_contribution,platform_fee) VALUES(?,?,'Low Entry','REGISTRATION',?,?,?,?)",(name,skill,fee,main,fast,plat))
ns['apply_low_entry_pricing'](c); rows=list(c.execute("SELECT * FROM races ORDER BY skill_class")); assert len(rows)==4, len(rows)
print('PRICING VERIFIED',[(r['skill_class'],r['name'],r['entry_fee']) for r in rows])

with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts: z.write(f,f.relative_to(work).as_posix())
with zipfile.ZipFile(OUT) as z:
    names=set(z.namelist()); missing=[x for x in required if x not in names]
    if missing: raise SystemExit('Packaged ZIP incomplete: '+', '.join(missing))
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
Path('race-control/latest.json').write_text(json.dumps({'version':'0.3.0','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_0_UPDATE.zip','sha256':digest,'notes':NOTES},indent=2)+'\n',encoding='utf-8')
print('BUILT',OUT,digest)
