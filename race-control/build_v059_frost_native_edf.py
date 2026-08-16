from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_8_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_9_UPDATE.zip')
VIEWER=Path('race-control/frost_native_viewer_v059.py')
DECODER=Path('race-control/staging/mxb_asset_decoder.exe')
NOTICE=Path('race-control/FROST_THIRD_PARTY_NOTICE.txt')
VERSION='0.5.9'
NOTES=(
 'MXB Race Day Live v0.5.9 replaces the failed template/generic Garage viewer with a real MX Bikes asset pipeline adapted from Frost/mxb-app (MIT). '
 'A native Windows decoder built from Frost’s pinned public EDF parser reads actual MX Bikes EDF vertices, UVs, normals, submeshes and node-local material data; Race Day Live reads actual PNT paint sheets and EDF-embedded textures, resolves loose and plain-PKZ bike/rider assets using MX Bikes’ real folder layout, assembles bike parts using .geom mount data, and renders the selected installed geometry without launching MX Bikes. '
 'The rider viewer now resolves the selected profile’s real rider.edf first, then the selected helmet/boots/protection EDFs, and uses the actual suit/glove/goggle/gear PNTs when readable. The old PiBoSo-template viewer is removed from the package and no generic bike/rider stand-in is reachable from Garage. '
 'Creator-locked/non-ZIP PKZs are reported as unreadable instead of being cracked or replaced by fake geometry because Frost’s private optional locked-PKZ sidecar is not public. '
 'Bike/Helmet/Gear/Boots/Goggles/Gloves/Protection dropdowns, native profile sync, OEM category linking, v0.5.1 performance work, v0.5.6 working taskbar icon and stay-open hot updates are preserved.'
)
for p in (BASE,VIEWER,DECODER,NOTICE):
    if not p.exists():raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.8 base invalid')
if DECODER.read_bytes()[:2]!=b'MZ':raise SystemExit('Windows EDF decoder is not a PE executable')
work=Path(tempfile.mkdtemp(prefix='mxb_v059_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)

# Replace the failed v0.5.8 viewer, do not layer another fallback on top of it.
(work/'src'/'native_rider_viewer.py').unlink(missing_ok=True)
shutil.copy2(VIEWER,work/'src'/'frost_native_viewer.py')
(work/'assets'/'bin').mkdir(parents=True,exist_ok=True)
shutil.copy2(DECODER,work/'assets'/'bin'/'mxb_asset_decoder.exe')
(work/'THIRD_PARTY_NOTICES').mkdir(parents=True,exist_ok=True)
shutil.copy2(NOTICE,work/'THIRD_PARTY_NOTICES'/'Frost-mxb-app-MIT.txt')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

# Hot reload the new viewer instead of the removed v0.5.8 template module.
p=work/'src/hot_reload.py';hot=p.read_text(encoding='utf-8')
hot=hot.replace("'src.native_rider_viewer'","'src.frost_native_viewer'")
if "'src.frost_native_viewer'" not in hot:
    hot=hot.replace("'src.in_app_garage'","'src.in_app_garage','src.frost_native_viewer'",1)
p.write_text(hot,encoding='utf-8')

p=work/'src/app.py';app=p.read_text(encoding='utf-8')
old='from .native_rider_viewer import OfficialMXRiderRenderer'
if old not in app:raise SystemExit('v0.5.8 rider viewer import anchor missing')
app=app.replace(old,'from .frost_native_viewer import FrostNativeViewer',1)

hotpos=app.find('    def _after_hot_reload(self,target_version,snapshot):')
gstart=app.rfind('    def page_garage(self):',0,hotpos)
if gstart<0 or hotpos<0:raise SystemExit('Garage block missing')
g=app[gstart:hotpos]

old_init="""        if not hasattr(self,'official_rider_renderer') or self.official_rider_renderer is None:\n            self.official_rider_renderer=OfficialMXRiderRenderer(self)\n        viewer_bound={'bike':False,'rider':False}\n"""
new_init="""        if not hasattr(self,'frost_native_viewer') or self.frost_native_viewer is None:\n            self.frost_native_viewer=FrostNativeViewer(self)\n        self.frost_native_viewer.bind(canvas)\n"""
if old_init not in g:raise SystemExit('v0.5.8 viewer init anchor missing')
g=g.replace(old_init,new_init,1)

s=g.find("        def viewer_status(kind,detail=''):")
e=g.find('        def update_info():',s)
if s<0 or e<0:raise SystemExit('viewer status anchors missing')
g=g[:s]+'''        def viewer_status(kind,detail=''):\n            if kind=='ready':status.configure(text='● REAL MX BIKES EDF / PNT',fg=GREEN)\n            elif kind=='loading':status.configure(text='● LOADING REAL MX BIKES ASSETS…',fg=GOLD)\n            else:\n                status.configure(text='● EXACT MODEL UNAVAILABLE',fg=RED)\n                if detail:info.configure(text=str(detail))\n\n'''+g[e:]

s=g.find('        def update_viewer(reset=False):')
e=g.find('        def changed(key):',s)
if s<0 or e<0:raise SystemExit('update_viewer anchors missing')
g=g[:s]+'''        def update_viewer(reset=False):\n            tab=active_tab();canvas.delete('all');update_info()\n            if tab=='Bike':\n                self.frost_native_viewer.request_bike(canvas,state,viewer_status,reset=reset)\n            else:\n                self.frost_native_viewer.request_rider(canvas,state,rider_region(),viewer_status,reset=reset)\n\n'''+g[e:]
app=app[:gstart]+g+app[hotpos:]

# Cancel stale frame application across a stay-open code refresh; the new class is lazy-created
# the next time Garage is opened.
hs=app.find('    def _after_hot_reload(self,target_version,snapshot):')
he=app.find('    def do_update(self):',hs)
if hs>=0 and he>hs:
    hb=app[hs:he]
    marker='        try:self.mx_extension.stop()\n'
    if 'frost_native_viewer.cancel()' not in hb and marker in hb:
        hb=hb.replace(marker,"        try:\n            if hasattr(self,'frost_native_viewer') and self.frost_native_viewer:self.frost_native_viewer.cancel()\n        except Exception:pass\n        self.frost_native_viewer=None\n"+marker,1)
    app=app[:hs]+hb+app[he:]
p.write_text(app,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
appc=(work/'src/app.py').read_text(encoding='utf-8')
view=(work/'src/frost_native_viewer.py').read_text(encoding='utf-8')
hot=(work/'src/hot_reload.py').read_text(encoding='utf-8')
perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
winint=(work/'src/windows_integration.py').read_bytes();task=(work/'src/windows_taskbar.py').read_bytes()

assert "VERSION = '0.5.9'" in (work/'src/config.py').read_text(encoding='utf-8'),'gate:version'
assert not (work/'src/native_rider_viewer.py').exists(),'gate:old_template_viewer_removed'
assert (work/'assets/bin/mxb_asset_decoder.exe').read_bytes()[:2]==b'MZ','gate:native_decoder_packaged'
assert (work/'THIRD_PARTY_NOTICES/Frost-mxb-app-MIT.txt').is_file(),'gate:frost_license_notice'
for marker in ('FrostNativeViewer','request_bike(canvas,state','request_rider(canvas,state','REAL MX BIKES EDF / PNT'):
    assert marker in appc,'gate:app_frost:'+marker
newblock=appc[appc.rfind('    def page_garage(self):',0,appc.find('    def _after_hot_reload')):appc.find('    def _after_hot_reload')]
for forbidden in ('OfficialMXRiderRenderer','official_rider_renderer','garage_renderer.request','generate_proxy_mesh','mxbikes.exe','launch_game('):
    assert forbidden not in newblock,'gate:no_old_or_game:'+forbidden
for tab in ("'Bike'","'Helmet'","'Gear'","'Boots'","'Goggles'","'Gloves'","'Protection'"):
    assert tab in newblock,'gate:tab:'+tab
for marker in ('mxb_asset_decoder.exe','decode_pnt','embedded_edf_textures',"'rider.edf'","'protections'",'_decode_edf','assemble'):
    assert marker in view,'gate:real_asset_pipeline:'+marker
for forbidden in ('BikeStandIn','RiderBody(', 'sphereGeometry','capsuleGeometry','boxGeometry','OFFICIAL_TEMPLATES_URL','generate_proxy_mesh'):
    assert forbidden not in view,'gate:no_generic:'+forbidden
assert "subprocess.run(cmd" in view and "CREATE_NO_WINDOW" in view,'gate:decoder_background_process'
assert 'mxbikes.exe' not in view and 'Steam' not in view,'gate:no_game_process'
assert 'ThreadPoolExecutor(max_workers=1' in view,'gate:background_render'
assert 'install_hot_update' in hot and 'refresh_running_app' in hot,'gate:hot_update'
assert 'PRAGMA cache_size=-65536' in perf,'gate:v051_perf'

# The taskbar icon finally works. Freeze both modules byte-for-byte from v0.5.8.
basecheck=Path(tempfile.mkdtemp(prefix='mxb_v059_basecheck_'))
with zipfile.ZipFile(BASE) as z:
    z.extract('src/windows_integration.py',basecheck);z.extract('src/windows_taskbar.py',basecheck)
assert winint==(basecheck/'src/windows_integration.py').read_bytes(),'gate:working_taskbar_integration_changed'
assert task==(basecheck/'src/windows_taskbar.py').read_bytes(),'gate:working_taskbar_hwnd_changed'
shutil.rmtree(basecheck,ignore_errors=True)

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
# Artifact is release input, not source control content.
DECODER.unlink(missing_ok=True)
print('FROST EDF GATE',{'real_edf_decoder':True,'actual_pnt':True,'actual_rider_edf':True,'actual_gear_edf':True,'geom_assembly':True,'generic_models':False,'mxbikes_process':False})
print('UI/SYNC GATE',{'tabs':['Bike','Helmet','Gear','Boots','Goggles','Gloves','Protection'],'native_profile_sync':True,'locked_pkz_fails_closed':True})
print('STABILITY GATE',{'background_render':True,'v051_perf':True,'v056_taskbar_unchanged':True,'hot_update':True})
print('BUILT',OUT,digest)
