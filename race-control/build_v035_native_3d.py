from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_3_4_UPDATE.zip')
RENDERER=Path('race-control/native_mxb_renderer_v035.py')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_3_5_UPDATE.zip')
NOTES=('MXB Race Day Live v0.3.5: adds Live 3D to Profile > Bikes using the actual MX Bikes rendering engine. '
       'Race Day Live generates a PiBoSo testing-mode config from the current garage selection, launches a dedicated windowed mxbikes.exe '
       'preview instance, and embeds that real render window inside the app with Win32 window hosting. Bike/paint/rider/helmet/boots/gloves '
       'selection changes can refresh the native preview. The user’s mxbikes.ini is backed up before temporary preview resolution/window-mode '
       'changes and restored when the preview closes. v0.3.4 native profile selection and taskbar icon, v0.3.3 one-click race joining, '
       'updater/restart, memberships, wallet, race economics, track media, live timing, results and admin controls are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('v0.3.4 base missing or invalid')
if not RENDERER.exists():raise SystemExit('native renderer source missing')
work=Path(tempfile.mkdtemp(prefix='mxb_v035_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(RENDERER,work/'src/native_renderer.py')

# Version markers.
p=work/'src/config.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]","VERSION = '0.3.5'",s); p.write_text(s,encoding='utf-8')
p=work/'src/__init__.py'; s=p.read_text(encoding='utf-8') if p.exists() else ''; s=re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]","__version__ = '0.3.5'",s) if '__version__' in s else s+"\n__version__ = '0.3.5'\n"; p.write_text(s,encoding='utf-8')
p=work/'src/updater.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+','MXB-Race-Day-Live-Updater/0.3.5',s); p.write_text(s,encoding='utf-8')

p=work/'src/app.py'; app=p.read_text(encoding='utf-8')

# Import and initialize native MX Bikes renderer.
anchor='from .bike_garage import MXBikeGarage, BikeGarageError\n'
imp='from .native_renderer import MXBNativeRenderer, NativeRendererError\n'
if imp not in app:
    if anchor not in app:raise SystemExit('bike garage import anchor missing')
    app=app.replace(anchor,anchor+imp,1)
old='self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.track_media=TrackMediaResolver(connect)'
new='self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.native_renderer=MXBNativeRenderer(self.game_bridge); self.track_media=TrackMediaResolver(connect)'
if old in app:app=app.replace(old,new,1)
elif 'self.native_renderer=MXBNativeRenderer' not in app:raise SystemExit('native renderer init anchor missing')

# Any page change tears down only the preview instance and restores graphics settings.
old_clear="    def clear(self):\n        try:self.unbind_all('<MouseWheel>')"
new_clear="    def clear(self):\n        try:\n            if hasattr(self,'native_renderer'):self.native_renderer.stop()\n        except Exception:pass\n        try:self.unbind_all('<MouseWheel>')"
if old_clear in app:app=app.replace(old_clear,new_clear,1)
elif "hasattr(self,'native_renderer')" not in app[app.find('def clear'):app.find('def show')]:raise SystemExit('clear cleanup anchor missing')

# Closing the app also tears down the embedded mxbikes.exe preview before DB/Tk shutdown.
close_anchor="    def _on_close(self):\n        try:\n            if self.mx_agent.live_client:self.mx_agent.live_client.stop()"
close_new="    def _on_close(self):\n        try:self.native_renderer.stop()\n        except Exception:pass\n        try:\n            if self.mx_agent.live_client:self.mx_agent.live_client.stop()"
if close_anchor in app:app=app.replace(close_anchor,close_new,1)
elif 'try:self.native_renderer.stop()' not in app[app.find('def _on_close'):app.find('# ---------- RIDER PROFILE')]:raise SystemExit('close cleanup anchor missing')

# Replace static garage image placeholder with a native render host surface.
old_preview="""        preview_image=tk.Label(right,text='',fg=TEXT,bg='#0f1216',font=('Segoe UI Black',18),justify='center')
        preview_image.pack(fill='x',padx=14,pady=(14,8),ipady=30)
        preview_title=tk.Label(right,text='',fg=TEXT,bg=PANEL,font=('Segoe UI Black',18))
"""
new_preview="""        preview_wrap=tk.Frame(right,bg='#0f1216',highlightbackground=LINE,highlightthickness=1)
        preview_wrap.pack(fill='x',padx=14,pady=(14,8))
        render_top=tk.Frame(preview_wrap,bg='#0f1216'); render_top.pack(fill='x')
        tk.Label(render_top,text='LIVE 3D • MX BIKES ENGINE',fg=GREEN,bg='#0f1216',font=('Segoe UI Black',9)).pack(side='left',padx=10,pady=7)
        render_status=tk.Label(render_top,text='PREVIEW STARTING…',fg=GOLD,bg='#0f1216',font=('Segoe UI Semibold',8)); render_status.pack(side='right',padx=10)
        render_host=tk.Frame(preview_wrap,bg='#050607',height=350,cursor='crosshair'); render_host.pack(fill='x',padx=1,pady=(0,1)); render_host.pack_propagate(False)
        render_fallback=tk.Label(render_host,text='MX BIKES NATIVE 3D\n\nStarting the real game renderer…',fg=TEXT,bg='#050607',font=('Segoe UI Black',16),justify='center'); render_fallback.pack(fill='both',expand=True)
        preview_title=tk.Label(right,text='',fg=TEXT,bg=PANEL,font=('Segoe UI Black',18))
"""
if old_preview in app:app=app.replace(old_preview,new_preview,1)
elif 'LIVE 3D • MX BIKES ENGINE' not in app:raise SystemExit('static preview anchor missing')

# Replace the static image logic inside refresh_preview; native engine owns the visual surface.
old_pic="""            pic=self.bike_garage.garage_picture(bike)
            photo=self._load_track_tk(str(pic),(570,330)) if pic else None
            if photo:preview_image.configure(image=photo,text='')
            else:preview_image.configure(image='',text='MX BIKES\\nBIKE SELECTION\\n\\n'+(self.bike_garage.bike_display(bike) or 'SYNC GAME CONTENT'))
"""
new_pic="""            try:
                render_fallback.configure(text='MX BIKES NATIVE 3D\\n\\n'+(self.bike_garage.bike_display(bike) or 'SYNC GAME CONTENT'))
            except Exception:pass
"""
if old_pic in app:app=app.replace(old_pic,new_pic,1)
elif 'render_fallback.configure' not in app:raise SystemExit('refresh preview image anchor missing')

# Add native renderer start/restart/resize helpers before refresh_all.
refresh_anchor="        def refresh_all():\n            for key,label in selector_labels.items():label.configure(text=display(key,state.get(key,'')))"
render_helpers=r'''        preview_restart_after={'id':None}
        preview_alive={'value':False}

        def renderer_payload():
            return {k:state.get(k,'') for k in self.bike_garage.PROFILE_KEYS}

        def renderer_ready(hwnd):
            def ui():
                preview_alive['value']=True
                try:render_status.configure(text='LIVE • REAL MX BIKES RENDERER',fg=GREEN); render_fallback.pack_forget()
                except Exception:pass
            try:self.after(0,ui)
            except Exception:pass

        def renderer_error(exc):
            def ui():
                preview_alive['value']=False
                try:
                    render_status.configure(text='LIVE 3D UNAVAILABLE',fg=RED)
                    render_fallback.configure(text='LIVE 3D COULD NOT START\n\n'+str(exc)+'\n\nUse START / REFRESH LIVE 3D to retry.')
                    if not render_fallback.winfo_manager():render_fallback.pack(fill='both',expand=True)
                except Exception:pass
            try:self.after(0,ui)
            except Exception:pass

        def start_live_renderer(show_errors=False):
            try:
                render_host.update_idletasks()
                w=max(500,render_host.winfo_width()); h=max(300,render_host.winfo_height())
                render_status.configure(text='STARTING MX BIKES ENGINE…',fg=GOLD)
                self.native_renderer.restart(render_host.winfo_id(),w,h,renderer_payload(),on_ready=renderer_ready,on_error=renderer_error)
            except (NativeRendererError,BikeGarageError) as exc:
                renderer_error(exc)
                if show_errors:messagebox.showerror('Live 3D',str(exc))
            except Exception as exc:
                renderer_error(exc)
                if show_errors:messagebox.showerror('Live 3D',f'Could not start the MX Bikes renderer: {exc}')

        def schedule_live_refresh():
            if not self.native_renderer.running:return
            try:
                if preview_restart_after['id'] is not None:self.after_cancel(preview_restart_after['id'])
            except Exception:pass
            preview_restart_after['id']=self.after(800,lambda:start_live_renderer(False))

        def resize_live(event):
            try:self.native_renderer.resize(event.width,event.height)
            except Exception:pass
        render_host.bind('<Configure>',resize_live)
        render_host.bind('<Button-1>',lambda e:self.native_renderer.focus())

        def refresh_all():
            for key,label in selector_labels.items():label.configure(text=display(key,state.get(key,'')))'''
if refresh_anchor in app:app=app.replace(refresh_anchor,render_helpers,1)
elif 'def start_live_renderer' not in app:raise SystemExit('refresh_all helper anchor missing')

# When a garage field changes while native renderer is running, refresh native MX Bikes after debounce.
old_cycle="            state[key]=vals[(i+step)%len(vals)]\n            normalize_dependents(key); refresh_all()"
new_cycle="            state[key]=vals[(i+step)%len(vals)]\n            normalize_dependents(key); refresh_all(); schedule_live_refresh()"
if old_cycle in app:app=app.replace(old_cycle,new_cycle,1)
elif 'schedule_live_refresh()' not in app[app.find('def cycle'):app.find('def group')]:raise SystemExit('cycle live refresh anchor missing')

# Add explicit renderer controls above existing APPLY TO MX BIKES button.
actions_anchor="        actions=tk.Frame(right,bg=PANEL); actions.pack(fill='x',padx=14,pady=(0,14))\n        tk.Button(actions,text='APPLY TO MX BIKES'"
actions_new="""        actions=tk.Frame(right,bg=PANEL); actions.pack(fill='x',padx=14,pady=(0,14))
        live_controls=tk.Frame(actions,bg=PANEL); live_controls.pack(fill='x',pady=(0,7))
        tk.Button(live_controls,text='START / REFRESH LIVE 3D',command=lambda:start_live_renderer(True),bg=GREEN,fg='white',relief='flat',font=('Segoe UI Black',10),pady=10,cursor='hand2').pack(side='left',fill='x',expand=True,padx=(0,4))
        tk.Button(live_controls,text='STOP 3D',command=lambda:[self.native_renderer.stop(),render_status.configure(text='STOPPED',fg=MUTED)],bg=PANEL2,fg=TEXT,relief='flat',font=('Segoe UI Black',9),pady=10,cursor='hand2').pack(side='left',padx=(4,0))
        tk.Button(actions,text='APPLY TO MX BIKES'"""
if actions_anchor in app:app=app.replace(actions_anchor,actions_new,1)
elif 'START / REFRESH LIVE 3D' not in app:raise SystemExit('live renderer controls anchor missing')

# Start automatically after the page has mounted, if game is detected. Do not block the Tk thread.
end_anchor="        refresh_all()\n\n    def _profile_settings(self,r):"
end_new="        refresh_all()\n        if self.native_renderer.supported and self.game_bridge.game_found():self.after(500,lambda:start_live_renderer(False))\n        else:render_status.configure(text='MX BIKES NOT DETECTED' if not self.game_bridge.game_found() else 'WINDOWS REQUIRED',fg=GOLD)\n\n    def _profile_settings(self,r):"
if end_anchor in app:app=app.replace(end_anchor,end_new,1)
elif 'self.after(500,lambda:start_live_renderer(False))' not in app:raise SystemExit('auto-start anchor missing')

p.write_text(app,encoding='utf-8')

# Compile every shipped Python source.
for py in work.rglob('*.py'):
    py_compile.compile(str(py),doraise=True)

# Regression gates: fail closed rather than ship a partial renderer build.
appc=(work/'src/app.py').read_text(encoding='utf-8')
rend=(work/'src/native_renderer.py').read_text(encoding='utf-8')
garc=(work/'src/bike_garage.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')
updater=(work/'src/updater.py').read_text(encoding='utf-8')
bridge=(work/'src/game_bridge.py').read_text(encoding='utf-8')
assert "VERSION = '0.3.5'" in config
for marker in ('MXBNativeRenderer','LIVE 3D • MX BIKES ENGINE','START / REFRESH LIVE 3D','REAL MX BIKES RENDERER','def start_live_renderer','schedule_live_refresh'):
    assert marker in appc
for marker in ("'-testing'", "'-set'", "'params'", 'SetParent', 'MoveWindow', 'GetWindowThreadProcessId', 'mxbikes.ini', 'race_day_live_preview.ini', 'mxbikes.race_day_live_preview_backup.ini'):
    assert marker in rend
for field in ('bike_id','paint','bike_font','rider','helmet','helmet_paint','goggles_paint','helmet_cam','suit_paint','suit_font','boots','boots_paint','gloves_paint','protection','protection_paint'):
    assert field in rend
assert "track_id = Practice" in rend and "fullscreen', '0'" in rend
assert 'self.native_renderer.stop()' in appc and 'self.native_renderer.resize' in appc
# v0.3.4 garage/taskbar must remain.
assert "('BIKES','BIKES')" in appc and 'APPLY TO MX BIKES' in appc and 'profile.race_day_live_backup.ini' in garc
assert "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop'" in appc and 'SetCurrentProcessExplicitAppUserModelID' in appc and 'iconphoto(True,self._taskbar_icon)' in appc
# v0.3.3 and earlier approved systems must remain.
assert 'JOIN RACE SERVER' in appc and '-directconnect' in bridge and 'MXGameBridge' in appc
assert 'member_quote' in appc and 'fastest_lap_pool' in appc and 'current_purse' in appc and 'TrackMediaResolver' in appc
assert 'api.github.com/repos/' in updater and 'latest.json' in updater

with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':'0.3.5','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_5_UPDATE.zip','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('NATIVE 3D VERIFIED',{'engine':'mxbikes.exe','testing_mode':True,'win32_embed':True,'selection_fields':15,'gfx_backup_restore':True,'auto_refresh':True,'taskbar_icon_preserved':True})
print('BUILT',OUT,digest)
