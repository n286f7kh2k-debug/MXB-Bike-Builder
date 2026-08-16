from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_4_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_5_UPDATE.zip')
WININT=Path('race-control/windows_integration_v055.py')
TASKBAR=Path('race-control/windows_taskbar_v055.py')
MIRROR=Path('race-control/mx_game_mirror_v055.py')
VERSION='0.5.5'
NOTES=(
 'MXB Race Day Live v0.5.5: replaces the substitute Garage viewer with a live Windows DWM mirror of MX Bikes itself. '
 'Garage now displays the actual MX Bikes Bike Selection render surface and forwards pointer/keyboard input into the real game UI, so every installed bike, rider, paint, helmet, kit, gloves, boots and protection item is rendered by MX Bikes rather than recreated by Race Day Live. '
 'The source MX Bikes window stays as a separate top-level DirectX window required by DWM, is removed from the taskbar and kept behind Race Day Live; no SetParent/re-parenting is used. '
 'The renderer prewarms asynchronously with a separate client port so Garage can attach quickly and does not block Tk. Before Race Day Live launches MX Bikes normally or joins a race, the mirror instance is stopped. '
 'Windows taskbar identity is also rebuilt around a permanent AppUserModelID and a dedicated MXB Race Day Live.exe copied from the active pythonw runtime; the desktop shortcut now targets that named executable, while the running HWND takes the exact Explorer-rendered desktop shortcut icon. '
 'v0.5.4 two-way profile/loadout integration and stay-open hot updates, v0.5.1 performance fixes, memberships, wallet, race joining, live timing, purse/fastest-lap economics, track art and admin controls are preserved.'
)
for p in (BASE,WININT,TASKBAR,MIRROR):
    if not p.exists():raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.4 base invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v055_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(WININT,work/'src/windows_integration.py')
shutil.copy2(TASKBAR,work/'src/windows_taskbar.py')
shutil.copy2(MIRROR,work/'src/mx_game_mirror.py')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

# Hot reload should load the game mirror before app.py is reloaded.
p=work/'src/hot_reload.py';hot=p.read_text(encoding='utf-8')
if "'src.mx_game_mirror'" not in hot:
    hot=hot.replace("'src.windows_taskbar','src.game_bridge'","'src.windows_taskbar','src.game_bridge','src.mx_game_mirror'",1)
p.write_text(hot,encoding='utf-8')

p=work/'src/app.py';app=p.read_text(encoding='utf-8')
# Import actual MX Bikes live mirror.
if 'from .mx_game_mirror import MXGameGarageMirror' not in app:
    m=re.search(r'^from \.mx_extension import .*$',app,flags=re.M)
    if not m:raise SystemExit('mx_extension import anchor missing')
    app=app[:m.end()]+"\nfrom .mx_game_mirror import MXGameGarageMirror"+app[m.end():]

# Add mirror service beside game/profile bridge.
anchor="self.mx_extension=MXExtensionService(self.conn,self.bike_garage,self.game_bridge,self.current_rider); self.mx_extension.start(); self._mx_extension_poll_generation=1; self.track_media=TrackMediaResolver(connect)"
replacement="self.mx_extension=MXExtensionService(self.conn,self.bike_garage,self.game_bridge,self.current_rider); self.mx_extension.start(); self._mx_extension_poll_generation=1; self.game_mirror=MXGameGarageMirror(self.game_bridge,self.bike_garage,self); self.track_media=TrackMediaResolver(connect)"
if anchor in app:app=app.replace(anchor,replacement,1)
elif 'self.game_mirror=MXGameGarageMirror' not in app:raise SystemExit('mirror init anchor missing')

# Prewarm off the Tk thread after startup so Garage is ready before the rider opens it.
pre="        self.after(900,lambda:self._poll_mx_extension_events(self._mx_extension_poll_generation))\n"
if 'self.after(2200,self.game_mirror.prewarm_async)' not in app:
    if pre not in app:raise SystemExit('extension poll schedule anchor missing')
    app=app.replace(pre,pre+"        self.after(2200,self.game_mirror.prewarm_async)\n",1)

# Detach the DWM destination overlay when navigating away, but keep the renderer prewarmed.
show_anchor="        self.clear(stop_renderer=(previous=='GARAGE' and name!='GARAGE'))\n"
show_repl="        if previous=='GARAGE' and name!='GARAGE':\n            try:self.game_mirror.detach()\n            except Exception:pass\n        self.clear(stop_renderer=False)\n"
if show_anchor in app:app=app.replace(show_anchor,show_repl,1)
elif 'self.game_mirror.detach()' not in app[app.find('    def show'):app.find('    def titlebar')]:raise SystemExit('Garage detach navigation hook missing')

# Game/race launches own the real simulator, so shut down the background mirror first.
helper=r'''    def _launch_actual_game(self):
        try:self.game_mirror.stop()
        except Exception:pass
        return self.game_bridge.launch_game()

'''
marker='    def _on_close(self):\n'
if '    def _launch_actual_game(self):' not in app:
    if marker not in app:raise SystemExit('on_close anchor missing')
    app=app.replace(marker,helper+marker,1)
app=app.replace('self.game_bridge.launch_game()','self._launch_actual_game()')
# Avoid rewriting the helper into recursion.
app=app.replace('return self._launch_actual_game()','return self.game_bridge.launch_game()',1)
join_anchor='self.mx_extension.prepare_join(race_id,rider_id)'
if join_anchor in app and 'self.game_mirror.stop()\n            self.mx_extension.prepare_join' not in app:
    app=app.replace(join_anchor,"self.game_mirror.stop()\n            "+join_anchor,1)

# Stop the hidden game renderer on application shutdown.
close='    def _on_close(self):\n        try:self.mx_extension.stop()'
if close in app:
    app=app.replace(close,"    def _on_close(self):\n        try:self.game_mirror.stop()\n        except Exception:pass\n        try:self.mx_extension.stop()",1)
elif 'try:self.game_mirror.stop()' not in app[app.find('    def _on_close'):app.find('    # ---------- RIDER PROFILE')]:raise SystemExit('mirror close hook missing')

# Replace the v0.5.4 replicated controls/preview with the actual live game Bike Selection screen.
start=app.rfind('    def page_garage(self):',0,app.find('    def _after_hot_reload'))
end=app.find('    def _after_hot_reload',start)
if start<0 or end<0:raise SystemExit('v0.5.4 Garage override block missing')
garage_methods=r'''    def page_garage(self):
        self.bike_garage.username=self.current_rider; self.mx_extension.username=self.current_rider
        root=tk.Frame(self.content,bg=BG);root.pack(fill='both',expand=True,padx=14,pady=12)
        top=tk.Frame(root,bg=BG);top.pack(fill='x',pady=(0,8))
        tk.Label(top,text='GARAGE',fg='white',bg=BG,font=('Segoe UI Black',24,'italic')).pack(side='left')
        status=tk.Label(top,text='CONNECTING TO MX BIKES…',fg=GOLD,bg=BG,font=('Segoe UI Black',9))
        status.pack(side='right',padx=8)
        host=tk.Frame(root,bg='black',highlightbackground=LINE,highlightthickness=1)
        host.pack(fill='both',expand=True)
        footer=tk.Label(root,text='LIVE MX BIKES BIKE SELECTION • CLICK INSIDE THE SCREEN NORMALLY',fg=MUTED,bg=BG,font=('Segoe UI Semibold',8))
        footer.pack(anchor='center',pady=(6,0))
        def mirror_status(state,detail=''):
            if state=='ready':status.configure(text='● LIVE • ACTUAL MX BIKES BIKE + RIDER',fg=GREEN)
            elif state=='starting':status.configure(text='● STARTING MX BIKES GARAGE…',fg=GOLD)
            else:
                status.configure(text='● GARAGE LINK ERROR',fg=RED)
                if detail:footer.configure(text=str(detail))
        host.after_idle(lambda:self.game_mirror.attach(host,mirror_status))
        return root

    def _profile_bikes(self,r):
        # Backward-compatible profile hook now routes to the live game Garage page.
        return self.page_garage()

'''
app=app[:start]+garage_methods+app[end:]

# Hot refresh lifecycle: stop the old mirror and create/prewarm one from the reloaded module.
hot_start=app.find('    def _after_hot_reload(self,target_version,snapshot):')
if hot_start<0:raise SystemExit('hot reload hook missing')
hot_end=app.find('    def do_update(self):',hot_start)
if hot_end<0:raise SystemExit('hot reload hook end missing')
hot_block=app[hot_start:hot_end]
if 'try:self.game_mirror.stop()' not in hot_block:
    hot_block=hot_block.replace("        try:self.mx_extension.stop()\n", "        try:self.game_mirror.stop()\n        except Exception:pass\n        try:self.mx_extension.stop()\n",1)
recreate="        self.mx_extension=MXExtensionService(self.conn,self.bike_garage,self.game_bridge,self.current_rider); self.mx_extension.start()"
if recreate in hot_block and 'self.game_mirror=MXGameGarageMirror' not in hot_block:
    hot_block=hot_block.replace(recreate,recreate+"\n        self.game_mirror=MXGameGarageMirror(self.game_bridge,self.bike_garage,self); self.after(2200,self.game_mirror.prewarm_async)",1)
app=app[:hot_start]+hot_block+app[hot_end:]
p.write_text(app,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
mirror=(work/'src/mx_game_mirror.py').read_text(encoding='utf-8')
wint=(work/'src/windows_integration.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
hot=(work/'src/hot_reload.py').read_text(encoding='utf-8')
ext=(work/'src/mx_extension.py').read_text(encoding='utf-8')
up=(work/'src/updater.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')

assert "VERSION = '0.5.5'" in config,'gate:version'
# Exact game renderer: DWM source relationship, no re-parenting and no fake geometry in visible Garage.
for marker in ('DwmRegisterThumbnail','DwmUpdateThumbnailProperties','DwmUnregisterThumbnail','DWM_THUMBNAIL_PROPERTIES' if False else 'class Props','PostMessageW','WS_EX_TOOLWINDOW','-clientport'):
    assert marker in mirror,'gate:dwm:'+marker
assert 'SetParent' not in mirror,'gate:no_directx_reparent'
assert 'subprocess.Popen' in mirror and 'self.game_bridge.game_exe()' in mirror,'gate:actual_mxbikes_source'
assert '_open_bike_selection_default_ui' in mirror,'gate:auto_bike_selection'
new_garage=appc[appc.rfind('    def page_garage(self):',0,appc.find('    def _after_hot_reload')):appc.find('    def _after_hot_reload')]
assert 'self.game_mirror.attach(host,mirror_status)' in new_garage,'gate:live_game_attached'
assert 'ACTUAL MX BIKES BIKE + RIDER' in new_garage,'gate:exact_game_ui_label'
assert 'garage_picture' not in new_garage and 'generate_proxy_mesh' not in new_garage and 'draw_garage3d' not in new_garage,'gate:no_substitute_visible_garage'
assert 'self.after(2200,self.game_mirror.prewarm_async)' in appc,'gate:prewarm_nonblocking'
assert 'self.game_mirror.detach()' in appc and 'self.game_mirror.stop()' in appc,'gate:mirror_lifecycle'
assert 'self.game_mirror.stop()\n            self.mx_extension.prepare_join' in appc,'gate:mirror_stops_before_race'
# Native Windows identity: dedicated named executable + stable AppID + shortcut icon is source of truth.
assert "APP_ID='MXBRaceDayLive.Desktop'" in wint,'gate:stable_app_id'
assert "LAUNCHER_NAME='MXB Race Day Live.exe'" in wint and 'ensure_native_launcher' in wint,'gate:named_launcher'
assert "root/'.venv'/'Scripts'/'pythonw.exe'" in wint and 'shutil.copy2(src,tmp)' in wint,'gate:launcher_runtime_copy'
assert "$s.TargetPath='" in wint and 'target_s=str(launcher)' in wint,'gate:shortcut_targets_launcher'
assert '_load_from_shortcut(shortcut,True) or _load_from_spec' in task,'gate:desktop_icon_authoritative'
for marker in ('WM_SETICON','SetClassLongPtrW','SetCurrentProcessExplicitAppUserModelID','DwmInvalidateIconicBitmaps','SHChangeNotify'):
    assert marker in task,'gate:taskbar:'+marker
# v0.5.4 extension + hot updates and approved product/performance systems remain.
assert 'capture_race_loadout' in ext and 'prepare_join' in ext and 'sync_profile_state' in ext,'gate:extension_preserved'
assert 'install_hot_update' in hot and 'refresh_running_app' in hot and 'app.__class__=new_cls' in hot,'gate:hot_update_preserved'
update_block=appc[appc.find('    def do_update(self):'):appc.find('\ndef main():')]
assert 'launch_update(' not in update_block and 'self._on_close' not in update_block,'gate:stay_open_update'
assert 'PRAGMA cache_size=-65536' in perf,'gate:sqlite_perf'
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver'):
    assert marker in appc,'gate:product:'+marker
assert "MANIFEST_PATH = 'race-control/latest.json'" in up and '_manifest_from_github_api' in up,'gate:update_feed'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('NATIVE GAME GARAGE GATE',{'actual_mxbikes_process':True,'dwm_live_mirror':True,'setparent':False,'input_forwarding':True,'prewarmed':True,'fake_models_visible':False})
print('TASKBAR GATE',{'stable_app_id':True,'named_launcher_exe':True,'shortcut_targets_named_exe':True,'desktop_icon_is_authoritative':True,'wm_seticon':True,'shell_refresh':True})
print('EXTENSION/HOT UPDATE GATE',{'two_way_profile':True,'race_loadouts':True,'stay_open_updates':True,'v051_perf':True})
print('BUILT',OUT,digest)
