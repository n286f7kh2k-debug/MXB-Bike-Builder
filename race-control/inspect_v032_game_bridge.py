from pathlib import Path
import re, tempfile, zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_2_UPDATE.zip')
if not base.exists() or not zipfile.is_zipfile(base):
    raise SystemExit('v0.3.2 release missing or invalid')
work=Path(tempfile.mkdtemp(prefix='inspect032_bridge_'))
with zipfile.ZipFile(base) as z:z.extractall(work)
p=work/'src/app.py'
s=p.read_text(encoding='utf-8',errors='replace')
for pat in ['def open_race_details','def _profile_settings','def _profile_overview','def render_find','server','password','bike','track','def __init__','class App']:
    print('\n--- '+pat+' ---')
    for m in list(re.finditer(pat,s,re.I))[:8]:
        a=max(0,m.start()-900); b=min(len(s),m.end()+4200)
        print(s[a:b].replace('\r',''))
