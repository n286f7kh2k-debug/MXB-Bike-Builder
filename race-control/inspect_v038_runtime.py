from pathlib import Path
import zipfile,re
p=Path('race-control/releases/MXB_Race_Day_Live_v0_3_8_UPDATE.zip')
if not p.exists() or not zipfile.is_zipfile(p):raise SystemExit('v038 missing')
with zipfile.ZipFile(p) as z:
    print('FILES')
    for n in z.namelist():print(n)
    def txt(name):return z.read(name).decode('utf-8','replace')
    app=txt('src/app.py')
    for needle in ['def _profile_bikes','def page_garage','native_renderer','APP_USER_MODEL_ID','def _apply_windows_taskbar_icon','def _on_close']:
        print('\n### APP',needle)
        i=app.find(needle)
        print(app[max(0,i-1800):i+6500] if i>=0 else 'NOT FOUND')
    for name in ['Start MXB Race Day Live.vbs','app.py','src/windows_taskbar.py','src/native_renderer.py']:
        print('\n### FILE',name)
        try:
            s=txt(name)
            if name=='src/native_renderer.py':
                for needle in ['class NativeMXRenderer','def start(','def restart(','subprocess.Popen','mxbikes.exe']:
                    i=s.find(needle); print('\n--',needle); print(s[max(0,i-800):i+3500] if i>=0 else 'NOT FOUND')
            else:print(s[:12000])
        except Exception as e:print('ERROR',e)
