from pathlib import Path
import tempfile,zipfile
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_5_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='inspect_v035_hot_'))
with zipfile.ZipFile(base) as z:z.extractall(work)
app=(work/'src/app.py').read_text(encoding='utf-8')
for needle,span in [('def _run_mx_sync',4500),('def _apply_mx_environment',5000),('def _refresh_live_widgets',7500),('def page_live',6500),('def page_upcoming',8000),('def _track_photo',5000),('def _set_profile_section',2000)]:
    i=app.find(needle)
    print('\n===== '+needle+' =====')
    print(app[i:i+span] if i>=0 else 'NOT FOUND')
