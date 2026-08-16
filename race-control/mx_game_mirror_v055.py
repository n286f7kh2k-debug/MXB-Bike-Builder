from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
except Exception:
    tk=None


class MXGameMirrorError(RuntimeError):
    pass


class MXGameGarageMirror:
    """Live mirror of MX Bikes' own Bike Selection renderer inside Race Day Live.

    The MX Bikes DirectX window remains a separate top-level window (required by DWM), is
    removed from the taskbar and kept behind Race Day Live. Windows DWM then renders that
    exact source window into a borderless owned overlay positioned over the Garage page.
    No EDF decoding, substitute geometry or DirectX re-parenting is used.
    """

    CLIENT_PORT='54219'

    def __init__(self,game_bridge,garage,root):
        self.game_bridge=game_bridge
        self.garage=garage
        self.root=root
        self.process=None
        self.source_hwnd=0
        self.overlay=None
        self.host=None
        self.thumbnail=0
        self._starting=False
        self._stop=threading.Event()
        self._lock=threading.Lock()
        self._status_cb=None
        self._source_size=(1280,720)
        self._sync_after=None

    @staticmethod
    def supported():
        return os.name=='nt' and tk is not None

    def _status(self,state,detail=''):
        cb=self._status_cb
        if cb:
            try:self.root.after(0,lambda:cb(state,detail))
            except Exception:pass

    def prewarm_async(self):
        if not self.supported():return
        with self._lock:
            if self._starting or (self.process and self.process.poll() is None and self.source_hwnd):return
            self._starting=True;self._stop.clear()
        threading.Thread(target=self._start_worker,name='RDL-MXB-Garage-Mirror',daemon=True).start()

    def _start_worker(self):
        try:
            self._status('starting','Starting the MX Bikes garage renderer…')
            exe=self.game_bridge.game_exe()
            if not exe:raise MXGameMirrorError('MX Bikes executable was not found. Run game sync first.')
            exe=Path(exe)
            flags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)
            startup=None
            if os.name=='nt':
                startup=subprocess.STARTUPINFO();startup.dwFlags|=getattr(subprocess,'STARTF_USESHOWWINDOW',1)
                # Start without activation. The render window is immediately placed behind RDL.
                startup.wShowWindow=4  # SW_SHOWNOACTIVATE
            self.process=subprocess.Popen([str(exe),'-clientport',self.CLIENT_PORT],cwd=str(exe.parent),
                                          startupinfo=startup,creationflags=flags)
            hwnd=self._wait_for_window(self.process.pid,30.0)
            if not hwnd:raise MXGameMirrorError('MX Bikes started but its render window was not found.')
            self.source_hwnd=int(hwnd)
            self._prepare_source_window()
            # Give the home screen time to finish its own content load, then select Bike.
            time.sleep(2.2)
            self._open_bike_selection_default_ui()
            self._status('ready','MX Bikes Bike Selection is live.')
            try:self.root.after(0,self._attach_if_waiting)
            except Exception:pass
        except Exception as exc:
            self._status('error',str(exc));self._terminate_process()
        finally:
            with self._lock:self._starting=False

    def _wait_for_window(self,pid,timeout):
        import ctypes
        from ctypes import wintypes
        user32=ctypes.windll.user32;found=[]
        EnumProc=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        def scan():
            found.clear()
            @EnumProc
            def cb(hwnd,lparam):
                proc=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(proc))
                if int(proc.value)==int(pid) and user32.GetWindow(hwnd,4)==0: # GW_OWNER == 4
                    # Accept the first real top-level window with a client area.
                    rc=wintypes.RECT()
                    if user32.GetClientRect(hwnd,ctypes.byref(rc)) and (rc.right-rc.left)>200 and (rc.bottom-rc.top)>150:
                        found.append(int(hwnd));return False
                return True
            user32.EnumWindows(cb,0)
            return found[0] if found else 0
        end=time.time()+timeout
        while time.time()<end and not self._stop.is_set():
            h=scan()
            if h:return h
            if self.process and self.process.poll() is not None:return 0
            time.sleep(.1)
        return 0

    def _prepare_source_window(self):
        if not self.source_hwnd:return
        import ctypes
        user32=ctypes.windll.user32
        GWL_EXSTYLE=-20;WS_EX_APPWINDOW=0x00040000;WS_EX_TOOLWINDOW=0x00000080
        SWP_NOACTIVATE=0x0010;SWP_FRAMECHANGED=0x0020;SWP_SHOWWINDOW=0x0040
        try:
            style=int(user32.GetWindowLongW(self.source_hwnd,GWL_EXSTYLE))
            style=(style|WS_EX_TOOLWINDOW)&~WS_EX_APPWINDOW
            user32.SetWindowLongW(self.source_hwnd,GWL_EXSTYLE,style)
        except Exception:pass
        # Keep the game composed but completely behind the Race Day Live window.
        try:
            x=int(self.root.winfo_rootx());y=int(self.root.winfo_rooty())
            user32.SetWindowPos(self.source_hwnd,1,x,y,self._source_size[0],self._source_size[1],
                                SWP_NOACTIVATE|SWP_FRAMECHANGED|SWP_SHOWWINDOW) # HWND_BOTTOM
        except Exception:
            try:user32.SetWindowPos(self.source_hwnd,1,-32000,-32000,self._source_size[0],self._source_size[1],SWP_NOACTIVATE|SWP_SHOWWINDOW)
            except Exception:pass

    def _client_size(self):
        if not self.source_hwnd:return self._source_size
        try:
            import ctypes
            from ctypes import wintypes
            rc=wintypes.RECT();ctypes.windll.user32.GetClientRect(self.source_hwnd,ctypes.byref(rc))
            w=max(1,int(rc.right-rc.left));h=max(1,int(rc.bottom-rc.top));self._source_size=(w,h);return w,h
        except Exception:return self._source_size

    @staticmethod
    def _lp(x,y):
        return (int(y)&0xffff)<<16 | (int(x)&0xffff)

    def _post_click(self,x,y):
        if not self.source_hwnd:return
        import ctypes
        user32=ctypes.windll.user32;WM_MOUSEMOVE=0x0200;WM_LBUTTONDOWN=0x0201;WM_LBUTTONUP=0x0202;MK_LBUTTON=1
        lp=self._lp(x,y)
        user32.PostMessageW(self.source_hwnd,WM_MOUSEMOVE,0,lp)
        user32.PostMessageW(self.source_hwnd,WM_LBUTTONDOWN,MK_LBUTTON,lp)
        user32.PostMessageW(self.source_hwnd,WM_LBUTTONUP,0,lp)

    def _post_key(self,vk):
        if not self.source_hwnd:return
        import ctypes
        u=ctypes.windll.user32;WM_KEYDOWN=0x0100;WM_KEYUP=0x0101
        u.PostMessageW(self.source_hwnd,WM_KEYDOWN,int(vk),0);u.PostMessageW(self.source_hwnd,WM_KEYUP,int(vk),0)

    def _open_bike_selection_default_ui(self):
        """Open the game's Bike menu without taking desktop focus.

        The default PiBoSo menu keeps Bike in the left navigation. A relative pointer click is
        used because it is independent of the source resolution. If a custom UI moves the item,
        the live mirror still exposes the actual main menu and the user can click My Bike/Bike
        directly in the embedded surface; input is forwarded one-for-one.
        """
        try:
            w,h=self._client_size()
            # Default MX Bikes menu: left column, Bike row. The fallback keyboard pass below
            # covers the stock keyboard-navigable menu if the pointer row changed slightly.
            self._post_click(int(w*.075),int(h*.655))
            time.sleep(.35)
            # Do not keep blindly clicking. A keyboard B mnemonic is harmless on the menu and
            # is supported by some UI themes; the live embedded screen remains authoritative.
            self._post_key(ord('B'))
        except Exception:pass

    def attach(self,host,status_cb=None):
        self.host=host;self._status_cb=status_cb
        if not self.supported():
            self._status('error','The live MX Bikes Garage mirror requires Windows.');return False
        self.prewarm_async()
        if not self.source_hwnd:
            self._status('starting','Preparing the real MX Bikes Bike Selection screen…');return False
        return self._attach_if_waiting()

    def _attach_if_waiting(self):
        if not self.host or not self.source_hwnd:return False
        try:
            if not self.host.winfo_exists():return False
        except Exception:return False
        self.detach(keep_host=True)
        try:
            self.root.update_idletasks();self.host.update_idletasks()
            ov=tk.Toplevel(self.root);ov.overrideredirect(True);ov.configure(bg='black')
            try:ov.transient(self.root)
            except Exception:pass
            self.overlay=ov
            self._position_overlay()
            ov.bind('<Button-1>',self._mouse_down,add='+');ov.bind('<ButtonRelease-1>',self._mouse_up,add='+')
            ov.bind('<Motion>',self._mouse_move,add='+');ov.bind('<B1-Motion>',self._mouse_drag,add='+')
            ov.bind('<MouseWheel>',self._mouse_wheel,add='+');ov.bind('<KeyPress>',self._key_down,add='+')
            ov.bind('<Escape>',lambda e:self._post_key(0x1B),add='+')
            ov.focus_set()
            if not self._register_thumbnail():raise MXGameMirrorError('Windows DWM could not attach the MX Bikes render surface.')
            self._status('ready','LIVE • ACTUAL MX BIKES BIKE + RIDER')
            self._schedule_sync();return True
        except Exception as exc:
            self._status('error',str(exc));self.detach();return False

    def _position_overlay(self):
        if not self.overlay or not self.host:return
        try:
            self.host.update_idletasks()
            x=self.host.winfo_rootx();y=self.host.winfo_rooty();w=max(2,self.host.winfo_width());h=max(2,self.host.winfo_height())
            self.overlay.geometry(f'{w}x{h}+{x}+{y}');self.overlay.lift(self.root)
        except Exception:pass

    def _register_thumbnail(self):
        import ctypes
        from ctypes import wintypes
        if self.thumbnail:
            try:ctypes.windll.dwmapi.DwmUnregisterThumbnail(self.thumbnail)
            except Exception:pass
            self.thumbnail=0
        dest=int(self.overlay.winfo_id());thumb=ctypes.c_void_p()
        fn=ctypes.windll.dwmapi.DwmRegisterThumbnail
        hr=int(fn(dest,int(self.source_hwnd),ctypes.byref(thumb)))
        if hr!=0:return False
        self.thumbnail=int(thumb.value or 0);return self._update_thumbnail()

    def _update_thumbnail(self):
        if not self.thumbnail or not self.overlay:return False
        import ctypes
        from ctypes import wintypes
        class Props(ctypes.Structure):
            _fields_=[('dwFlags',wintypes.DWORD),('rcDestination',wintypes.RECT),('rcSource',wintypes.RECT),
                      ('opacity',ctypes.c_ubyte),('fVisible',wintypes.BOOL),('fSourceClientAreaOnly',wintypes.BOOL)]
        try:
            w=max(2,self.overlay.winfo_width());h=max(2,self.overlay.winfo_height());sw,sh=self._client_size()
            p=Props();p.dwFlags=0x1|0x2|0x4|0x8|0x10
            p.rcDestination=wintypes.RECT(0,0,w,h);p.rcSource=wintypes.RECT(0,0,sw,sh)
            p.opacity=255;p.fVisible=True;p.fSourceClientAreaOnly=True
            return int(ctypes.windll.dwmapi.DwmUpdateThumbnailProperties(self.thumbnail,ctypes.byref(p)))==0
        except Exception:return False

    def _schedule_sync(self):
        try:
            if self._sync_after:self.root.after_cancel(self._sync_after)
        except Exception:pass
        def tick():
            if not self.overlay:return
            self._prepare_source_window();self._position_overlay();self._update_thumbnail()
            try:self._sync_after=self.root.after(250,tick)
            except Exception:self._sync_after=None
        try:self._sync_after=self.root.after(250,tick)
        except Exception:self._sync_after=None

    def _map_xy(self,event):
        try:
            dw=max(1,self.overlay.winfo_width());dh=max(1,self.overlay.winfo_height());sw,sh=self._client_size()
            return max(0,min(sw-1,int(event.x*sw/dw))),max(0,min(sh-1,int(event.y*sh/dh)))
        except Exception:return 0,0

    def _mouse_down(self,event):
        x,y=self._map_xy(event);self._post_click(x,y)
    def _mouse_up(self,event):return None
    def _mouse_move(self,event):
        if not self.source_hwnd:return
        try:
            import ctypes
            x,y=self._map_xy(event);ctypes.windll.user32.PostMessageW(self.source_hwnd,0x0200,0,self._lp(x,y))
        except Exception:pass
    def _mouse_drag(self,event):
        if not self.source_hwnd:return
        try:
            import ctypes
            x,y=self._map_xy(event);ctypes.windll.user32.PostMessageW(self.source_hwnd,0x0200,1,self._lp(x,y))
        except Exception:pass
    def _mouse_wheel(self,event):
        if not self.source_hwnd:return
        try:
            import ctypes
            delta=int(getattr(event,'delta',0));x,y=self._map_xy(event)
            wp=(delta&0xffff)<<16;ctypes.windll.user32.PostMessageW(self.source_hwnd,0x020A,wp,self._lp(x,y))
        except Exception:pass
    def _key_down(self,event):
        try:self._post_key(int(event.keycode))
        except Exception:pass

    def detach(self,keep_host=False):
        try:
            if self._sync_after:self.root.after_cancel(self._sync_after)
        except Exception:pass
        self._sync_after=None
        if self.thumbnail:
            try:
                import ctypes
                ctypes.windll.dwmapi.DwmUnregisterThumbnail(self.thumbnail)
            except Exception:pass
        self.thumbnail=0
        if self.overlay:
            try:self.overlay.destroy()
            except Exception:pass
        self.overlay=None
        if not keep_host:self.host=None

    def _terminate_process(self):
        p=self.process
        self.process=None;self.source_hwnd=0
        if p and p.poll() is None:
            try:p.terminate();p.wait(timeout=3)
            except Exception:
                try:p.kill()
                except Exception:pass

    def stop(self):
        self._stop.set();self.detach();self._terminate_process()

    def status(self):
        return {'running':bool(self.process and self.process.poll() is None),'hwnd':int(self.source_hwnd or 0),
                'attached':bool(self.thumbnail),'client_port':self.CLIENT_PORT}
