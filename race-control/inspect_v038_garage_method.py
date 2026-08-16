from pathlib import Path
import zipfile
p=Path('race-control/releases/MXB_Race_Day_Live_v0_3_8_UPDATE.zip')
with zipfile.ZipFile(p) as z:
    app=z.read('src/app.py').decode('utf-8','replace')
start=app.index('    def _profile_bikes(self,r):')
end=app.index('\n    def ',start+10)
print(app[start:end])
