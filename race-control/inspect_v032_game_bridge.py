from pathlib import Path
import re,struct,zlib
base=Path('race-control/releases/MXB_Race_Day_Live_v0_2_0_UPDATE.zip')
data=base.read_bytes()
print('ARCHIVE_BYTES',len(data),'LOCAL_HEADERS',data.count(b'PK\x03\x04'))
entries={}
pos=0
while True:
 i=data.find(b'PK\x03\x04',pos)
 if i<0: break
 if i+30>len(data): break
 sig,ver,flags,method,mt,md,crc,csize,usize,nlen,xlen=struct.unpack_from('<IHHHHHIIIHH',data,i)
 name=data[i+30:i+30+nlen].decode('utf-8','replace')
 start=i+30+nlen+xlen
 print('LOCAL',i,name,'flags',flags,'method',method,'csize',csize,'usize',usize,'data',start)
 if not (flags & 8) and csize and start+csize<=len(data):
  blob=data[start:start+csize]
  try:
   raw=blob if method==0 else zlib.decompress(blob,-15) if method==8 else None
   if raw is not None:
    entries[name]=raw
    print('RECOVERED',name,len(raw))
  except Exception as exc: print('DECOMPRESS_FAIL',name,exc)
 pos=i+4
for rel in ['src/mx_agent.py','src/database.py']:
 if rel not in entries: print('NOT_RECOVERED',rel); continue
 s=entries[rel].decode('utf-8','replace')
 print('\n===== '+rel+' =====')
 pats=['class MXEnvironment','class MXRaceAgent','def _discover','def discover','def sync','def sync_async','def prepare_race','def start_race_server','def stop_race_server','def diagnostics','def _scan','steam','install','profile','bikes','tracks','mods','game_port','live_port','server_process','CREATE TABLE races','CREATE TABLE game_sync_state','CREATE TABLE game_content']
 for pat in pats:
  print('\n--- '+pat+' ---')
  for m in list(re.finditer(pat,s,re.I))[:8]:
   a=max(0,m.start()-700);b=min(len(s),m.end()+4200)
   print(s[a:b].replace('\r',''))
