from __future__ import annotations

import math
import os
import shutil
import struct
import tempfile
import threading
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .in_app_garage import Mesh, GarageModelError

try:
    from PIL import Image, ImageDraw, ImageTk
except Exception:
    Image = ImageDraw = ImageTk = None


OFFICIAL_TEMPLATES_URL='https://www.mx-bikes.com/downloads/templates.zip'
OFFICIAL_SOURCE_LABEL='PiBoSo MX Bikes official rider template'


def _cache_root():
    base=os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or str(Path.home())
    return Path(base)/'MXB Race Day Live'/'cache'/'official_mxb_templates'


def _safe_extract(z:zipfile.ZipFile,dst:Path):
    dst=dst.resolve()
    for info in z.infolist():
        rel=Path(info.filename)
        if rel.is_absolute() or '..' in rel.parts:continue
        target=(dst/rel).resolve()
        try:target.relative_to(dst)
        except Exception:continue
        if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
        # Official package is ~36 MB; reject absurd individual payloads.
        if int(info.file_size or 0)>128*1024*1024:continue
        target.parent.mkdir(parents=True,exist_ok=True)
        with z.open(info) as src,target.open('wb') as out:shutil.copyfileobj(src,out)


def _download_official_templates():
    root=_cache_root();root.mkdir(parents=True,exist_ok=True)
    ready=root/'READY.txt'
    if ready.is_file():return root
    work=Path(tempfile.mkdtemp(prefix='rdl_mxb_templates_'))
    try:
        archive=work/'templates.zip'
        req=urllib.request.Request(OFFICIAL_TEMPLATES_URL,headers={'User-Agent':'MXB-Race-Day-Live/0.5.8'})
        with urllib.request.urlopen(req,timeout=60) as resp,archive.open('wb') as out:
            while True:
                chunk=resp.read(1024*1024)
                if not chunk:break
                out.write(chunk)
        if not zipfile.is_zipfile(archive):raise GarageModelError('PiBoSo templates download was not a valid ZIP file.')
        stage=work/'extract';stage.mkdir()
        with zipfile.ZipFile(archive) as z:_safe_extract(z,stage)
        # Do not leave half-extracted official content behind.
        for child in list(root.iterdir()):
            if child.name=='READY.txt':continue
            if child.is_dir():shutil.rmtree(child,ignore_errors=True)
            else:child.unlink(missing_ok=True)
        for child in stage.iterdir():shutil.move(str(child),str(root/child.name))
        ready.write_text(OFFICIAL_SOURCE_LABEL+'\n'+OFFICIAL_TEMPLATES_URL+'\n',encoding='utf-8')
        return root
    finally:shutil.rmtree(work,ignore_errors=True)


def _score_rider_fbx(path:Path):
    s=path.as_posix().lower();name=path.stem.lower();score=0
    if 'rider' in s:score+=80
    if name in ('rider','rider_model','model_rider'):score+=100
    if 'skeleton' in s or 'anim' in s:score-=160
    if any(x in s for x in ('boot','helmet','glove','bike','wheel','stand','armor','protection')):score-=80
    try:score+=min(40,int(path.stat().st_size//(1024*1024)))
    except Exception:pass
    return score


def find_official_rider_fbx(root:Path):
    files=[]
    try:files=list(root.rglob('*.fbx'))+list(root.rglob('*.FBX'))
    except Exception:files=[]
    files=[p for p in files if p.is_file()]
    if not files:return None
    files.sort(key=lambda p:(_score_rider_fbx(p),p.stat().st_size if p.exists() else 0),reverse=True)
    best=files[0]
    return best if _score_rider_fbx(best)>0 else None


def _read_scalar(data,off,t):
    if t=='Y':return struct.unpack_from('<h',data,off)[0],off+2
    if t=='C':return bool(data[off]),off+1
    if t=='I':return struct.unpack_from('<i',data,off)[0],off+4
    if t=='F':return struct.unpack_from('<f',data,off)[0],off+4
    if t=='D':return struct.unpack_from('<d',data,off)[0],off+8
    if t=='L':return struct.unpack_from('<q',data,off)[0],off+8
    raise GarageModelError('Unsupported FBX scalar property '+t)


def _read_property(data,off):
    t=chr(data[off]);off+=1
    if t in 'YCIFDL':return _read_scalar(data,off,t)
    if t in ('S','R'):
        n=struct.unpack_from('<I',data,off)[0];off+=4
        raw=data[off:off+n];off+=n
        return (raw.decode('utf-8',errors='ignore') if t=='S' else raw),off
    if t in ('f','d','i','l','b','c'):
        n,encoding,clen=struct.unpack_from('<III',data,off);off+=12
        raw=data[off:off+clen];off+=clen
        if encoding==1:raw=zlib.decompress(raw)
        fmt={'f':'f','d':'d','i':'i','l':'q','b':'b','c':'b'}[t]
        size=struct.calcsize('<'+fmt)
        if len(raw)<n*size:raise GarageModelError('Truncated FBX array property.')
        vals=list(struct.unpack_from('<'+fmt*n,raw,0))
        return vals,off
    raise GarageModelError('Unsupported FBX property type '+repr(t))


def _parse_binary_nodes(data):
    if not data.startswith(b'Kaydara FBX Binary'):
        raise GarageModelError('Not a binary FBX file.')
    version=struct.unpack_from('<I',data,23)[0];wide=version>=7500;header=25
    def node_at(off,limit):
        if wide:
            if off+25>len(data):return None,limit
            end,num,plen=struct.unpack_from('<QQQ',data,off);off+=24
        else:
            if off+13>len(data):return None,limit
            end,num,plen=struct.unpack_from('<III',data,off);off+=12
        nlen=data[off];off+=1
        if end==0:return None,limit
        name=data[off:off+nlen].decode('utf-8',errors='ignore');off+=nlen
        props=[]
        for _ in range(int(num)):
            v,off=_read_property(data,off);props.append(v)
        children=[];sentinel=25 if wide else 13
        while off+sentinel<=min(int(end),len(data)):
            # NULL record marks end of children.
            if all(b==0 for b in data[off:off+sentinel]):off+=sentinel;break
            child,new_off=node_at(off,int(end))
            if child is None:break
            children.append(child);off=new_off
        return (name,props,children),int(end)
    nodes=[];off=header
    while off<len(data):
        node,new_off=node_at(off,len(data))
        if node is None:break
        nodes.append(node);off=new_off
    return nodes


def _mesh_from_binary_fbx(path:Path):
    nodes=_parse_binary_nodes(path.read_bytes());verts=[];faces=[]
    def walk(node):
        name,props,children=node
        if name=='Geometry':
            va=ia=None
            for c in children:
                if c[0]=='Vertices' and c[1] and isinstance(c[1][0],list):va=c[1][0]
                elif c[0]=='PolygonVertexIndex' and c[1] and isinstance(c[1][0],list):ia=c[1][0]
            if va and ia:
                base=len(verts)
                for i in range(0,len(va)-2,3):verts.append((float(va[i]),float(va[i+1]),float(va[i+2])))
                poly=[]
                for raw in ia:
                    end=int(raw)<0;idx=(-int(raw)-1) if end else int(raw)
                    if 0<=idx<len(va)//3:poly.append(base+idx)
                    if end:
                        if len(poly)>=3:
                            a=poly[0]
                            for j in range(1,len(poly)-1):faces.append((a,poly[j],poly[j+1]))
                        poly=[]
        for c in children:walk(c)
    for n in nodes:walk(n)
    return Mesh(verts,faces,path)


def _numbers(text):
    out=[]
    for token in text.replace('\n',' ').replace('\r',' ').split(','):
        token=token.strip()
        if not token:continue
        try:out.append(float(token))
        except Exception:pass
    return out


def _mesh_from_ascii_fbx(path:Path):
    import re
    text=path.read_text(encoding='utf-8',errors='ignore')
    verts=[];faces=[]
    # FBX ASCII arrays are typically `Vertices: *N { a: ... }`.
    for gm in re.finditer(r'Geometry\s*:\s*[^\{]+\{(.*?)\n\s*\}',text,flags=re.S):
        block=gm.group(1)
        vm=re.search(r'Vertices\s*:\s*\*\d+\s*\{\s*a\s*:\s*(.*?)\}',block,flags=re.S)
        im=re.search(r'PolygonVertexIndex\s*:\s*\*\d+\s*\{\s*a\s*:\s*(.*?)\}',block,flags=re.S)
        if not vm or not im:continue
        va=_numbers(vm.group(1));ia=[int(x) for x in _numbers(im.group(1))]
        base=len(verts)
        for i in range(0,len(va)-2,3):verts.append((va[i],va[i+1],va[i+2]))
        poly=[]
        for raw in ia:
            end=raw<0;idx=(-raw-1) if end else raw
            if 0<=idx<len(va)//3:poly.append(base+idx)
            if end:
                if len(poly)>=3:
                    a=poly[0]
                    for j in range(1,len(poly)-1):faces.append((a,poly[j],poly[j+1]))
                poly=[]
    return Mesh(verts,faces,path)


def load_fbx_mesh(path:Path):
    data=path.read_bytes()[:32]
    if data.startswith(b'Kaydara FBX Binary'):return _mesh_from_binary_fbx(path)
    return _mesh_from_ascii_fbx(path)


def render_rider(mesh:Mesh,yaw,pitch,zoom,width,height,region='full'):
    if Image is None or ImageDraw is None:raise GarageModelError('Pillow is unavailable.')
    width=max(360,min(1000,int(width)));height=max(300,min(760,int(height)))
    image=Image.new('RGB',(width,height),(5,7,9));draw=ImageDraw.Draw(image,'RGB')
    # Region focus stays on the same official rider model; it only changes camera framing.
    focus={'full':(0.0,1.0),'helmet':(0.72,2.0),'gear':(0.25,1.55),'boots':(-0.70,2.0),'goggles':(0.76,2.25),'gloves':(0.18,1.35),'protection':(0.25,1.65)}
    fy,mul=focus.get(region,focus['full']);cx,cy=width/2.0,height/2.0+fy*height*0.28
    scale=min(width,height)*0.39*max(.45,min(3.0,zoom))*mul
    cyaw,syaw=math.cos(yaw),math.sin(yaw);cp,sp=math.cos(pitch),math.sin(pitch);pts=[]
    for x,y,z in mesh.vertices:
        x1=x*cyaw-z*syaw;z1=x*syaw+z*cyaw;y2=y*cp-z1*sp;z2=y*sp+z1*cp
        d=4.3+z2;persp=4.3/max(1.15,d);pts.append((cx+x1*scale*persp,cy-y2*scale*persp,z2,y))
    tris=[]
    for a,b,c in mesh.faces:
        try:
            pa,pb,pc=pts[a],pts[b],pts[c]
            cross=(pb[0]-pa[0])*(pc[1]-pa[1])-(pb[1]-pa[1])*(pc[0]-pa[0])
            if cross>=0:continue
            tris.append(((pa[2]+pb[2]+pc[2])/3.0,pa,pb,pc))
        except Exception:pass
    tris.sort(reverse=True,key=lambda t:t[0])
    for depth,pa,pb,pc in tris:
        shade=max(62,min(205,int(138-depth*28)))
        draw.polygon(((pa[0],pa[1]),(pb[0],pb[1]),(pc[0],pc[1])),fill=(shade,min(220,shade+6),min(225,shade+12)))
    return image


class OfficialMXRiderRenderer:
    """In-app renderer for PiBoSo's official MX Bikes rider template model."""
    def __init__(self,tk_root):
        self.root=tk_root;self.yaw=-0.35;self.pitch=-0.08;self.zoom=1.0
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='RDLOfficialRider')
        self._mesh=None;self._source=None;self._token=0;self._lock=threading.Lock();self._drag=None;self._after=None

    @property
    def supported(self):return Image is not None and ImageTk is not None

    def _load(self):
        if self._mesh is not None:return self._mesh,self._source
        root=_download_official_templates();source=find_official_rider_fbx(root)
        if not source:raise GarageModelError('The official PiBoSo templates package did not contain a readable rider FBX.')
        mesh=load_fbx_mesh(source);self._mesh=mesh;self._source=source;return mesh,source

    def request(self,canvas,region='full',status_cb=None,reset=False):
        if reset:self.yaw=-0.35;self.pitch=-0.08;self.zoom=1.0
        try:w=max(500,canvas.winfo_width());h=max(350,canvas.winfo_height())
        except Exception:return
        with self._lock:self._token+=1;token=self._token
        if status_cb:
            try:status_cb('loading','Official MX Bikes rider model')
            except Exception:pass
        def worker():
            try:
                mesh,source=self._load();frame=render_rider(mesh,self.yaw,self.pitch,self.zoom,w,h,region);result=('ready',frame,source.name)
            except Exception as exc:result=('error',None,str(exc))
            def apply():
                with self._lock:
                    if token!=self._token:return
                try:
                    if not canvas.winfo_exists():return
                except Exception:return
                state,frame,detail=result
                if state=='ready' and frame is not None:
                    try:
                        photo=ImageTk.PhotoImage(frame);canvas.delete('official_rider_frame')
                        canvas.create_image(canvas.winfo_width()/2,canvas.winfo_height()/2,image=photo,anchor='center',tags='official_rider_frame');canvas._official_rider_photo=photo
                    except Exception as exc:state,detail='error',str(exc)
                if status_cb:
                    try:status_cb(state,detail)
                    except Exception:pass
            try:canvas.after(0,apply)
            except Exception:pass
        self._executor.submit(worker)

    def bind(self,canvas,region_getter,status_cb=None):
        def schedule(delay=70):
            try:
                if self._after is not None:canvas.after_cancel(self._after)
            except Exception:pass
            try:self._after=canvas.after(delay,lambda:self.request(canvas,region_getter(),status_cb))
            except Exception:self.request(canvas,region_getter(),status_cb)
        def down(e):self._drag=(e.x,e.y,self.yaw,self.pitch)
        def move(e):
            if not self._drag:return
            x,y,yaw,pitch=self._drag;self.yaw=yaw+(e.x-x)*.012;self.pitch=max(-1.25,min(1.25,pitch+(e.y-y)*.009));schedule(45)
        def up(e):self._drag=None
        def wheel(e):self.zoom=max(.45,min(3.0,self.zoom*(1.12 if e.delta>0 else .88)));schedule(45)
        canvas.bind('<Button-1>',down,add='+');canvas.bind('<B1-Motion>',move,add='+');canvas.bind('<ButtonRelease-1>',up,add='+');canvas.bind('<MouseWheel>',wheel,add='+')

    def stop(self):
        with self._lock:self._token+=1
