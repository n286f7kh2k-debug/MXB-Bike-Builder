from pathlib import Path
import tempfile,zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_5_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='inspect_v035_layout_'))
with zipfile.ZipFile(base) as z:z.extractall(work)
app=(work/'src/app.py').read_text(encoding='utf-8')
for needle,span in [('NAV = [',1800),('def show(',3500),('def clear(',1600),('def _profile_subnav',3000),('def _profile_bikes',17000),('def _layout',5000),('def _on_close',2200)]:
    i=app.find(needle)
    print('\n===== '+needle+' =====')
    print(app[i:i+span] if i>=0 else 'NOT FOUND')
