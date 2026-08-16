from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

APP_ID='MXBRaceDayLive.Desktop.v4'
SHORTCUT_NAME='MXB Race Day Live.lnk'
_cache_lock=threading.Lock()
_shortcut_cache=None
_info_cache=None


def desktop_dirs():
    roots=[]
    for key in ('USERPROFILE','ONEDRIVE','OneDriveConsumer','OneDriveCommercial','PUBLIC'):
        raw=os.environ.get(key)
        if raw: roots.append(Path(raw)/'Desktop')
    out=[]; seen=set()
    for p in roots:
        k=str(p).lower()
        if k not in seen: seen.add(k); out.append(p)
    return out


def find_shortcut(refresh=False):
    global _shortcut_cache
    with _cache_lock:
        if not refresh and _shortcut_cache:
            p=Path(_shortcut_cache)
            if p.is_file(): return p
    found=None
    for root in desktop_dirs():
        p=root/SHORTCUT_NAME
        if p.is_file(): found=p; break
        try:
            matches=sorted(root.glob('*MXB*Race*Day*Live*.lnk')) if root.is_dir() else []
            if matches: found=matches[0]; break
        except Exception: pass
    with _cache_lock: _shortcut_cache=str(found) if found else ''
    return found


def _ps_quote(value): return str(value).replace("'","''")


def shortcut_info(shortcut=None,refresh=False):
    global _info_cache
    if os.name!='nt': return {}
    with _cache_lock:
        if not refresh and isinstance(_info_cache,dict) and _info_cache: return dict(_info_cache)
    shortcut=Path(shortcut or find_shortcut(refresh=refresh) or '')
    if not shortcut.is_file(): return {}
    ps=("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$o=[ordered]@{target=$s.TargetPath;arguments=$s.Arguments;working=$s.WorkingDirectory;icon=$s.IconLocation};"
        "$o|ConvertTo-Json -Compress")
    info={}
    try:
        cp=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                          capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        import json
        info=json.loads((cp.stdout or '{}').strip() or '{}')
    except Exception: info={}
    with _cache_lock: _info_cache=dict(info)
    return info


def shortcut_icon_spec(shortcut=None,refresh=False):
    return str(shortcut_info(shortcut,refresh).get('icon') or '').strip().strip('"')


def packaged_icon(root):
    root=Path(root)
    for p in (root/'assets'/'mxb_race_day_live.ico',root/'mxb_race_day_live.ico'):
        if p.is_file(): return str(p)
    try:
        icons=sorted((root/'assets').glob('*.ico')) if (root/'assets').is_dir() else []
        if icons:return str(icons[0])
    except Exception:pass
    return ''


def best_icon(root,refresh=False):
    spec=shortcut_icon_spec(refresh=refresh)
    if spec:return spec
    return packaged_icon(root)


def _launcher_target(root):
    root=Path(root).resolve()
    candidates=[root/'.venv'/'Scripts'/'pythonw.exe', Path(sys.executable).with_name('pythonw.exe'), Path(sys.executable)]
    for p in candidates:
        try:
            if p.is_file(): return p, f'"{root / "app.py"}"'
        except Exception: pass
    return Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32'/'wscript.exe', f'"{root / "Start MXB Race Day Live.vbs"}"'


def ensure_desktop_shortcut(root):
    """Make the shortcut launch Race Day Live directly through pythonw, not WScript.

    This avoids Windows grouping the taskbar button under wscript.exe while preserving
    the shortcut's existing custom IconLocation exactly.
    """
    if os.name!='nt':return None
    global _shortcut_cache,_info_cache
    root=Path(root).resolve()
    shortcut=find_shortcut() or next((d/SHORTCUT_NAME for d in desktop_dirs() if d.is_dir() and 'public' not in str(d).lower()), Path.home()/'Desktop'/SHORTCUT_NAME)
    shortcut.parent.mkdir(parents=True,exist_ok=True)
    old=shortcut_info(shortcut) if shortcut.is_file() else {}
    icon=str(old.get('icon') or packaged_icon(root) or '')
    target,args=_launcher_target(root)
    target_s=str(target)
    if shortcut.is_file() and str(old.get('target') or '').lower()==target_s.lower() and str(old.get('arguments') or '').strip()==args:
        return shortcut
    ps=("$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$s.TargetPath='"+_ps_quote(target_s)+"';"
        "$s.Arguments='"+_ps_quote(args)+"';"
        "$s.WorkingDirectory='"+_ps_quote(root)+"';"
        "$s.Description='MXB Race Day Live';")
    if icon: ps+="$s.IconLocation='"+_ps_quote(icon)+"';"
    ps+='$s.Save()'
    try:
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                       timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
    except Exception:pass
    with _cache_lock:
        _shortcut_cache=str(shortcut); _info_cache=None
    return shortcut
