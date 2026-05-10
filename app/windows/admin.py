from __future__ import annotations
import sys
import os

IS_WINDOWS = sys.platform == "win32"


def is_admin() -> bool:
    if not IS_WINDOWS:
        return os.geteuid() == 0
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def restart_as_admin():
    """Re-launch the current process with elevated privileges (Windows only)."""
    if not IS_WINDOWS:
        return
    import ctypes
    import subprocess
    executable = sys.executable
    params = " ".join([f'"{a}"' for a in sys.argv])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    sys.exit(0)
