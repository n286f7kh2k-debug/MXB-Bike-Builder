from pathlib import Path
import tempfile, zipfile
BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_0_UPDATE.zip')
if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('missing v0.5.0')
work=Path(tempfile.mkdtemp(prefix='mxb_v050_methods_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
app=(work/'src/app.py').read_text(encoding='utf-8')
db=(work/'src/database.py').read_text(encoding='utf-8') if (work/'src/database.py').exists() else ''

def method(name):
    needle='\n    def '+name+'('
    s=app.find(needle)
    if s<0:return f'MISSING METHOD: {name}\n'
    s+=1
    e=app.find('\n    def ',s+8)
    if e<0:e=len(app)
    return app[s:e]

def dump(path,names):
    text='\n\n'.join(method(n) for n in names)
    Path(path).write_text(text,encoding='utf-8')

dump('race-control/staging/v050_profile_methods.txt',['_profile_header','_profile_subnav','_profile_overview','_profile_my_races','_profile_settings'])
dump('race-control/staging/v050_wallet_methods.txt',['_profile_wallet','rider','do_signup','open_race_details'])
dump('race-control/staging/v050_findrace_methods.txt',['page_upcoming','open_race_details','race_card','eligible','race_class_label'])
dump('race-control/staging/v050_navigation_methods.txt',['_layout','show','_set_profile_section'])
Path('race-control/staging/v050_database_schema.txt').write_text(db[:60000],encoding='utf-8')
print('WROTE V050 METHOD INSPECTION')
