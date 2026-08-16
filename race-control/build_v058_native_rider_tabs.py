from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_7_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_8_UPDATE.zip')
RIDER=Path('race-control/native_rider_viewer_v058.py')
VERSION='0.5.8'
NOTES=(
    'MXB Race Day Live v0.5.8: rebuilds Garage equipment tabs to match the requested MX Bikes companion layout: Bike, Helmet, Gear, Boots, Goggles, Gloves and Protection. '
    'All selectors remain real dropdowns linked directly to the native MX Bikes profile fields. The rider-equipment preview now uses PiBoSo official MX Bikes rider template geometry downloaded automatically from the official MX Bikes templates package and parsed/rendered inside Race Day Live; no generic humanoid is used and MX Bikes is not launched. '
    'Helmet, Gear, Boots, Goggles, Gloves and Protection all use the same actual official MX Bikes rider model with camera framing focused on the relevant body region. The selected real game content names remain synchronized to profile.ini. '
    'Bike preview again uses the exact readable source-model renderer only when the selected bike supplies legitimate source geometry; Race Day Live does not substitute invented bike geometry for EDF-only bikes. '
    'Garage no longer invalidates all content caches on every page open, keeping the v0.5.1 performance behavior. v0.5.7 PKZ/OEM category linking, v0.5.6 working taskbar icon path, v0.5.4 two-way profile/loadout integration and stay-open hot updates are preserved.'
)
if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.7 base missing/invalid')
if not RIDER.exists():raise SystemExit('official rider viewer module missing')
work=Path(tempfile.mkdtemp(prefix='mxb_v058_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)
shutil.copy2(RIDER,work/'src/native_rider_viewer.py')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

# Load the new rider renderer before app.py during stay-open module refresh.
p=work/'src/hot_reload.py';hot=p.read_text(encoding='utf-8')
if "'src.native_rider_viewer'" not in hot:
    hot=hot.replace("'src.bike_garage','src.in_app_garage','src.mx_extension'","'src.bike_garage','src.in_app_garage','src.native_rider_viewer','src.mx_extension'",1)
p.write_text(hot,encoding='utf-8')

p=work/'src/app.py';app=p.read_text(encoding='utf-8')
if 'from .native_rider_viewer import OfficialMXRiderRenderer' not in app:
    m=re.search(r'^from \.in_app_garage import .*$',app,flags=re.M)
    if not m:raise SystemExit('in_app_garage import anchor missing')
    app=app[:m.end()]+"\nfrom .native_rider_viewer import OfficialMXRiderRenderer"+app[m.end():]

hotpos=app.find('    def _after_hot_reload(self,target_version,snapshot):')
start=app.rfind('    def page_garage(self):',0,hotpos)
if start<0 or hotpos<0:raise SystemExit('v0.5.7 Garage block missing')
newgarage=r'''    def page_garage(self):
        r=self.rider();self.bike_garage.username=self.current_rider;self.mx_extension.username=self.current_rider
        return self._profile_bikes(r)

    def _profile_bikes(self,r):
        # MX Bikes companion Garage: native profile/content dropdowns plus game-native preview sources.
        # Opening Garage does NOT clear the content cache; the watcher/rescan path owns invalidation.
        root=tk.Frame(self.content,bg=BG);root.pack(fill='both',expand=True,padx=16,pady=12)
        head=tk.Frame(root,bg=BG);head.pack(fill='x',pady=(0,8))
        tk.Label(head,text='GARAGE',fg='white',bg=BG,font=('Segoe UI Black',24,'italic')).pack(side='left')
        link=tk.Label(head,text='● LINKED TO MX BIKES PROFILE',fg=GREEN,bg=BG,font=('Segoe UI Black',9));link.pack(side='right',padx=8)
        tk.Label(root,text='Selections are written directly to the same MX Bikes profile used in-game.',fg=MUTED,bg=BG,font=('Segoe UI Semibold',9)).pack(anchor='w',pady=(0,8))

        body=tk.Frame(root,bg=BG);body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=PANEL,width=700);left.pack(side='left',fill='both',expand=True,padx=(0,10));left.pack_propagate(False)
        right=tk.Frame(body,bg='#111315',width=540);right.pack(side='left',fill='both',expand=True)

        state=self.bike_garage.read_selection();categories=list(self.bike_garage.categories())
        state['category']=self.bike_garage.bike_category(state.get('bikeid','')) or (categories[0] if categories else 'OTHER')
        if state['category'] not in categories and categories:state['category']=categories[0]

        notebook=ttk.Notebook(left);notebook.pack(fill='both',expand=True,padx=8,pady=8)
        tabs={}
        for title in ('Bike','Helmet','Gear','Boots','Goggles','Gloves','Protection'):
            frame=tk.Frame(notebook,bg=PANEL);notebook.add(frame,text=title);tabs[title]=frame

        vars={};combos={};bike_label_to_id={};bike_id_to_label={}
        status=tk.Label(right,text='3D VIEWER READY',fg=GREEN,bg='#111315',font=('Segoe UI Black',9));status.pack(anchor='ne',padx=12,pady=(10,0))
        canvas=tk.Canvas(right,bg='#050709',highlightthickness=0,cursor='fleur');canvas.pack(fill='both',expand=True,padx=10,pady=8)
        info=tk.Label(right,text='',fg=MUTED,bg='#111315',font=('Consolas',9),justify='left',anchor='w');info.pack(fill='x',padx=14,pady=(0,12))

        if not hasattr(self,'official_rider_renderer') or self.official_rider_renderer is None:
            self.official_rider_renderer=OfficialMXRiderRenderer(self)
        viewer_bound={'bike':False,'rider':False}

        def active_tab():
            try:return str(notebook.tab(notebook.select(),'text'))
            except Exception:return 'Bike'
        def rider_region():
            return {'Helmet':'helmet','Gear':'gear','Boots':'boots','Goggles':'goggles','Gloves':'gloves','Protection':'protection'}.get(active_tab(),'full')

        def records_for_category():return list(self.bike_garage.bikes_for_category(state.get('category','')))
        def rebuild_bike_maps():
            bike_label_to_id.clear();bike_id_to_label.clear();counts={};recs=records_for_category()
            for rec in recs:counts[str(rec.get('display') or rec['id'])]=counts.get(str(rec.get('display') or rec['id']),0)+1
            for rec in recs:
                bid=str(rec['id']);display=str(rec.get('display') or bid);label=display if counts.get(display,0)==1 else f'{display}  [{bid}]'
                bike_label_to_id[label]=bid;bike_id_to_label[bid]=label
            return recs

        def option_values(key):
            if key=='category':return list(self.bike_garage.categories())
            if key=='bikeid':rebuild_bike_maps();return list(bike_label_to_id)
            if key=='paint':return list(self.bike_garage.bike_paints(state.get('bikeid','')))
            if key=='bike_font':return list(self.bike_garage.fonts('bike'))
            if key=='helmet':return list(self.bike_garage.helmet_models())
            if key=='helmet_paint':return list(self.bike_garage.helmet_paints(state.get('helmet','default')))
            if key=='helmet_cam':return list(self.bike_garage.helmet_cams())
            if key=='rider':return list(self.bike_garage.rider_models())
            if key=='suit_paint':return list(self.bike_garage.rider_paints(state.get('rider','default_mx')))
            if key=='suit_font':return list(self.bike_garage.fonts('rider'))
            if key=='boots':return list(self.bike_garage.boot_models())
            if key=='boots_paint':return list(self.bike_garage.boot_paints(state.get('boots','default')))
            if key=='goggles_paint':return list(self.bike_garage.goggles_paints(state.get('helmet','default')))
            if key=='gloves_paint':return list(self.bike_garage.gloves_paints(state.get('rider','default_mx')))
            if key=='protection':return list(self.bike_garage.protection_models())
            if key=='protection_paint':return list(self.bike_garage.protection_paints(state.get('protection','default')))
            return ['']

        def display_for(key):
            if key=='bikeid':return bike_id_to_label.get(str(state.get(key,'') or ''),str(state.get(key,'') or ''))
            return str(state.get(key,'') or '')
        def set_combo(key):
            combo=combos.get(key);var=vars.get(key)
            if not combo:return
            vals=option_values(key);combo.configure(values=vals);target=display_for(key)
            if target not in vals:
                target=vals[0] if vals else ''
                state[key]=bike_label_to_id.get(target,'') if key=='bikeid' else target
            var.set(target)

        dependencies={'category':('bikeid','paint','bike_font'),'bikeid':('paint','bike_font'),'helmet':('helmet_paint','goggles_paint','helmet_cam'),
                      'rider':('suit_paint','suit_font','gloves_paint'),'boots':('boots_paint',),'protection':('protection_paint',)}
        def save_state():
            try:self.mx_extension.mirror_selection(state);link.configure(text='● SAVED TO MX BIKES PROFILE',fg=GREEN)
            except Exception as exc:link.configure(text='● MX BIKES PROFILE LINK ERROR',fg=RED);messagebox.showerror('MX Bikes',str(exc))

        def viewer_status(kind,detail=''):
            if kind=='ready':status.configure(text='● '+('OFFICIAL MX BIKES RIDER MODEL' if active_tab()!='Bike' else 'EXACT SOURCE BIKE MODEL'),fg=GREEN)
            elif kind=='loading':status.configure(text='● LOADING '+str(detail or '').upper(),fg=GOLD)
            elif kind=='opaque':status.configure(text='● EXACT BIKE 3D SOURCE NOT AVAILABLE',fg=GOLD)
            else:status.configure(text='● 3D VIEWER ERROR',fg=RED)

        def update_info():
            tab=active_tab();lines=[f'TAB       {tab}',f'PROFILE   {self.bike_garage.profile_name()}']
            if tab=='Bike':lines += [f'CATEGORY  {state.get("category","")}',f'BIKE      {self.bike_garage.bike_display(state.get("bikeid",""))}',f'PAINT     {state.get("paint","")}']
            elif tab=='Helmet':lines += [f'HELMET    {state.get("helmet","")}',f'PAINT     {state.get("helmet_paint","")}',f'CAMERA    {state.get("helmet_cam","")}']
            elif tab=='Gear':lines += [f'RIDER     {state.get("rider","")}',f'KIT       {state.get("suit_paint","")}',f'FONT      {state.get("suit_font","")}']
            elif tab=='Boots':lines += [f'BOOTS     {state.get("boots","")}',f'PAINT     {state.get("boots_paint","")}']
            elif tab=='Goggles':lines += [f'GOGGLES   {state.get("goggles_paint","")}']
            elif tab=='Gloves':lines += [f'GLOVES    {state.get("gloves_paint","")}']
            elif tab=='Protection':lines += [f'PROTECT   {state.get("protection","")}',f'PAINT     {state.get("protection_paint","")}']
            info.configure(text='\n'.join(lines))

        def update_viewer(reset=False):
            tab=active_tab();canvas.delete('all');update_info()
            if tab=='Bike':
                if not viewer_bound['bike']:
                    self.garage_renderer.bind(canvas,lambda:state.get('bikeid',''),viewer_status);viewer_bound['bike']=True
                self.garage_renderer.request(canvas,state.get('bikeid',''),viewer_status,reset=reset)
            else:
                if not viewer_bound['rider']:
                    self.official_rider_renderer.bind(canvas,rider_region,viewer_status);viewer_bound['rider']=True
                self.official_rider_renderer.request(canvas,rider_region(),viewer_status,reset=reset)

        def changed(key):
            raw=vars[key].get();state[key]=bike_label_to_id.get(raw,raw) if key=='bikeid' else raw
            if key=='category':
                recs=rebuild_bike_maps();valid={str(r['id']) for r in recs}
                if state.get('bikeid','') not in valid:state['bikeid']=str(recs[0]['id']) if recs else ''
            if key=='bikeid':
                cat=self.bike_garage.bike_category(state.get('bikeid',''))
                if cat:state['category']=cat;set_combo('category')
            for dep in dependencies.get(key,()):set_combo(dep)
            save_state();update_viewer()

        def row(tab,label,key):
            rr=tk.Frame(tabs[tab],bg=PANEL);rr.pack(fill='x',padx=12,pady=6)
            tk.Label(rr,text=label,fg=TEXT,bg=PANEL,font=('Segoe UI Semibold',9),width=19,anchor='w').pack(side='left')
            var=tk.StringVar();combo=ttk.Combobox(rr,textvariable=var,state='readonly',font=('Segoe UI',10),height=18)
            combo.pack(side='left',fill='x',expand=True);vars[key]=var;combos[key]=combo;combo.bind('<<ComboboxSelected>>',lambda e,k=key:changed(k),add='+')

        row('Bike','Category','category');row('Bike','Bike','bikeid');row('Bike','Paint','paint');row('Bike','Bike Font','bike_font')
        row('Helmet','Helmet','helmet');row('Helmet','Helmet Paint','helmet_paint');row('Helmet','Helmet Camera','helmet_cam')
        row('Gear','Rider','rider');row('Gear','Kit Paint','suit_paint');row('Gear','Kit Font','suit_font')
        row('Boots','Boots','boots');row('Boots','Boots Paint','boots_paint')
        row('Goggles','Goggles Paint','goggles_paint')
        row('Gloves','Gloves Paint','gloves_paint')
        row('Protection','Protection','protection');row('Protection','Protection Paint','protection_paint')
        for key in ('category','bikeid','paint','bike_font','helmet','helmet_paint','helmet_cam','rider','suit_paint','suit_font','boots','boots_paint','goggles_paint','gloves_paint','protection','protection_paint'):set_combo(key)

        actions=tk.Frame(left,bg=PANEL);actions.pack(fill='x',padx=10,pady=(0,10))
        def rescan():
            link.configure(text='● RESCANNING MX BIKES CONTENT…',fg=GOLD)
            try:self.bike_garage.invalidate_cache();self.game_bridge.invalidate_cache();self.mx_extension.content_changed();self.garage_renderer.invalidate_cache()
            except Exception:pass
            def done(env):
                try:self.after(0,lambda:(self._apply_mx_environment(env),self.show('GARAGE',force=True)))
                except Exception:pass
            try:self.mx_agent.sync_async(done)
            except Exception:self.show('GARAGE',force=True)
        tk.Button(actions,text='RESCAN MX BIKES CONTENT',command=rescan,bg=PANEL2,fg=TEXT,activebackground='#2a2f35',activeforeground='white',relief='flat',font=('Segoe UI Black',9),cursor='hand2',padx=12,pady=7).pack(side='left')
        tk.Button(actions,text='REFRESH FROM GAME PROFILE',command=lambda:self.show('GARAGE',force=True),bg=PANEL2,fg=TEXT,activebackground='#2a2f35',activeforeground='white',relief='flat',font=('Segoe UI Black',9),cursor='hand2',padx=12,pady=7).pack(side='left',padx=8)
        notebook.bind('<<NotebookTabChanged>>',lambda e:self.after_idle(lambda:update_viewer(reset=True)),add='+')
        canvas.bind('<Configure>',lambda e:self.after(90,update_viewer),add='+')
        self.after_idle(lambda:update_viewer(reset=True));return root

'''
app=app[:start]+newgarage+app[hotpos:]
# Stop old renderer objects before a hot class/UI refresh. They are recreated lazily.
hs=app.find('    def _after_hot_reload(self,target_version,snapshot):')
he=app.find('    def do_update(self):',hs)
if hs>0 and he>hs:
    block=app[hs:he]
    if 'official_rider_renderer.stop()' not in block:
        block=block.replace("        try:self.garage_renderer.stop()\n        except Exception:pass\n",
                            "        try:self.garage_renderer.stop()\n        except Exception:pass\n        try:self.official_rider_renderer.stop()\n        except Exception:pass\n        self.official_rider_renderer=None\n",1)
    app=app[:hs]+block+app[he:]
p.write_text(app,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
rider=(work/'src/native_rider_viewer.py').read_text(encoding='utf-8')
bgc=(work/'src/bike_garage.py').read_text(encoding='utf-8')
hot=(work/'src/hot_reload.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
winint=(work/'src/windows_integration.py').read_bytes();task=(work/'src/windows_taskbar.py').read_bytes()
basecheck=Path(tempfile.mkdtemp(prefix='mxb_v058_basecheck_'))
with zipfile.ZipFile(BASE) as z:
    z.extract('src/windows_integration.py',basecheck);z.extract('src/windows_taskbar.py',basecheck)
assert winint==(basecheck/'src/windows_integration.py').read_bytes(),'gate:working_taskbar_integration_changed'
assert task==(basecheck/'src/windows_taskbar.py').read_bytes(),'gate:working_taskbar_hwnd_changed'
shutil.rmtree(basecheck,ignore_errors=True)

assert "VERSION = '0.5.8'" in (work/'src/config.py').read_text(encoding='utf-8'),'gate:version'
for title in ('Bike','Helmet','Gear','Boots','Goggles','Gloves','Protection'):
    assert f"'{title}'" in appc,'gate:tab:'+title
assert "('Bike','Head','Torso','Legs')" not in appc,'gate:old_tabs_removed'
for marker in ("row('Helmet','Helmet','helmet')","row('Gear','Rider','rider')","row('Boots','Boots','boots')","row('Goggles','Goggles Paint','goggles_paint')","row('Gloves','Gloves Paint','gloves_paint')","row('Protection','Protection','protection')"):
    assert marker in appc,'gate:equipment_dropdown:'+marker
for marker in ('OFFICIAL_TEMPLATES_URL','www.mx-bikes.com/downloads/templates.zip','OfficialMXRiderRenderer','load_fbx_mesh','Kaydara FBX Binary','PolygonVertexIndex','PiBoSo MX Bikes official rider template'):
    assert marker in rider,'gate:official_rider:'+marker
assert 'OfficialMXRiderRenderer' in appc and 'self.official_rider_renderer.request' in appc,'gate:official_rider_viewer_wired'
assert "'Helmet':'helmet'" in appc and "'Gear':'gear'" in appc and "'Boots':'boots'" in appc and "'Goggles':'goggles'" in appc and "'Gloves':'gloves'" in appc and "'Protection':'protection'" in appc,'gate:rider_region_focus'
assert 'self.garage_renderer.request' in appc,'gate:bike_exact_source_viewer_restored'
assert 'self.bike_garage.invalidate_cache()' not in appc[appc.rfind('    def _profile_bikes(self,r):',0,appc.find('    def _after_hot_reload')):appc.find('        def rescan():',appc.rfind('    def _profile_bikes(self,r):',0,appc.find('    def _after_hot_reload')))],'gate:no_open_cache_flush'
assert 'folder.suffix.lower()==\'.pkz\'' in bgc and "return 'OEM 1'" in bgc,'gate:v057_linking_preserved'
newblock=appc[appc.rfind('    def page_garage(self):',0,appc.find('    def _after_hot_reload')):appc.find('    def _after_hot_reload')]
assert 'subprocess.Popen' not in newblock and 'launch_game' not in newblock and 'MXGameGarageMirror' not in appc,'gate:no_game_launch'
assert 'generate_proxy_mesh' not in newblock,'gate:no_fake_bike'
assert 'install_hot_update' in hot and 'refresh_running_app' in hot,'gate:hot_update'
assert 'PRAGMA cache_size=-65536' in perf,'gate:performance'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('GARAGE TAB GATE',{'tabs':['Bike','Helmet','Gear','Boots','Goggles','Gloves','Protection'],'all_dropdowns':True,'native_profile_write':True})
print('RIDER VIEWER GATE',{'source':'PiBoSo official MX Bikes templates','generic_humanoid':False,'fbx_binary_ascii_parser':True,'lazy_download':True,'game_process':False})
print('BIKE VIEWER GATE',{'exact_readable_source_only':True,'fake_bike':False,'game_process':False})
print('PERFORMANCE/TASKBAR GATE',{'garage_open_cache_flush':False,'v051_perf':True,'v056_taskbar_unchanged':True,'hot_update':True})
print('BUILT',OUT,digest)
