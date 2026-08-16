from __future__ import annotations

import ctypes
import os
import re
import subprocess
import threading
import time
from pathlib import Path


class NativeRendererError(RuntimeError):
    pass


class MXBNativeRenderer:
    """Hosts the real MX Bikes renderer inside a Race Day Live Tk frame on Windows.

    MX Bikes itself remains the renderer. Race Day Live creates a testing-mode config
    from the current garage selection, launches mxbikes.exe, finds that process' top-level
    window and reparents it into the Tk host window using Win32 SetParent.
    """

    CONFIG_NAME = 'race_day_live_preview.ini'
    GFX_BACKUP_NAME = 'mxbikes.race_day_live_preview_backup.ini'

    def __init__(self, game_bridge):
        self.game_bridge = game_bridge
        self.process = None
        self.game_hwnd = 0
        self.host_hwnd = 0
        self._attach_thread = None
        self._stop = threading.Event()
        self._original_gfx_bytes = None
        self._gfx_path = None
        self._config_path = None
        self._lock = threading.RLock()

    @property
    def supported(self):
        return os.name == 'nt'

    @property
    def running(self):
        p = self.process
        return bool(p and p.poll() is None)

    def _exe(self):
        exe = self.game_bridge.game_exe()
        if not exe:
            raise NativeRendererError('MX Bikes was not found. Run game sync first.')
        return Path(exe)

    @staticmethod
    def _ini_set(text, section, key, value):
        lines = text.splitlines()
        section_lower = section.lower()
        start = None
        end = len(lines)
        for i, raw in enumerate(lines):
            s = raw.strip()
            if s.startswith('[') and s.endswith(']'):
                if start is not None:
                    end = i
                    break
                if s[1:-1].strip().lower() == section_lower:
                    start = i
        if start is None:
            if lines and lines[-1].strip():
                lines.append('')
            lines.extend([f'[{section}]', f'{key}={value}'])
            return '\n'.join(lines) + '\n'
        key_lower = key.lower()
        for i in range(start + 1, end):
            if '=' in lines[i] and lines[i].split('=', 1)[0].strip().lower() == key_lower:
                lines[i] = f'{key}={value}'
                return '\n'.join(lines) + '\n'
        lines.insert(end, f'{key}={value}')
        return '\n'.join(lines) + '\n'

    def _recover_stale_gfx_backup(self, install_root):
        gfx = install_root / 'mxbikes.ini'
        bak = install_root / self.GFX_BACKUP_NAME
        if bak.is_file():
            try:
                os.replace(bak, gfx)
            except Exception:
                try:
                    gfx.write_bytes(bak.read_bytes())
                    bak.unlink(missing_ok=True)
                except Exception:
                    pass

    def _prepare_windowed_gfx(self, install_root, width, height):
        self._recover_stale_gfx_backup(install_root)
        gfx = install_root / 'mxbikes.ini'
        bak = install_root / self.GFX_BACKUP_NAME
        original = gfx.read_bytes() if gfx.is_file() else b''
        self._original_gfx_bytes = original
        self._gfx_path = gfx
        try:
            bak.write_bytes(original)
        except Exception as exc:
            raise NativeRendererError(f'Could not back up MX Bikes graphics settings: {exc}')
        text = original.decode('utf-8', errors='ignore') if original else ''
        text = self._ini_set(text, 'GFX_DEFAULT', 'fullscreen', '0')
        text = self._ini_set(text, 'GFX_DEFAULT', 'x', str(max(640, int(width))))
        text = self._ini_set(text, 'GFX_DEFAULT', 'y', str(max(480, int(height))))
        gfx.write_text(text, encoding='utf-8')

    def _restore_gfx(self):
        gfx, original = self._gfx_path, self._original_gfx_bytes
        if gfx is None or original is None:
            return
        try:
            gfx.write_bytes(original)
            gfx.with_name(self.GFX_BACKUP_NAME).unlink(missing_ok=True)
        except Exception:
            pass
        self._gfx_path = None
        self._original_gfx_bytes = None

    @staticmethod
    def _clean(value):
        return str(value or '').replace('\r', ' ').replace('\n', ' ').strip()

    def _write_testing_config(self, install_root, selection):
        mapping = {
            'bike_id': selection.get('bikeid', ''),
            'paint': selection.get('paint', ''),
            'bike_font': selection.get('bike_font', ''),
            'rider': selection.get('rider', 'default_mx'),
            'helmet': selection.get('helmet', 'default'),
            'helmet_paint': selection.get('helmet_paint', ''),
            'goggles_paint': selection.get('goggles_paint', ''),
            'helmet_cam': selection.get('helmet_cam', ''),
            'suit_paint': selection.get('suit_paint', ''),
            'suit_font': selection.get('suit_font', ''),
            'boots': selection.get('boots', 'default'),
            'boots_paint': selection.get('boots_paint', ''),
            'gloves_paint': selection.get('gloves_paint', ''),
            'protection': selection.get('protection', ''),
            'protection_paint': selection.get('protection_paint', ''),
        }
        if not self._clean(mapping['bike_id']):
            raise NativeRendererError('Choose a bike before starting Live 3D.')
        lines = ['[bike]']
        lines.extend(f'{k} = {self._clean(v)}' for k, v in mapping.items())
        lines += [
            '[track]',
            'track_id = Practice',
            'track_layout =',
            '[settings]',
            'weather_realistic = 0',
            'weather_conditions = 0',
            'temperature = 25',
            'wind_direction = 0',
            'wind_speed = 0',
            'track_conditions = 0',
        ]
        path = install_root / self.CONFIG_NAME
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self._config_path = path
        return path

    @staticmethod
    def _enum_process_windows(pid):
        if os.name != 'nt':
            return []
        user32 = ctypes.windll.user32
        windows = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        @WNDENUMPROC
        def callback(hwnd, lparam):
            proc_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == pid and user32.IsWindowVisible(hwnd):
                windows.append(int(hwnd))
            return True

        user32.EnumWindows(callback, 0)
        return windows

    def _find_window(self, timeout=35.0):
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop.is_set():
            p = self.process
            if not p or p.poll() is not None:
                return 0
            wins = self._enum_process_windows(p.pid)
            if wins:
                return wins[0]
            time.sleep(0.20)
        return 0

    def _embed(self, hwnd, host_hwnd, width, height):
        user32 = ctypes.windll.user32
        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        WS_VISIBLE = 0x10000000
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        style |= WS_CHILD | WS_VISIBLE
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        if not user32.SetParent(hwnd, host_hwnd):
            # SetParent can return NULL when previous parent was desktop; check last error only when nonzero.
            err = ctypes.get_last_error()
            if err:
                raise NativeRendererError(f'Windows could not embed the MX Bikes renderer (error {err}).')
        user32.MoveWindow(hwnd, 0, 0, max(320, int(width)), max(240, int(height)), True)
        user32.ShowWindow(hwnd, 5)

    def start(self, host_hwnd, width, height, selection, on_ready=None, on_error=None):
        if not self.supported:
            raise NativeRendererError('Live MX Bikes embedding is available on Windows only.')
        self.stop()
        with self._lock:
            self._stop.clear()
            exe = self._exe()
            install_root = exe.parent
            self._prepare_windowed_gfx(install_root, width, height)
            cfg = self._write_testing_config(install_root, selection)
            cmd = [str(exe), '-testing', '-set', 'params', cfg.name]
            try:
                self.process = subprocess.Popen(cmd, cwd=str(install_root))
            except Exception:
                self._restore_gfx()
                raise
            self.host_hwnd = int(host_hwnd)

        def attach_worker():
            try:
                hwnd = self._find_window()
                if not hwnd:
                    raise NativeRendererError('MX Bikes started, but its render window could not be attached to Race Day Live.')
                with self._lock:
                    if self._stop.is_set():
                        return
                    self.game_hwnd = hwnd
                    self._embed(hwnd, self.host_hwnd, width, height)
                if on_ready:
                    on_ready(hwnd)
            except Exception as exc:
                if on_error:
                    on_error(exc)
                self.stop()

        self._attach_thread = threading.Thread(target=attach_worker, name='MXB-Native-Renderer', daemon=True)
        self._attach_thread.start()
        return self.process.pid

    def resize(self, width, height):
        hwnd = self.game_hwnd
        if not hwnd or os.name != 'nt':
            return
        try:
            ctypes.windll.user32.MoveWindow(hwnd, 0, 0, max(320, int(width)), max(240, int(height)), True)
        except Exception:
            pass

    def focus(self):
        if self.game_hwnd and os.name == 'nt':
            try:
                ctypes.windll.user32.SetFocus(self.game_hwnd)
            except Exception:
                pass

    def stop(self):
        with self._lock:
            self._stop.set()
            p = self.process
            self.process = None
            self.game_hwnd = 0
            self.host_hwnd = 0
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self._restore_gfx()
        try:
            if self._config_path:
                self._config_path.unlink(missing_ok=True)
        except Exception:
            pass
        self._config_path = None

    def restart(self, host_hwnd, width, height, selection, on_ready=None, on_error=None):
        return self.start(host_hwnd, width, height, selection, on_ready=on_ready, on_error=on_error)
