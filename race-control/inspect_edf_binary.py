from __future__ import annotations
import io, math, re, struct, urllib.request, zipfile

URLS = [
    ('horse','https://mxb-mods.com/wp-content/uploads/2021/12/horse.zip'),
    ('banana','https://mxb-mods.com/wp-content/uploads/2021/12/banana.zip'),
    ('fish','https://mxb-mods.com/wp-content/uploads/2021/12/fish.zip'),
    ('kxpipe','https://mxb-mods.com/wp-content/uploads/2023/04/1695837851-kx450pcti6.zip'),
]

def entropy(data):
    if not data:return 0.0
    counts=[0]*256
    for b in data:counts[b]+=1
    n=len(data)
    return -sum((c/n)*math.log2(c/n) for c in counts if c)

def printable_runs(data,minlen=4):
    out=[]
    for m in re.finditer(rb'[\x20-\x7e]{%d,}'%minlen,data):
        s=m.group().decode('ascii','replace')
        if len(s)<120: out.append((m.start(),s))
    return out[:150]

def inspect(label,data):
    print('\n===',label,'size',len(data),'entropy',round(entropy(data),3),'===')
    print('HEAD HEX',data[:128].hex(' '))
    print('TAIL HEX',data[-64:].hex(' '))
    print('STRINGS')
    for off,s in printable_runs(data):print(hex(off),repr(s))
    # scan first 1KB as little endian uint32/float quartets to expose obvious magic/counts
    print('U32 FIRST64', [struct.unpack_from('<I',data,i)[0] for i in range(0,min(256,len(data)-3),4)][:64])
    vals=[]
    for i in range(0,min(512,len(data)-3),4):
        f=struct.unpack_from('<f',data,i)[0]
        if math.isfinite(f) and abs(f)<100000: vals.append((i,round(f,6)))
    print('FLOAT CANDIDATES FIRST512',vals[:80])

for label,url in URLS:
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        raw=urllib.request.urlopen(req,timeout=30).read()
        print('DOWNLOADED',label,len(raw),raw[:4])
        if raw[:2]==b'PK':
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                print('ZIP',z.namelist())
                for name in z.namelist():
                    if name.lower().endswith('.edf') and not name.lower().endswith('shadow.edf'):
                        inspect(label+':'+name,z.read(name))
        elif url.lower().endswith('.edf'):
            inspect(label,raw)
    except Exception as e:
        print('ERROR',label,repr(e))
