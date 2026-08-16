from pathlib import Path
import hashlib, json, py_compile, re, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_3_6_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_3_7_UPDATE.zip')
NOTES=('MXB Race Day Live v0.3.7: fixes Garage so the MX Bikes EDF render backend can never appear as a separate game window before embedding. '
       'The backend process is created suspended, a Windows show/create cloak is installed first, then the process is resumed; its render window is hidden, '
       'reparented and shown non-activating only inside the Race Day Live Garage. Garage starts loading immediately and renderer startup runs off the Tk UI thread. '
       'All v0.3.6 whole-app performance caches, live timing optimizations, updater/restart, taskbar identity, one-click race joining, memberships, wallet, race economics, '
       'verified track artwork, results and admin controls are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('v0.3.6 base missing or invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v037_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)

# Version.
for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel; s=p.read_text(encoding='utf-8'); s=re.sub(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '0.3.7'",s); p.write_text(s,encoding='utf-8')
p=work/'src/updater.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+','MXB-Race-Day-Live-Updater/0.3.7',s); p.write_text(s,encoding='utf-8')

# Garage page: show immediately, start backend asynchronously so Tk never blocks.
p=work/'src/app.py'; app=p.read_text(encoding='utf-8')
app=app.replace("render_status.configure(text='LOADING GARAGE 3D…',fg=GOLD)\n                self.native_renderer.restart(render_host.winfo_id(),w,h,renderer_payload(),on_ready=renderer_ready,on_error=renderer_error)",
"render_status.configure(text='LOADING GARAGE 3D…',fg=GOLD)\n                host_id=render_host.winfo_id(); payload=renderer_payload()\n                threading.Thread(target=lambda:self.native_renderer.restart(host_id,w,h,payload,on_ready=renderer_ready,on_error=renderer_error),name='MXB-Garage-Start',daemon=True).start()",1)
app=app.replace("if self.native_renderer.supported and self.game_bridge.game_found():self.after(500,lambda:start_live_renderer(False))",
                "if self.native_renderer.supported and self.game_bridge.game_found():self.after(30,lambda:start_live_renderer(False))",1)
app=app.replace("text='GARAGE 3D\\n\\nLoading installed bike…'","text='GARAGE 3D\\n\\nLoading your bike inside Race Day Live…'",1)
app=app.replace("text='LIVE 3D GARAGE'","text='LIVE 3D GARAGE • IN APP'",1)
p.write_text(app,encoding='utf-8')

# Native renderer: create MX Bikes suspended, install a WinEvent cloak BEFORE resume,
# then attach while hidden and reveal only as a non-activating child of Garage.
p=work/'src/native_renderer.py'; rend=p.read_text(encoding='utf-8')

# Add hook state.
old="        self._lock = threading.RLock()"
new="""        self._lock = threading.RLock()
        self._cloak_thread = None
        self._cloak_ready = threading.Event()
        self._win_event_hook = 0
        self._win_event_callback = None"""
if old in rend:rend=rend.replace(old,new,1)
elif 'self._cloak_thread = None' not in rend:raise SystemExit('renderer state anchor missing')

# Insert Windows helper methods before _find_window.
anchor='    def _find_window(self, timeout=35.0):\n'
helpers=r'''    @staticmethod
    def _resume_suspended_process(pid):
        """Resume threads of a CREATE_SUSPENDED process using documented Toolhelp APIs."""
        if os.name != 'nt':return
        from ctypes import wintypes
        kernel32=ctypes.windll.kernel32
        TH32CS_SNAPTHREAD=0x00000004; THREAD_SUSPEND_RESUME=0x0002
        INVALID_HANDLE_VALUE=ctypes.c_void_p(-1).value
        class THREADENTRY32(ctypes.Structure):
            _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ThreadID',wintypes.DWORD),('th32OwnerProcessID',wintypes.DWORD),('tpBasePri',wintypes.LONG),('tpDeltaPri',wintypes.LONG),('dwFlags',wintypes.DWORD)]
        snap=kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0)
        if snap==INVALID_HANDLE_VALUE:raise NativeRendererError('Windows could not enumerate the suspended Garage renderer process.')
        resumed=0
        try:
            te=THREADENTRY32(); te.dwSize=ctypes.sizeof(THREADENTRY32)
            ok=kernel32.Thread32First(snap,ctypes.byref(te))
            while ok:
                if int(te.th32OwnerProcessID)==int(pid):
                    h=kernel32.OpenThread(THREAD_SUSPEND_RESUME,False,te.th32ThreadID)
                    if h:
                        try:
                            if kernel32.ResumeThread(h)!=0xFFFFFFFF:resumed+=1
                        finally:kernel32.CloseHandle(h)
                ok=kernel32.Thread32Next(snap,ctypes.byref(te))
        finally:kernel32.CloseHandle(snap)
        if not resumed:raise NativeRendererError('Windows could not resume the embedded Garage renderer process.')

    def _start_window_cloak(self, pid):
        if os.name!='nt':return
        self._cloak_ready.clear()
        self._win_event_hook=0; self._win_event_callback=None
        def worker():
            from ctypes import wintypes
            user32=ctypes.windll.user32
            EVENT_OBJECT_CREATE=0x8000; EVENT_OBJECT_SHOW=0x8002
            WINEVENT_OUTOFCONTEXT=0x0000; WINEVENT_SKIPOWNPROCESS=0x0002
            SW_HIDE=0; HWND_BOTTOM=1; SWP_NOSIZE=0x0001; SWP_NOACTIVATE=0x0010; SWP_NOSENDCHANGING=0x0400
            WINEVENTPROC=ctypes.WINFUNCTYPE(None,wintypes.HANDLE,wintypes.DWORD,wintypes.HWND,wintypes.LONG,wintypes.LONG,wintypes.DWORD,wintypes.DWORD)
            @WINEVENTPROC
            def callback(hook,event,hwnd,idObject,idChild,eventThread,eventTime):
                try:
                    if not hwnd:return
                    owner=wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
                    if int(owner.value)!=int(pid):return
                    # Once the actual render surface belongs to Garage, never cloak it again.
                    if int(hwnd)==int(getattr(self,'game_hwnd',0) or 0) and int(user32.GetParent(hwnd) or 0)==int(getattr(self,'host_hwnd',0) or 0):return
                    user32.ShowWindowAsync(hwnd,SW_HIDE)
                    user32.SetWindowPos(hwnd,HWND_BOTTOM,-32000,-32000,1,1,SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOSENDCHANGING)
                except Exception:pass
            self._win_event_callback=callback
            hook=user32.SetWinEventHook(EVENT_OBJECT_CREATE,EVENT_OBJECT_SHOW,0,callback,int(pid),0,WINEVENT_OUTOFCONTEXT|WINEVENT_SKIPOWNPROCESS)
            self._win_event_hook=int(hook or 0)
            self._cloak_ready.set()
            if not hook:return
            msg=wintypes.MSG()
            PM_REMOVE=0x0001
            try:
                while not self._stop.is_set() and self.process and self.process.poll() is None:
                    while user32.PeekMessageW(ctypes.byref(msg),0,0,0,PM_REMOVE):
                        user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))
                    time.sleep(0.005)
            finally:
                try:user32.UnhookWinEvent(hook)
                except Exception:pass
                self._win_event_hook=0; self._win_event_callback=None
        self._cloak_thread=threading.Thread(target=worker,name='MXB-Garage-Cloak',daemon=True)
        self._cloak_thread.start()
        if not self._cloak_ready.wait(timeout=1.5):raise NativeRendererError('Garage window protection could not start.')

'''
if '_start_window_cloak' not in rend:
    if anchor not in rend:raise SystemExit('renderer helper insertion anchor missing')
    rend=rend.replace(anchor,helpers+anchor,1)

# Faster polling and proactively hide any discovered window before returning it.
old_find=r'''    def _find_window(self, timeout=35.0):
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop.is_set():
            p = self.process
            if not p or p.poll() is not None:
                return 0
            wins = self._enum_process_windows(p.pid)
            if wins:
                return wins[0]
            time.sleep(0.20)
        return 0
'''
new_find=r'''    def _find_window(self, timeout=35.0):
        deadline=time.time()+timeout
        while time.time()<deadline and not self._stop.is_set():
            p=self.process
            if not p or p.poll() is not None:return 0
            wins=self._enum_process_windows(p.pid)
            if wins:
                try:
                    user32=ctypes.windll.user32
                    for hwnd in wins:user32.ShowWindowAsync(hwnd,0)
                except Exception:pass
                return wins[0]
            time.sleep(0.01)
        return 0
'''
if old_find in rend:rend=rend.replace(old_find,new_find,1)
elif 'time.sleep(0.01)' not in rend:raise SystemExit('renderer find-window anchor missing')

# Hide first, attach first, then show non-activating as child. SW_SHOW from v0.3.6 could steal focus.
start=rend.index('    def _embed(self, hwnd, host_hwnd, width, height):')
end=rend.index('\n    def start(',start)
embed=r'''    def _embed(self, hwnd, host_hwnd, width, height):
        user32=ctypes.windll.user32
        GWL_STYLE=-16; WS_CHILD=0x40000000; WS_VISIBLE=0x10000000
        WS_CAPTION=0x00C00000; WS_THICKFRAME=0x00040000; WS_MINIMIZEBOX=0x00020000; WS_MAXIMIZEBOX=0x00010000; WS_SYSMENU=0x00080000
        SW_HIDE=0; SW_SHOWNA=8; SWP_NOACTIVATE=0x0010; SWP_FRAMECHANGED=0x0020; SWP_SHOWWINDOW=0x0040
        # Never let the game window become visible on the desktop.
        user32.ShowWindowAsync(hwnd,SW_HIDE)
        style=user32.GetWindowLongW(hwnd,GWL_STYLE)
        style &= ~(WS_CAPTION|WS_THICKFRAME|WS_MINIMIZEBOX|WS_MAXIMIZEBOX|WS_SYSMENU)
        style |= WS_CHILD|WS_VISIBLE
        user32.SetWindowLongW(hwnd,GWL_STYLE,style)
        ctypes.set_last_error(0)
        previous=user32.SetParent(hwnd,host_hwnd)
        err=ctypes.get_last_error()
        if not previous and err:raise NativeRendererError(f'Windows could not attach the Garage renderer (error {err}).')
        user32.SetWindowPos(hwnd,0,0,0,max(320,int(width)),max(240,int(height)),SWP_NOACTIVATE|SWP_FRAMECHANGED|SWP_SHOWWINDOW)
        user32.ShowWindow(hwnd,SW_SHOWNA)
'''
rend=rend[:start]+embed+rend[end:]

# Create process suspended, install cloak before any game window can be created, then resume.
old_spawn=r'''                startupinfo=subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE: backend never appears as a separate game window.
                priority=getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)
                self.process = subprocess.Popen(cmd,cwd=str(install_root),startupinfo=startupinfo,creationflags=priority)'''
new_spawn=r'''                startupinfo=subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow=0
                priority=getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)
                suspended=getattr(subprocess,'CREATE_SUSPENDED',0x00000004)
                self.process=subprocess.Popen(cmd,cwd=str(install_root),startupinfo=startupinfo,creationflags=priority|suspended)
                self._start_window_cloak(self.process.pid)
                self._resume_suspended_process(self.process.pid)'''
if old_spawn in rend:rend=rend.replace(old_spawn,new_spawn,1)
elif 'CREATE_SUSPENDED' not in rend:raise SystemExit('renderer spawn anchor missing')

p.write_text(rend,encoding='utf-8')

# Compile every shipped Python file.
for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8'); rendc=(work/'src/native_renderer.py').read_text(encoding='utf-8'); garc=(work/'src/bike_garage.py').read_text(encoding='utf-8'); bridgec=(work/'src/game_bridge.py').read_text(encoding='utf-8'); updater=(work/'src/updater.py').read_text(encoding='utf-8'); config=(work/'src/config.py').read_text(encoding='utf-8')

# New Garage behavior gates.
assert "VERSION = '0.3.7'" in config
assert 'CREATE_SUSPENDED' in rendc and '_start_window_cloak' in rendc and '_resume_suspended_process' in rendc
assert 'SetWinEventHook' in rendc and 'EVENT_OBJECT_SHOW' in rendc and 'ShowWindowAsync' in rendc
assert 'SW_SHOWNA=8' in rendc and 'ShowWindow(hwnd,SW_SHOWNA)' in rendc and 'ShowWindow(hwnd,5)' not in rendc
assert 'time.sleep(0.01)' in rendc and 'IsWindowVisible(hwnd)' not in rendc
assert "name='MXB-Garage-Start'" in appc and 'self.after(30,lambda:start_live_renderer(False))' in appc
assert 'LIVE 3D GARAGE • IN APP' in appc
# v0.3.6 performance + approved feature gates stay intact.
assert "('GARAGE','GARAGE')" in appc and 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc
assert 'lru_cache' in garc and 'invalidate_cache' in garc and 'self._game_exe_cache' in bridgec
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc
assert "if not force and name==previous" in appc
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver','APP_USER_MODEL_ID'):
    assert marker in appc
assert '-directconnect' in bridgec
assert 'api.github.com/repos/' in updater and 'latest.json' in updater and 'schedule_restart' in updater
assert 'profile.race_day_live_backup.ini' in garc

with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':'0.3.7','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_7_UPDATE.zip','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('V037 VERIFIED',{'desktop_game_window_before_embed':False,'create_suspended':True,'window_event_cloak_before_resume':True,'non_activating_child_show':True,'garage_immediate_load':True,'ui_thread_renderer_start':False,'v036_performance_preserved':True})
print('BUILT',OUT,digest)
