from __future__ import annotations

import os
import subprocess
from pathlib import Path

APP_ID='MXBRaceDayLive.Desktop.v3'
SHORTCUT_NAME='MXB Race Day Live.lnk'


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


def find_shortcut():
    for root in desktop_dirs():
        p=root/SHORTCUT_NAME
        if p.is_file():return p
        try:
            matches=sorted(root.glob('*MXB*Race*Day*Live*.lnk')) if root.is_dir() else []
            if matches:return matches[0]
        except Exception:pass
    return None


def _ps_quote(value):
    return str(value).replace("'","''")


def shortcut_icon_location(shortcut=None):
    """Read the actual IconLocation configured on the Windows .lnk.

    Unlike SHGetFileInfo(.lnk), this returns the custom logo configured for the
    shortcut rather than the WScript/target file association icon.
    """
    if os.name!='nt':return ''
    shortcut=Path(shortcut or find_shortcut() or '')
    if not shortcut.is_file():return ''
    ps=("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"+_ps_quote(shortcut)+"');"
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::UTF8;Write-Output $s.IconLocation")
    try:
        cp=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',ps],
                          capture_output=True,text=True,timeout=4,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raw=(cp.stdout or '').strip().strip('"')
        # IconLocation may be "C:\path\app.ico,0".
        if ',' in raw:
            maybe,idx=raw.rsplit(',',1)
            if idx.strip().lstrip('-').isdigit():raw=maybe.strip().strip('"')
        raw=os.path.expandvars(raw)
        return raw if raw and Path(raw).is_file() else ''
    except Exception:return ''


def packaged_icon(root):
    root=Path(root)
    for p in (root/'assets'/'mxb_race_day_live.ico',root/'mxb_race_day_live.ico'):
        if p.is_file():return str(p)
    try:
        icons=sorted((root/'assets').glob('*.ico')) if (root/'assets').is_dir() else []
        if icons:return str(icons[0])
    except Exception:pass
    return ''


def best_icon(root):
    # Prefer the logo the user is already seeing on the desktop shortcut.
    existing=shortcut_icon_location()
    if existing:return existing
    return packaged_icon(root)


def ensure_desktop_shortcut(root):
    if os.name!='nt':return None
    root=Path(root).resolve()
    icon=best_icon(root) or packaged_icon(root)
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
                       timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
    except Exception:pass
    return shortcut
