from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

IS_WINDOWS = sys.platform == "win32"


@dataclass
class PSResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    exception: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.exception is None


def run_ps(command: str, timeout: int = 30) -> PSResult:
    if not IS_WINDOWS:
        return PSResult(stdout="", stderr="Not running on Windows", exit_code=1)

    try:
        proc = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return PSResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return PSResult(stdout="", stderr="Command timed out", exit_code=-1, timed_out=True)
    except Exception as e:
        return PSResult(stdout="", stderr=str(e), exit_code=-1, exception=str(e))


def ping_host(host: str, timeout_seconds: int = 5) -> bool:
    """Returns True if host is reachable."""
    if IS_WINDOWS:
        result = run_ps(f"Test-Connection -ComputerName {host} -Count 1 -Quiet -ErrorAction SilentlyContinue",
                        timeout=timeout_seconds + 5)
        return result.success and "True" in result.stdout
    else:
        import subprocess as sp
        try:
            r = sp.run(["ping", "-c", "1", "-W", str(timeout_seconds), host],
                       capture_output=True, timeout=timeout_seconds + 2)
            return r.returncode == 0
        except Exception:
            return False
