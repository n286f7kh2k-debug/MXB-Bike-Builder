from __future__ import annotations

import os
import runpy
import site
import sys
import traceback
from pathlib import Path

# These imports are intentionally explicit.  The app source remains external so
# the GitHub updater can replace it, therefore PyInstaller cannot discover its
# imports by static analysis.  Keeping the complete Tk/Pillow surface in this
# host prevents the v0.5.13 frozen-runtime failure (ttk/messagebox/filedialog).
import tkinter
from tkinter import colorchooser, filedialog, font, messagebox, scrolledtext, simpledialog, ttk

try:
    from PIL import Image as _PIL_Image
    from PIL import ImageDraw as _PIL_ImageDraw
    from PIL import ImageFont as _PIL_ImageFont
    from PIL import ImageOps as _PIL_ImageOps
    from PIL import ImageTk as _PIL_ImageTk
except Exception:
    _PIL_Image = _PIL_ImageDraw = _PIL_ImageFont = _PIL_ImageOps = _PIL_ImageTk = None

APP_ID = 'MXBRaceDayLive.Desktop'
SMOKE_ARG = '--rdl-smoke-test'


def _add_runtime_packages(root: Path) -> None:
    """Expose packages already installed with Race Day Live to this branded host."""
    candidates = [root / '.venv' / 'Lib' / 'site-packages']
    hint = root / 'assets' / 'bin' / 'rdl_runtime.txt'
    try:
        if hint.is_file():
            raw = hint.read_text(encoding='utf-8').strip().strip('"')
            if raw:
                runtime = Path(raw)
                if not runtime.is_absolute():
                    runtime = (root / runtime).resolve()
                candidates.append(runtime.parent.parent / 'Lib' / 'site-packages')
    except Exception:
        pass

    seen = set()
    for folder in candidates:
        try:
            folder = folder.resolve()
            key = str(folder).lower()
            if key in seen or not folder.is_dir():
                continue
            seen.add(key)
            site.addsitedir(str(folder))
        except Exception:
            pass


def _set_windows_identity() -> None:
    if os.name != 'nt':
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _show_fatal(message: str) -> None:
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, 'MXB Race Day Live', 0x10)
            return
        except Exception:
            pass
    try:
        sys.stderr.write(message + '\n')
    except Exception:
        pass


def _smoke_test() -> int:
    """CI gate for the exact imports that broke the previous branded host."""
    try:
        assert tkinter is not None
        assert all(x is not None for x in (ttk, messagebox, filedialog, colorchooser, simpledialog, font, scrolledtext))
        if _PIL_Image is not None:
            assert _PIL_ImageTk is not None and _PIL_ImageDraw is not None
        return 0
    except Exception:
        return 91


def main() -> int:
    if SMOKE_ARG in sys.argv[1:]:
        return _smoke_test()

    root = Path(sys.executable).resolve().parent
    app = root / 'app.py'
    if not app.is_file():
        _show_fatal(f'Race Day Live could not find its app runtime:\n{app}')
        return 2

    try:
        _set_windows_identity()
        os.chdir(root)
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        _add_runtime_packages(root)

        # The branded executable owns the Tk window.  No python/pythonw child is
        # started, so Windows taskbar/jump-list identity comes from this EXE.
        sys.argv = [str(app), *sys.argv[1:]]
        runpy.run_path(str(app), run_name='__main__')
        return 0
    except SystemExit as exc:
        try:
            return int(exc.code or 0)
        except Exception:
            return 0
    except Exception:
        detail = traceback.format_exc()
        _show_fatal('MXB Race Day Live could not start.\n\n' + detail[-7000:])
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
