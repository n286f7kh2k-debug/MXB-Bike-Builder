from pathlib import Path
import re,zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_2_0_UPDATE.zip')
with zipfile.ZipFile(base) as z:
 for rel in ['src/mx_agent.py','src/database.py']:
  s=z.read(rel).decode('utf-8','replace')
  print('\n===== '+rel+' =====')
  pats=['class MXEnvironment','class MXRaceAgent','def _discover','def discover','def sync','def sync_async','def prepare_race','def start_race_server','def stop_race_server','def diagnostics','def _scan','steam','install','profile','bikes','tracks','mods','game_port','live_port','server_process','CREATE TABLE races','CREATE TABLE game_sync_state','CREATE TABLE game_content']
  for pat in pats:
   print('\n--- '+pat+' ---')
   for m in list(re.finditer(pat,s,re.I))[:8]:
    a=max(0,m.start()-700);b=min(len(s),m.end()+4200)
    print(s[a:b].replace('\r',''))
