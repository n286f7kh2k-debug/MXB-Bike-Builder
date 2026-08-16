from pathlib import Path
import zipfile
releases=Path('race-control/releases')
found=[]
for zpath in sorted(releases.glob('*.zip')):
    try:
        with zipfile.ZipFile(zpath) as z:
            names=set(z.namelist())
            hits=[x for x in ('src/mx_agent.py','src/database.py','src/commentary.py','src/broadcast.py') if x in names]
            if hits:
                found.append((zpath.name,hits))
                print('FOUND',zpath.name,hits)
    except Exception as exc:
        print('BADZIP',zpath.name,exc)
if not found: raise SystemExit('No core MX agent release located')
print('TOTAL',len(found))
