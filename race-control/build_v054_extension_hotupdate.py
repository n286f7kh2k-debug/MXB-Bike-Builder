from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_3_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_4_UPDATE.zip')
EXT=Path('race-control/mx_extension_v054.py')
HOT=Path('race-control/hot_reload_v054.py')
VERSION='0.5.4'
NOTES=(
    'MXB Race Day Live v0.5.4: deepens MX Bikes integration into a true companion/extension layer. Race Day Live now watches the native MX Bikes profile and mod roots, '
    'mirrors game-side bike/paint/kit changes back into the app, invalidates content caches only when the real game folders change, captures the complete native bike+rider loadout per race, '
    'and reapplies that exact loadout to profile.ini immediately before one-click direct-connect. Garage is rebuilt to mirror the MX Bikes Bike Selection workflow (Bike, Head, Torso, Legs) '
    'with immediate native profile writes and no fake/procedural bike models in the visible Garage. Exact game garage/preview art is used when available. This release also installs the new '
    'stay-open hot updater: beginning with updates after v0.5.4, UPDATE overlays verified files, reloads changed modules and refreshes the existing Race Day Live window without closing/restarting. '
    'v0.5.3 taskbar identity, v0.5.2 source/authorized renderer support, v0.5.1 performance fixes, memberships, wallet, race joining, live timing, purse/fastest-lap economics, track art and admin controls are preserved.'
)
for p in (BASE,EXT,HOT):
    if not p.exists():raise SystemExit(f'missing {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.3 base invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v054_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(EXT,work/'src/mx_extension.py')
shutil.copy2(HOT,work/'src/hot_reload.py')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

p=work/'src/app.py';app=p.read_text(encoding='utf-8')
# Imports.
if 'from .mx_extension import MXExtensionService' not in app:
    m=re.search(r'^from \.bike_garage import .*$',app,flags=re.M)
    if not m:raise SystemExit('bike_garage import anchor missing')
    app=app[:m.end()]+"\nfrom .mx_extension import MXExtensionService"+app[m.end():]
if 'from .hot_reload import install_hot_update, refresh_running_app' not in app:
    m=re.search(r'^from \.updater import .*$',app,flags=re.M)
    if not m:raise SystemExit('updater import anchor missing')
    app=app[:m.end()]+"\nfrom .hot_reload import install_hot_update, refresh_running_app"+app[m.end():]

# Extension service lives beside the existing real game bridge/garage objects.
old="self.mx_agent=MXRaceAgent(connect,self.current_rider); ensure_game_bridge_schema(self.conn); self.game_bridge=MXGameBridge(self.conn); self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.garage_renderer=InAppGarageRenderer(self.bike_garage); self.track_media=TrackMediaResolver(connect)"
new="self.mx_agent=MXRaceAgent(connect,self.current_rider); ensure_game_bridge_schema(self.conn); self.game_bridge=MXGameBridge(self.conn); self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider); self.garage_renderer=InAppGarageRenderer(self.bike_garage); self.mx_extension=MXExtensionService(self.conn,self.bike_garage,self.game_bridge,self.current_rider); self.mx_extension.start(); self._mx_extension_poll_generation=1; self.track_media=TrackMediaResolver(connect)"
if old in app:app=app.replace(old,new,1)
elif 'self.mx_extension=MXExtensionService' not in app:raise SystemExit('init extension anchor missing')

app=app.replace("        self.after(650,self._start_mx_sync)\n", "        self.after(650,self._start_mx_sync)\n        self.after(900,lambda:self._poll_mx_extension_events(self._mx_extension_poll_generation))\n",1)

# Make ordinary MX sync refresh the extension's resolved watch roots/state too.
app=app.replace("try:self.after(0,lambda:self._apply_mx_environment(env))","try:self.after(0,lambda:self._apply_mx_environment_extended(env))",1)

extension_methods=r'''
    def _apply_mx_environment_extended(self,env):
        self._apply_mx_environment(env)
        try:self.bike_garage.invalidate_cache()
        except Exception:pass
        try:self.mx_extension.content_changed(); self.mx_extension.sync_profile_state(force=True)
        except Exception:pass

    def _poll_mx_extension_events(self,generation=None):
        generation=self._mx_extension_poll_generation if generation is None else generation
        if generation!=getattr(self,'_mx_extension_poll_generation',generation):return
        try:
            events=self.mx_extension.drain_events()
            for event in events:
                if event.get('kind')=='content':
                    self.mx_extension.content_changed()
                    try:self.mx_agent.sync_async(lambda env:self.after(0,lambda:self._apply_mx_environment(env)))
                    except Exception:pass
                elif event.get('kind')=='profile':
                    result=self.mx_extension.sync_profile_state()
                    if result.get('changed') and getattr(self,'current_page','')=='GARAGE':
                        self.show('GARAGE',force=True)
        except Exception:pass
        try:self.after(1000,lambda g=generation:self._poll_mx_extension_events(g))
        except Exception:pass

'''
marker='    def _on_close(self):\n'
if '_poll_mx_extension_events' not in app:
    if marker not in app:raise SystemExit('on_close method anchor missing')
    app=app.replace(marker,extension_methods+marker,1)
# ensure insertion even if method name appeared only in timer we added
elif '    def _poll_mx_extension_events(self,generation=None):' not in app:
    if marker not in app:raise SystemExit('on_close method anchor missing')
    app=app.replace(marker,extension_methods+marker,1)

# Stop extension watcher cleanly.
close_anchor="    def _on_close(self):\n        try:\n            if self.mx_agent.live_client:self.mx_agent.live_client.stop()"
close_new="    def _on_close(self):\n        try:self.mx_extension.stop()\n        except Exception:pass\n        try:\n            if self.mx_agent.live_client:self.mx_agent.live_client.stop()"
if close_anchor in app:app=app.replace(close_anchor,close_new,1)
elif 'try:self.mx_extension.stop()' not in app[app.find('    def _on_close'):app.find('    # ---------- RIDER PROFILE')]:raise SystemExit('extension close hook missing')

# A selected race bike now snapshots the full native profile loadout.
save="saved=self.game_bridge.select_bike(race_id,rider_id,item['content_id'],item['display_name'])"
if save in app:
    app=app.replace(save,save+"\n            self.mx_extension.capture_race_loadout(race_id,rider_id,item['content_id'],item['display_name'])",1)
elif 'capture_race_loadout(race_id,rider_id' not in app:raise SystemExit('race bike loadout anchor missing')
# Right before direct-connect, reapply the exact saved bike+paint+kit to profile.ini.
join="result=self.game_bridge.launch_race(race_id,rider_id)"
if join in app:
    app=app.replace(join,"self.mx_extension.prepare_join(race_id,rider_id)\n            "+join,1)
elif 'self.mx_extension.prepare_join(race_id,rider_id)' not in app:raise SystemExit('join loadout anchor missing')

# Override the older Garage methods with an MX Bikes-style Bike Selection mirror.
garage_methods=r'''
    def page_garage(self):
        r=self.rider(); self.bike_garage.username=self.current_rider; self.mx_extension.username=self.current_rider
        return self._profile_bikes(r)

    def _profile_bikes(self,r):
        # Mirror the native MX Bikes Bike Selection workflow. No made-up/proxy bike is shown.
        root=tk.Frame(self.content,bg=BG); root.pack(fill='both',expand=True,padx=18,pady=14)
        tk.Label(root,text='Bike Selection',fg='white',bg=BG,font=('Segoe UI Black',25,'italic')).pack(anchor='ne',padx=18,pady=(0,8))
        body=tk.Frame(root,bg=BG); body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=BG,width=570); left.pack(side='left',fill='y',padx=(0,14)); left.pack_propagate(False)
        right=tk.Frame(body,bg='#111315'); right.pack(side='left',fill='both',expand=True)

        state=self.bike_garage.read_selection(); state['category']=self.bike_garage.bike_category(state.get('bikeid','')) or (self.bike_garage.categories()[0] if self.bike_garage.categories() else 'OTHER')
        labels={}
        preview_label=tk.Label(right,text='',fg='white',bg='#111315',font=('Segoe UI Semibold',11),compound='center',justify='center')
        preview_label.pack(fill='both',expand=True,padx=12,pady=12)
        status=tk.Label(right,text='LIVE LINK • MX BIKES PROFILE',fg=GREEN,bg='#111315',font=('Segoe UI Black',9))
        status.place(relx=.02,rely=.02,anchor='nw')

        def options(key):
            if key=='category':return list(self.bike_garage.categories())
            if key=='bikeid':return [x['id'] for x in self.bike_garage.bikes_for_category(state.get('category',''))]
            if key=='paint':return list(self.bike_garage.bike_paints(state.get('bikeid','')))
            if key=='bike_font':return list(self.bike_garage.fonts('bike'))
            if key=='helmet':return list(self.bike_garage.helmet_models())
            if key=='helmet_paint':return list(self.bike_garage.helmet_paints(state.get('helmet','default')))
            if key=='goggles_paint':return list(self.bike_garage.goggles_paints(state.get('helmet','default')))
            if key=='helmet_cam':return list(self.bike_garage.helmet_cams())
            if key=='rider':return list(self.bike_garage.rider_models())
            if key=='suit_paint':return list(self.bike_garage.rider_paints(state.get('rider','default_mx')))
            if key=='suit_font':return list(self.bike_garage.fonts('rider'))
            if key=='gloves_paint':return list(self.bike_garage.gloves_paints(state.get('rider','default_mx')))
            if key=='protection':return list(self.bike_garage.protection_models())
            if key=='protection_paint':return list(self.bike_garage.protection_paints(state.get('protection','default')))
            if key=='boots':return list(self.bike_garage.boot_models())
            if key=='boots_paint':return list(self.bike_garage.boot_paints(state.get('boots','default')))
            return ['']

        def normalize(changed=''):
            if changed=='category':
                bikes=options('bikeid'); state['bikeid']=bikes[0] if bikes else ''
            if changed in ('category','bikeid'):
                state['category']=self.bike_garage.bike_category(state.get('bikeid','')) or state.get('category','OTHER')
                vals=options('paint'); state['paint']=state.get('paint','') if state.get('paint','') in vals else (vals[0] if vals else '')
            for key in ('bike_font','helmet','helmet_paint','goggles_paint','helmet_cam','rider','suit_paint','suit_font','gloves_paint','protection','protection_paint','boots','boots_paint'):
                vals=options(key)
                if state.get(key,'') not in vals:state[key]=vals[0] if vals else ''

        def display_value(key):
            value=str(state.get(key,'') or '')
            if key=='bikeid':return self.bike_garage.bike_display(value) or '-Base-'
            return value or '-None-'

        def refresh_preview():
            pic=None
            try:pic=self.bike_garage.garage_picture(state.get('bikeid',''))
            except Exception:pass
            if pic:
                try:
                    photo=self._load_track_tk(str(pic),size=(720,520))
                    if photo:
                        preview_label.configure(image=photo,text='');preview_label.image=photo;return
                except Exception:pass
            preview_label.configure(image='',text='MX BIKES NATIVE BIKE\n\n'+self.bike_garage.bike_display(state.get('bikeid',''))+'\n\nNo substitute model is shown.\nThis selection is linked directly to the real MX Bikes profile.')
            preview_label.image=None

        def refresh_values():
            for key,lab in labels.items():lab.configure(text=display_value(key))
            refresh_preview()

        def cycle(key,step):
            vals=options(key)
            if not vals:return
            cur=state.get(key,'')
            try:i=vals.index(cur)
            except ValueError:i=0
            state[key]=vals[(i+step)%len(vals)]
            normalize(key)
            try:
                self.mx_extension.mirror_selection(state)
                status.configure(text='LIVE LINK • SAVED TO MX BIKES',fg=GREEN)
            except Exception as exc:
                status.configure(text='MX BIKES LINK ERROR',fg=RED); messagebox.showerror('MX Bikes',str(exc))
            refresh_values()

        def selector(group,label,key):
            row=tk.Frame(group,bg='#d8d4ce');row.pack(fill='x',padx=8,pady=2)
            tk.Label(row,text=label+':',fg='#151515',bg='#d8d4ce',font=('Segoe UI Black',9),width=18,anchor='w').pack(side='left',padx=(5,2),pady=4)
            tk.Button(row,text='◀',command=lambda:cycle(key,-1),bg='#d8d4ce',fg='#4b4b4b',activebackground='#c9c5bf',relief='flat',bd=0,font=('Segoe UI Black',10),width=2,cursor='hand2').pack(side='left')
            val=tk.Label(row,text='',fg='#4a4a4a',bg='#eeeeec',font=('Segoe UI Bold',9,'italic'),anchor='w',padx=7)
            val.pack(side='left',fill='x',expand=True,padx=2,ipady=4);labels[key]=val
            tk.Button(row,text='▶',command=lambda:cycle(key,1),bg='#d8d4ce',fg='#4b4b4b',activebackground='#c9c5bf',relief='flat',bd=0,font=('Segoe UI Black',10),width=2,cursor='hand2').pack(side='left',padx=(0,4))

        def group(title,rows):
            box=tk.Frame(left,bg='#d8d4ce',highlightbackground='#bdb8b0',highlightthickness=1);box.pack(fill='x',pady=(0,8))
            tk.Label(box,text=title.upper(),fg='#55514b',bg='#d8d4ce',font=('Segoe UI Black',8)).pack(anchor='w',padx=10,pady=(6,1))
            for label,key in rows:selector(box,label,key)
            tk.Frame(box,bg='#d8d4ce',height=5).pack()

        group('Bike',[('Category','category'),('Bike','bikeid'),('Paint','paint'),('Bike Font','bike_font')])
        group('Head',[('Helmet','helmet'),('Helmet Paint','helmet_paint'),('Goggles Paint','goggles_paint'),('Helmet Cam','helmet_cam')])
        group('Torso',[('Rider','rider'),('Kit Paint','suit_paint'),('Kit Font','suit_font'),('Gloves Paint','gloves_paint'),('Protection','protection'),('Protection Paint','protection_paint')])
        group('Legs',[('Boots','boots'),('Boots Paint','boots_paint')])
        normalize(); refresh_values()
        try:self.mx_extension.sync_profile_state(force=True)
        except Exception:pass

        bar=tk.Frame(root,bg='#151719');bar.pack(fill='x',pady=(8,0))
        tk.Button(bar,text='BACK',command=lambda:self.show('PROFILE'),bg='#151719',fg='white',relief='flat',font=('Segoe UI Black',9),padx=18,pady=7,cursor='hand2').pack(side='left')
        def info():
            d=self.bike_garage.diagnostics(); s=self.mx_extension.status()
            messagebox.showinfo('MX Bikes Link',f"Profile: {s.get('profile','')}\nBike: {self.bike_garage.bike_display(state.get('bikeid',''))}\nMods: {d.get('mods_root','')}\nProfile file: {d.get('profile_ini','')}")
        tk.Button(bar,text='INFO',command=info,bg='#151719',fg='white',relief='flat',font=('Segoe UI Black',9),padx=18,pady=7,cursor='hand2').pack(side='left',expand=True)
        tk.Button(bar,text='DONE',command=lambda:self.show('PROFILE'),bg='#151719',fg='white',relief='flat',font=('Segoe UI Black',9),padx=18,pady=7,cursor='hand2').pack(side='right')

'''
insert_at=app.find('    def do_update(self):')
if insert_at<0:raise SystemExit('do_update anchor missing')
app=app[:insert_at]+garage_methods+app[insert_at:]

# Replace close/restart updater with stay-open install + module/UI refresh.
start=app.find('    def do_update(self):')
end=app.find('\ndef main():',start)
if start<0 or end<0:raise SystemExit('do_update block missing')
hot_methods=r'''    def _after_hot_reload(self,target_version,snapshot):
        try:self.mx_extension.stop()
        except Exception:pass
        try:self.garage_renderer.stop()
        except Exception:pass
        self.settings=load_settings()
        ensure_game_bridge_schema(self.conn); ensure_subscription_schema(self.conn)
        self.game_bridge=MXGameBridge(self.conn)
        self.bike_garage=MXBikeGarage(self.conn,self.game_bridge,self.current_rider)
        self.garage_renderer=InAppGarageRenderer(self.bike_garage)
        self.mx_extension=MXExtensionService(self.conn,self.bike_garage,self.game_bridge,self.current_rider); self.mx_extension.start()
        self._mx_extension_poll_generation=getattr(self,'_mx_extension_poll_generation',0)+1
        self.track_media=TrackMediaResolver(connect)
        self._photo_cache={}; self._profile_photo_cache={}; self._track_media_mem={}; self._image_refs=[]
        self.profile_section=snapshot.get('profile_section','OVERVIEW'); self.race_filter=snapshot.get('race_filter','ALL')
        for child in list(self.winfo_children()):
            try:child.destroy()
            except Exception:pass
        self._styles(); self._layout(); self.current_page=''
        page=snapshot.get('page','PROFILE') or 'PROFILE'
        try:self.show(page,force=True)
        except Exception:self.show('PROFILE',force=True)
        self.title(f'{APP_NAME}  v{target_version}')
        self.after(700,lambda g=self._mx_extension_poll_generation:self._poll_mx_extension_events(g))
        try:self.after_idle(self._apply_windows_taskbar_icon)
        except Exception:pass

    def do_update(self):
        self.update_btn.configure(state='disabled',text='REFRESHING UPDATE FEED…')
        def worker():
            try:
                m=check_for_update()
                if not m.get('available'):
                    self.after(0,lambda:(self.update_btn.configure(state='normal',text='UPDATE'),messagebox.showinfo('MXB Race Day Live',f'You are on the latest version: v{VERSION}')))
                    return
                self.after(0,lambda:self.update_btn.configure(text=f"DOWNLOADING {m['version']}…"))
                z=download_update(m)
                self.after(0,lambda:self.update_btn.configure(text=f"INSTALLING {m['version']}…"))
                tx=install_hot_update(z)
                def finish():
                    try:
                        try:self.update_btn.configure(text='REFRESHING APP…')
                        except Exception:pass
                        refresh_running_app(self,tx,m['version'])
                        try:self.update_btn.configure(state='normal',text='UPDATE')
                        except Exception:pass
                        messagebox.showinfo('MXB Race Day Live',f"Updated to v{m['version']}. Race Day Live stayed open and refreshed in place.")
                    except Exception as exc:
                        try:self.update_btn.configure(state='normal',text='UPDATE')
                        except Exception:pass
                        messagebox.showerror('Update Failed',str(exc))
                self.after(0,finish)
            except Exception as e:
                msg=str(e)
                def fail(msg=msg):
                    try:self.update_btn.configure(state='normal',text='UPDATE')
                    except Exception:pass
                    messagebox.showerror('Update Failed',msg)
                self.after(0,fail)
        threading.Thread(target=worker,daemon=True).start()
'''
app=app[:start]+hot_methods+app[end:]
p.write_text(app,encoding='utf-8')

# Compile full overlay.
for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)

appc=(work/'src/app.py').read_text(encoding='utf-8')
hot=(work/'src/hot_reload.py').read_text(encoding='utf-8')
ext=(work/'src/mx_extension.py').read_text(encoding='utf-8')
up=(work/'src/updater.py').read_text(encoding='utf-8')
gar=(work/'src/bike_garage.py').read_text(encoding='utf-8')
bridge=(work/'src/game_bridge.py').read_text(encoding='utf-8')
rend=(work/'src/in_app_garage.py').read_text(encoding='utf-8')
task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
config=(work/'src/config.py').read_text(encoding='utf-8')

assert "VERSION = '0.5.4'" in config,'gate:version'
# Extension gates.
for marker in ('game_profile_state','race_loadouts','sync_profile_state','capture_race_loadout','prepare_join','refresh_watch_paths','drain_events'):
    assert marker in ext,'gate:extension:'+marker
assert 'self.mx_extension.prepare_join(race_id,rider_id)' in appc,'gate:loadout_before_join'
assert 'capture_race_loadout(race_id,rider_id' in appc,'gate:full_loadout_on_race_bike'
assert '_poll_mx_extension_events' in appc and "event.get('kind')=='profile'" in appc,'gate:two_way_profile_watch'
assert "event.get('kind')=='content'" in appc and 'invalidate_cache' in ext,'gate:content_watch'
# MX Bikes-style Garage visible flow: exact native values, no proxy renderer call.
for label in ('Bike Selection','Category','Bike Font','Helmet Paint','Goggles Paint','Kit Paint','Kit Font','Gloves Paint','Protection Paint','Boots Paint'):
    assert label in appc,'gate:garage_ui:'+label
assert 'self.mx_extension.mirror_selection(state)' in appc,'gate:immediate_native_profile_write'
new_garage=appc[appc.rfind('    def _profile_bikes(self,r):'):appc.find('    def _after_hot_reload',appc.rfind('    def _profile_bikes(self,r):'))]
assert 'draw_garage3d' not in new_garage and 'generate_proxy_mesh' not in new_garage,'gate:no_fake_visible_model'
assert 'garage_picture' in new_garage and 'No substitute model is shown' in new_garage,'gate:exact_game_art_only'
# Hot update gates.
for marker in ('install_hot_update','rollback_hot_update','refresh_running_app','importlib.reload','app.__class__=new_cls'):
    assert marker in hot,'gate:hot:'+marker
assert "text='REFRESHING APP…'" in appc and 'refresh_running_app(self,tx' in appc,'gate:stay_open_update_ui'
update_block=appc[appc.find('    def do_update(self):'):appc.find('\ndef main():')]
assert 'self._on_close' not in update_block and 'launch_update(' not in update_block and 'schedule_restart' not in update_block,'gate:no_close_restart_after_v054'
assert '_after_hot_reload' in appc and "for child in list(self.winfo_children())" in appc,'gate:in_place_ui_rebuild'
# Preserve approved systems/performance.
assert 'APP_USER_MODEL_ID' in appc and 'WM_SETICON' in task,'gate:taskbar'
assert 'ThreadPoolExecutor(max_workers=1' in rend and 'MAX_FACES = 5500' in rend,'gate:renderer_perf_preserved'
assert 'PRAGMA cache_size=-65536' in perf,'gate:sqlite_perf'
assert 'self._photo_cache' in appc and 'self._profile_photo_cache' in appc and 'self._track_media_mem' in appc,'gate:media_cache'
assert "if not force and name==previous" in appc,'gate:navigation_perf'
assert "self.after(1000,lambda rid=race_id:self._refresh_live_widgets(rid))" in appc,'gate:live_1hz'
for marker in ('JOIN RACE SERVER','member_quote','fastest_lap_pool','current_purse','TrackMediaResolver'):
    assert marker in appc,'gate:product:'+marker
assert '-directconnect' in bridge,'gate:directconnect'
assert "MANIFEST_PATH = 'race-control/latest.json'" in up and '_manifest_from_github_api' in up and 'time.time_ns()' in up,'gate:update_feed'
assert 'profile.race_day_live_backup.ini' in gar,'gate:profile_backup'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('EXTENSION GATE',{'native_profile_two_way':True,'native_content_watch':True,'full_race_loadout':True,'apply_loadout_before_join':True,'fake_visible_bikes':False,'game_style_groups':['Bike','Head','Torso','Legs']})
print('HOT UPDATE GATE',{'current_window_stays_open':True,'atomic_overlay':True,'module_reload':True,'class_swap':True,'ui_rebuild_same_tk_root':True,'rollback':True,'restart_after_v054':False})
print('PERFORMANCE/PRODUCT GATE',{'v051_perf':True,'taskbar_v053':True,'directconnect':True,'live_timing_1hz':True,'memberships_wallet_purse':True})
print('BUILT',OUT,digest)
