from __future__ import annotations
import io, re, urllib.request, zipfile, hashlib

ITEMS=[
 ('viewer','https://mxb-mods.com/uploads/3DViewer/dmkrtz3DViewer_v1.0.9151.32085.zip'),
 ('converter','https://mxb-mods.com/uploads/3DViewer/converter/dmkrtz3DModelConverter_v0.1.zip'),
 ('horse','https://mxb-mods.com/wp-content/uploads/2021/12/horse.zip'),
]

def get(url):
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36',
        'Referer':'https://mxb-mods.com/insanes-3d-viewer/',
        'Accept':'*/*',
    })
    return urllib.request.urlopen(req,timeout=60).read()

def strings(data,minlen=5,limit=300):
    out=[]
    for m in re.finditer(rb'[\x20-\x7e]{%d,}'%minlen,data):
        s=m.group().decode('ascii','ignore')
        if len(s)<=240:out.append((m.start(),s))
        if len(out)>=limit:break
    return out

for label,url in ITEMS:
    print('\n###',label,url)
    try:raw=get(url)
    except Exception as e:
        print('DOWNLOAD ERROR',repr(e));continue
    print('DOWNLOADED',len(raw),raw[:8],hashlib.sha256(raw).hexdigest())
    if raw[:2]!=b'PK':continue
    try:z=zipfile.ZipFile(io.BytesIO(raw))
    except Exception as e:print('ZIP ERROR',e);continue
    names=z.namelist(); print('FILES',len(names))
    for name in names[:500]:print(' ',name)
    interesting=[n for n in names if n.lower().endswith(('.model','.edf','.dll','.exe','.json','.xml','.config','.txt'))]
    print('INTERESTING',len(interesting))
    for name in interesting[:150]:
        data=z.read(name)
        print('\n--',name,'size',len(data),'head',data[:32].hex(' '))
        for off,s in strings(data,limit=120):
            low=s.lower()
            if any(k in low for k in ('model','fbx','obj','gltf','assimp','unity','babylon','sharpdx','opengl','directx','mesh','vertex','texture','json','convert','edf','helix','three')):
                print(hex(off),repr(s))
