from pathlib import Path
import ast, tempfile, zipfile, re

base=Path('race-control/releases/MXB_Race_Day_Live_v0_3_5_UPDATE.zip')
work=Path(tempfile.mkdtemp(prefix='profile_v035_perf_'))
with zipfile.ZipFile(base) as z:z.extractall(work)

HOT_NAMES={
    'execute','executemany','fetchone','fetchall','read_text','read_bytes','write_text','write_bytes',
    'glob','rglob','iterdir','open','urlopen','request','get','post','sleep','Popen','run','check_output',
    'Image','open','resize','thumbnail','PhotoImage','after','after_idle','update','update_idletasks'
}

def call_name(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        parts=[]
        cur=node
        while isinstance(cur,ast.Attribute):
            parts.append(cur.attr); cur=cur.value
        if isinstance(cur,ast.Name): parts.append(cur.id)
        return '.'.join(reversed(parts))
    return ''

def audit_file(path):
    text=path.read_text(encoding='utf-8',errors='ignore')
    tree=ast.parse(text,filename=str(path))
    rows=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        calls=[]; loops=0; tk_widgets=0; sql=0; fileio=0; net=0; img=0; timers=0; process=0
        for sub in ast.walk(node):
            if isinstance(sub,(ast.For,ast.While,ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)): loops+=1
            if isinstance(sub,ast.Call):
                name=call_name(sub.func)
                low=name.lower()
                if name: calls.append(name)
                if any(x in low for x in ('tk.label','tk.frame','tk.button','tk.canvas','ttk.','tk.entry','tk.text','tk.scrollbar')): tk_widgets+=1
                if '.execute' in low or low.endswith('execute') or '.executemany' in low: sql+=1
                if any(x in low for x in ('read_text','read_bytes','write_text','write_bytes','iterdir','glob','rglob','path.open','open')): fileio+=1
                if any(x in low for x in ('urlopen','urllib','requests.','http.client')): net+=1
                if any(x in low for x in ('image.open','imagetk.photoimage','photoimage','resize','thumbnail')): img+=1
                if low.endswith('.after') or low.endswith('.after_idle'): timers+=1
                if any(x in low for x in ('subprocess.popen','subprocess.run','check_output')): process+=1
        score=sql*3+fileio*5+net*8+img*5+process*7+tk_widgets+max(0,loops-1)*2
        if score>=5 or node.name.startswith(('page_','_profile_','show','clear','refresh','load','sync','open_')):
            rows.append((score,node.lineno,node.name,loops,tk_widgets,sql,fileio,net,img,timers,process,calls[:12]))
    rows.sort(reverse=True)
    print(f'\n### {path.relative_to(work)}')
    for r in rows[:80]:
        score,line,name,loops,widgets,sql,fileio,net,img,timers,process,calls=r
        print(f'{score:3d} L{line:4d} {name:36s} loops={loops} widgets={widgets} sql={sql} fileio={fileio} net={net} img={img} timers={timers} proc={process} :: {", ".join(calls)}')
    print('\nTimers / refresh patterns:')
    for m in re.finditer(r'after\(([^\n]{0,120})',text):
        line=text.count('\n',0,m.start())+1
        print(f' L{line}: after({m.group(1).strip()}')
    print('\nThreads:')
    for i,line in enumerate(text.splitlines(),1):
        if 'Thread(' in line or 'threading.' in line or 'ThreadPoolExecutor' in line:
            print(f' L{i}: {line.strip()}')

for rel in ['src/app.py','src/bike_garage.py','src/native_renderer.py','src/game_bridge.py','src/track_media.py','src/subscriptions.py','src/updater.py']:
    p=work/rel
    if p.exists():
        audit_file(p)

print('\n### PACKAGE CONTENTS')
for p in sorted(work.rglob('*')):
    if p.is_file():print(p.relative_to(work),p.stat().st_size)
