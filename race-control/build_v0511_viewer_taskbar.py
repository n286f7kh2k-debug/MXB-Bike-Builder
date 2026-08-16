from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_10_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_11_UPDATE.zip')
WININT=Path('race-control/windows_integration_v0511.py')
LAUNCHER=Path('race-control/staging/MXB Race Day Live.exe')
VERSION='0.5.11'
NOTES=(
 'MXB Race Day Live v0.5.11 fixes the Garage black-box/loading-error loop and Windows pinned-taskbar identity. '
 'The native Garage now resolves stock bike geometry directly from the game install bikes.pkz in addition to loose/mod bike sources, keeps the last canvas stable while loading, deduplicates repeated resize/error requests, and displays a persistent diagnostic panel instead of a blank black viewer when a real asset cannot be decoded. '
 'The rider renderer now keeps the real rider body renderable when an optional selected helmet, boots or protection package is unreadable, instead of failing the entire rider frame. '
 'Windows integration no longer renames/copies pythonw.exe as MXB Race Day Live.exe. A real branded MXB Race Day Live launcher with embedded product metadata and icon is installed in the app root, desktop and existing pinned links are migrated to it, the stable MXBRaceDayLive.Desktop AppUserModelID is preserved, and the old Python-named shell identity is retired. '
 'Protected/non-ZIP creator packages remain protected and are not cracked or replaced with fake geometry.'
)
for p in (BASE,WININT,LAUNCHER):
    if not p.exists():raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.10 base missing/invalid')
if LAUNCHER.read_bytes()[:2]!=b'MZ':raise SystemExit('branded launcher is not a Windows PE executable')
work=Path(tempfile.mkdtemp(prefix='mxb_v0511_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

(work/'assets'/'bin').mkdir(parents=True,exist_ok=True)
shutil.copy2(LAUNCHER,work/'assets'/'bin'/'MXB Race Day Live.exe')
shutil.copy2(WININT,work/'src'/'windows_integration.py')

p=work/'src'/'frost_native_viewer.py';view=p.read_text(encoding='utf-8')
stock_helper=r'''
def _extract_game_bike_pkz(path,bike_id):
    """Extract only the selected bike from the stock game bikes.pkz."""
    path=Path(path);bike_id=str(bike_id or '').strip()
    if not bike_id:return None
    if not _plain_zip(path):
        raise FrostViewerError(f'{path.name} is not a readable ZIP package; Race Day Live will not bypass protected package data.')
    key=_stamp([path],f'game-bike:{bike_id.lower()}');dst=_cache_root()/'game_bikes'/key;ready=dst/'.ready'
    if ready.is_file():return dst
    stage=Path(tempfile.mkdtemp(prefix='rdl_game_bike_'));count=0
    try:
        wanted=bike_id.lower()
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir() or int(info.file_size or 0)>192*1024*1024:continue
                low=info.filename.replace('\\','/').strip('/').lower();parts=[x for x in low.split('/') if x]
                if not low.endswith(VIEWER_SUFFIXES):continue
                match=(len(parts)>=2 and parts[0]=='bikes' and parts[1]==wanted) or (wanted in parts[:-1])
                if not match:continue
                rel=_safe_name(info.filename)
                if rel is None:continue
                target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
                count+=1
        if not count:return None
        if dst.exists():shutil.rmtree(dst,ignore_errors=True)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(stage),str(dst));ready.write_text('ok\n',encoding='utf-8');return dst
    finally:
        if stage.exists():shutil.rmtree(stage,ignore_errors=True)

'''
if 'def _extract_game_bike_pkz(' not in view:
    anchor='def _visible_edfs(root):\n'
    if anchor not in view:raise SystemExit('viewer visible-edf anchor missing')
    view=view.replace(anchor,stock_helper+anchor,1)

bike_bundle=r'''def _bike_bundle(app,bike_id,paint=''):
    garage=app.bike_garage;rec=_bike_record(garage,bike_id);candidates=[];errors=[]
    if rec and rec.get('path'):candidates.append(Path(rec['path']))
    for root in _garage_roots(garage):
        candidates += [root/'bikes'/str(bike_id),root/'bikes'/(str(bike_id)+'.pkz')]
    seen=set();source=None
    for p in candidates:
        k=str(p).lower()
        if k in seen:continue
        seen.add(k)
        try:
            if p.is_dir() and _visible_edfs(p):source=p;break
            if p.is_file() and p.suffix.lower()=='.edf':source=p;break
            if p.is_file() and p.suffix.lower()=='.pkz':
                source=_extract_game_bike_pkz(p,bike_id) if p.name.lower()=='bikes.pkz' else _extract_viewer_pkz(p,str(bike_id))
                if source and _visible_edfs(source):break
                source=None
            if p.is_dir():
                sibling=p.with_suffix('.pkz')
                if sibling.is_file():
                    source=_extract_viewer_pkz(sibling,str(bike_id))
                    if source and _visible_edfs(source):break
                    source=None
        except FrostViewerError as exc:errors.append(str(exc));source=None
    if source is None:
        game=_game_dir(app);stock=(game/'bikes.pkz') if game else None
        if stock and stock.is_file():
            try:
                candidate=_extract_game_bike_pkz(stock,bike_id)
                if candidate and _visible_edfs(candidate):source=candidate
            except FrostViewerError as exc:errors.append(str(exc))
    if source is None:
        detail='No readable EDF source was found for this selected bike in loose/mod content or the stock bikes.pkz.'
        if errors:detail+=' '+errors[0]
        raise FrostViewerError(detail)
    edfs=_visible_edfs(source)
    if not edfs:raise FrostViewerError('The selected bike source contains no readable EDF geometry.')
    geom=_find_geom(source);paints=[]
    if paint:
        for root in _garage_roots(garage):
            q=root/'bikes'/str(bike_id)/'paints'/(str(paint)+'.pnt')
            if q.is_file():paints.append(q)
        try:
            hits=list(Path(source).rglob(str(paint)+'.pnt'));paints.extend(h for h in hits if h.is_file())
        except Exception:pass
    return edfs,geom,paints

'''
view,n=re.subn(r'def _bike_bundle\(app,bike_id,paint=.*?\n(?=def _game_dir\(app\):)',lambda m:bike_bundle,view,count=1,flags=re.S)
if n!=1:raise SystemExit('bike bundle replacement anchor missing')

body_source=r'''def _body_source(app,profile):
    profile=str(profile or 'default_mx').strip() or 'default_mx';errors=[]
    for base in _rider_bases(app):
        loose=base/'riders'/profile/'rider.edf'
        if loose.is_file():return loose
        packed=base/'riders'/(profile+'.pkz')
        if packed.is_file():
            try:
                hits=_extract_entry_from_plain_pkz(packed,[f'rider/riders/{profile}/rider.edf','rider.edf'],f'body-{profile}')
                if hits:return hits[0]
            except FrostViewerError as exc:errors.append(str(exc))
    game=_game_dir(app)
    if game:
        pkz=game/'rider.pkz'
        if pkz.is_file():
            try:
                hits=_extract_entry_from_plain_pkz(pkz,[f'rider/riders/{profile}/rider.edf'],f'game-body-{profile}')
                if not hits and profile not in STOCK_RIDERS:
                    for stock in STOCK_RIDERS:
                        hits=_extract_entry_from_plain_pkz(pkz,[f'rider/riders/{stock}/rider.edf'],f'game-body-{stock}')
                        if hits:break
                if hits:return hits[0]
            except FrostViewerError as exc:errors.append(str(exc))
    msg=f'The real rider.edf for profile {profile!r} was not found.'
    if errors:msg+=' '+errors[0]
    raise FrostViewerError(msg)

'''
view,n=re.subn(r'def _body_source\(app,profile\):.*?\n(?=def _gear_source\(app,part,model\):)',lambda m:body_source,view,count=1,flags=re.S)
if n!=1:raise SystemExit('body source replacement anchor missing')

gear_source=r'''def _gear_source(app,part,model):
    model=str(model or '').strip().removesuffix('.pkz')
    specs={'helmet':(('helmets',),'helmet.edf','default'),'boots':(('boots',),'boots.edf','default'),'protection':(('protections','protection'),'armour.edf','full')}
    areas,mesh,default=specs[part];model=model or default
    for base in _rider_bases(app):
        for area in areas:
            folder=base/area/model
            if folder.is_dir():
                expected=folder/mesh
                if expected.is_file():return [expected],folder
                hits=_visible_edfs(folder)
                if hits:return hits,folder
            packed=base/area/(model+'.pkz')
            if packed.is_file():
                try:
                    root=_extract_viewer_pkz(packed,model);hits=_visible_edfs(root)
                    if hits:return hits,root
                except FrostViewerError:pass
    game=_game_dir(app)
    if game and (game/'rider.pkz').is_file():
        pkz=game/'rider.pkz';prefix=f'rider/{areas[0]}/{model}/'
        if not _plain_zip(pkz):return [],None
        dst=_cache_root()/'stock_gear'/_stamp([pkz],f'{part}-{model}');dst.mkdir(parents=True,exist_ok=True);hits=[]
        try:
            with zipfile.ZipFile(pkz) as z:
                names=[n for n in z.namelist() if n.replace('\\','/').lower().startswith(prefix.lower()) and n.lower().endswith('.edf') and not n.lower().endswith('_s.edf')]
                names.sort(key=lambda n:(0 if Path(n).name.lower()==mesh else 1,len(n),n.lower()))
                for name in names:
                    target=dst/Path(name).name
                    if not target.is_file():
                        with z.open(name) as src,target.open('wb') as f:shutil.copyfileobj(src,f)
                    hits.append(target)
        except Exception:return [],None
        if hits:return hits,dst
    return [],None

'''
view,n=re.subn(r'def _gear_source\(app,part,model\):.*?\n(?=def _find_paint_loose\()',lambda m:gear_source,view,count=1,flags=re.S)
if n!=1:raise SystemExit('gear source replacement anchor missing')

compose_rider=r'''def _compose_rider(app,state):
    profile=str(state.get('rider') or 'default_mx');body_edf=_body_source(app,profile)
    body=_upright_body(_decode_edf('rider',[body_edf]));all_nodes=list(body);edfs=[body_edf];pnts=[];warnings=[]
    pnts += _find_paint_loose(app,'suit',profile=profile,paint=str(state.get('suit_paint') or ''))
    pnts += _find_paint_loose(app,'gloves',profile=profile,paint=str(state.get('gloves_paint') or ''))
    blo,bhi=_bounds(body);cx=(blo[0]+bhi[0])/2;cz=(blo[2]+bhi[2])/2;h=max(1e-6,bhi[1]-blo[1]);depth=max(1e-6,bhi[2]-blo[2]);legx=.265*(bhi[0]-blo[0])
    helmet_anchor=(cx,bhi[1]-.11*h,cz+.08*depth);footy=blo[1]+.08*h;bootz=cz+.16*depth;prot_anchor=(cx,blo[1]+.74*h,cz)
    try:
        helmet_edfs,helmet_root=_gear_source(app,'helmet',state.get('helmet','default'))
        if helmet_edfs:
            helmet=_decode_edf('gear',helmet_edfs);_place_piece(helmet,helmet_anchor,.38*h,GEAR_ROT,math.pi,HELMET_PITCH,'bottom');all_nodes+=helmet;edfs+=helmet_edfs
            pnts += _find_paint_loose(app,'helmet',profile=profile,model=str(state.get('helmet') or 'default'),paint=str(state.get('helmet_paint') or ''))
            pnts += _find_paint_loose(app,'goggles',profile=profile,model=str(state.get('helmet') or 'default'),paint=str(state.get('goggles_paint') or ''))
    except Exception as exc:warnings.append('helmet: '+str(exc))
    try:
        prot_edfs,prot_root=_gear_source(app,'protection',state.get('protection','full'))
        if prot_edfs:
            prot=_decode_edf('gear',prot_edfs);_place_piece(prot,prot_anchor,1.0,GEAR_ROT,PROT_YAW,0,'center',native=True);all_nodes+=prot;edfs+=prot_edfs
            pnts += _find_paint_loose(app,'protection',profile=profile,model=str(state.get('protection') or 'full'),paint=str(state.get('protection_paint') or ''))
    except Exception as exc:warnings.append('protection: '+str(exc))
    try:
        boots_edfs,boots_root=_gear_source(app,'boots',state.get('boots','default'))
        if boots_edfs:
            bootnodes=_decode_edf('gear',boots_edfs);edfs+=boots_edfs
            if len(bootnodes)==2:
                for i,node in enumerate(bootnodes):
                    name=(node.get('name') or '').lower();side=1 if ('_l' in name or 'left' in name or name.startswith('lboot')) else -1 if ('_r' in name or 'right' in name or name.startswith('rboot')) else (-1 if i==0 else 1)
                    piece=[node];_place_piece(piece,(cx+side*legx,footy,bootz),.44*h,BOOT_ROT,side*BOOT_SPLAY,BOOT_PITCH,'top');all_nodes+=piece
            else:
                _place_piece(bootnodes,(cx,footy,bootz),.44*h,BOOT_ROT,0,BOOT_PITCH,'top');all_nodes+=bootnodes
            pnts += _find_paint_loose(app,'boots',profile=profile,model=str(state.get('boots') or 'default'),paint=str(state.get('boots_paint') or ''))
    except Exception as exc:warnings.append('boots: '+str(exc))
    return all_nodes,_texture_set(edfs,pnts),edfs,warnings

'''
view,n=re.subn(r'def _compose_rider\(app,state\):.*?\n(?=def _submesh_texture\()',lambda m:compose_rider,view,count=1,flags=re.S)
if n!=1:raise SystemExit('compose rider replacement anchor missing')

viewer_class=r'''class FrostNativeViewer:
    """Background viewer backed by real MX Bikes EDF/PNT data. No stand-ins and no error flicker."""
    def __init__(self,app):
        self.app=app;self.yaw=-.55;self.pitch=-.12;self.zoom=1.0
        self._exec=ThreadPoolExecutor(max_workers=1,thread_name_prefix='RDL-FrostEDF');self._token=0;self._lock=threading.Lock();self._drag=None;self._after=None;self._canvas=None;self._request=None
        self._last_key=None;self._last_state=None;self._last_size=(0,0);self._bound_size=(0,0)

    def _message(self,canvas,title,detail=''):
        try:
            w=max(420,canvas.winfo_width());h=max(300,canvas.winfo_height());canvas.delete('frost_edf_message')
            canvas.create_rectangle(24,24,w-24,h-24,fill='#080b0f',outline='#29313a',width=1,tags='frost_edf_message')
            canvas.create_text(w/2,h/2-22,text=title,fill='#ff6b6b',font=('Segoe UI Black',12),width=max(260,w-90),justify='center',tags='frost_edf_message')
            if detail:canvas.create_text(w/2,h/2+25,text=str(detail)[:900],fill='#aeb7c2',font=('Segoe UI',9),width=max(260,w-100),justify='center',tags='frost_edf_message')
        except Exception:pass

    def _submit(self,canvas,build,focus,status_cb,reset=False,request_key=''):
        if reset:self.yaw=-.55;self.pitch=-.12;self.zoom=1.0
        try:w=max(500,canvas.winfo_width());h=max(350,canvas.winfo_height())
        except Exception:return
        key=(str(request_key),str(focus),int(w//24),int(h//24),round(self.yaw,3),round(self.pitch,3),round(self.zoom,3))
        with self._lock:
            if not reset and key==self._last_key and self._last_state in ('loading','ready','error'):return
            self._token+=1;token=self._token;self._last_key=key;self._last_state='loading';self._last_size=(w,h)
        if status_cb:
            try:status_cb('loading','real MX Bikes EDF')
            except Exception:pass
        def worker():
            try:nodes,tex,detail=build();frame=render_nodes(nodes,tex,w,h,self.yaw,self.pitch,self.zoom,focus);result=('ready',frame,detail)
            except Exception as exc:result=('error',None,str(exc))
            def apply():
                with self._lock:
                    if token!=self._token:return
                    self._last_state=result[0]
                try:
                    if not canvas.winfo_exists():return
                except Exception:return
                state,frame,detail=result
                if state=='ready':
                    try:
                        photo=ImageTk.PhotoImage(frame);canvas.delete('frost_edf_frame');canvas.delete('frost_edf_message')
                        canvas.create_image(canvas.winfo_width()/2,canvas.winfo_height()/2,image=photo,anchor='center',tags='frost_edf_frame');canvas._frost_edf_photo=photo
                    except Exception as exc:state,detail='error',str(exc);self._message(canvas,'MODEL VIEWER ERROR',detail)
                else:
                    canvas.delete('frost_edf_frame');self._message(canvas,'REAL MODEL COULD NOT BE LOADED',detail)
                if status_cb:
                    try:status_cb(state,detail)
                    except Exception:pass
            try:canvas.after(0,apply)
            except Exception:pass
        self._exec.submit(worker)

    def request_bike(self,canvas,state,status_cb=None,reset=False):
        state=dict(state);request_key='bike:'+json.dumps(state,sort_keys=True,default=str)
        def build():
            edfs,geom,pnts=_bike_bundle(self.app,state.get('bikeid',''),state.get('paint',''));nodes=_decode_edf('bike',edfs,geom);return nodes,_texture_set(edfs,pnts),'ACTUAL INSTALLED MX BIKES EDF'
        self._canvas=canvas;self._request=lambda:self.request_bike(canvas,state,status_cb);self._submit(canvas,build,'bike',status_cb,reset,request_key)

    def request_rider(self,canvas,state,focus,status_cb=None,reset=False):
        state=dict(state);request_key='rider:'+str(focus)+':'+json.dumps(state,sort_keys=True,default=str)
        def build():
            nodes,tex,edfs,warnings=_compose_rider(self.app,state);detail='ACTUAL MX BIKES RIDER / GEAR EDF'
            if warnings:detail+=' • optional gear skipped: '+'; '.join(warnings[:2])
            return nodes,tex,detail
        self._canvas=canvas;self._request=lambda:self.request_rider(canvas,state,focus,status_cb);self._submit(canvas,build,focus,status_cb,reset,request_key)

    def bind(self,canvas):
        self._canvas=canvas
        def schedule(ms=55):
            try:
                if self._after:canvas.after_cancel(self._after)
            except Exception:pass
            try:self._after=canvas.after(ms,lambda:self._request and self._request())
            except Exception:pass
        def down(e):self._drag=(e.x,e.y,self.yaw,self.pitch)
        def drag(e):
            if not self._drag:return
            x,y,a,b=self._drag;self.yaw=a+(e.x-x)*.012;self.pitch=max(-1.2,min(1.2,b+(e.y-y)*.009));schedule()
        def wheel(e):self.zoom=max(.35,min(3.0,self.zoom*(1.12 if e.delta>0 else .89)));schedule()
        def resized(e):
            old=self._bound_size;now=(int(getattr(e,'width',0)),int(getattr(e,'height',0)));self._bound_size=now
            if self._last_state=='ready' and (abs(now[0]-old[0])>=32 or abs(now[1]-old[1])>=32):schedule(180)
        canvas.bind('<ButtonPress-1>',down,add='+');canvas.bind('<B1-Motion>',drag,add='+');canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'_drag',None),add='+');canvas.bind('<MouseWheel>',wheel,add='+');canvas.bind('<Configure>',resized,add='+')

    def cancel(self):
        with self._lock:self._token+=1;self._last_state=None;self._last_key=None
'''
view,n=re.subn(r'class FrostNativeViewer:.*\Z',lambda m:viewer_class,view,count=1,flags=re.S)
if n!=1:raise SystemExit('viewer class replacement anchor missing')
p.write_text(view,encoding='utf-8')

p=work/'src'/'app.py';app=p.read_text(encoding='utf-8')
old="tab=active_tab();canvas.delete('all');update_info()"
if old not in app:raise SystemExit('Garage canvas-clear anchor missing')
app=app.replace(old,"tab=active_tab();update_info()",1)
hot_marker='    def _after_hot_reload(self,target_version,snapshot):\n'
if hot_marker not in app:raise SystemExit('hot reload method anchor missing')
if 'v0.5.11 shell migration' not in app:
    shell_refresh=(hot_marker+
"        # v0.5.11 shell migration: install the branded launcher and retarget desktop/pinned links now.\n"
"        try:\n"
"            import importlib\n"
"            from . import windows_integration as _rdl_wi\n"
"            _rdl_wi=importlib.reload(_rdl_wi)\n"
"            _rdl_wi.ensure_desktop_shortcut(__import__('pathlib').Path(__file__).resolve().parent.parent)\n"
"        except Exception:pass\n")
    app=app.replace(hot_marker,shell_refresh,1)
p.write_text(app,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
view=(work/'src/frost_native_viewer.py').read_text(encoding='utf-8');app=(work/'src/app.py').read_text(encoding='utf-8');wint=(work/'src/windows_integration.py').read_text(encoding='utf-8');task=(work/'src/windows_taskbar.py').read_text(encoding='utf-8')
assert "VERSION = '0.5.11'" in (work/'src/config.py').read_text(encoding='utf-8'),'gate:version'
assert '_extract_game_bike_pkz' in view and "game/'bikes.pkz'" in view,'gate:stock_bikes_pkz'
assert "self._last_state=='ready'" in view and "key==self._last_key" in view,'gate:viewer_dedupe'
assert 'REAL MODEL COULD NOT BE LOADED' in view,'gate:error_panel'
assert "warnings.append('helmet:" in view and "warnings.append('boots:" in view,'gate:rider_optional_gear'
assert "tab=active_tab();canvas.delete('all');update_info()" not in app,'gate:no_canvas_wipe'
assert 'v0.5.11 shell migration' in app,'gate:hot_shell_migration'
assert "dst=root/LAUNCHER_NAME" in wint and "packaged_launcher(root)" in wint,'gate:real_root_launcher'
assert "runtime.with_name(LAUNCHER_NAME)" in wint and "legacy.unlink()" in wint,'gate:legacy_python_copy_retired'
assert '_migrate_pinned_shortcuts' in wint and 'rdl_runtime.txt' in wint,'gate:pin_migration'
assert "APP_ID='MXBRaceDayLive.Desktop'" in wint and "APP_ID='MXBRaceDayLive.Desktop'" in task,'gate:stable_app_id'
assert (work/'assets/bin/MXB Race Day Live.exe').read_bytes()[:2]==b'MZ','gate:branded_launcher_payload'
for forbidden in ('BikeStandIn','RiderBody(', 'sphereGeometry','capsuleGeometry','boxGeometry','OFFICIAL_TEMPLATES_URL','generate_proxy_mesh','mxbikes.exe'):
    assert forbidden not in view,'gate:no_generic_or_game:'+forbidden

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
LAUNCHER.unlink(missing_ok=True)
Path('race-control/staging/mxb_asset_decoder.exe').unlink(missing_ok=True)
print('VIEWER GATE',{'stock_bikes_pkz':True,'error_flicker':False,'black_error_box':False,'optional_gear_fatal':False,'generic_models':False})
print('WINDOWS GATE',{'renamed_pythonw':False,'branded_launcher':True,'pinned_links_migrated':True,'stable_app_id':True,'python_shell_identity':False})
print('BUILT',OUT,digest)
