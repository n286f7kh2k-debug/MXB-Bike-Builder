from pathlib import Path
import re, tempfile, zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_1_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='inspect031_'))
with zipfile.ZipFile(base) as z: z.extractall(work)
for rel in ['src/database.py','src/app.py']:
 p=work/rel
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 print('\n===== '+rel+' =====')
 pats=['def register_with_wallet','CREATE TABLE registrations','CREATE TABLE payment_transactions','def wallet_debit','def wallet_credit','def current_purse','def fastest_lap_pool','def race_financials']
 for pat in pats:
  print('\n---',pat,'---')
  for m in list(re.finditer(pat,s,re.I))[:6]:
   a=max(0,m.start()-500); b=min(len(s),m.end()+2500)
   print(s[a:b].replace('\r',''))
