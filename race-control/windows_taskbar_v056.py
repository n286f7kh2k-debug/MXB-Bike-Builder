from __future__ import annotations

import os
from pathlib import Path

APP_ID='MXBRaceDayLive.Desktop'
_handles=[]
_cached_icon=''


def set_process_app_id(app_id=APP_ID):
    if os.name!='nt':return False
    try:
        import ctypes
        from ctypes import wintypes
        fn=ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        fn.argtypes=[wintypes.LPCWSTR];fn.restype=ctypes.c_long
        return int(fn(str(app_id)))==0
    except Exception:return False


def _desktop_shortcut():
    try:
        from .windows_integration import find_shortcut
        return find_shortcut(refresh=True)
    except Exception:return None


def _extract_shortcut_icon_png(shortcut,out_png):
    """Extract the exact icon Explorer renders for the desktop shortcut into a PNG."""
    if os.name!='nt' or not shortcut:return False
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
        class SHFILEINFOW(ctypes.Structure):
            _fields_=[('hIcon',wintypes.HICON),('iIcon',ctypes.c_int),('dwAttributes',wintypes.DWORD),('szDisplayName',wintypes.WCHAR*260),('szTypeName',wintypes.WCHAR*80)]
        info=SHFILEINFOW();SHGFI_ICON=0x100;SHGFI_LARGEICON=0x0
        if not ctypes.windll.shell32.SHGetFileInfoW(str(shortcut),0,ctypes.byref(info),ctypes.sizeof(info),SHGFI_ICON|SHGFI_LARGEICON):return False
        hicon=int(info.hIcon or 0)
        if not hicon:return False
        class ICONINFO(ctypes.Structure):
            _fields_=[('fIcon',wintypes.BOOL),('xHotspot',wintypes.DWORD),('yHotspot',wintypes.DWORD),('hbmMask',wintypes.HBITMAP),('hbmColor',wintypes.HBITMAP)]
        ii=ICONINFO()
        if not ctypes.windll.user32.GetIconInfo(hicon,ctypes.byref(ii)):
            ctypes.windll.user32.DestroyIcon(hicon);return False
        class BITMAP(ctypes.Structure):
            _fields_=[('bmType',wintypes.LONG),('bmWidth',wintypes.LONG),('bmHeight',wintypes.LONG),('bmWidthBytes',wintypes.LONG),('bmPlanes',wintypes.WORD),('bmBitsPixel',wintypes.WORD),('bmBits',ctypes.c_void_p)]
        bmp=BITMAP();gdi=ctypes.windll.gdi32
        if not ii.hbmColor or not gdi.GetObjectW(ii.hbmColor,ctypes.sizeof(bmp),ctypes.byref(bmp)):
            ctypes.windll.user32.DestroyIcon(hicon);return False
        w=max(1,int(bmp.bmWidth));h=max(1,int(bmp.bmHeight))
        class BIH(ctypes.Structure):
            _fields_=[('biSize',wintypes.DWORD),('biWidth',wintypes.LONG),('biHeight',wintypes.LONG),('biPlanes',wintypes.WORD),('biBitCount',wintypes.WORD),('biCompression',wintypes.DWORD),('biSizeImage',wintypes.DWORD),('biXPelsPerMeter',wintypes.LONG),('biYPelsPerMeter',wintypes.LONG),('biClrUsed',wintypes.DWORD),('biClrImportant',wintypes.DWORD)]
        bih=BIH();bih.biSize=ctypes.sizeof(BIH);bih.biWidth=w;bih.biHeight=-h;bih.biPlanes=1;bih.biBitCount=32;bih.biCompression=0
        buf=(ctypes.c_ubyte*(w*h*4))();hdc=gdi.CreateCompatibleDC(None)
        ok=gdi.GetDIBits(hdc,ii.hbmColor,0,h,ctypes.byref(buf),ctypes.byref(bih),0)
        gdi.DeleteDC(hdc)
        try:
            if ii.hbmColor:gdi.DeleteObject(ii.hbmColor)
            if ii.hbmMask:gdi.DeleteObject(ii.hbmMask)
            ctypes.windll.user32.DestroyIcon(hicon)
        except Exception:pass
        if not ok:return False
        im=Image.frombuffer('RGBA',(w,h),bytes(buf),'raw','BGRA',0,1)
        out_png=Path(out_png);out_png.parent.mkdir(parents=True,exist_ok=True);im.save(out_png,'PNG')
        return True
    except Exception:return False


def ensure_local_icon(root):
    """Create a real .ico file from the exact desktop shortcut icon and reuse it everywhere."""
    global _cached_icon
    root=Path(root).resolve();assets=root/'assets';assets.mkdir(parents=True,exist_ok=True)
    ico=assets/'mxb_race_day_live.ico'
    if _cached_icon and Path(_cached_icon).is_file():return Path(_cached_icon)
    # Prefer a valid packaged icon when one already exists.
    try:
        from PIL import Image
        if ico.is_file():
            with Image.open(ico) as im:
                im.verify()
            _cached_icon=str(ico);return ico
    except Exception:pass
    png=assets/'mxb_race_day_live_extracted.png'
    if _extract_shortcut_icon_png(_desktop_shortcut(),png):
        try:
            from PIL import Image
            with Image.open(png) as im:
                base=im.convert('RGBA')
                # One physical source, multiple Windows icon sizes.
                base.save(ico,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
            _cached_icon=str(ico);return ico
        except Exception:pass
    return ico if ico.is_file() else None


def _load_icon(path,size):
    if not path:return 0
    try:
        import ctypes
        from ctypes import wintypes
        h=ctypes.windll.user32.LoadImageW(None,str(path),1,int(size),int(size),0x0010|0x0040)
        h=int(h or 0)
        if h:_handles.append(h)
        return h
    except Exception:return 0


def _top_hwnds(root):
    try:
        import ctypes
        hwnd=int(root.winfo_id());ga=ctypes.windll.user32.GetAncestor
        top=int(ga(hwnd,2) or hwnd)
        return list(dict.fromkeys(x for x in (hwnd,top) if x))
    except Exception:return []


def apply_taskbar_identity(tk_root,icon_path='',app_id=APP_ID):
    if os.name!='nt':return False
    try:
        import ctypes
        set_process_app_id(app_id)
        root=Path(__file__).resolve().parent.parent
        icon=ensure_local_icon(root) or (Path(icon_path) if icon_path and Path(icon_path).is_file() else None)
        if not icon:return False
        # Tk and the native HWND both receive the same concrete .ico file.
        try:tk_root.iconbitmap(default=str(icon))
        except Exception:pass
        big=_load_icon(icon,48);small=_load_icon(icon,16) or big
        if not big:return False
        u=ctypes.windll.user32;WM_SETICON=0x0080;ICON_SMALL=0;ICON_BIG=1
        set_class=getattr(u,'SetClassLongPtrW',None);GCLP_HICON=-14;GCLP_HICONSM=-34
        for hwnd in _top_hwnds(tk_root):
            u.SendMessageW(hwnd,WM_SETICON,ICON_BIG,big);u.SendMessageW(hwnd,WM_SETICON,ICON_SMALL,small)
            if set_class:
                try:set_class(hwnd,GCLP_HICON,ctypes.c_void_p(big));set_class(hwnd,GCLP_HICONSM,ctypes.c_void_p(small))
                except Exception:pass
            try:u.RedrawWindow(hwnd,None,None,0x0001|0x0100|0x0400)
            except Exception:pass
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)
        except Exception:pass
        try:tk_root._taskbar_icon_source=str(icon)
        except Exception:pass
        return True
    except Exception:return False


def release_taskbar_icons():
    if os.name=='nt':
        try:
            import ctypes
            while _handles:
                try:ctypes.windll.user32.DestroyIcon(_handles.pop())
                except Exception:pass
        except Exception:_handles.clear()
    else:_handles.clear()
