from __future__ import annotations

import os
from pathlib import Path

_handles = []
_cached_icon = ''


def _desktop_shortcut():
    try:
        from .windows_integration import find_shortcut
        return find_shortcut(refresh=True)
    except Exception:
        return None


def ensure_local_icon(root):
    """Keep one valid multi-size ICO for Tk/WM_SETICON; pins use the EXE's embedded icon."""
    global _cached_icon
    root = Path(root).resolve()
    assets = root / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    ico = assets / 'mxb_race_day_live.ico'
    if _cached_icon and Path(_cached_icon).is_file():
        return Path(_cached_icon)
    try:
        from PIL import Image
        if ico.is_file():
            with Image.open(ico) as image:
                image.verify()
            _cached_icon = str(ico)
            return ico
    except Exception:
        pass
    return ico if ico.is_file() else None


def _load_icon(path, size):
    if not path:
        return 0
    try:
        import ctypes
        h = ctypes.windll.user32.LoadImageW(None, str(path), 1, int(size), int(size), 0x0010 | 0x0040)
        h = int(h or 0)
        if h:
            _handles.append(h)
        return h
    except Exception:
        return 0


def _top_hwnds(root):
    try:
        import ctypes
        hwnd = int(root.winfo_id())
        top = int(ctypes.windll.user32.GetAncestor(hwnd, 2) or hwnd)
        return list(dict.fromkeys(x for x in (hwnd, top) if x))
    except Exception:
        return []


def apply_taskbar_identity(tk_root, icon_path='', app_id=None):
    """Apply only the window icon. Process identity comes from MXB Race Day Live.exe itself."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        root = Path(__file__).resolve().parent.parent
        icon = ensure_local_icon(root)
        if not icon and icon_path and Path(icon_path).is_file():
            icon = Path(icon_path)
        if not icon:
            return False

        try:
            tk_root.iconbitmap(default=str(icon))
        except Exception:
            pass

        big = _load_icon(icon, 48)
        small = _load_icon(icon, 16) or big
        if not big:
            return False

        user32 = ctypes.windll.user32
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        set_class = getattr(user32, 'SetClassLongPtrW', None)
        for hwnd in _top_hwnds(tk_root):
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
            if set_class:
                try:
                    set_class(hwnd, -14, ctypes.c_void_p(big))
                    set_class(hwnd, -34, ctypes.c_void_p(small))
                except Exception:
                    pass
            try:
                user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0100 | 0x0400)
            except Exception:
                pass

        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass
        try:
            tk_root._taskbar_icon_source = str(icon)
        except Exception:
            pass
        return True
    except Exception:
        return False


def release_taskbar_icons():
    if os.name == 'nt':
        try:
            import ctypes
            while _handles:
                try:
                    ctypes.windll.user32.DestroyIcon(_handles.pop())
                except Exception:
                    pass
        except Exception:
            _handles.clear()
    else:
        _handles.clear()
