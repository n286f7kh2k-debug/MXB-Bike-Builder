from pathlib import Path
import re,zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_2_UPDATE.zip')
with zipfile.ZipFile(base) as z:
 s=z.read('src/app.py').decode('utf-8','replace')
print('APP_BYTES',len(s))
for pat in ['^from \\.mx_agent','class RaceDayLiveApp','def __init__','def _build_sidebar','def render_profile','def _profile_races','def open_race_details','def signup_demo','def _start_mx_sync','def _apply_mx_environment','def _profile_settings','def render_find']:
 print('\n===== '+pat+' =====')
 for m in list(re.finditer(pat,s,re.I|re.M))[:3]:
  a=max(0,m.start()-400); b=min(len(s),m.end()+7500)
  print(s[a:b].replace('\r',''))
