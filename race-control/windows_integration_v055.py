from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

# Permanent Windows identity. Do not version this value again: Windows taskbar grouping
# should follow one stable app identity for the lifetime of Race Day Live.
APP_ID='MXBRaceDayLive.Desktop'
SHORTCUT_NAME='MXB Race Day Live.lnk'
LAUNCHER_NAME='MXB Race Day Live.exe'
_cache_lock=threading.Lock()
_shortcut_cache=None
_info_cache=None


def desktop_dirs():
    roots=[]
    for key in ('USERPROFILE','ONEDRIVE','OneDriveConsumer','OneDriveCommercial','PUBLIC'):
        raw=os.environ.get(key)
        if raw: roots.append(Path(raw)/'Desktop')
    try:
        roots.append(Path.home()/'Desktop')
    except Exception: pass
    out=[];seen=set()
    for p in roots:
        k=str(p).lower()
        if k not in seen:
            seen.add(k);out.append(p)
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
        cp=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                          capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        import json
        info=json.loads((cp.stdout or '{}').strip() or '{}')
    except Exception:info={}
    with _cache_lock:_info_cache=dict(info)
    return info


def shortcut_icon_spec(shortcut=None,refresh=False):
    return str(shortcut_info(shortcut,refresh).get('icon') or '').strip().strip('"')


def packaged_icon(root):
    root=Path(root)
    for p in (root/'assets'/'mxb_race_day_live.ico',root/'mxb_race_day_live.ico'):
        if p.is_file():return str(p)
    try:
        icons=sorted((root/'assets').glob('*.ico')) if (root/'assets').is_dir() else []
        if icons:return str(icons[0])
    except Exception:pass
    return ''


def _pythonw_source(root):
    root=Path(root).resolve()
    candidates=[root/'.venv'/'Scripts'/'pythonw.exe',Path(sys.executable).with_name('pythonw.exe')]
    for p in candidates:
        try:
            if p.is_file():return p
        except Exception:pass
    return None


def native_launcher_path(root):
    src=_pythonw_source(root)
    return src.with_name(LAUNCHER_NAME) if src else None


def _same_runtime(a,b):
    try:
        if not Path(a).is_file() or not Path(b).is_file():return False
        sa=Path(a).stat();sb=Path(b).stat()
        if sa.st_size!=sb.st_size:return False
        # Hash only the small Python bootstrap executable. This avoids stale launcher copies
        # after a Python runtime update while remaining cheap enough for startup.
        def digest(p):
            h=hashlib.sha256()
            with Path(p).open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            return h.digest()
        return digest(a)==digest(b)
    except Exception:return False


def ensure_native_launcher(root):
    """Create a real, named Race Day Live executable from the active pythonw runtime.

    The copied interpreter stays beside pythonw.exe inside the same venv, so it uses the same
    Python environment but Windows sees a dedicated MXB Race Day Live executable instead of
    grouping the taskbar button under pythonw.exe/wscript.exe.
    """
    if os.name!='nt':return None
    root=Path(root).resolve();src=_pythonw_source(root)
    if not src:return None
    dst=src.with_name(LAUNCHER_NAME)
    try:
        if not _same_runtime(src,dst):
            tmp=dst.with_name(dst.name+'.rdlnew')
            shutil.copy2(src,tmp);os.replace(tmp,dst)
    except Exception:
        return None
    return dst


def best_icon(root,refresh=False):
    # The desktop shortcut is authoritative because that is the logo the user already sees.
    spec=shortcut_icon_spec(refresh=refresh)
    if spec:return spec
    icon=packaged_icon(root)
    if icon:return icon
    launcher=native_launcher_path(root)
    return str(launcher) if launcher and launcher.is_file() else ''


def ensure_desktop_shortcut(root):
    """Point the desktop shortcut at Race Day Live's own named executable.

    Existing custom IconLocation is preserved exactly, including an EXE/DLL resource index.
    """
    if os.name!='nt':return None
    global _shortcut_cache,_info_cache
    root=Path(root).resolve();launcher=ensure_native_launcher(root)
    if not launcher:return None
    shortcut=find_shortcut() or next((d/SHORTCUT_NAME for d in desktop_dirs() if d.is_dir() and 'public' not in str(d).lower()),Path.home()/'Desktop'/SHORTCUT_NAME)
    shortcut.parent.mkdir(parents=True,exist_ok=True)
    old=shortcut_info(shortcut,refresh=True) if shortcut.is_file() else {}
    icon=str(old.get('icon') or packaged_icon(root) or '')
    args=f'"{root / "app.py"}"'
    target_s=str(launcher)
    ps=("$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$s.TargetPath='"+_ps_quote(target_s)+"';"
        "$s.Arguments='"+_ps_quote(args)+"';"
        "$s.WorkingDirectory='"+_ps_quote(root)+"';"
        "$s.Description='MXB Race Day Live';")
    if icon:ps+="$s.IconLocation='"+_ps_quote(icon)+"';"
    ps+='$s.Save()'
    try:
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                       timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
    except Exception:pass
    with _cache_lock:
        _shortcut_cache=str(shortcut);_info_cache=None
    # Notify Explorer immediately so it re-reads the shortcut/icon instead of retaining an old
    # pythonw/wscript taskbar identity from its icon cache.
    try:
        import ctypes
        SHCNE_ASSOCCHANGED=0x08000000;SHCNF_IDLIST=0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED,SHCNF_IDLIST,None,None)
    except Exception:pass
    return shortcut
