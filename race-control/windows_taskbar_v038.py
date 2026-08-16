from __future__ import annotations

import os
from pathlib import Path

APP_ID = 'MXBRaceDayLive.Desktop.v2'

_handles = []
_icon_cache = {}


def set_process_app_id(app_id: str = APP_ID):
    if os.name != 'nt':
        return False
    try:
        import ctypes
        from ctypes import wintypes
        fn = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes = [wintypes.LPCWSTR]
        fn.restype = ctypes.c_long
        return int(fn(str(app_id))) == 0
    except Exception:
        return False


def _desktop_dirs():
    roots = []
    for key in ('USERPROFILE','ONEDRIVE','OneDriveConsumer','OneDriveCommercial','PUBLIC'):
        raw = os.environ.get(key)
        if raw:
            roots.append(Path(raw) / 'Desktop')
    out=[]; seen=set()
    for root in roots:
        key=str(root).lower()
        if key not in seen:
            seen.add(key); out.append(root)
    return out


def find_race_day_live_shortcut():
    exact = ('MXB Race Day Live.lnk','MXB Race Day Live Launcher.lnk')
    for root in _desktop_dirs():
        for name in exact:
            p=root/name
            if p.is_file():return p
        if root.is_dir():
            try:
                matches=sorted(root.glob('*MXB*Race*Day*Live*.lnk'))
                if matches:return matches[0]
            except Exception:pass
    return None


def _shortcut_icon(shortcut: Path, small: bool):
    import ctypes
    from ctypes import wintypes
    shell32=ctypes.windll.shell32
    SHGFI_ICON=0x000000100
    SHGFI_SMALLICON=0x000000001
    SHGFI_LARGEICON=0x000000000
    class SHFILEINFOW(ctypes.Structure):
        _fields_=[('hIcon',wintypes.HICON),('iIcon',ctypes.c_int),('dwAttributes',wintypes.DWORD),('szDisplayName',wintypes.WCHAR*260),('szTypeName',wintypes.WCHAR*80)]
    info=SHFILEINFOW()
    fn=shell32.SHGetFileInfoW
    fn.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.POINTER(SHFILEINFOW),wintypes.UINT,wintypes.UINT]
    fn.restype=ctypes.c_void_p
    flags=SHGFI_ICON | (SHGFI_SMALLICON if small else SHGFI_LARGEICON)
    ok=fn(str(shortcut),0,ctypes.byref(info),ctypes.sizeof(info),flags)
    h=int(info.hIcon or 0) if ok else 0
    if h:_handles.append(h)
    return h


def _load_icon(path: str, size: int):
    p=Path(path)
    if not p.is_file():return 0
    key = (str(p.resolve()).lower(), int(size))
    if key in _icon_cache:
        return _icon_cache[key]
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    load = user32.LoadImageW
    load.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    load.restype = wintypes.HANDLE
    hicon = int(load(None, str(p), IMAGE_ICON, int(size), int(size), LR_LOADFROMFILE) or 0)
    if hicon:
        _handles.append(hicon)
        _icon_cache[key] = hicon
    return hicon


def _top_hwnds(tk_root):
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    get_ancestor = user32.GetAncestor
    get_ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
    get_ancestor.restype = wintypes.HWND
    GA_ROOT = 2
    hwnd = int(tk_root.winfo_id())
    root = int(get_ancestor(hwnd, GA_ROOT) or hwnd)
    out = []
    for value in (hwnd, root):
        if value and value not in out:
            out.append(value)
    return out


def _icon_pair(icon_path: str = ''):
    # First choice: use the exact icon Explorer already shows on the Race Day Live desktop shortcut.
    shortcut=find_race_day_live_shortcut()
    if shortcut:
        big=_shortcut_icon(shortcut,False)
        small=_shortcut_icon(shortcut,True)
        if big or small:return big or small, small or big, str(shortcut)
    # Fallback: use any packaged/local ICO the app can find.
    candidates=[]
    if icon_path:candidates.append(Path(icon_path))
    try:
        install=Path(__file__).resolve().parent.parent
        candidates += [install/'assets'/'mxb_race_day_live.ico',install/'mxb_race_day_live.ico']
        candidates += sorted(install.glob('*.ico'))
        if (install/'assets').is_dir():candidates += sorted((install/'assets').glob('*.ico'))
    except Exception:pass
    seen=set()
    for p in candidates:
        key=str(p).lower()
        if key in seen:continue
        seen.add(key)
        big=_load_icon(str(p),32); small=_load_icon(str(p),16)
        if big or small:return big or small, small or big, str(p)
    return 0,0,''


def apply_taskbar_identity(tk_root, icon_path: str = '', app_id: str = APP_ID):
    """Force the exact Race Day Live desktop icon onto the actual Windows taskbar HWND."""
    if os.name != 'nt':return False
    try:
        import ctypes
        from ctypes import wintypes
        set_process_app_id(app_id)
        user32 = ctypes.windll.user32
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        GCLP_HICON = -14
        GCLP_HICONSM = -34
        RDW_INVALIDATE = 0x0001
        RDW_FRAME = 0x0400
        RDW_UPDATENOW = 0x0100

        send = user32.SendMessageW
        send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        send.restype = wintypes.LRESULT
        redraw = user32.RedrawWindow
        redraw.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
        redraw.restype = wintypes.BOOL

        set_class = getattr(user32, 'SetClassLongPtrW', None)
        if set_class:
            set_class.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            set_class.restype = ctypes.c_void_p
        else:
            set_class = user32.SetClassLongW
            set_class.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            set_class.restype = wintypes.DWORD

        big,small,source=_icon_pair(icon_path)
        if not big and not small:return False
        for hwnd in _top_hwnds(tk_root):
            send(hwnd, WM_SETICON, ICON_BIG, big)
            send(hwnd, WM_SETICON, ICON_SMALL, small)
            try:
                if hasattr(user32, 'SetClassLongPtrW'):
                    set_class(hwnd, GCLP_HICON, ctypes.c_void_p(big))
                    set_class(hwnd, GCLP_HICONSM, ctypes.c_void_p(small))
                else:
                    set_class(hwnd, GCLP_HICON, big)
                    set_class(hwnd, GCLP_HICONSM, small)
            except Exception:pass
            try:redraw(hwnd,None,None,RDW_INVALIDATE|RDW_FRAME|RDW_UPDATENOW)
            except Exception:pass
        try:tk_root._taskbar_icon_source=source
        except Exception:pass
        return True
    except Exception:return False


def release_taskbar_icons():
    _icon_cache.clear()
    if os.name != 'nt':
        _handles.clear(); return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        while _handles:
            handle = _handles.pop()
            try:user32.DestroyIcon(handle)
            except Exception:pass
    except Exception:_handles.clear()
