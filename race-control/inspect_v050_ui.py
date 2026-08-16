from pathlib import Path
import re, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_0_UPDATE.zip')
if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit(f'missing/invalid {BASE}')
work=Path(tempfile.mkdtemp(prefix='mxb_inspect_v050_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
app=(work/'src/app.py').read_text(encoding='utf-8')
wallet=''
for candidate in ('src/wallet.py','src/wallet_service.py','src/payments.py'):
    p=work/candidate
    if p.exists():
        wallet += f'\n\n===== {candidate} =====\n'+p.read_text(encoding='utf-8')[:24000]

def section(label, needles, radius=4500):
    hits=[]
    low=app.lower()
    for needle in needles:
        pos=low.find(needle.lower())
        if pos>=0:
            start=max(0,pos-radius); end=min(len(app),pos+radius)
            hits.append(f'--- needle: {needle} @ {pos} ---\n'+app[start:end])
    return f'\n\n===== {label} =====\n'+'\n\n'.join(hits)

out=[]
out.append('VERSION 0.5.0 CURRENT UI INSPECTION')
out.append(section('PROFILE',['def page_profile','def show_profile','MY PROFILE','PROFILE SETTINGS','My Races','MY RACES','banner','profile picture']))
out.append(section('FIND RACE',['def page_find','FIND A RACE','Find a Race','JOIN RACE SERVER','event card','signup']))
out.append(section('WALLET UI',['def page_wallet','WALLET','ADD FUNDS','balance','transaction']))
out.append(section('NAVIGATION',['nav_items','Paddock','PROFILE SETTINGS','WALLET','FIND A RACE']))
out.append(wallet)
text='\n'.join(out)
# Keep file comfortably under connector limits while preserving all first-hit contexts.
Path('race-control/staging/v050_current_ui.txt').write_text(text[:180000],encoding='utf-8')
print('WROTE UI INSPECTION',len(text[:180000]))
