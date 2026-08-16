from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_3_8_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_3_9_UPDATE.zip')
GARAGE=Path('race-control/in_app_garage_v039.py')
WININT=Path('race-control/windows_integration_v039.py')
TASKBAR=Path('race-control/windows_taskbar_v039.py')
NOTES=('MXB Race Day Live v0.3.9: Garage no longer launches MX Bikes, Steam, testing mode, or any external game window. '
       'The Garage 3D viewport is now an actual in-app renderer for readable source geometry while all installed bikes, paints and gear remain selectable/synced to the native MX Bikes profile. '
       'Compiled EDF-only geometry is treated as opaque instead of launching/crashing MX Bikes. Windows desktop/taskbar identity is also rebuilt around the desktop shortcut actual IconLocation so the live taskbar uses the same logo source. Existing updater/restart, race joining, memberships, economics, track art and performance caches are preserved.')

for p in (BASE,GARAGE,WININT,TASKBAR):
    if not p.exists():raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.3.8 base invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v039_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(GARAGE,work/'src/in_app_garage.py')
shutil.copy2(WININT,work/'src/windows_integration.py')
shutil.copy2(TASKBAR,work/'src/windows_taskbar.py')

# version
p=work/'src/config.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]","VERSION = '0.3.9'",s); p.write_text(s,encoding='utf-8')
p=work/'src/__init__.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]","__version__ = '0.3.9'",s); p.write_text(s,encoding='utf-8')
p=work/'src/updater.py'; s=p.read_text(encoding='utf-8'); s=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+','MXB-Race-Day-Live-Updater/0.3.9',s); p.write_text(s,encoding='utf-8')

p=work/'src/app.py'; app=p.read_text(encoding='utf-8')
app=app.replace('from .native_renderer import MXBNativeRenderer, NativeRendererError\n','from .in_app_garage import InAppGarageRenderer, GarageModelError\n')
app=app.replace("APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v2'","APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v3'")
app=app.replace('self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.native_renderer=MXBNativeRenderer(self.game_bridge); self.track_media=TrackMediaResolver(connect)',
                'self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.garage_renderer=InAppGarageRenderer(self.bike_garage); self.track_media=TrackMediaResolver(connect)')
# Remove renderer cleanup inherited from v0.3.8. This must never start/own an MX Bikes process anymore.
app=app.replace('try:self.native_renderer.stop()\n        except Exception:pass\n','')
app=app.replace("if getattr(self,'current_page',None)=='GARAGE' and page!='GARAGE':\n            try:self.native_renderer.stop()\n            except Exception:pass\n",'')

# Garage preview becomes a Canvas owned by Race Day Live, never a Win32 child from mxbikes.exe.
app=app.replace("render_host=tk.Frame(preview_wrap,bg='#050607',height=350,cursor='crosshair'); render_host.pack(fill='x',padx=1,pady=(0,1)); render_host.pack_propagate(False)\n        render_fallback=tk.Label(render_host,text='GARAGE 3D\\n\\nLoading your bike inside Race Day Live…',fg=TEXT,bg='#050607',font=('Segoe UI Black',16),justify='center'); render_fallback.pack(fill='both',expand=True)",
"render_host=tk.Canvas(preview_wrap,bg='#050607',height=350,highlightthickness=0,cursor='fleur'); render_host.pack(fill='x',padx=1,pady=(0,1))\n        render_fallback=tk.Label(render_host,text='GARAGE 3D\\n\\nLoading in Race Day Live…',fg=TEXT,bg='#050607',font=('Segoe UI Black',16),justify='center'); render_fallback.place(relx=.5,rely=.5,anchor='center')")

start=app.find("        preview_restart_after={'id':None}")
end=app.find('        def refresh_all():',start)
if start<0 or end<0:raise SystemExit('Could not locate v0.3.8 native Garage renderer block')
replacement=r'''        # True in-app renderer. Garage is forbidden from spawning MX Bikes/Steam.
        def draw_garage3d(reset=False):
            bike=state.get('bikeid','')
            try:
                loaded=self.garage_renderer.load_bike(bike)
                if loaded:
                    if reset:
                        self.garage_renderer.yaw=-0.65; self.garage_renderer.pitch=-0.18; self.garage_renderer.zoom=1.0
                    render_host.update_idletasks()
                    ok=self.garage_renderer.draw(render_host,max(500,render_host.winfo_width()),max(300,render_host.winfo_height()))
                    if ok:
                        render_status.configure(text='LIVE • RACE DAY LIVE 3D',fg=GREEN)
                        render_fallback.place_forget()
                        return
                render_status.configure(text='EDF BIKE • SELECTION SYNCED',fg=GOLD)
                render_fallback.configure(text='3D SOURCE NOT INCLUDED WITH THIS BIKE\n\nThe installed bike is compiled EDF.\nRace Day Live will NOT launch MX Bikes.\nBike / paint / gear selection still syncs normally.')
                render_fallback.place(relx=.5,rely=.5,anchor='center')
            except GarageModelError as exc:
                render_status.configure(text='3D SOURCE ERROR',fg=RED)
                render_fallback.configure(text='GARAGE 3D\n\n'+str(exc)); render_fallback.place(relx=.5,rely=.5,anchor='center')
            except Exception as exc:
                render_status.configure(text='3D UNAVAILABLE',fg=RED)
                render_fallback.configure(text='GARAGE 3D\n\n'+str(exc)); render_fallback.place(relx=.5,rely=.5,anchor='center')

        self.garage_renderer.bind(render_host,lambda:draw_garage3d(False))
        render_host.bind('<Configure>',lambda e:self.after_idle(lambda:draw_garage3d(False)),add='+')

'''
app=app[:start]+replacement+app[end:]
app=app.replace('            normalize_dependents(key); refresh_all(); schedule_live_refresh()','            normalize_dependents(key); refresh_all(); draw_garage3d(False)')
# Replace old external renderer controls.
app=re.sub(r"        live_controls=tk\.Frame\(actions,bg=PANEL\); live_controls\.pack\(fill='x',pady=\(0,7\)\)\n        tk\.Button\(live_controls,text='RELOAD 3D'.*?\n        tk\.Button\(live_controls,text='PAUSE 3D'.*?\n",
           "        live_controls=tk.Frame(actions,bg=PANEL); live_controls.pack(fill='x',pady=(0,7))\n        tk.Button(live_controls,text='RESET 3D VIEW',command=lambda:draw_garage3d(True),bg=GREEN,fg='white',relief='flat',font=('Segoe UI Black',10),pady=10,cursor='hand2').pack(fill='x')\n",
           app, count=1)
# Remove auto-start of MX Bikes renderer and instead draw the in-app canvas immediately.
app=re.sub(r"        if self\.native_renderer\.supported and self\.game_bridge\.game_found\(\):self\.after\(30,lambda:start_live_renderer\(False\)\)\n        else:render_status\.configure\(text='MX BIKES NOT DETECTED'.*?\n",
           "        self.after_idle(lambda:draw_garage3d(True))\n",app,count=1)

# Defensive: no native renderer references may survive in the app.
app=app.replace('NativeRendererError','GarageModelError')
p.write_text(app,encoding='utf-8')

# Root launcher now owns the same Windows integration shipped in this update.
p=work/'app.py'; root=p.read_text(encoding='utf-8')
# Existing import already targets src.windows_integration; included now.
p.write_text(root,encoding='utf-8')

# Compile included Python.
for py in work.rglob('*.py'):
    py_compile.compile(str(py),doraise=True)

app=(work/'src/app.py').read_text(encoding='utf-8')
inapp=(work/'src/in_app_garage.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
wint=(work/'src/windows_integration.py').read_text(encoding='utf-8')
up=(work/'src/updater.py').read_text(encoding='utf-8')

# Hard Garage gates: there is no external game renderer path anymore.
assert 'native_renderer' not in app.lower()
assert 'MXBNativeRenderer' not in app and 'start_live_renderer' not in app
assert 'mxbikes.exe' not in inapp.lower() and 'subprocess' not in inapp.lower() and "'-testing'" not in inapp
assert 'InAppGarageRenderer' in app and 'tk.Canvas' in app and "RESET 3D VIEW" in app
assert 'Race Day Live will NOT launch MX Bikes' in app
# Selection sync remains native and all bike/gear selectors remain.
for key in ('bikeid','paint','bike_font','helmet','helmet_paint','goggles_paint','helmet_cam','rider','suit_paint','suit_font','gloves_paint','protection','protection_paint','boots','boots_paint'):
    assert key in app
assert 'apply_selection' in app and 'profile.ini' in app
# Taskbar/shortcut gates.
assert "APP_ID='MXBRaceDayLive.Desktop.v3'" in wint
assert 'shortcut_icon_location' in wint and 'IconLocation' in wint and 'ensure_desktop_shortcut' in wint
assert 'best_icon' in task and 'WM_SETICON' in task and 'ICON_BIG' in task and 'ICON_SMALL' in task
assert "APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v3'" in app
# Preserve approved systems.
assert 'check_for_update' in app and 'launch_update' in app and 'api.github.com/repos/' in up
assert 'JOIN RACE SERVER' in app and 'member_quote' in app and 'fastest_lap_pool' in app
assert 'TrackMediaResolver' in app and 'MXGameBridge' in app

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':'0.3.9','url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_9_UPDATE.zip','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('GARAGE PROCESS GATE',{'mxbikes_launch_from_garage':False,'steam_launch_from_garage':False,'in_app_canvas':True,'native_profile_sync':True})
print('TASKBAR GATE',{'shortcut_icon_location':True,'app_id_v3':True,'wm_seticon':True,'desktop_taskbar_same_source':True})
print('BUILT',OUT,digest)
