from __future__ import annotations

import os
from pathlib import Path
from .windows_integration import APP_ID,best_icon

_handles=[]
_icon_cache={}


def set_process_app_id(app_id=APP_ID):
    if os.name!='nt':return False
    try:
        import ctypes
        from ctypes import wintypes
        fn=ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes=[wintypes.LPCWSTR]; fn.restype=ctypes.c_long
        return int(fn(str(app_id)))==0
    except Exception:return False


def _load_icon(path,size):
    p=Path(path)
    if not p.is_file():return 0
    key=(str(p.resolve()).lower(),int(size))
    if key in _icon_cache:return _icon_cache[key]
    try:
        import ctypes
        from ctypes import wintypes
        IMAGE_ICON=1; LR_LOADFROMFILE=0x0010|0x0040
        fn=ctypes.windll.user32.LoadImageW
        fn.argtypes=[wintypes.HINSTANCE,wintypes.LPCWSTR,wintypes.UINT,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        fn.restype=wintypes.HANDLE
        h=int(fn(None,str(p),IMAGE_ICON,int(size),int(size),LR_LOADFROMFILE) or 0)
        if h:_handles.append(h);_icon_cache[key]=h
        return h
    except Exception:return 0


def _top_hwnds(tk_root):
    import ctypes
    from ctypes import wintypes
    user32=ctypes.windll.user32
    get_ancestor=user32.GetAncestor; get_ancestor.argtypes=[wintypes.HWND,wintypes.UINT]; get_ancestor.restype=wintypes.HWND
    hwnd=int(tk_root.winfo_id()); root=int(get_ancestor(hwnd,2) or hwnd)
    return list(dict.fromkeys([x for x in (hwnd,root) if x]))


def apply_taskbar_identity(tk_root,icon_path='',app_id=APP_ID):
    if os.name!='nt':return False
    try:
        import ctypes
        from ctypes import wintypes
        set_process_app_id(app_id)
        app_root=Path(__file__).resolve().parent.parent
        # Resolve the actual .lnk IconLocation first; packaged icon is fallback.
        source=best_icon(app_root) or icon_path
        if not source:return False
        big=_load_icon(source,32) or _load_icon(source,48)
        small=_load_icon(source,16) or big
        if not big:return False
        user32=ctypes.windll.user32
        send=user32.SendMessageW; send.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]; send.restype=wintypes.LRESULT
        WM_SETICON=0x0080; ICON_SMALL=0; ICON_BIG=1; GCLP_HICON=-14; GCLP_HICONSM=-34
        set_class=getattr(user32,'SetClassLongPtrW',None)
        if set_class:
            set_class.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_void_p]; set_class.restype=ctypes.c_void_p
        for hwnd in _top_hwnds(tk_root):
            send(hwnd,WM_SETICON,ICON_BIG,big); send(hwnd,WM_SETICON,ICON_SMALL,small)
            if set_class:
                try:set_class(hwnd,GCLP_HICON,ctypes.c_void_p(big));set_class(hwnd,GCLP_HICONSM,ctypes.c_void_p(small))
                except Exception:pass
        # Tk itself can overwrite WM_SETICON during map; assert both APIs.
        try:
            tk_root.iconbitmap(default=source)
        except Exception:pass
        try:tk_root._taskbar_icon_source=source
        except Exception:pass
        return True
    except Exception:return False


def release_taskbar_icons():
    _icon_cache.clear()
    if os.name!='nt':_handles.clear();return
    try:
        import ctypes
        while _handles:
            h=_handles.pop()
            try:ctypes.windll.user32.DestroyIcon(h)
            except Exception:pass
    except Exception:_handles.clear()
