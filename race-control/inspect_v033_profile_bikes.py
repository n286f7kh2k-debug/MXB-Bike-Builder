from pathlib import Path
import tempfile,zipfile,re
base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_3_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='inspect_v033_profile_'))
with zipfile.ZipFile(base) as z:z.extractall(work)
app=(work/'src/app.py').read_text(encoding='utf-8')
for name in ['def _profile_subnav','def page_profile','def _profile_settings','def _layout']:
    i=app.find(name)
    print('\n===== '+name+' =====')
    print(app[i:i+5000] if i>=0 else 'NOT FOUND')
root=(work/'app.py').read_text(encoding='utf-8') if (work/'app.py').exists() else ''
print('\n===== ROOT APP.PY =====')
print(root[:3500])
print('\n===== ASSETS =====')
for p in sorted(work.rglob('*')):
    if p.is_file() and ('asset' in str(p).lower() or p.suffix.lower() in ('.ico','.png','.jpg','.jpeg')):
        print(p.relative_to(work))
