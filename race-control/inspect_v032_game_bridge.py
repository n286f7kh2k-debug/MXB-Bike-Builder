from pathlib import Path
import re, tempfile, zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_2_UPDATE.zip')
if not base.exists() or not zipfile.is_zipfile(base): raise SystemExit('v0.3.2 release missing or invalid')
work=Path(tempfile.mkdtemp(prefix='inspect032_agent_'))
with zipfile.ZipFile(base) as z:z.extractall(work)
for rel in ['src/mx_agent.py','src/database.py']:
 p=work/rel
 if not p.exists():
  print('MISSING',rel); continue
 s=p.read_text(encoding='utf-8',errors='replace')
 print('\n===== '+rel+' =====')
 pats=['class MXRaceAgent','def discover','def sync','def prepare_race','def start_race_server','def stop_race_server','def diagnostics','bikes_found','mods','profiles','steam','mxbikes','server','game_port','live_port','CREATE TABLE races','ALTER TABLE races']
 for pat in pats:
  print('\n--- '+pat+' ---')
  for m in list(re.finditer(pat,s,re.I))[:10]:
   a=max(0,m.start()-900); b=min(len(s),m.end()+5000)
   print(s[a:b].replace('\r',''))
