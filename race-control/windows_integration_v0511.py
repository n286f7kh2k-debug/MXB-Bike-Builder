from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

APP_ID='MXBRaceDayLive.Desktop'
SHORTCUT_NAME='MXB Race Day Live.lnk'
LAUNCHER_NAME='MXB Race Day Live.exe'
RUNTIME_FILE='rdl_runtime.txt'
_cache_lock=threading.Lock();_shortcut_cache=None;_info_cache=None


def desktop_dirs():
    roots=[]
    for key in ('USERPROFILE','ONEDRIVE','OneDriveConsumer','OneDriveCommercial','PUBLIC'):
        raw=os.environ.get(key)
        if raw:roots.append(Path(raw)/'Desktop')
    try:roots.append(Path.home()/'Desktop')
    except Exception:pass
    out=[];seen=set()
    for p in roots:
        k=str(p).lower()
        if k not in seen:seen.add(k);out.append(p)
    return out


def find_shortcut(refresh=False):
    global _shortcut_cache
    with _cache_lock:
        if not refresh and _shortcut_cache:
            p=Path(_shortcut_cache)
            if p.is_file():return p
    found=None
    for root in desktop_dirs():
        p=root/SHORTCUT_NAME
        if p.is_file():found=p;break
        try:
            matches=sorted(root.glob('*MXB*Race*Day*Live*.lnk')) if root.is_dir() else []
            if matches:found=matches[0];break
        except Exception:pass
    with _cache_lock:_shortcut_cache=str(found) if found else ''
    return found


def _ps_quote(value):return str(value).replace("'","''")


def _read_shortcut(shortcut):
    if os.name!='nt':return {}
    shortcut=Path(shortcut or '')
    if not shortcut.is_file():return {}
    ps=("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$o=[ordered]@{target=$s.TargetPath;arguments=$s.Arguments;working=$s.WorkingDirectory;icon=$s.IconLocation};"
        "$o|ConvertTo-Json -Compress")
    try:
        cp=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        import json;return json.loads((cp.stdout or '{}').strip() or '{}')
    except Exception:return {}


def shortcut_info(shortcut=None,refresh=False):
    global _info_cache
    if os.name!='nt':return {}
    shortcut=Path(shortcut or find_shortcut(refresh=refresh) or '')
    if not shortcut.is_file():return {}
    use_cache=(shortcut==find_shortcut())
    if use_cache:
        with _cache_lock:
            if not refresh and isinstance(_info_cache,dict) and _info_cache:return dict(_info_cache)
    info=_read_shortcut(shortcut)
    if use_cache:
        with _cache_lock:_info_cache=dict(info)
    return info


def shortcut_icon_spec(shortcut=None,refresh=False):
    return str(shortcut_info(shortcut,refresh).get('icon') or '').strip().strip('"')


def _pythonw_source(root):
    root=Path(root).resolve()
    candidates=[root/'.venv'/'Scripts'/'pythonw.exe']
    try:candidates.append(Path(sys.executable).with_name('pythonw.exe'))
    except Exception:pass
    for p in candidates:
        try:
            if p.is_file():return p.resolve()
        except Exception:pass
    return None


def packaged_launcher(root):
    p=Path(root).resolve()/'assets'/'bin'/LAUNCHER_NAME
    return p if p.is_file() else None


def native_launcher_path(root):
    p=Path(root).resolve()/LAUNCHER_NAME
    return p if p.is_file() else None


def _same_file(a,b):
    try:
        a=Path(a);b=Path(b)
        if not a.is_file() or not b.is_file() or a.stat().st_size!=b.stat().st_size:return False
        def dg(p):
            h=hashlib.sha256()
            with p.open('rb') as f:
                for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
            return h.digest()
        return dg(a)==dg(b)
    except Exception:return False


def _write_runtime_hint(root):
    root=Path(root).resolve();runtime=_pythonw_source(root)
    if not runtime:return None
    hint=root/'assets'/'bin'/RUNTIME_FILE;hint.parent.mkdir(parents=True,exist_ok=True)
    try:
        try:value=str(runtime.relative_to(root)).replace('/','\\')
        except Exception:value=str(runtime)
        tmp=hint.with_suffix('.tmp');tmp.write_text(value+'\n',encoding='utf-8');os.replace(tmp,hint)
    except Exception:return None
    return hint


def ensure_native_launcher(root):
    """Install the real branded launcher in the app root; never rename/copy pythonw.exe again."""
    if os.name!='nt':return None
    root=Path(root).resolve();src=packaged_launcher(root);dst=root/LAUNCHER_NAME
    if not src:return dst if dst.is_file() else None
    try:
        if not _same_file(src,dst):
            tmp=dst.with_name(dst.name+'.rdlnew');shutil.copy2(src,tmp);os.replace(tmp,dst)
        _write_runtime_hint(root)
        # v0.5.6-v0.5.10 created this beside pythonw.exe. It carries Python's embedded identity,
        # so remove only that legacy app-named copy after the real root launcher exists.
        runtime=_pythonw_source(root)
        if runtime:
            legacy=runtime.with_name(LAUNCHER_NAME)
            if legacy.is_file() and legacy.resolve()!=dst.resolve():
                try:legacy.unlink()
                except Exception:pass
    except Exception:return None
    return dst


def packaged_icon(root):
    root=Path(root);p=root/'assets'/'mxb_race_day_live.ico'
    return str(p) if p.is_file() else ''


def best_icon(root,refresh=False):
    p=packaged_icon(root)
    if p:return p
    return shortcut_icon_spec(refresh=refresh)


def _write_shortcut(shortcut,root,launcher,icon=''):
    shortcut=Path(shortcut);root=Path(root).resolve();launcher=Path(launcher)
    shortcut.parent.mkdir(parents=True,exist_ok=True)
    args=f'"{root / "app.py"}"'
    ps=("$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$s.TargetPath='"+_ps_quote(launcher)+"';"
        "$s.Arguments='"+_ps_quote(args)+"';"
        "$s.WorkingDirectory='"+_ps_quote(root)+"';"
        "$s.Description='MXB Race Day Live';")
    if icon:ps+="$s.IconLocation='"+_ps_quote(icon)+",0';"
    ps+='$s.Save()'
    try:
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
        return shortcut.is_file()
    except Exception:return False


def _pinned_dirs():
    raw=os.environ.get('APPDATA','')
    if not raw:return []
    base=Path(raw)/'Microsoft'/'Internet Explorer'/'Quick Launch'/'User Pinned'
    return [base/'TaskBar',base/'StartMenu']


def _is_our_shortcut(path,root):
    path=Path(path);name=path.stem.lower()
    if 'mxb race day live' in name:return True
    info=_read_shortcut(path);target=str(info.get('target') or '').lower();args=str(info.get('arguments') or '').lower()
    app_py=str((Path(root).resolve()/'app.py')).lower()
    return bool(app_py in args or (Path(target).name.lower() in ('pythonw.exe',LAUNCHER_NAME.lower()) and app_py in args))


def _migrate_pinned_shortcuts(root,launcher,icon):
    changed=0
    for folder in _pinned_dirs():
        try:links=list(folder.glob('*.lnk')) if folder.is_dir() else []
        except Exception:links=[]
        for link in links:
            try:
                if _is_our_shortcut(link,root) and _write_shortcut(link,root,launcher,icon):changed+=1
            except Exception:pass
    return changed


def _refresh_shell():
    try:
        import ctypes;ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)
    except Exception:pass
    try:
        exe=shutil.which('ie4uinit.exe')
        if exe:subprocess.run([exe,'-show'],timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
    except Exception:pass


def ensure_desktop_shortcut(root):
    """Create/migrate desktop and existing pinned links to the branded launcher + permanent icon."""
    if os.name!='nt':return None
    global _shortcut_cache,_info_cache
    root=Path(root).resolve();launcher=ensure_native_launcher(root)
    if not launcher:return None
    shortcut=find_shortcut() or next((d/SHORTCUT_NAME for d in desktop_dirs() if d.is_dir() and 'public' not in str(d).lower()),Path.home()/'Desktop'/SHORTCUT_NAME)
    old=shortcut_info(shortcut,refresh=True) if shortcut.is_file() else {}
    try:
        from .windows_taskbar import ensure_local_icon
        icon_path=ensure_local_icon(root)
    except Exception:icon_path=None
    icon=str(icon_path or packaged_icon(root) or old.get('icon') or '')
    _write_shortcut(shortcut,root,launcher,icon)
    _migrate_pinned_shortcuts(root,launcher,icon)
    with _cache_lock:_shortcut_cache=str(shortcut);_info_cache=None
    _refresh_shell()
    return shortcut
