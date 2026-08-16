from pathlib import Path
import zipfile

candidates=[
    Path('race-control/releases/MXB_Race_Day_Live_v0_2_0_UPDATE.zip'),
    Path('race-control/releases/MXB_Race_Day_Live_v0_2_4_UPDATE.zip'),
    Path('race-control/releases/MXB_Race_Day_Live_v0_2_7_UPDATE.zip'),
    Path('race-control/releases/MXB_Race_Day_Live_v0_2_8_UPDATE.zip'),
    Path('race-control/releases/MXB_Race_Day_Live_v0_3_0_UPDATE.zip'),
    Path('race-control/releases/MXB_Race_Day_Live_v0_3_4_UPDATE.zip'),
]
for zpath in candidates:
    print('\nARCHIVE',zpath)
    if not zpath.exists() or not zipfile.is_zipfile(zpath):
        print('missing/invalid'); continue
    with zipfile.ZipFile(zpath) as z:
        names=z.namelist()
        hits=[n for n in names if n.lower().endswith(('.ico','.png','.jpg','.jpeg','.webp')) or 'icon' in n.lower() or 'logo' in n.lower()]
        print('entries',len(names),'visual_hits',len(hits))
        for name in hits:
            try:
                info=z.getinfo(name); data=z.read(name)
                print(' ',name,'size',info.file_size,'magic',data[:12].hex())
            except Exception as exc:
                print(' ',name,'ERROR',repr(exc))
