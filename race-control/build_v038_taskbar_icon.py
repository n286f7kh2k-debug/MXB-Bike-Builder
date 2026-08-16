from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_3_7_UPDATE.zip')
TASKBAR=Path('race-control/windows_taskbar_v038.py')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_3_8_UPDATE.zip')
NOTES=('MXB Race Day Live v0.3.8: fixes the Windows taskbar icon at the native HWND/shell level. '
       'Race Day Live now uses a fresh AppUserModelID to bypass stale Python/Tk icon caching, applies the packaged Race Day Live ICO directly '
       'with WM_SETICON for both large and small taskbar icons, assigns the class icons to the real top-level Windows HWND, and re-applies the '
       'icon after the window maps so Tk/Windows cannot replace it during startup. Existing Garage, performance optimizations, updater/restart, '
       'one-click joining, memberships, wallet, race economics, track artwork, results and admin controls are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('v0.3.7 base missing or invalid')
if not TASKBAR.exists():raise SystemExit('taskbar bridge source missing')
work=Path(tempfile.mkdtemp(prefix='mxb_v038_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(TASKBAR,work/'src/windows_taskbar.py')

# Version markers.
for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel; s=p.read_text(encoding='utf-8'); s=re.sub(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '0.3.8'",s); p.write_text(s,encoding='utf-8')
p=work/'src/updater.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+','MXB-Race-Day-Live-Updater/0.3.8',s); p.write_text(s,encoding='utf-8')

# Validate that the actual packaged desktop logo is a Windows ICO before publishing.
ico=work/'assets/mxb_race_day_live.ico'
if not ico.is_file():raise SystemExit('Race Day Live ICO asset is missing from the release')
data=ico.read_bytes()
if len(data)<32 or data[:4]!=b'\x00\x00\x01\x00':raise SystemExit('Race Day Live taskbar asset is not a valid ICO file')
count=int.from_bytes(data[4:6],'little')
if count<1:raise SystemExit('Race Day Live ICO contains no icon images')
print('ICO VERIFIED',ico,len(data),'images',count)

# Patch the actual running Tk app.
p=work/'src/app.py'; app=p.read_text(encoding='utf-8')

# Fresh shell identity avoids Windows reusing the old Python/Tk icon cache.
app=app.replace("APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'","APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v2'")
if "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v2'" not in app:raise SystemExit('AppUserModelID anchor missing')

# Native taskbar bridge import.
imp='from .windows_taskbar import apply_taskbar_identity, release_taskbar_icons\n'
if imp not in app:
    anchors=['from .bike_garage import MXBikeGarage, BikeGarageError\n','from .game_bridge import MXGameBridge, GameBridgeError, ensure_game_bridge_schema\n']
    for anchor in anchors:
        if anchor in app:
            app=app.replace(anchor,anchor+imp,1); break
    else:raise SystemExit('Could not insert Windows taskbar bridge import')

# Replace the earlier Tk-only icon assignment with Tk fallback + direct Win32 application after mapping.
old="""        try:
            icon_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),'assets','mxb_race_day_live.ico')
            self.iconbitmap(default=icon_path)
            if Image is not None and ImageTk is not None:
                with Image.open(icon_path) as icon_im:
                    icon_im=icon_im.convert('RGBA'); icon_im.thumbnail((256,256),Image.Resampling.LANCZOS)
                    self._taskbar_icon=ImageTk.PhotoImage(icon_im.copy())
                self.iconphoto(True,self._taskbar_icon)
        except Exception:pass"""
new="""        self._taskbar_icon_path=os.path.join(os.path.dirname(os.path.dirname(__file__)),'assets','mxb_race_day_live.ico')
        self._taskbar_icon=None
        try:
            self.iconbitmap(default=self._taskbar_icon_path)
            if Image is not None and ImageTk is not None:
                with Image.open(self._taskbar_icon_path) as icon_im:
                    icon_im=icon_im.convert('RGBA'); icon_im.thumbnail((256,256),Image.Resampling.LANCZOS)
                    self._taskbar_icon=ImageTk.PhotoImage(icon_im.copy())
                self.iconphoto(True,self._taskbar_icon)
        except Exception:pass
        try:self.update_idletasks()
        except Exception:pass
        self.after_idle(self._apply_windows_taskbar_icon)
        self.after(250,self._apply_windows_taskbar_icon)
        self.after(1000,self._apply_windows_taskbar_icon)
        try:self.bind('<Map>',lambda e:self.after_idle(self._apply_windows_taskbar_icon),add='+')
        except Exception:pass"""
if old in app:app=app.replace(old,new,1)
elif 'self._taskbar_icon_path=' not in app:raise SystemExit('Tk taskbar icon assignment anchor missing')

# Direct HWND icon method. This intentionally re-applies after map because Windows/Tk can reset class/window icons during initial mapping.
method=r'''    def _apply_windows_taskbar_icon(self):
        try:
            return apply_taskbar_identity(self,self._taskbar_icon_path,APP_USER_MODEL_ID)
        except Exception:
            return False

'''
anchor='    def _on_close(self):\n'
if '    def _apply_windows_taskbar_icon(self):\n' not in app:
    if anchor not in app:raise SystemExit('taskbar method insertion anchor missing')
    app=app.replace(anchor,method+anchor,1)

# Release native icon handles only when the whole app closes.
close_anchor="    def _on_close(self):\n"
start=app.index(close_anchor)
end=app.find('\n    def ',start+len(close_anchor))
if end<0:end=len(app)
close_block=app[start:end]
if 'release_taskbar_icons()' not in close_block:
    needle='        try:self.conn.close()\n        except Exception:pass\n'
    if needle in close_block:
        close_block=close_block.replace(needle,needle+"        try:release_taskbar_icons()\n        except Exception:pass\n",1)
    else:
        needle='        self.destroy()'
        if needle not in close_block:raise SystemExit('Could not patch taskbar icon cleanup')
        close_block=close_block.replace(needle,"        try:release_taskbar_icons()\n        except Exception:pass\n"+needle,1)
    app=app[:start]+close_block+app[end:]

p.write_text(app,encoding='utf-8')

# Compile every Python file in the shipped overlay.
for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
taskc=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
bridgec=(work/'src/game_bridge.py').read_text(encoding='utf-8')
garc=(work/'src/bike_garage.py').read_text(encoding='utf-8')
rendc=(work/'src/native_renderer.py').read_text(encoding='utf-8')
updater=(work/'src/updater.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')

# Taskbar-specific hard gates.
assert "VERSION = '0.3.8'" in config
assert "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v2'" in appc
assert 'apply_taskbar_identity' in appc and 'self._apply_windows_taskbar_icon' in appc
assert "self.bind('<Map>'" in appc and 'self.after(250,self._apply_windows_taskbar_icon)' in appc and 'self.after(1000,self._apply_windows_taskbar_icon)' in appc
assert 'WM_SETICON = 0x0080' in taskc and 'ICON_BIG = 1' in taskc and 'ICON_SMALL = 0' in taskc
assert 'SetClassLongPtrW' in taskc and 'GetAncestor' in taskc and 'SetCurrentProcessExplicitAppUserModelID' in taskc
assert 'LoadImageW' in taskc and 'RedrawWindow' in taskc and 'release_taskbar_icons' in appc
assert ico.is_file() and ico.read_bytes()[:4]==b'\x00\x00\x01\x00'

# Everything already approved must survive this release unchanged.
for marker in ('GARAGE','JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver'):
    assert marker in appc
assert 'CREATE_SUSPENDED' in rendc and '_start_window_cloak' in rendc and 'SW_SHOWNA=8' in rendc
assert 'lru_cache' in garc and 'invalidate_cache' in garc and 'profile.race_day_live_backup.ini' in garc
assert '-directconnect' in bridgec and 'self._game_exe_cache' in bridgec
assert 'api.github.com/repos/' in updater and 'latest.json' in updater and 'schedule_restart' in updater
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc
assert "if not force and name==previous" in appc

with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':'0.3.8','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_8_UPDATE.zip','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('V038 VERIFIED',{'ico_valid':True,'fresh_app_user_model_id':True,'wm_seticon_big_small':True,'class_icon_hwnd':True,'map_reapply':True,'tk_fallback':True,'v037_garage_preserved':True,'performance_preserved':True})
print('BUILT',OUT,digest)
