from __future__ import annotations

import math
import os
from pathlib import Path


class GarageModelError(RuntimeError):
    pass


class ObjModel:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.vertices = []
        self.faces = []
        self._load()
        self._normalize()

    def _load(self):
        verts=[]; faces=[]
        with self.path.open('r',encoding='utf-8',errors='ignore') as f:
            for raw in f:
                line=raw.strip()
                if not line or line.startswith('#'):continue
                parts=line.split()
                if not parts:continue
                if parts[0]=='v' and len(parts)>=4:
                    try:verts.append((float(parts[1]),float(parts[2]),float(parts[3])))
                    except Exception:pass
                elif parts[0]=='f' and len(parts)>=4:
                    idx=[]
                    for token in parts[1:]:
                        try:
                            i=int(token.split('/')[0]); i=(len(verts)+i if i<0 else i-1)
                            if 0<=i<len(verts):idx.append(i)
                        except Exception:pass
                    if len(idx)>=3:
                        a=idx[0]
                        for j in range(1,len(idx)-1):faces.append((a,idx[j],idx[j+1]))
        if len(verts)<3 or not faces:raise GarageModelError('Readable OBJ geometry was not found.')
        # Keep UI responsive on huge source meshes.
        if len(faces)>45000:
            step=max(1,len(faces)//45000); faces=faces[::step]
        self.vertices=verts; self.faces=faces

    def _normalize(self):
        xs=[v[0] for v in self.vertices]; ys=[v[1] for v in self.vertices]; zs=[v[2] for v in self.vertices]
        cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
        span=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs),1e-6)
        scale=2.2/span
        self.vertices=[((x-cx)*scale,(y-cy)*scale,(z-cz)*scale) for x,y,z in self.vertices]


class InAppGarageRenderer:
    """Small software 3D renderer that lives entirely inside the Tk Garage page.

    It intentionally never launches Steam or mxbikes.exe. It renders readable source
    geometry when a mod includes it next to the compiled EDF. Compiled EDF is treated
    as opaque and never passed to an external process.
    """
    SOURCE_EXTS=('.obj',)

    def __init__(self, garage):
        self.garage=garage
        self.model=None; self.model_path=None
        self.yaw=-0.65; self.pitch=-0.18; self.zoom=1.0
        self._drag=None

    def source_for_bike(self,bike_id):
        # Prefer source geometry living with the selected bike. Never decode/launch EDF.
        roots=[]
        try:
            for rec in self.garage.bike_records():
                if str(rec.get('id',''))==str(bike_id):
                    raw=rec.get('path') or rec.get('folder') or ''
                    if raw:roots.append(Path(raw))
        except Exception:pass
        try:
            mods=self.garage.mods_root()
            if mods: roots.extend([Path(mods)/'bikes'/str(bike_id),Path(mods)/'Bikes'/str(bike_id)])
        except Exception:pass
        seen=set()
        for root in roots:
            try:
                root=root if root.is_dir() else root.parent
                key=str(root.resolve()).lower()
                if key in seen or not root.is_dir():continue
                seen.add(key)
                preferred=[root/'model.obj',root/(str(bike_id)+'.obj')]
                for p in preferred:
                    if p.is_file():return p
                # Source packs sometimes leave an OBJ in a source/template subfolder.
                for sub in ('source','Source','template','Template','3d','3D'):
                    d=root/sub
                    if d.is_dir():
                        found=next(iter(sorted(d.glob('*.obj'))),None)
                        if found:return found
                found=next(iter(sorted(root.glob('*.obj'))),None)
                if found:return found
            except Exception:pass
        return None

    def load_bike(self,bike_id):
        path=self.source_for_bike(bike_id)
        if not path:
            self.model=None; self.model_path=None
            return False
        if self.model_path==path and self.model is not None:return True
        self.model=ObjModel(path); self.model_path=path
        self.yaw=-0.65; self.pitch=-0.18; self.zoom=1.0
        return True

    def bind(self,canvas,redraw):
        def down(e):self._drag=(e.x,e.y,self.yaw,self.pitch)
        def move(e):
            if not self._drag:return
            x,y,yaw,pitch=self._drag
            self.yaw=yaw+(e.x-x)*0.012
            self.pitch=max(-1.25,min(1.25,pitch+(e.y-y)*0.009))
            redraw()
        def up(e):self._drag=None
        def wheel(e):
            self.zoom=max(0.45,min(2.8,self.zoom*(1.0+(0.12 if e.delta>0 else -0.12))))
            redraw()
        canvas.bind('<ButtonPress-1>',down); canvas.bind('<B1-Motion>',move); canvas.bind('<ButtonRelease-1>',up); canvas.bind('<MouseWheel>',wheel)

    def draw(self,canvas,width,height):
        canvas.delete('garage3d')
        if self.model is None:return False
        w=max(320,int(width)); h=max(260,int(height)); cx=w/2; cy=h/2
        cyaw,syaw=math.cos(self.yaw),math.sin(self.yaw); cp,sp=math.cos(self.pitch),math.sin(self.pitch)
        pts=[]
        scale=min(w,h)*0.38*self.zoom
        for x,y,z in self.model.vertices:
            x1=x*cyaw-z*syaw; z1=x*syaw+z*cyaw
            y2=y*cp-z1*sp; z2=y*sp+z1*cp
            d=4.2+z2; persp=4.2/max(1.0,d)
            pts.append((cx+x1*scale*persp,cy-y2*scale*persp,z2))
        tris=[]
        for a,b,c in self.model.faces:
            try:
                pa,pb,pc=pts[a],pts[b],pts[c]
                # screen-space backface cull
                cross=(pb[0]-pa[0])*(pc[1]-pa[1])-(pb[1]-pa[1])*(pc[0]-pa[0])
                if cross>=0:continue
                tris.append(((pa[2]+pb[2]+pc[2])/3,(pa,pb,pc)))
            except Exception:pass
        tris.sort(reverse=True,key=lambda x:x[0])
        # Tk software rendering: neutral shading only; game paints remain handled by selection/profile sync.
        for depth,(pa,pb,pc) in tris:
            shade=max(55,min(205,int(132-depth*28)))
            col=f'#{shade:02x}{shade:02x}{shade:02x}'
            canvas.create_polygon(pa[0],pa[1],pb[0],pb[1],pc[0],pc[1],fill=col,outline='',tags='garage3d')
        return True
