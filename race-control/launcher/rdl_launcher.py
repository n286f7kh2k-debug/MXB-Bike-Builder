from __future__ import annotations

import os
import runpy
import site
import sys
import traceback
from pathlib import Path

# Import Tk here so PyInstaller includes Tcl/Tk in the branded host runtime.
import tkinter  # noqa: F401


def _add_runtime_packages(root: Path) -> None:
    """Expose the existing app venv packages to the branded host process."""
    candidates = [root / '.venv' / 'Lib' / 'site-packages']
    hint = root / 'assets' / 'bin' / 'rdl_runtime.txt'
    try:
        if hint.is_file():
            raw = hint.read_text(encoding='utf-8').strip().strip('"')
            if raw:
                runtime = Path(raw)
                if not runtime.is_absolute():
                    runtime = (root / runtime).resolve()
                # Typical runtime is .../.venv/Scripts/pythonw.exe.
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


def main() -> int:
    # In a PyInstaller one-file build sys.executable is the installed branded EXE.
    root = Path(sys.executable).resolve().parent
    app = root / 'app.py'
    if not app.is_file():
        _show_fatal(f'Race Day Live could not find its app runtime:\n{app}')
        return 2

    try:
        os.chdir(root)
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        _add_runtime_packages(root)

        # Keep the installed source tree external/updatable, but execute it inside
        # this branded process. Windows therefore sees MXB Race Day Live.exe as
        # the actual owner of the Tk application window instead of pythonw.exe.
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
        _show_fatal('MXB Race Day Live could not start.\n\n' + detail[-6000:])
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
