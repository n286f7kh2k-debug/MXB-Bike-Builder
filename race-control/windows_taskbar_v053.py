from __future__ import annotations

import os
from pathlib import Path
from .windows_integration import APP_ID,best_icon,find_shortcut

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


def _split_spec(spec):
    raw=str(spec or '').strip().strip('"'); idx=0
    if ',' in raw:
        maybe,suffix=raw.rsplit(',',1)
        if suffix.strip().lstrip('-').isdigit(): raw=maybe.strip().strip('"'); idx=int(suffix.strip())
    return os.path.expandvars(raw),idx


def _remember(h):
    h=int(h or 0)
    if h and h not in _handles:_handles.append(h)
    return h


def _load_from_spec(spec,large=True):
    path,index=_split_spec(spec)
    if not path or not Path(path).is_file():return 0
    key=(path.lower(),index,bool(large))
    if key in _icon_cache:return _icon_cache[key]
    try:
        import ctypes
        from ctypes import wintypes
        user32=ctypes.windll.user32
        suffix=Path(path).suffix.lower()
        h=0
        if suffix=='.ico':
            IMAGE_ICON=1;LR_LOADFROMFILE=0x0010|0x0040
            fn=user32.LoadImageW;fn.restype=wintypes.HANDLE
            h=fn(None,path,IMAGE_ICON,32 if large else 16,32 if large else 16,LR_LOADFROMFILE)
        else:
            big=wintypes.HICON();small=wintypes.HICON()
            fn=ctypes.windll.shell32.ExtractIconExW
            fn.argtypes=[wintypes.LPCWSTR,ctypes.c_int,ctypes.POINTER(wintypes.HICON),ctypes.POINTER(wintypes.HICON),wintypes.UINT]
            fn.restype=wintypes.UINT
            if fn(path,index,ctypes.byref(big),ctypes.byref(small),1): h=big.value if large else small.value
            other=small.value if large else big.value
            if other:_remember(other)
        h=_remember(h)
        if h:_icon_cache[key]=h
        return h
    except Exception:return 0


def _load_from_shortcut(shortcut,large=True):
    if not shortcut:return 0
    try:
        import ctypes
        from ctypes import wintypes
        class SHFILEINFOW(ctypes.Structure):
            _fields_=[('hIcon',wintypes.HICON),('iIcon',ctypes.c_int),('dwAttributes',wintypes.DWORD),('szDisplayName',wintypes.WCHAR*260),('szTypeName',wintypes.WCHAR*80)]
        info=SHFILEINFOW();SHGFI_ICON=0x100;SHGFI_LARGEICON=0;SHGFI_SMALLICON=1
        result=ctypes.windll.shell32.SHGetFileInfoW(str(shortcut),0,ctypes.byref(info),ctypes.sizeof(info),SHGFI_ICON|(SHGFI_LARGEICON if large else SHGFI_SMALLICON))
        return _remember(info.hIcon if result else 0)
    except Exception:return 0


def _top_hwnds(tk_root):
    import ctypes
    from ctypes import wintypes
    get_ancestor=ctypes.windll.user32.GetAncestor;get_ancestor.restype=wintypes.HWND
    hwnd=int(tk_root.winfo_id());root=int(get_ancestor(hwnd,2) or hwnd)
    return list(dict.fromkeys(x for x in (hwnd,root) if x))


def apply_taskbar_identity(tk_root,icon_path='',app_id=APP_ID):
    if os.name!='nt':return False
    try:
        import ctypes
        from ctypes import wintypes
        set_process_app_id(app_id)
        app_root=Path(__file__).resolve().parent.parent
        spec=best_icon(app_root) or icon_path
        shortcut=find_shortcut()
        big=_load_from_spec(spec,True) or _load_from_shortcut(shortcut,True)
        small=_load_from_spec(spec,False) or _load_from_shortcut(shortcut,False) or big
        if not big:return False
        user32=ctypes.windll.user32
        send=user32.SendMessageW;send.restype=wintypes.LRESULT
        WM_SETICON=0x0080;ICON_SMALL=0;ICON_BIG=1;GCLP_HICON=-14;GCLP_HICONSM=-34
        set_class=getattr(user32,'SetClassLongPtrW',None)
        for hwnd in _top_hwnds(tk_root):
            send(hwnd,WM_SETICON,ICON_BIG,big);send(hwnd,WM_SETICON,ICON_SMALL,small)
            if set_class:
                try:set_class(hwnd,GCLP_HICON,ctypes.c_void_p(big));set_class(hwnd,GCLP_HICONSM,ctypes.c_void_p(small))
                except Exception:pass
            try:user32.RedrawWindow(hwnd,None,None,0x0001|0x0100|0x0400)
            except Exception:pass
        try:tk_root._taskbar_icon_source=spec
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
