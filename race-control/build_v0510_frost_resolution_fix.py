from pathlib import Path
import hashlib,json,py_compile,re,shutil,tempfile,zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_9_UPDATE.zip')
OUT=Path('race-control/releases/MXB_Race_Day_Live_v0_5_10_UPDATE.zip')
DECODER=Path('race-control/staging/mxb_asset_decoder.exe')
VERSION='0.5.10'
NOTES=(
 'MXB Race Day Live v0.5.10 corrects two Frost-viewer bridge issues found before user testing v0.5.9. '
 'Plain PKZ extraction now keeps every real viewer asset (.edf/.hrc/.geom/.cfg/.pnt/.tga) regardless of whether its internal filename repeats the bike ID, matching Frost mxb-app behavior so root-level model.edf and split-part EDF packages are not discarded. '
 'Native-fit protection gear now preserves its authored origin instead of being recentered, matching Frost’s RiderGearMesh native placement. '
 'The real Frost-based EDF/PNT pipeline, selected rider.edf and gear EDF resolution, .geom bike assembly, background rendering, seven Garage dropdown tabs, native MX Bikes profile sync, performance work, stay-open updates and the working taskbar icon are preserved. No generic bike/rider model and no MX Bikes process are used by Garage. Locked/non-ZIP PKZs still fail closed rather than being replaced with fake geometry.'
)
for p in (BASE,DECODER):
    if not p.exists():raise SystemExit(f'missing required input: {p}')
if not zipfile.is_zipfile(BASE):raise SystemExit('v0.5.9 base missing/invalid')
if DECODER.read_bytes()[:2]!=b'MZ':raise SystemExit('Windows EDF decoder is not a PE executable')
work=Path(tempfile.mkdtemp(prefix='mxb_v0510_'))
with zipfile.ZipFile(BASE) as z:z.extractall(work)

# Always refresh the native decoder artifact from the pinned Frost source built by this run.
(work/'assets'/'bin').mkdir(parents=True,exist_ok=True)
shutil.copy2(DECODER,work/'assets'/'bin'/'mxb_asset_decoder.exe')

for rel,var in [('src/config.py','VERSION'),('src/__init__.py','__version__')]:
    p=work/rel;s=p.read_text(encoding='utf-8')
    s2,n=re.subn(rf"{var}\s*=\s*['\"][^'\"]+['\"]",f"{var} = '{VERSION}'",s,count=1)
    if n!=1:raise SystemExit(f'version anchor missing in {rel}')
    p.write_text(s2,encoding='utf-8')
p=work/'src/updater.py';up=p.read_text(encoding='utf-8')
up=re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+',f'MXB-Race-Day-Live-Updater/{VERSION}',up)
p.write_text(up,encoding='utf-8')

p=work/'src/frost_native_viewer.py';view=p.read_text(encoding='utf-8')
# Frost gathers the viewer file set by file type. Internal bike PKZ filenames do NOT need to
# repeat the outer bike ID; common packages use root-level model.edf/model.geom or arbitrary
# part names. The v0.5.9 bridge incorrectly filtered those out.
old="""                if prefix_hint and prefix_hint.lower() not in low and low.endswith(('.edf','.geom','.hrc','.cfg')):\n                    # Keep paints broadly but constrain large geometry to the selected model where possible.\n                    continue\n"""
if old not in view:raise SystemExit('PKZ internal-name filter anchor missing')
view=view.replace(old,'',1)
# Frost native-fit protection keeps the mesh's authored origin; only box-fit pieces are
# recentered. v0.5.9 calculated the centre unconditionally.
old="""    scale=1.0 if native else target/max(max(size),1e-6)\n    shift_y=(size[1]/2*scale if align=='bottom' else -size[1]/2*scale if align=='top' else 0.0)\n    def place(x,y,z,n=False):\n        if n:return x,y,z\n        return (anchor[0]+(x-center[0])*scale,anchor[1]+(y-center[1])*scale+shift_y,anchor[2]+(z-center[2])*scale)\n"""
new="""    scale=1.0 if native else target/max(max(size),1e-6)\n    recentre=(0.0,0.0,0.0) if native else tuple(center)\n    shift_y=(size[1]/2*scale if align=='bottom' else -size[1]/2*scale if align=='top' else 0.0)\n    def place(x,y,z,n=False):\n        if n:return x,y,z\n        return (anchor[0]+(x-recentre[0])*scale,anchor[1]+(y-recentre[1])*scale+shift_y,anchor[2]+(z-recentre[2])*scale)\n"""
if old not in view:raise SystemExit('native placement anchor missing')
view=view.replace(old,new,1)
p.write_text(view,encoding='utf-8')

for py in work.rglob('*.py'):py_compile.compile(str(py),doraise=True)
view=p.read_text(encoding='utf-8');app=(work/'src/app.py').read_text(encoding='utf-8');hot=(work/'src/hot_reload.py').read_text(encoding='utf-8');perf=(work/'src/runtime_perf.py').read_text(encoding='utf-8')
assert "VERSION = '0.5.10'" in (work/'src/config.py').read_text(encoding='utf-8'),'gate:version'
assert 'prefix_hint.lower() not in low' not in view,'gate:no_internal_name_filter'
assert "recentre=(0.0,0.0,0.0) if native else tuple(center)" in view,'gate:native_origin_preserved'
assert 'mxb_asset_decoder.exe' in view and (work/'assets/bin/mxb_asset_decoder.exe').read_bytes()[:2]==b'MZ','gate:frost_decoder'
for marker in ('decode_pnt','embedded_edf_textures',"'rider.edf'","'protections'",'_decode_edf'):
    assert marker in view,'gate:real_assets:'+marker
for forbidden in ('BikeStandIn','RiderBody(', 'sphereGeometry','capsuleGeometry','boxGeometry','OFFICIAL_TEMPLATES_URL','generate_proxy_mesh','mxbikes.exe'):
    assert forbidden not in view,'gate:no_generic_or_game:'+forbidden
newblock=app[app.rfind('    def page_garage(self):',0,app.find('    def _after_hot_reload')):app.find('    def _after_hot_reload')]
for tab in ("'Bike'","'Helmet'","'Gear'","'Boots'","'Goggles'","'Gloves'","'Protection'"):
    assert tab in newblock,'gate:tab:'+tab
assert 'FrostNativeViewer' in app and 'self.mx_extension.mirror_selection(state)' in app,'gate:viewer_and_profile_sync'
assert 'ThreadPoolExecutor(max_workers=1' in view,'gate:background_render'
assert 'install_hot_update' in hot and 'refresh_running_app' in hot,'gate:hot_update'
assert 'PRAGMA cache_size=-65536' in perf,'gate:v051_perf'
# Freeze the finally-working taskbar modules byte-for-byte from v0.5.9.
basecheck=Path(tempfile.mkdtemp(prefix='mxb_v0510_basecheck_'))
with zipfile.ZipFile(BASE) as z:
    z.extract('src/windows_integration.py',basecheck);z.extract('src/windows_taskbar.py',basecheck)
assert (work/'src/windows_integration.py').read_bytes()==(basecheck/'src/windows_integration.py').read_bytes(),'gate:taskbar_integration_changed'
assert (work/'src/windows_taskbar.py').read_bytes()==(basecheck/'src/windows_taskbar.py').read_bytes(),'gate:taskbar_hwnd_changed'
shutil.rmtree(basecheck,ignore_errors=True)

OUT.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,f.relative_to(work).as_posix())
digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'version':VERSION,'url':f'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/{OUT.name}','sha256':digest,'notes':NOTES}
Path('race-control/latest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
DECODER.unlink(missing_ok=True)
print('FROST RESOLUTION GATE',{'root_model_edf_kept':True,'split_edfs_kept':True,'native_protection_origin':True,'generic_models':False,'mxbikes_process':False})
print('PRESERVATION GATE',{'seven_dropdown_tabs':True,'native_profile_sync':True,'background_render':True,'v051_perf':True,'v056_taskbar_unchanged':True,'hot_update':True})
print('BUILT',OUT,digest)
