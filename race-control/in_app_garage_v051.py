from __future__ import annotations

import math
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageTk
except Exception:  # Pillow is already used by Race Day Live, but fail closed if unavailable.
    Image = ImageDraw = ImageTk = None


class GarageModelError(RuntimeError):
    pass


class Mesh:
    MAX_FACES = 5500

    def __init__(self, vertices, faces, source: Path):
        if len(vertices) < 3 or not faces:
            raise GarageModelError('No readable 3D geometry was found in the source model.')
        self.source = Path(source)
        self.vertices = list(vertices)
        self.faces = self._limit_faces(list(faces))
        self._normalize()

    @classmethod
    def _limit_faces(cls, faces):
        if len(faces) <= cls.MAX_FACES:
            return faces
        step = max(1, len(faces) // cls.MAX_FACES)
        return faces[::step][:cls.MAX_FACES]

    def _normalize(self):
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0
        span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 1e-6)
        scale = 2.15 / span
        self.vertices = [((x-cx)*scale, (y-cy)*scale, (z-cz)*scale) for x,y,z in self.vertices]


def _load_obj(path: Path):
    verts, faces = [], []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if not parts:
                continue
            if parts[0] == 'v' and len(parts) >= 4:
                try:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except Exception:
                    pass
            elif parts[0] == 'f' and len(parts) >= 4:
                idx = []
                for token in parts[1:]:
                    try:
                        i = int(token.split('/')[0])
                        i = len(verts) + i if i < 0 else i - 1
                        if 0 <= i < len(verts):
                            idx.append(i)
                    except Exception:
                        pass
                if len(idx) >= 3:
                    a = idx[0]
                    for j in range(1, len(idx)-1):
                        faces.append((a, idx[j], idx[j+1]))
    return Mesh(verts, faces, path)


def _load_ascii_ply(path: Path):
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        header = []
        while True:
            line = f.readline()
            if not line:
                raise GarageModelError('Invalid PLY file.')
            header.append(line.strip())
            if line.strip() == 'end_header':
                break
        if not header or header[0] != 'ply' or 'format ascii 1.0' not in header:
            raise GarageModelError('Only ASCII PLY source geometry is supported in Garage.')
        vcount = fcount = 0
        for line in header:
            p = line.split()
            if len(p) == 3 and p[0] == 'element' and p[1] == 'vertex':
                vcount = int(p[2])
            elif len(p) == 3 and p[0] == 'element' and p[1] == 'face':
                fcount = int(p[2])
        verts = []
        for _ in range(vcount):
            p = f.readline().split()
            if len(p) >= 3:
                verts.append((float(p[0]), float(p[1]), float(p[2])))
        faces = []
        for _ in range(fcount):
            p = f.readline().split()
            if not p:
                continue
            n = int(p[0]); idx = [int(x) for x in p[1:1+n]]
            if len(idx) >= 3:
                a = idx[0]
                for j in range(1, len(idx)-1):
                    faces.append((a, idx[j], idx[j+1]))
        return Mesh(verts, faces, path)


def _load_stl(path: Path):
    data = path.read_bytes()
    # Binary STL has 80-byte header + uint32 triangle count + 50 bytes/triangle.
    if len(data) >= 84:
        count = struct.unpack_from('<I', data, 80)[0]
        if 84 + count * 50 == len(data):
            verts, faces, lookup = [], [], {}
            offset = 84
            for _ in range(count):
                offset += 12  # normal
                tri = []
                for _v in range(3):
                    xyz = struct.unpack_from('<fff', data, offset); offset += 12
                    key = tuple(round(float(x), 6) for x in xyz)
                    idx = lookup.get(key)
                    if idx is None:
                        idx = len(verts); lookup[key] = idx; verts.append(tuple(float(x) for x in xyz))
                    tri.append(idx)
                faces.append(tuple(tri)); offset += 2
            return Mesh(verts, faces, path)
    # ASCII fallback.
    verts, faces, tri = [], [], []
    for raw in data.decode('utf-8', errors='ignore').splitlines():
        p = raw.strip().split()
        if len(p) == 4 and p[0].lower() == 'vertex':
            try:
                verts.append((float(p[1]), float(p[2]), float(p[3])))
                tri.append(len(verts)-1)
                if len(tri) == 3:
                    faces.append(tuple(tri)); tri = []
            except Exception:
                pass
    return Mesh(verts, faces, path)


def load_mesh(path: Path):
    ext = path.suffix.lower()
    if ext == '.obj':
        return _load_obj(path)
    if ext == '.stl':
        return _load_stl(path)
    if ext == '.ply':
        return _load_ascii_ply(path)
    raise GarageModelError(f'Unsupported source format: {ext}')


def render_mesh(mesh: Mesh, yaw: float, pitch: float, zoom: float, width: int, height: int):
    if Image is None or ImageDraw is None:
        raise GarageModelError('Pillow is unavailable, so the in-app 3D renderer cannot draw a frame.')
    width = max(360, min(1100, int(width)))
    height = max(260, min(700, int(height)))
    image = Image.new('RGB', (width, height), (5, 7, 9))
    draw = ImageDraw.Draw(image, 'RGB')
    cx, cy = width / 2.0, height / 2.0
    scale = min(width, height) * 0.39 * max(0.45, min(2.8, zoom))
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    pts = []
    for x, y, z in mesh.vertices:
        x1 = x*cyaw - z*syaw
        z1 = x*syaw + z*cyaw
        y2 = y*cp - z1*sp
        z2 = y*sp + z1*cp
        d = 4.3 + z2
        persp = 4.3 / max(1.15, d)
        pts.append((cx + x1*scale*persp, cy - y2*scale*persp, z2))
    tris = []
    for a,b,c in mesh.faces:
        try:
            pa,pb,pc = pts[a],pts[b],pts[c]
            cross = (pb[0]-pa[0])*(pc[1]-pa[1]) - (pb[1]-pa[1])*(pc[0]-pa[0])
            if cross >= 0:
                continue
            depth = (pa[2]+pb[2]+pc[2])/3.0
            tris.append((depth, pa,pb,pc))
        except Exception:
            pass
    tris.sort(reverse=True, key=lambda t:t[0])
    for depth,pa,pb,pc in tris:
        shade = max(58, min(205, int(135-depth*30)))
        # Slight blue-neutral metal shade without expensive per-pixel lighting.
        color = (shade, min(220, shade+5), min(225, shade+10))
        draw.polygon(((pa[0],pa[1]),(pb[0],pb[1]),(pc[0],pc[1])), fill=color)
    return image


class InAppGarageRenderer:
    """Nonblocking Race Day Live Garage renderer.

    All model discovery, parsing and rasterization happen off Tk's UI thread. Tk only
    receives one completed PhotoImage frame. This module never launches MX Bikes,
    Steam, PaintEd or another viewer process.
    """

    SOURCE_EXTS = ('.obj', '.stl', '.ply')

    def __init__(self, garage):
        self.garage = garage
        self.yaw = -0.65
        self.pitch = -0.18
        self.zoom = 1.0
        self._mesh_cache = {}
        self._source_cache = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='RDLGarage3D')
        self._token = 0
        self._lock = threading.Lock()
        self._drag = None
        self._after_id = None
        self._canvas = None
        self._bike_getter = None
        self._status_cb = None

    @property
    def supported(self):
        return Image is not None and ImageTk is not None

    def invalidate_cache(self):
        self._source_cache.clear()
        self._mesh_cache.clear()

    def source_for_bike(self, bike_id):
        bike_id = str(bike_id or '').strip()
        if not bike_id:
            return None
        if bike_id in self._source_cache:
            cached = self._source_cache[bike_id]
            return Path(cached) if cached else None
        roots = []
        try:
            for rec in self.garage.bike_records():
                if str(rec.get('id','')).lower() == bike_id.lower():
                    raw = rec.get('path') or rec.get('folder') or ''
                    if raw:
                        roots.append(Path(raw))
                    break
        except Exception:
            pass
        try:
            mods = self.garage.mods_root()
            if mods:
                roots.extend([Path(mods)/'bikes'/bike_id, Path(mods)/'Bikes'/bike_id])
        except Exception:
            pass
        seen = set()
        for root in roots:
            try:
                root = root if root.is_dir() else root.parent
                key = str(root.resolve()).lower()
                if key in seen or not root.is_dir():
                    continue
                seen.add(key)
                for stem in ('model', bike_id):
                    for ext in self.SOURCE_EXTS:
                        p = root / (stem + ext)
                        if p.is_file():
                            self._source_cache[bike_id] = str(p); return p
                for sub in ('source','Source','template','Template','3d','3D'):
                    d = root/sub
                    if not d.is_dir():
                        continue
                    for ext in self.SOURCE_EXTS:
                        found = next(iter(sorted(d.glob('*'+ext))), None)
                        if found:
                            self._source_cache[bike_id] = str(found); return found
                for ext in self.SOURCE_EXTS:
                    found = next(iter(sorted(root.glob('*'+ext))), None)
                    if found:
                        self._source_cache[bike_id] = str(found); return found
            except Exception:
                pass
        self._source_cache[bike_id] = ''
        return None

    def _mesh_for(self, source: Path):
        try:
            st = source.stat(); key = (str(source.resolve()).lower(), int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            key = (str(source).lower(), 0, 0)
        mesh = self._mesh_cache.get(key)
        if mesh is None:
            mesh = load_mesh(source)
            self._mesh_cache = {key: mesh}  # one bike at a time keeps memory bounded
        return mesh

    def request(self, canvas, bike_id, callback=None, reset=False):
        if reset:
            self.yaw = -0.65; self.pitch = -0.18; self.zoom = 1.0
        self._canvas = canvas
        if callback is not None:
            self._status_cb = callback
        bike_id = str(bike_id or '').strip()
        try:
            width = max(500, canvas.winfo_width()); height = max(300, canvas.winfo_height())
        except Exception:
            return
        with self._lock:
            self._token += 1
            token = self._token
        if self._status_cb:
            try:self._status_cb('loading', bike_id)
            except Exception:pass

        def worker():
            try:
                source = self.source_for_bike(bike_id)
                if not source:
                    result = ('opaque', None, bike_id)
                else:
                    mesh = self._mesh_for(source)
                    frame = render_mesh(mesh, self.yaw, self.pitch, self.zoom, width, height)
                    result = ('ready', frame, source.name)
            except Exception as exc:
                result = ('error', None, str(exc))

            def apply():
                with self._lock:
                    if token != self._token:
                        return
                try:
                    if not canvas.winfo_exists():
                        return
                except Exception:
                    return
                status, frame, detail = result
                if status == 'ready' and frame is not None:
                    try:
                        photo = ImageTk.PhotoImage(frame)
                        canvas.delete('garage3d_frame')
                        canvas.create_image(canvas.winfo_width()/2, canvas.winfo_height()/2, image=photo, anchor='center', tags='garage3d_frame')
                        canvas._garage3d_photo = photo
                    except Exception as exc:
                        status, detail = 'error', str(exc)
                if self._status_cb:
                    try:self._status_cb(status, detail)
                    except Exception:pass
            try:canvas.after(0, apply)
            except Exception:pass
        self._executor.submit(worker)

    def schedule(self, canvas=None, bike_id=None, callback=None, reset=False, delay=90):
        canvas = canvas or self._canvas
        if canvas is None:
            return
        if callback is not None:
            self._status_cb = callback
        if bike_id is None and self._bike_getter is not None:
            try:bike_id = self._bike_getter()
            except Exception:bike_id = ''
        try:
            if self._after_id is not None:
                canvas.after_cancel(self._after_id)
        except Exception:
            pass
        try:self._after_id = canvas.after(max(0,int(delay)), lambda:self.request(canvas,bike_id,self._status_cb,reset))
        except Exception:self.request(canvas,bike_id,self._status_cb,reset)

    def bind(self, canvas, bike_getter, callback=None):
        self._canvas = canvas; self._bike_getter = bike_getter; self._status_cb = callback
        def down(e):self._drag=(e.x,e.y,self.yaw,self.pitch)
        def move(e):
            if not self._drag:return
            x,y,yaw,pitch=self._drag
            self.yaw=yaw+(e.x-x)*0.012
            self.pitch=max(-1.25,min(1.25,pitch+(e.y-y)*0.009))
            self.schedule(delay=55)
        def up(e):self._drag=None
        def wheel(e):
            factor=1.12 if e.delta>0 else 0.88
            self.zoom=max(0.45,min(2.8,self.zoom*factor))
            self.schedule(delay=45)
        def resize(_e):self.schedule(delay=160)
        canvas.bind('<ButtonPress-1>',down,add='+')
        canvas.bind('<B1-Motion>',move,add='+')
        canvas.bind('<ButtonRelease-1>',up,add='+')
        canvas.bind('<MouseWheel>',wheel,add='+')
        canvas.bind('<Configure>',resize,add='+')

    # Compatibility with older lifecycle calls; these never launch or own another process.
    def stop(self):
        with self._lock:self._token += 1
        try:
            if self._canvas is not None and self._after_id is not None:self._canvas.after_cancel(self._after_id)
        except Exception:pass
        self._after_id=None

    def resize(self,*_args,**_kwargs):
        self.schedule(delay=160)

    def focus(self,*_args,**_kwargs):
        return None
