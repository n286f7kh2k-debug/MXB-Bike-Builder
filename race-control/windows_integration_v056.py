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


def shortcut_info(shortcut=None,refresh=False):
    global _info_cache
    if os.name!='nt':return {}
    with _cache_lock:
        if not refresh and isinstance(_info_cache,dict) and _info_cache:return dict(_info_cache)
    shortcut=Path(shortcut or find_shortcut(refresh=refresh) or '')
    if not shortcut.is_file():return {}
    ps=("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$o=[ordered]@{target=$s.TargetPath;arguments=$s.Arguments;working=$s.WorkingDirectory;icon=$s.IconLocation};"
        "$o|ConvertTo-Json -Compress")
    info={}
    try:
        cp=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        import json;info=json.loads((cp.stdout or '{}').strip() or '{}')
    except Exception:info={}
    with _cache_lock:_info_cache=dict(info)
    return info


def shortcut_icon_spec(shortcut=None,refresh=False):
    return str(shortcut_info(shortcut,refresh).get('icon') or '').strip().strip('"')


def _pythonw_source(root):
    root=Path(root).resolve()
    for p in (root/'.venv'/'Scripts'/'pythonw.exe',Path(sys.executable).with_name('pythonw.exe')):
        try:
            if p.is_file():return p
        except Exception:pass
    return None


def native_launcher_path(root):
    src=_pythonw_source(root);return src.with_name(LAUNCHER_NAME) if src else None


def _same_runtime(a,b):
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


def ensure_native_launcher(root):
    if os.name!='nt':return None
    root=Path(root).resolve();src=_pythonw_source(root)
    if not src:return None
    dst=src.with_name(LAUNCHER_NAME)
    try:
        if not _same_runtime(src,dst):
            tmp=dst.with_name(dst.name+'.rdlnew');shutil.copy2(src,tmp);os.replace(tmp,dst)
    except Exception:return None
    return dst


def packaged_icon(root):
    root=Path(root);p=root/'assets'/'mxb_race_day_live.ico'
    return str(p) if p.is_file() else ''


def best_icon(root,refresh=False):
    p=packaged_icon(root)
    if p:return p
    return shortcut_icon_spec(refresh=refresh)


def ensure_desktop_shortcut(root):
    """Create/migrate the shortcut to the named Race Day Live executable and a real local ICO."""
    if os.name!='nt':return None
    global _shortcut_cache,_info_cache
    root=Path(root).resolve();launcher=ensure_native_launcher(root)
    if not launcher:return None
    shortcut=find_shortcut() or next((d/SHORTCUT_NAME for d in desktop_dirs() if d.is_dir() and 'public' not in str(d).lower()),Path.home()/'Desktop'/SHORTCUT_NAME)
    shortcut.parent.mkdir(parents=True,exist_ok=True)
    # First preserve the old desktop icon. windows_taskbar turns that exact Explorer icon into
    # a concrete local ICO so Python/Tk/Explorer all use one file from this point forward.
    old=shortcut_info(shortcut,refresh=True) if shortcut.is_file() else {}
    try:
        from .windows_taskbar import ensure_local_icon
        icon_path=ensure_local_icon(root)
    except Exception:icon_path=None
    icon=str(icon_path or old.get('icon') or '')
    args=f'"{root / "app.py"}"';target=str(launcher)
    ps=("$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$s.TargetPath='"+_ps_quote(target)+"';"
        "$s.Arguments='"+_ps_quote(args)+"';"
        "$s.WorkingDirectory='"+_ps_quote(root)+"';"
        "$s.Description='MXB Race Day Live';")
    if icon:ps+="$s.IconLocation='"+_ps_quote(icon)+",0';"
    ps+='$s.Save()'
    try:
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
    except Exception:pass
    with _cache_lock:_shortcut_cache=str(shortcut);_info_cache=None
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)
    except Exception:pass
    return shortcut
