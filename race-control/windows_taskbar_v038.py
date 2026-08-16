from __future__ import annotations

import os
from pathlib import Path

APP_ID = 'MXBRaceDayLive.Desktop.v2'

_handles = []


def set_process_app_id(app_id: str = APP_ID):
    if os.name != 'nt':
        return False
    try:
        import ctypes
        hr = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
        return int(hr) == 0
    except Exception:
        return False


def _load_icon(path: str, size: int):
    import ctypes
    user32 = ctypes.windll.user32
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    LR_DEFAULTCOLOR = 0x0000
    hicon = user32.LoadImageW(None, str(path), IMAGE_ICON, int(size), int(size), LR_LOADFROMFILE | LR_DEFAULTCOLOR)
    if hicon:
        _handles.append(int(hicon))
    return int(hicon or 0)


def _top_hwnds(tk_root):
    import ctypes
    user32 = ctypes.windll.user32
    GA_ROOT = 2
    hwnd = int(tk_root.winfo_id())
    root = int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
    out = []
    for value in (hwnd, root):
        if value and value not in out:
            out.append(value)
    return out


def apply_taskbar_identity(tk_root, icon_path: str, app_id: str = APP_ID):
    """Apply the icon to the actual Windows top-level HWND, not only Tk metadata."""
    if os.name != 'nt':
        return False
    icon = Path(icon_path)
    if not icon.is_file():
        return False
    try:
        import ctypes
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

        big = _load_icon(str(icon), 32)
        small = _load_icon(str(icon), 16)
        if not big and not small:
            return False
        if not big:
            big = small
        if not small:
            small = big

        set_class = getattr(user32, 'SetClassLongPtrW', None) or getattr(user32, 'SetClassLongW', None)
        for hwnd in _top_hwnds(tk_root):
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
            if set_class:
                try:
                    set_class(hwnd, GCLP_HICON, big)
                    set_class(hwnd, GCLP_HICONSM, small)
                except Exception:
                    pass
            try:
                user32.RedrawWindow(hwnd, None, None, RDW_INVALIDATE | RDW_FRAME | RDW_UPDATENOW)
            except Exception:
                pass
        return True
    except Exception:
        return False


def release_taskbar_icons():
    if os.name != 'nt':
        _handles.clear()
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        while _handles:
            handle = _handles.pop()
            try:
                user32.DestroyIcon(handle)
            except Exception:
                pass
    except Exception:
        _handles.clear()
