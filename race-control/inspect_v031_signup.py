from pathlib import Path
import re, tempfile, zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_1_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='inspect031_'))
with zipfile.ZipFile(base) as z: z.extractall(work)
for rel in ['src/app.py','src/db.py','src/logic.py']:
 p=work/rel
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 print('\n===== '+rel+' =====')
 for pat in ['def .*register','def .*signup','def .*wallet','entry_fee','payment_status','registrations','ADD FUNDS','SIGN UP','ENTER RACE','JOIN RACE','Wallet']:
  print('\n---',pat,'---')
  for m in list(re.finditer(pat,s,re.I))[:12]:
   a=max(0,m.start()-700); b=min(len(s),m.end()+1500)
   print(s[a:b].replace('\r',''))
