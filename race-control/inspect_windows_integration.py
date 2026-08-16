from pathlib import Path
import zipfile
candidates=[
 Path('race-control/releases/MXB_Race_Day_Live_v0_2_0_UPDATE.zip'),
 Path('race-control/releases/MXB_Race_Day_Live_v0_2_3_UPDATE.zip'),
 Path('race-control/releases/MXB_Race_Day_Live_v0_2_4_UPDATE.zip'),
]
for p in candidates:
 print('\n###',p)
 if not p.exists() or not zipfile.is_zipfile(p):print('missing');continue
 with zipfile.ZipFile(p) as z:
  names=z.namelist()
  for n in names:
   if 'windows' in n.lower() or 'icon' in n.lower() or 'shortcut' in n.lower() or n.lower().endswith(('.ico','.png')):
    print('FILE',n)
    try:
     data=z.read(n)
     if n.lower().endswith('.py'):print(data.decode('utf-8','replace')[:20000])
     else:print('binary',len(data),data[:16].hex())
    except Exception as e:print('ERR',e)
