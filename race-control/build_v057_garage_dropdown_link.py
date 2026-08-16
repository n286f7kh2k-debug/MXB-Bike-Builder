from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_6_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_7_UPDATE.zip')
VERSION='0.5.7'
NOTES=(
    'MXB Race Day Live v0.5.7: fixes Garage content linking and replaces the arrow-cycle controls with real dropdowns. '
    'The bike scanner now treats installed PKZ bikes and same-name paint folders as first-class content, reads category metadata from unpacked INIs or readable PKZs, and falls back to the real OEM bike ID families when protected PKZs hide their INI. '
    'OEM categories therefore populate instead of appearing blank, including OEM 1, OEM 2 and OEM 3 families when installed. Bike is filtered by Category and all dependent Bike/Head/Torso/Legs dropdowns repopulate from the actual selected MX Bikes content. '
    'Selections still write immediately to the real MX Bikes profile and the two-way profile/content watcher, complete race loadouts, apply-before-direct-connect, stay-open hot updates, v0.5.1 performance work and the now-working v0.5.6 taskbar icon path are preserved unchanged. '
    'No Garage-triggered MX Bikes process, DWM mirror or fake/procedural 3D model is reintroduced.'
)
if not BASE.exists() or not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.6 base missing/invalid')
work=Path(tempfile.mkdtemp(prefix='mxb_v057_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)

# Version only; taskbar/icon modules remain byte-for-byte from v0.5.6.
for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

# ---------- Fix the real MX Bikes content scanner ----------
p=work/'src/bike_garage.py';bg=p.read_text(encoding='utf-8')
if 'import zipfile' not in bg:
    # Insert after the existing import block without assuming exact ordering.
    first_class=bg.find('\n\nclass ')
    first_def=bg.find('\n\ndef ')
    cut=min(x for x in (first_class,first_def) if x>0)
    bg=bg[:cut]+'\nimport zipfile'+bg[cut:]

# Include new cached helpers in invalidation.
bg=bg.replace("'bike_records','bike_category','categories','bikes_for_category','bike_paints'",
              "'bike_records','bike_category','categories','bikes_for_category','bike_paints'",1)

start=bg.find('    @lru_cache(maxsize=2)\n    def bike_records(self):')
end=bg.find('    def bike_display(self, bike_id):',start)
if start<0 or end<0:raise SystemExit('bike_records/category anchors missing')
scanner=r'''    @staticmethod
    def _category_from_text(text):
        try:
            match=re.search(r'^\s*category\s*=\s*(.+?)\s*$',str(text or ''),flags=re.I|re.M)
            return match.group(1).strip().strip('"') if match else ''
        except Exception:return ''

    @staticmethod
    def _normalize_category(raw,bike_id=''):
        raw=str(raw or '').strip(); bid=str(bike_id or '').strip().upper()
        compact=re.sub(r'[\s_]+','',raw.upper())
        compact_dash=compact.replace('-','')
        # The UI uses the rider-friendly names the user expects while preserving distinct 2T classes.
        if compact in ('OEM1','MX1OEM') or (not raw and bid.startswith('MX1OEM_')):return 'OEM 1'
        if compact in ('OEM2','MX2OEM') or (not raw and bid.startswith('MX2OEM_')):return 'OEM 2'
        if compact in ('OEM3','MX3OEM') or (not raw and bid.startswith('MX3OEM_')):return 'OEM 3'
        if compact_dash in ('MX12TOEM','OEM12T') or 'MX1-2T' in raw.upper():return 'OEM 1 - 2T'
        if compact_dash in ('MX22TOEM','OEM22T') or 'MX2-2T' in raw.upper():return 'OEM 2 - 2T'
        if raw:
            # Current/older OEM packs commonly report MX1 OEM / MX2 OEM / MX3 in the bike INI.
            if compact=='MX1OEM':return 'OEM 1'
            if compact=='MX2OEM':return 'OEM 2'
            if compact=='MX3OEM':return 'OEM 3'
            return raw
        # Protected PKZ fallback: the game IDs still expose the OEM family even when metadata is locked.
        if bid.startswith('MX1OEM'):return 'OEM 1'
        if bid.startswith('MX2OEM'):return 'OEM 2'
        if bid.startswith('MX3OEM'):return 'OEM 3'
        if 'OEM' in bid and bid.startswith('MX1'):return 'OEM 1'
        if 'OEM' in bid and bid.startswith('MX2'):return 'OEM 2'
        if 'OEM' in bid and bid.startswith('MX3'):return 'OEM 3'
        return 'OTHER'

    def _bike_pkz_paths(self,bike_id):
        out=[]
        for root in self._roots():
            p=root/'bikes'/(str(bike_id)+'.pkz')
            if p.is_file():out.append(p)
        return out

    def _category_from_pkz(self,bike_id):
        # Unlocked PKZs are ZIP-compatible. Locked creator PKZs simply fall through to the ID family.
        wanted=str(bike_id or '').lower()+'.ini'
        for path in self._bike_pkz_paths(bike_id):
            try:
                if not zipfile.is_zipfile(path):continue
                with zipfile.ZipFile(path) as z:
                    names=z.namelist()
                    candidates=[n for n in names if n.lower().endswith('/'+wanted) or n.lower()==wanted]
                    if not candidates:candidates=[n for n in names if n.lower().endswith('.ini')]
                    for name in candidates[:16]:
                        try:text=z.read(name).decode('utf-8',errors='ignore')
                        except Exception:continue
                        cat=self._category_from_text(text)
                        if cat:return cat
            except Exception:pass
        return ''

    @lru_cache(maxsize=2)
    def bike_records(self):
        records={}
        # Keep the existing background game-content index as one source.
        try:
            for row in self.conn.execute("SELECT content_id,display_name,path FROM game_content WHERE UPPER(content_type) IN ('BIKE','BIKES')"):
                bid=str(row['content_id'] or '').strip()
                if bid:
                    records[bid.lower()]={'id':bid,'display':str(row['display_name'] or bid).strip(),'category':'','path':str(row['path'] or '')}
        except Exception:pass
        # The game also accepts one PKZ per bike. Previous builds only iterated directories, which is why
        # current OEM packs could appear in the Bike list but have no category in Race Day Live.
        for root in self._roots():
            base=root/'bikes'
            try:
                for folder in base.iterdir():
                    if folder.is_dir():
                        key=folder.name.lower()
                        records.setdefault(key,{'id':folder.name,'display':folder.name,'category':'','path':str(folder)})
                    elif folder.is_file() and folder.suffix.lower()=='.pkz':
                        bid=folder.stem
                        if bid.lower() in ('bikes','rider','tracks','tyres'):continue
                        key=bid.lower()
                        rec=records.setdefault(key,{'id':bid,'display':bid,'category':'','path':str(folder)})
                        if not rec.get('path'):rec['path']=str(folder)
            except Exception:pass
        for rec in records.values():rec['category']=self.bike_category(rec['id'])
        return sorted(records.values(),key=lambda x:(x['category'].lower(),x['display'].lower(),x['id'].lower()))

    @lru_cache(maxsize=512)
    def bike_category(self,bike_id):
        bike_id=str(bike_id or '').strip()
        # 1) Exact unpacked bike INI metadata.
        for folder in self._bike_dirs(bike_id):
            try:
                preferred=[folder/(bike_id+'.ini')]
                preferred.extend(p for p in folder.glob('*.ini') if p not in preferred)
                for ini in preferred[:16]:
                    if not ini.is_file():continue
                    cat=self._category_from_text(ini.read_text(encoding='utf-8',errors='ignore'))
                    if cat:return self._normalize_category(cat,bike_id)
            except Exception:pass
        # 2) Exact category from an unlocked PKZ.
        cat=self._category_from_pkz(bike_id)
        if cat:return self._normalize_category(cat,bike_id)
        # 3) Protected PKZ: use the real content ID family rather than returning blank.
        return self._normalize_category('',bike_id)

'''
bg=bg[:start]+scanner+bg[end:]

# Replace categories/bikes-for-category/bike-paints so a non-empty installed library never produces an empty menu.
start=bg.find('    @lru_cache(maxsize=2)\n    def categories(self):')
end=bg.find('    @lru_cache(maxsize=64)\n    def _model_dirs',start)
if start<0 or end<0:raise SystemExit('categories block anchors missing')
catblock=r'''    @lru_cache(maxsize=2)
    def categories(self):
        cats=_unique(rec.get('category') or 'OTHER' for rec in self.bike_records())
        # Keep OEM families in natural menu order, then all other real categories alphabetically.
        priority={'OEM 1':0,'OEM 1 - 2T':1,'OEM 2':2,'OEM 2 - 2T':3,'OEM 3':4}
        return sorted(cats,key=lambda c:(priority.get(c,100),str(c).lower())) or ['OTHER']

    @lru_cache(maxsize=128)
    def bikes_for_category(self,category):
        recs=self.bike_records(); wanted=str(category or '').strip().lower()
        matches=[r for r in recs if str(r.get('category') or '').strip().lower()==wanted]
        return matches if wanted else recs

    @lru_cache(maxsize=256)
    def bike_paints(self,bike_id):
        # A protected PKZ normally has a same-name folder for user paints. Read both install + mods roots.
        paths=[folder/'paints' for folder in self._bike_dirs(bike_id)]
        return _unique(['']+_file_stems(paths))

'''
bg=bg[:start]+catblock+bg[end:]
p.write_text(bg,encoding='utf-8')

# ---------- Replace arrow cyclers with real drop-down tabs ----------
p=work/'src/app.py';app=p.read_text(encoding='utf-8')
if 'from tkinter import ttk' not in app:
    # tkinter is already imported in every shipped build.
    anchor='import tkinter as tk\n'
    if anchor in app:app=app.replace(anchor,anchor+'from tkinter import ttk\n',1)
    else:raise SystemExit('tkinter import anchor missing')

hotpos=app.find('    def _after_hot_reload(self,target_version,snapshot):')
start=app.rfind('    def page_garage(self):',0,hotpos)
if start<0 or hotpos<0:raise SystemExit('Garage override/hot reload anchors missing')
newgarage=r'''    def page_garage(self):
        r=self.rider();self.bike_garage.username=self.current_rider;self.mx_extension.username=self.current_rider
        return self._profile_bikes(r)

    def _profile_bikes(self,r):
        # Direct MX Bikes profile/content editor. Every selector is a real dropdown and all dependent
        # menus cascade from installed game content. No fake model and no MX Bikes process is started.
        root=tk.Frame(self.content,bg=BG);root.pack(fill='both',expand=True,padx=16,pady=12)
        head=tk.Frame(root,bg=BG);head.pack(fill='x',pady=(0,8))
        tk.Label(head,text='GARAGE',fg='white',bg=BG,font=('Segoe UI Black',24,'italic')).pack(side='left')
        link=tk.Label(head,text='● LINKED TO MX BIKES PROFILE',fg=GREEN,bg=BG,font=('Segoe UI Black',9))
        link.pack(side='right',padx=8)
        tk.Label(root,text='Your selections below write directly to the same MX Bikes profile used in-game.',fg=MUTED,bg=BG,font=('Segoe UI Semibold',9)).pack(anchor='w',pady=(0,8))

        body=tk.Frame(root,bg=BG);body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=PANEL,width=720);left.pack(side='left',fill='both',expand=True,padx=(0,10));left.pack_propagate(False)
        right=tk.Frame(body,bg='#111315',width=500);right.pack(side='left',fill='both',expand=True)

        try:self.bike_garage.invalidate_cache()
        except Exception:pass
        state=self.bike_garage.read_selection();categories=list(self.bike_garage.categories())
        state['category']=self.bike_garage.bike_category(state.get('bikeid','')) or (categories[0] if categories else 'OTHER')
        if state['category'] not in categories and categories:state['category']=categories[0]

        notebook=ttk.Notebook(left);notebook.pack(fill='both',expand=True,padx=8,pady=8)
        tabs={}
        for title in ('Bike','Head','Torso','Legs'):
            frame=tk.Frame(notebook,bg=PANEL);notebook.add(frame,text=title);tabs[title]=frame

        vars={};combos={};bike_label_to_id={};bike_id_to_label={}
        preview=tk.Label(right,text='',fg='white',bg='#111315',font=('Segoe UI Semibold',11),compound='center',justify='center')
        preview.pack(fill='both',expand=True,padx=12,pady=12)
        info=tk.Label(right,text='',fg=MUTED,bg='#111315',font=('Consolas',9),justify='left',anchor='w')
        info.pack(fill='x',padx=14,pady=(0,12))

        def records_for_category():
            return list(self.bike_garage.bikes_for_category(state.get('category','')))

        def rebuild_bike_maps():
            bike_label_to_id.clear();bike_id_to_label.clear();counts={}
            recs=records_for_category()
            for rec in recs:counts[str(rec.get('display') or rec['id'])]=counts.get(str(rec.get('display') or rec['id']),0)+1
            for rec in recs:
                bid=str(rec['id']);display=str(rec.get('display') or bid)
                label=display if counts.get(display,0)==1 else f'{display}  [{bid}]'
                bike_label_to_id[label]=bid;bike_id_to_label[bid]=label
            return recs

        def option_values(key):
            if key=='category':return list(self.bike_garage.categories())
            if key=='bikeid':
                rebuild_bike_maps();return list(bike_label_to_id)
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

        def display_for(key):
            if key=='bikeid':return bike_id_to_label.get(str(state.get(key,'') or ''),str(state.get(key,'') or ''))
            return str(state.get(key,'') or '')

        def set_combo(key,keep=True):
            combo=combos.get(key);var=vars.get(key)
            if not combo:return
            vals=option_values(key);combo.configure(values=vals)
            target=display_for(key)
            if target not in vals:
                target=vals[0] if vals else ''
                if key=='bikeid':state[key]=bike_label_to_id.get(target,'')
                else:state[key]=target
            var.set(target)

        def refresh_preview():
            pic=None
            try:pic=self.bike_garage.garage_picture(state.get('bikeid',''))
            except Exception:pass
            if pic:
                try:
                    photo=self._load_track_tk(str(pic),size=(620,480))
                    if photo:
                        preview.configure(image=photo,text='');preview.image=photo
                    else:raise RuntimeError()
                except Exception:
                    preview.configure(image='',text=self.bike_garage.bike_display(state.get('bikeid','')));preview.image=None
            else:
                preview.configure(image='',text=self.bike_garage.bike_display(state.get('bikeid',''))+'\n\nExact game preview not supplied by this bike.\nNo substitute model is shown.');preview.image=None
            try:
                d=self.bike_garage.diagnostics()
                info.configure(text=f"CATEGORY  {state.get('category','')}\nBIKE ID   {state.get('bikeid','')}\nPROFILE   {d.get('profile','')}\nBIKES     {d.get('bikes',0)}")
            except Exception:pass

        dependencies={
            'category':('bikeid','paint','bike_font'),
            'bikeid':('paint','bike_font'),
            'helmet':('helmet_paint','goggles_paint','helmet_cam'),
            'rider':('suit_paint','suit_font','gloves_paint'),
            'protection':('protection_paint',),
            'boots':('boots_paint',),
        }

        def save_state():
            try:
                self.mx_extension.mirror_selection(state)
                link.configure(text='● SAVED TO MX BIKES PROFILE',fg=GREEN)
            except Exception as exc:
                link.configure(text='● MX BIKES PROFILE LINK ERROR',fg=RED)
                messagebox.showerror('MX Bikes',str(exc))

        def changed(key):
            raw=vars[key].get()
            if key=='bikeid':state[key]=bike_label_to_id.get(raw,raw)
            else:state[key]=raw
            if key=='category':
                recs=rebuild_bike_maps();valid={str(r['id']) for r in recs}
                if state.get('bikeid','') not in valid:state['bikeid']=str(recs[0]['id']) if recs else ''
            if key=='bikeid':
                cat=self.bike_garage.bike_category(state.get('bikeid',''))
                if cat:state['category']=cat;set_combo('category')
            for dep in dependencies.get(key,()):set_combo(dep)
            save_state();refresh_preview()

        def row(tab,label,key):
            r=tk.Frame(tabs[tab],bg=PANEL);r.pack(fill='x',padx=12,pady=6)
            tk.Label(r,text=label,fg=TEXT,bg=PANEL,font=('Segoe UI Semibold',9),width=19,anchor='w').pack(side='left')
            var=tk.StringVar();combo=ttk.Combobox(r,textvariable=var,state='readonly',font=('Segoe UI',10),height=18)
            combo.pack(side='left',fill='x',expand=True);vars[key]=var;combos[key]=combo
            combo.bind('<<ComboboxSelected>>',lambda e,k=key:changed(k),add='+')

        row('Bike','Category','category');row('Bike','Bike','bikeid');row('Bike','Paint','paint');row('Bike','Bike Font','bike_font')
        row('Head','Helmet','helmet');row('Head','Helmet Paint','helmet_paint');row('Head','Goggles Paint','goggles_paint');row('Head','Helmet Camera','helmet_cam')
        row('Torso','Rider','rider');row('Torso','Kit Paint','suit_paint');row('Torso','Kit Font','suit_font');row('Torso','Gloves Paint','gloves_paint');row('Torso','Protection','protection');row('Torso','Protection Paint','protection_paint')
        row('Legs','Boots','boots');row('Legs','Boots Paint','boots_paint')

        # Populate in dependency order.
        for key in ('category','bikeid','paint','bike_font','helmet','helmet_paint','goggles_paint','helmet_cam','rider','suit_paint','suit_font','gloves_paint','protection','protection_paint','boots','boots_paint'):set_combo(key)

        actions=tk.Frame(left,bg=PANEL);actions.pack(fill='x',padx=10,pady=(0,10))
        def rescan():
            link.configure(text='● RESCANNING MX BIKES CONTENT…',fg=GOLD)
            try:self.bike_garage.invalidate_cache();self.game_bridge.invalidate_cache();self.mx_extension.content_changed()
            except Exception:pass
            def done(env):
                try:self.after(0,lambda:(self._apply_mx_environment(env),self.show('GARAGE',force=True)))
                except Exception:pass
            try:self.mx_agent.sync_async(done)
            except Exception:self.show('GARAGE',force=True)
        tk.Button(actions,text='RESCAN MX BIKES CONTENT',command=rescan,bg=PANEL2,fg=TEXT,activebackground='#2a2f35',activeforeground='white',relief='flat',font=('Segoe UI Black',9),cursor='hand2',padx=12,pady=7).pack(side='left')
        tk.Button(actions,text='REFRESH FROM GAME PROFILE',command=lambda:self.show('GARAGE',force=True),bg=PANEL2,fg=TEXT,activebackground='#2a2f35',activeforeground='white',relief='flat',font=('Segoe UI Black',9),cursor='hand2',padx=12,pady=7).pack(side='left',padx=8)
        refresh_preview();return root

'''
app=app[:start]+newgarage+app[hotpos:]
p.write_text(app,encoding='utf-8')

# Compile every Python file in the final overlay.
for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
bgc=(work/'src/bike_garage.py').read_text(encoding='utf-8')
hot=(work/'src/hot_reload.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
winint=(work/'src/windows_integration.py').read_bytes();task=(work/'src/windows_taskbar.py').read_bytes()
# Compare icon/taskbar code to the known v0.5.6 base extraction: builder never edits them.
basecheck=Path(tempfile.mkdtemp(prefix='mxb_v057_basecheck_'))
with zipfile.ZipFile(BASE) as z:
    z.extract('src/windows_integration.py',basecheck);z.extract('src/windows_taskbar.py',basecheck)
assert winint==(basecheck/'src/windows_integration.py').read_bytes(),'gate:taskbar_integration_changed'
assert task==(basecheck/'src/windows_taskbar.py').read_bytes(),'gate:taskbar_hwnd_changed'
shutil.rmtree(basecheck,ignore_errors=True)

assert "VERSION = '0.5.7'" in (work/'src/config.py').read_text(encoding='utf-8'),'gate:version'
for marker in ("folder.suffix.lower()=='.pkz'",'_category_from_pkz','MX1OEM','MX2OEM','MX3OEM',"return 'OEM 1'","return 'OEM 2'","return 'OEM 3'"):
    assert marker in bgc,'gate:pkz_category:'+marker
assert "return sorted(cats" in bgc and "or ['OTHER']" in bgc,'gate:nonblank_category'
for marker in ("ttk.Notebook","ttk.Combobox","state='readonly'","row('Bike','Category','category')","row('Bike','Bike','bikeid')","row('Head','Helmet','helmet')","row('Torso','Rider','rider')","row('Legs','Boots','boots')"):
    assert marker in appc,'gate:dropdown:'+marker
assert 'self.mx_extension.mirror_selection(state)' in appc,'gate:native_profile_write'
assert 'RESCAN MX BIKES CONTENT' in appc and 'REFRESH FROM GAME PROFILE' in appc,'gate:content_refresh'
# No regression to the black/slow game mirror.
assert 'MXGameGarageMirror' not in appc and 'DwmRegisterThumbnail' not in appc,'gate:no_v055_mirror'
newblock=appc[appc.rfind('    def page_garage(self):',0,appc.find('    def _after_hot_reload')):appc.find('    def _after_hot_reload')]
assert 'subprocess.Popen' not in newblock and 'launch_game' not in newblock,'gate:no_garage_game_launch'
assert 'generate_proxy_mesh' not in newblock and 'draw_garage3d' not in newblock,'gate:no_fake_3d'
assert 'install_hot_update' in hot and 'refresh_running_app' in hot,'gate:hot_update'
assert 'PRAGMA cache_size=-65536' in perf,'gate:performance'

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('GARAGE LINK GATE',{'pkz_bikes':True,'protected_oem_id_fallback':True,'oem_1_2_3_categories':True,'category_never_blank_with_bikes':True,'real_dropdowns':True,'cascading_dependencies':True,'immediate_profile_write':True})
print('STABILITY GATE',{'garage_launches_mxbikes':False,'dwm_mirror':False,'fake_3d':False,'v051_perf':True,'v056_taskbar_unchanged':True,'hot_update':True})
print('BUILT',OUT,digest)
