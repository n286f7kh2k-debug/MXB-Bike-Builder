from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

APP_ID='MXBRaceDayLive.Desktop.v3'
SHORTCUT_NAME='MXB Race Day Live.lnk'

_cache_lock=threading.Lock()
_shortcut_cache=None
_icon_cache=None


def desktop_dirs():
    roots=[]
    for key in ('USERPROFILE','ONEDRIVE','OneDriveConsumer','OneDriveCommercial','PUBLIC'):
        raw=os.environ.get(key)
        if raw:roots.append(Path(raw)/'Desktop')
    out=[]; seen=set()
    for p in roots:
        k=str(p).lower()
        if k not in seen:
            seen.add(k); out.append(p)
    return out


def find_shortcut(refresh=False):
    global _shortcut_cache
    with _cache_lock:
        if not refresh and _shortcut_cache:
            try:
                p=Path(_shortcut_cache)
                if p.is_file():return p
            except Exception:pass
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


def _ps_quote(value):
    return str(value).replace("'","''")


def shortcut_icon_location(shortcut=None,refresh=False):
    global _icon_cache
    if os.name!='nt':return ''
    with _cache_lock:
        if not refresh and _icon_cache:
            try:
                if Path(_icon_cache).is_file():return _icon_cache
            except Exception:pass
    shortcut=Path(shortcut or find_shortcut(refresh=refresh) or '')
    if not shortcut.is_file():return ''
    ps=("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"+_ps_quote(shortcut)+"');"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::UTF8;Write-Output $s.IconLocation")
    raw=''
    try:
        cp=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                          capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raw=(cp.stdout or '').strip().strip('"')
        if ',' in raw:
            maybe,idx=raw.rsplit(',',1)
            if idx.strip().lstrip('-').isdigit():raw=maybe.strip().strip('"')
        raw=os.path.expandvars(raw)
        if not raw or not Path(raw).is_file():raw=''
    except Exception:raw=''
    with _cache_lock:_icon_cache=raw
    return raw


def packaged_icon(root):
    root=Path(root)
    for p in (root/'assets'/'mxb_race_day_live.ico',root/'mxb_race_day_live.ico'):
        if p.is_file():return str(p)
    try:
        icons=sorted((root/'assets').glob('*.ico')) if (root/'assets').is_dir() else []
        if icons:return str(icons[0])
    except Exception:pass
    return ''


def best_icon(root,refresh=False):
    global _icon_cache
    with _cache_lock:
        if not refresh and _icon_cache:
            try:
                if Path(_icon_cache).is_file():return _icon_cache
            except Exception:pass
    existing=shortcut_icon_location(refresh=refresh)
    if existing:return existing
    fallback=packaged_icon(root)
    if fallback:
        with _cache_lock:_icon_cache=fallback
    return fallback


def ensure_desktop_shortcut(root):
    """Ensure the shortcut once. Do not rewrite it on every app launch when it is already valid."""
    if os.name!='nt':return None
    root=Path(root).resolve()
    existing=find_shortcut()
    if existing and existing.is_file():
        # Keep the existing shortcut; reading its icon is cached by best_icon().
        return existing
    icon=packaged_icon(root)
    desktop=None
    for d in desktop_dirs():
        if d.is_dir() and 'public' not in str(d).lower():desktop=d;break
    if desktop is None:
        desktop=Path(os.environ.get('USERPROFILE',str(Path.home())))/'Desktop'
        desktop.mkdir(parents=True,exist_ok=True)
    shortcut=desktop/SHORTCUT_NAME
    target=Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32'/'wscript.exe'
    launcher=root/'Start MXB Race Day Live.vbs'
    ps=("$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut('"+_ps_quote(shortcut)+"');"
        "$s.TargetPath='"+_ps_quote(target)+"';"
        "$s.Arguments='\""+_ps_quote(launcher)+"\"';"
        "$s.WorkingDirectory='"+_ps_quote(root)+"';"
        "$s.Description='MXB Race Day Live';")
    if icon:ps+="$s.IconLocation='"+_ps_quote(icon)+",0';"
    ps+='$s.Save()'
    try:
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                       timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
    except Exception:pass
    global _shortcut_cache
    with _cache_lock:_shortcut_cache=str(shortcut)
    return shortcut
