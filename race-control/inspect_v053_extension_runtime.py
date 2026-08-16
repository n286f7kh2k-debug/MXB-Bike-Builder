from pathlib import Path
import ast, zipfile

BASE=Path('race-control/releases/MXB_Race_Day_Live_v0_5_3_UPDATE.zip')
if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit('missing v0.5.3')

def funcs(src, names):
    tree=ast.parse(src)
    lines=src.splitlines()
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
            a=max(0,node.lineno-2); b=min(len(lines),getattr(node,'end_lineno',node.lineno)+2)
            print(f'\n### FUNCTION {node.name} lines {a+1}-{b}')
            print('\n'.join(lines[a:b]))
        if isinstance(node,ast.ClassDef) and node.name in names:
            a=max(0,node.lineno-2); b=min(len(lines),getattr(node,'end_lineno',node.lineno)+2)
            print(f'\n### CLASS {node.name} lines {a+1}-{b}')
            print('\n'.join(lines[a:b]))

with zipfile.ZipFile(BASE) as z:
    print('FILES',z.namelist())
    targets={
        'src/updater.py':['check_for_update','download_update','launch_update','schedule_restart','_validate_zip'],
        'src/app.py':['do_update','__init__','show','page_garage','_run_mx_sync','_on_close'],
        'src/bike_garage.py':['MXBikeGarage','read_current','apply_selection','scan_content','selection','profile_ini','mods_root'],
        'src/game_bridge.py':['MXGameBridge','launch_race','list_synced_bikes','save_race_bike'],
        'src/mx_agent.py':['MXRaceAgent','sync','prepare_race','start_race_server'],
        'app.py':[],
    }
    for name,names in targets.items():
        if name not in z.namelist():
            print('\nMISSING',name); continue
        src=z.read(name).decode('utf-8','replace')
        print('\n===== FILE',name,'=====')
        if names:
            funcs(src,names)
        else:
            print(src[:12000])
