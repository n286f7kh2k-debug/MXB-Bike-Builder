from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageTk
except Exception:
    Image = ImageDraw = ImageTk = None


class FrostViewerError(RuntimeError):
    pass


# Frost / MX Bikes viewer conventions.  See FROST_THIRD_PARTY_NOTICE.txt.
GEAR_ROT = (0.0, 0.0, -math.pi / 2.0)
BOOT_ROT = (0.0, 0.0, math.pi / 2.0)
PROT_YAW = -math.pi / 2.0
HELMET_PITCH = 0.25
BOOT_PITCH = 0.20
BOOT_SPLAY = 0.48
STOCK_RIDERS = ('default_mx', 'default_sm')
VIEWER_SUFFIXES = ('.edf', '.hrc', '.geom', '.cfg', '.pnt', '.tga')
MAX_RENDER_TRIS = 60000


def _cache_root():
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
    p = Path(base) / 'MXB Race Day Live' / 'cache' / 'frost_native_viewer'
    p.mkdir(parents=True, exist_ok=True)
    return p


def _decoder_path():
    root = Path(__file__).resolve().parent.parent
    for p in (root/'assets'/'bin'/'mxb_asset_decoder.exe', root/'mxb_asset_decoder.exe'):
        if p.is_file():
            return p
    raise FrostViewerError('MXB native EDF decoder is missing from this Race Day Live update.')


def _stamp(paths, extra=''):
    h = hashlib.sha256(str(extra).encode())
    for p in paths:
        p = Path(p)
        try:
            s = p.stat()
            h.update(str(p.resolve()).lower().encode('utf-8', errors='ignore'))
            h.update(struct.pack('<QQ', int(s.st_size), int(s.st_mtime_ns)))
        except Exception:
            h.update(str(p).lower().encode())
    return h.hexdigest()


def _decode_edf(mode, edfs, geom=None):
    edfs = [Path(p) for p in edfs if Path(p).is_file()]
    if not edfs:
        raise FrostViewerError('No real MX Bikes EDF mesh was found for this selection.')
    geom = Path(geom) if geom and Path(geom).is_file() else None
    key = _stamp(edfs + ([geom] if geom else []), mode)
    out = _cache_root() / 'decoded' / f'{key}.json.gz'
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.is_file():
        tmp = out.with_suffix('.tmp')
        cmd = [str(_decoder_path()), str(mode), str(tmp), str(geom) if geom else '-'] + [str(p) for p in edfs]
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=60, creationflags=flags)
        if cp.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise FrostViewerError((cp.stderr or cp.stdout or 'EDF decoder failed').strip())
        os.replace(tmp, out)
    with gzip.open(out, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    if data.get('format') != 'MXB-RDL-EDF-1' or not data.get('nodes'):
        raise FrostViewerError('The selected EDF did not contain renderable MX Bikes geometry.')
    return data['nodes']


def _plain_zip(path):
    try:
        with Path(path).open('rb') as f:
            return f.read(4) == b'PK\x03\x04'
    except Exception:
        return False


def _safe_name(name):
    parts = [p for p in name.replace('\\','/').split('/') if p and p not in ('.','..')]
    return Path(*parts) if parts else None


def _extract_viewer_pkz(path, prefix_hint=''):
    path = Path(path)
    if not _plain_zip(path):
        raise FrostViewerError(f'{path.name} is a locked/non-ZIP PKZ. The public Frost reader does not expose the private locked-PKZ sidecar, so Race Day Live will not fake or crack it.')
    key = _stamp([path], prefix_hint)
    dst = _cache_root() / 'pkz' / key
    ready = dst / '.ready'
    if ready.is_file():
        return dst
    stage = Path(tempfile.mkdtemp(prefix='rdl_pkz_'))
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir() or int(info.file_size or 0) > 192*1024*1024:
                    continue
                low = info.filename.replace('\\','/').lower()
                if not low.endswith(VIEWER_SUFFIXES):
                    continue
                if prefix_hint and prefix_hint.lower() not in low and low.endswith(('.edf','.geom','.hrc','.cfg')):
                    # Keep paints broadly but constrain large geometry to the selected model where possible.
                    continue
                rel = _safe_name(info.filename)
                if rel is None:
                    continue
                target = stage / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open('wb') as out:
                    shutil.copyfileobj(src, out)
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage), str(dst))
        ready.write_text('ok\n', encoding='utf-8')
        return dst
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def _visible_edfs(root):
    root = Path(root)
    files = []
    if root.is_file() and root.suffix.lower()=='.edf':
        return [root]
    try:
        files = list(root.rglob('*.edf'))
    except Exception:
        files = []
    def score(p):
        n=p.name.lower();s=0
        if n=='model.edf':s+=100
        if n.endswith('_s.edf') or 'shadow' in n:s-=200
        if n.startswith('c_'):s-=100
        return (-s, len(n), n)
    return sorted([p for p in files if p.is_file() and not p.name.lower().endswith('_s.edf') and not p.name.lower().startswith('c_')], key=score)


def _find_geom(root):
    try:
        hits=sorted(Path(root).rglob('*.geom'))
        return hits[0] if hits else None
    except Exception:return None


def _garage_roots(garage):
    try:return [Path(p) for p in garage._roots()]
    except Exception:return []


def _bike_record(garage,bike_id):
    try:
        for rec in garage.bike_records():
            if str(rec.get('id','')).lower()==str(bike_id).lower():return rec
    except Exception:pass
    return None


def _bike_bundle(app,bike_id,paint=''):
    garage=app.bike_garage;rec=_bike_record(garage,bike_id);candidates=[]
    if rec and rec.get('path'):candidates.append(Path(rec['path']))
    for root in _garage_roots(garage):
        candidates += [root/'bikes'/str(bike_id), root/'bikes'/(str(bike_id)+'.pkz')]
    seen=set();source=None
    for p in candidates:
        k=str(p).lower()
        if k in seen:continue
        seen.add(k)
        if p.is_dir() and _visible_edfs(p):source=p;break
        if p.is_file() and p.suffix.lower()=='.edf':source=p;break
        if p.is_file() and p.suffix.lower()=='.pkz':source=_extract_viewer_pkz(p,str(bike_id));break
        if p.is_dir():
            sibling=p.with_suffix('.pkz')
            if sibling.is_file():source=_extract_viewer_pkz(sibling,str(bike_id));break
    if source is None:
        raise FrostViewerError('No installed EDF/PKZ source was found for this bike.')
    edfs=_visible_edfs(source)
    if not edfs:raise FrostViewerError('The selected bike source contains no readable EDF geometry.')
    geom=_find_geom(source)
    paints=[]
    if paint:
        # Paints installed beside a packaged OEM bike override whatever the EDF embeds.
        for root in _garage_roots(garage):
            p=root/'bikes'/str(bike_id)/'paints'/(str(paint)+'.pnt')
            if p.is_file():paints.append(p)
        try:
            hits=list(Path(source).rglob(str(paint)+'.pnt'))
            paints.extend(h for h in hits if h.is_file())
        except Exception:pass
    return edfs,geom,paints


def _game_dir(app):
    try:
        exe=app.game_bridge.game_exe()
        return Path(exe).parent if exe else None
    except Exception:return None


def _rider_bases(app):
    return [r/'rider' for r in _garage_roots(app.bike_garage)]


def _extract_entry_from_plain_pkz(pkz, suffixes, tag):
    pkz=Path(pkz)
    if not pkz.is_file():return []
    if not _plain_zip(pkz):
        raise FrostViewerError(f'{pkz.name} is locked/non-ZIP; its private decoder is not in Frost\'s public repository.')
    dst=_cache_root()/'rider_pkz'/_stamp([pkz],tag);dst.mkdir(parents=True,exist_ok=True);out=[]
    wants=[s.replace('\\','/').lower() for s in suffixes]
    with zipfile.ZipFile(pkz) as z:
        for info in z.infolist():
            low=info.filename.replace('\\','/').lower()
            if not any(low.endswith(w) for w in wants):continue
            name=Path(low).name;target=dst/name
            if not target.is_file():
                with z.open(info) as src,target.open('wb') as f:shutil.copyfileobj(src,f)
            out.append(target)
    return out


def _body_source(app,profile):
    profile=str(profile or 'default_mx').strip() or 'default_mx'
    for base in _rider_bases(app):
        loose=base/'riders'/profile/'rider.edf'
        if loose.is_file():return loose
        packed=base/'riders'/(profile+'.pkz')
        if packed.is_file():
            hits=_extract_entry_from_plain_pkz(packed,[f'rider/riders/{profile}/rider.edf','rider.edf'],f'body-{profile}')
            if hits:return hits[0]
    game=_game_dir(app)
    if game:
        pkz=game/'rider.pkz'
        if pkz.is_file():
            hits=_extract_entry_from_plain_pkz(pkz,[f'rider/riders/{profile}/rider.edf'],f'game-body-{profile}')
            if not hits and profile not in STOCK_RIDERS:
                for stock in STOCK_RIDERS:
                    hits=_extract_entry_from_plain_pkz(pkz,[f'rider/riders/{stock}/rider.edf'],f'game-body-{stock}')
                    if hits:break
            if hits:return hits[0]
    raise FrostViewerError(f'The real rider.edf for profile {profile!r} was not found.')


def _gear_source(app,part,model):
    model=str(model or '').strip().removesuffix('.pkz')
    specs={
        'helmet':(('helmets',),'helmet.edf','default'),
        'boots':(('boots',),'boots.edf','default'),
        'protection':(('protections','protection'),'armour.edf','full'),
    }
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
                root=_extract_viewer_pkz(packed,model);hits=_visible_edfs(root)
                if hits:return hits,root
    game=_game_dir(app)
    if game and (game/'rider.pkz').is_file():
        pkz=game/'rider.pkz';prefix=f'rider/{areas[0]}/{model}/'
        if not _plain_zip(pkz):raise FrostViewerError('The game rider.pkz is not readable by the public Frost PKZ path.')
        dst=_cache_root()/'stock_gear'/_stamp([pkz],f'{part}-{model}');dst.mkdir(parents=True,exist_ok=True)
        hits=[]
        with zipfile.ZipFile(pkz) as z:
            names=[n for n in z.namelist() if n.replace('\\','/').lower().startswith(prefix.lower()) and n.lower().endswith('.edf') and not n.lower().endswith('_s.edf')]
            names.sort(key=lambda n:(0 if Path(n).name.lower()==mesh else 1,len(n),n.lower()))
            for n in names:
                target=dst/Path(n).name
                if not target.is_file():
                    with z.open(n) as src,target.open('wb') as f:shutil.copyfileobj(src,f)
                hits.append(target)
        if hits:return hits,dst
    return [],None


def _find_paint_loose(app,kind,profile='',model='',paint=''):
    if not paint:return []
    out=[]
    for base in _rider_bases(app):
        candidates=[]
        if kind=='suit':candidates.append(base/'riders'/profile/'paints'/(paint+'.pnt'))
        elif kind=='gloves':
            candidates += [base/'riders'/profile/'gloves'/(paint+'.pnt'),base/'gloves'/(paint+'.pnt')]
            for stock in STOCK_RIDERS:candidates.append(base/'riders'/stock/'gloves'/(paint+'.pnt'))
        elif kind=='helmet':candidates.append(base/'helmets'/model/'paints'/(paint+'.pnt'))
        elif kind=='goggles':
            candidates += [base/'helmets'/model/'goggles'/(paint+'.pnt'),base/'riders'/profile/'goggles'/(paint+'.pnt')]
        elif kind=='boots':candidates.append(base/'boots'/model/'paints'/(paint+'.pnt'))
        elif kind=='protection':
            candidates += [base/'protections'/model/'paints'/(paint+'.pnt'),base/'protection'/model/'paints'/(paint+'.pnt')]
        out += [p for p in candidates if p.is_file()]
    return out


def decode_pnt(path):
    data=Path(path).read_bytes()
    if len(data)<108 or data[:4]!=b'PNT\x00':return {}
    count=struct.unpack_from('<I',data,104)[0];off=108;out={}
    for _ in range(min(int(count),256)):
        if off+128>len(data):break
        raw=data[off:off+100];name=raw.split(b'\0',1)[0].decode('utf-8',errors='ignore')
        w=struct.unpack_from('<I',data,off+100)[0];h=struct.unpack_from('<I',data,off+104)[0]
        size=struct.unpack_from('<I',data,off+124)[0]
        if not name or not w or not h or size<8:break
        start=off+136;end=start+size-8
        if end>len(data):break
        try:
            rgba=zlib.decompress(data[start:end],-zlib.MAX_WBITS)
            if len(rgba)!=w*h*4:raise ValueError()
            out[name.lower()]=(name,Image.frombytes('RGBA',(w,h),rgba))
        except Exception:pass
        off=off+128+size
    return out


def embedded_edf_textures(path):
    if Image is None:return {}
    try:b=Path(path).read_bytes()
    except Exception:return {}
    sizes={64,128,256,512,1024,2048,4096};out={};o=0;n=len(b)
    while o+144<=n:
        c=b[o]
        if not (chr(c).isalnum()) or (o>0 and chr(b[o-1]).isalnum()):o+=1;continue
        e=o
        while e<n and e-o<40 and (chr(b[e]).isalnum() or chr(b[e]) in '._-'):e+=1
        if e==o or e>=n or b[e]!=0:o+=1;continue
        name=b[o:e].decode('utf-8',errors='ignore');hit=False
        for woff in (100,104):
            if len(name)>=woff or o+woff+40>n:continue
            w,h=struct.unpack_from('<II',b,o+woff);size=struct.unpack_from('<I',b,o+woff+28)[0]
            pad=o+woff+32;start=o+woff+40
            if w not in sizes or h not in sizes or size<=8 or pad+8>n or b[pad:pad+8]!=b'\0'*8 or start+size-8>n:continue
            try:
                rgba=zlib.decompress(b[start:start+size-8],-zlib.MAX_WBITS)
                if len(rgba)<w*h*4:raise ValueError()
                out[name.lower()]=(name,Image.frombytes('RGBA',(w,h),rgba[:w*h*4]));o=start+size-8;hit=True;break
            except Exception:pass
        if not hit:o+=1
    return out


def _texture_set(edfs,pnts):
    tex={}
    for p in edfs:tex.update(embedded_edf_textures(p))
    for p in pnts:
        try:tex.update(decode_pnt(p))
        except Exception:pass
    return tex


def _bounds(nodes):
    lo=[float('inf')]*3;hi=[float('-inf')]*3
    for n in nodes:
        pos=n.get('positions') or []
        for i in range(0,len(pos)-2,3):
            for k in range(3):
                v=float(pos[i+k]);lo[k]=min(lo[k],v);hi[k]=max(hi[k],v)
    if not math.isfinite(lo[0]):return ([0,0,0],[1,1,1])
    return lo,hi


def _transform_nodes(nodes,fn):
    for n in nodes:
        p=n.get('positions') or []
        for i in range(0,len(p)-2,3):p[i],p[i+1],p[i+2]=fn(float(p[i]),float(p[i+1]),float(p[i+2]))
        q=n.get('normals') or []
        for i in range(0,len(q)-2,3):q[i],q[i+1],q[i+2]=fn(float(q[i]),float(q[i+1]),float(q[i+2]),True)
    return nodes


def _upright_body(nodes):
    lo,hi=_bounds(nodes);span=[hi[i]-lo[i] for i in range(3)]
    # Frost's special correction for Z-up rider bodies: y=-z, z=-y. Stock rider is already Y-up.
    if span[2] > span[1]*1.15:
        return _transform_nodes(nodes,lambda x,y,z,n=False:(x,-z,-y))
    return nodes


def _rot_xyz(point,rot):
    x,y,z=point;rx,ry,rz=rot
    if rx:
        s,c=math.sin(rx),math.cos(rx);y,z=y*c-z*s,y*s+z*c
    if ry:
        s,c=math.sin(ry),math.cos(ry);x,z=x*c+z*s,-x*s+z*c
    if rz:
        s,c=math.sin(rz),math.cos(rz);x,y=x*c-y*s,x*s+y*c
    return x,y,z


def _place_piece(nodes,anchor,target=1.0,rot=(0,0,0),yaw=0,pitch=0,align='center',native=False):
    def orient(x,y,z,n=False):return _rot_xyz((x,y,z),(rot[0]+pitch,rot[1]+yaw,rot[2]))
    _transform_nodes(nodes,orient);lo,hi=_bounds(nodes);size=[hi[i]-lo[i] for i in range(3)];center=[(lo[i]+hi[i])/2 for i in range(3)]
    scale=1.0 if native else target/max(max(size),1e-6)
    shift_y=(size[1]/2*scale if align=='bottom' else -size[1]/2*scale if align=='top' else 0.0)
    def place(x,y,z,n=False):
        if n:return x,y,z
        return (anchor[0]+(x-center[0])*scale,anchor[1]+(y-center[1])*scale+shift_y,anchor[2]+(z-center[2])*scale)
    return _transform_nodes(nodes,place)


def _compose_rider(app,state):
    profile=str(state.get('rider') or 'default_mx');body_edf=_body_source(app,profile)
    body=_upright_body(_decode_edf('rider',[body_edf]));all_nodes=list(body);edfs=[body_edf];pnts=[]
    pnts += _find_paint_loose(app,'suit',profile=profile,paint=str(state.get('suit_paint') or ''))
    pnts += _find_paint_loose(app,'gloves',profile=profile,paint=str(state.get('gloves_paint') or ''))
    blo,bhi=_bounds(body);cx=(blo[0]+bhi[0])/2;cz=(blo[2]+bhi[2])/2;h=max(1e-6,bhi[1]-blo[1]);depth=max(1e-6,bhi[2]-blo[2]);legx=.265*(bhi[0]-blo[0])
    helmet_anchor=(cx,bhi[1]-.11*h,cz+.08*depth);footy=blo[1]+.08*h;bootz=cz+.16*depth;prot_anchor=(cx,blo[1]+.74*h,cz)
    # Actual selected helmet.
    helmet_edfs,helmet_root=_gear_source(app,'helmet',state.get('helmet','default'))
    if helmet_edfs:
        helmet=_decode_edf('gear',helmet_edfs);_place_piece(helmet,helmet_anchor,.38*h,GEAR_ROT,math.pi,HELMET_PITCH,'bottom');all_nodes+=helmet;edfs+=helmet_edfs
        pnts += _find_paint_loose(app,'helmet',profile=profile,model=str(state.get('helmet') or 'default'),paint=str(state.get('helmet_paint') or ''))
        pnts += _find_paint_loose(app,'goggles',profile=profile,model=str(state.get('helmet') or 'default'),paint=str(state.get('goggles_paint') or ''))
    # Actual selected protection. Native scale as Frost uses.
    prot_edfs,prot_root=_gear_source(app,'protection',state.get('protection','full'))
    if prot_edfs:
        prot=_decode_edf('gear',prot_edfs);_place_piece(prot,prot_anchor,1.0,GEAR_ROT,PROT_YAW,0,'center',native=True);all_nodes+=prot;edfs+=prot_edfs
        pnts += _find_paint_loose(app,'protection',profile=profile,model=str(state.get('protection') or 'full'),paint=str(state.get('protection_paint') or ''))
    boots_edfs,boots_root=_gear_source(app,'boots',state.get('boots','default'))
    if boots_edfs:
        bootnodes=_decode_edf('gear',boots_edfs);edfs+=boots_edfs
        # Frost splits the common two-node boot set left/right. Preserve node names when they say the side.
        if len(bootnodes)==2:
            for i,node in enumerate(bootnodes):
                n=(node.get('name') or '').lower();side=1 if ('_l' in n or 'left' in n or n.startswith('lboot')) else -1 if ('_r' in n or 'right' in n or n.startswith('rboot')) else (-1 if i==0 else 1)
                piece=[node];_place_piece(piece,(cx+side*legx,footy,bootz),.44*h,BOOT_ROT,side*BOOT_SPLAY,BOOT_PITCH,'top');all_nodes+=piece
        else:
            _place_piece(bootnodes,(cx,footy,bootz),.44*h,BOOT_ROT,0,BOOT_PITCH,'top');all_nodes+=bootnodes
        pnts += _find_paint_loose(app,'boots',profile=profile,model=str(state.get('boots') or 'default'),paint=str(state.get('boots_paint') or ''))
    return all_nodes,_texture_set(edfs,pnts),edfs


def _submesh_texture(node,tri,textures):
    subs=node.get('submeshes') or [];chosen=None
    for sm in subs:
        a=int(sm.get('triStart',0));b=a+int(sm.get('triCount',0))
        if a<=tri<b:chosen=sm;break
    name=(chosen or {}).get('texture') or node.get('texture')
    if name and str(name).lower() in textures:return str(name).lower()
    # Frost material ids are node-local. With a paint loaded, its texture order is the closest
    # public equivalent to the declared slot table; never borrow an unrelated texture by name.
    mat=(chosen or {}).get('mat')
    mats=node.get('materials') or []
    keys=list(textures.keys())
    try:
        slot=mats[int(mat)] if mat is not None else None
        if slot is not None and 0<=int(slot)<len(keys):return keys[int(slot)]
    except Exception:pass
    # Rider body convention: kit texture is normally named rider; face stays skin-toned.
    lname=((chosen or {}).get('name') or node.get('name') or '').lower()
    if any(x in lname for x in ('face','head','neck')):return '__skin__'
    if any(x in lname for x in ('goggle','lens')):
        for k in keys:
            if 'goggle' in k or 'lens' in k:return k
    if 'rider' in textures:return 'rider'
    return keys[0] if keys else None


def _sample(texkey,textures,u,v):
    if texkey=='__skin__':return (199,154,116)
    item=textures.get(texkey) if texkey else None
    if not item:return (150,158,168)
    img=item[1]
    try:
        x=int((u%1.0)*(img.width-1));y=int((v%1.0)*(img.height-1));p=img.getpixel((x,y));return tuple(p[:3])
    except Exception:return (150,158,168)


def render_nodes(nodes,textures,width,height,yaw=-.55,pitch=-.12,zoom=1.0,focus='bike'):
    if Image is None or ImageDraw is None:raise FrostViewerError('Pillow is unavailable.')
    width=max(420,min(1050,int(width)));height=max(300,min(760,int(height)));img=Image.new('RGB',(width,height),(5,7,9));draw=ImageDraw.Draw(img)
    lo,hi=_bounds(nodes);center=[(lo[i]+hi[i])/2 for i in range(3)];span=max(hi[i]-lo[i] for i in range(3)) or 1
    h=hi[1]-lo[1]
    focus_y={'bike':center[1],'full':center[1],'helmet':hi[1]-.12*h,'goggles':hi[1]-.12*h,'gear':lo[1]+.63*h,'protection':lo[1]+.70*h,'gloves':lo[1]+.58*h,'boots':lo[1]+.12*h}.get(focus,center[1])
    mul={'helmet':2.0,'goggles':2.15,'gear':1.45,'protection':1.5,'gloves':1.55,'boots':1.9}.get(focus,1.0)
    scale=min(width,height)*.72/span*max(.35,min(3.0,zoom))*mul;cx=width/2;cy=height/2
    sy,cyw=math.sin(yaw),math.cos(yaw);sp,cp=math.sin(pitch),math.cos(pitch);tris=[]
    total=sum(len(n.get('indices') or [])//3 for n in nodes);step=max(1,total//MAX_RENDER_TRIS);global_tri=0
    for node in nodes:
        pos=node.get('positions') or [];uv=node.get('uvs') or [];idx=node.get('indices') or [];pts=[]
        for i in range(0,len(pos)-2,3):
            x=pos[i]-center[0];y=pos[i+1]-focus_y;z=pos[i+2]-center[2];x1=x*cyw-z*sy;z1=x*sy+z*cyw;y2=y*cp-z1*sp;z2=y*sp+z1*cp;d=4.5+z2/span*2;persp=4.5/max(1.2,d);pts.append((cx+x1*scale*persp,cy-y2*scale*persp,z2))
        for t in range(0,len(idx)-2,3):
            tri=t//3
            if global_tri%step:global_tri+=1;continue
            global_tri+=1
            try:a,b,c=int(idx[t]),int(idx[t+1]),int(idx[t+2]);pa,pb,pc=pts[a],pts[b],pts[c]
            except Exception:continue
            uva=(uv[a*2],uv[a*2+1]) if a*2+1<len(uv) else (0,0);uvb=(uv[b*2],uv[b*2+1]) if b*2+1<len(uv) else uva;uvc=(uv[c*2],uv[c*2+1]) if c*2+1<len(uv) else uva
            key=_submesh_texture(node,tri,textures);color=_sample(key,textures,(uva[0]+uvb[0]+uvc[0])/3,(uva[1]+uvb[1]+uvc[1])/3)
            depth=(pa[2]+pb[2]+pc[2])/3;tris.append((depth,pa,pb,pc,color))
    tris.sort(key=lambda x:x[0],reverse=True)
    for depth,a,b,c,color in tris:
        shade=max(.50,min(1.18,1.0-depth/(span*5)));col=tuple(max(0,min(255,int(v*shade))) for v in color);draw.polygon(((a[0],a[1]),(b[0],b[1]),(c[0],c[1])),fill=col)
    return img


class FrostNativeViewer:
    """Background viewer backed by Frost's real MX Bikes EDF/PNT format work. No stand-ins."""
    def __init__(self,app):
        self.app=app;self.yaw=-.55;self.pitch=-.12;self.zoom=1.0;self._exec=ThreadPoolExecutor(max_workers=1,thread_name_prefix='RDL-FrostEDF');self._token=0;self._lock=threading.Lock();self._drag=None;self._after=None;self._canvas=None;self._request=None

    def _submit(self,canvas,build,focus,status_cb,reset=False):
        if reset:self.yaw=-.55;self.pitch=-.12;self.zoom=1.0
        try:w=max(500,canvas.winfo_width());h=max(350,canvas.winfo_height())
        except Exception:return
        with self._lock:self._token+=1;token=self._token
        if status_cb:
            try:status_cb('loading','real MX Bikes EDF')
            except Exception:pass
        def worker():
            try:nodes,tex,detail=build();frame=render_nodes(nodes,tex,w,h,self.yaw,self.pitch,self.zoom,focus);result=('ready',frame,detail)
            except Exception as exc:result=('error',None,str(exc))
            def apply():
                with self._lock:
                    if token!=self._token:return
                try:
                    if not canvas.winfo_exists():return
                except Exception:return
                state,frame,detail=result
                if state=='ready':
                    try:photo=ImageTk.PhotoImage(frame);canvas.delete('frost_edf_frame');canvas.create_image(canvas.winfo_width()/2,canvas.winfo_height()/2,image=photo,anchor='center',tags='frost_edf_frame');canvas._frost_edf_photo=photo
                    except Exception as exc:state,detail='error',str(exc)
                if status_cb:
                    try:status_cb(state,detail)
                    except Exception:pass
            try:canvas.after(0,apply)
            except Exception:pass
        self._exec.submit(worker)

    def request_bike(self,canvas,state,status_cb=None,reset=False):
        state=dict(state)
        def build():
            edfs,geom,pnts=_bike_bundle(self.app,state.get('bikeid',''),state.get('paint',''));nodes=_decode_edf('bike',edfs,geom);return nodes,_texture_set(edfs,pnts),'ACTUAL INSTALLED MX BIKES EDF'
        self._canvas=canvas;self._request=lambda:self.request_bike(canvas,state,status_cb);self._submit(canvas,build,'bike',status_cb,reset)

    def request_rider(self,canvas,state,focus,status_cb=None,reset=False):
        state=dict(state)
        def build():nodes,tex,edfs=_compose_rider(self.app,state);return nodes,tex,'ACTUAL MX BIKES RIDER / GEAR EDF'
        self._canvas=canvas;self._request=lambda:self.request_rider(canvas,state,focus,status_cb);self._submit(canvas,build,focus,status_cb,reset)

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
        canvas.bind('<ButtonPress-1>',down,add='+');canvas.bind('<B1-Motion>',drag,add='+');canvas.bind('<ButtonRelease-1>',lambda e:setattr(self,'_drag',None),add='+');canvas.bind('<MouseWheel>',wheel,add='+');canvas.bind('<Configure>',lambda e:schedule(140),add='+')

    def cancel(self):
        with self._lock:self._token+=1
