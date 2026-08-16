from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _runtime_path(root: Path) -> Path | None:
    hint = root / 'assets' / 'bin' / 'rdl_runtime.txt'
    try:
        if hint.is_file():
            raw = hint.read_text(encoding='utf-8').strip().strip('"')
            if raw:
                candidate = Path(raw)
                if not candidate.is_absolute():
                    candidate = (root / candidate).resolve()
                if candidate.is_file():
                    return candidate
    except Exception:
        pass

    for candidate in (
        root / '.venv' / 'Scripts' / 'pythonw.exe',
        root / 'pythonw.exe',
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    root = Path(sys.executable).resolve().parent
    app = root / 'app.py'
    runtime = _runtime_path(root)
    if runtime is None or not app.is_file():
        return 2

    try:
        env = dict(__import__('os').environ)
        # Never pass PyInstaller one-file parent/child state into the external runtime.
        # This prevents the v0.5.13 parent-process security validation failure.
        for key in tuple(env):
            if key.startswith('_PYI_') or key.startswith('PYINSTALLER_'):
                env.pop(key, None)
        subprocess.Popen(
            [str(runtime), str(app), *sys.argv[1:]],
            cwd=str(root),
            env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            close_fds=True,
        )
        # Exit immediately so updater can replace this launcher on future updates.
        return 0
    except Exception:
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
