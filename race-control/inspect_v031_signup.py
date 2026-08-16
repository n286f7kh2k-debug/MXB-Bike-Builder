from pathlib import Path
import re, tempfile, zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_2_5_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='inspectcore_'))
with zipfile.ZipFile(base) as z:
 print('ZIP FILES', [n for n in z.namelist() if 'data' in n.lower() or 'wallet' in n.lower() or n.endswith('.py')])
 z.extractall(work)
for p in work.rglob('*.py'):
 s=p.read_text(encoding='utf-8',errors='replace')
 if 'def register_with_wallet' not in s: continue
 print('\n===== '+str(p.relative_to(work))+' =====')
 for pat in ['def register_with_wallet','CREATE TABLE registrations','CREATE TABLE payment_transactions','def wallet_debit','def wallet_credit','def wallet_balance','def current_purse','def fastest_lap_pool','def race_financials']:
  print('\n---',pat,'---')
  for m in list(re.finditer(pat,s,re.I))[:6]:
   a=max(0,m.start()-500); b=min(len(s),m.end()+3500)
   print(s[a:b].replace('\r',''))
