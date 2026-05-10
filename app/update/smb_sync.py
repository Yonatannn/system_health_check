from __future__ import annotations
import subprocess
import shutil
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable

IS_WINDOWS = sys.platform == "win32"


@dataclass
class SMBSyncResult:
    name: str
    success: bool
    files_copied: int = 0
    error: Optional[str] = None


def _robocopy(src_unc: str, dst: Path, log: Callable[[str], None]) -> tuple[bool, str]:
    dst.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["robocopy", src_unc, str(dst), "/MIR", "/NP", "/NFL", "/NDL"],
            capture_output=True, text=True, timeout=120,
        )
        # Robocopy exit codes: 0-7 are success/info; 8+ are errors
        if proc.returncode < 8:
            return True, ""
        return False, proc.stderr.strip() or proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "robocopy timed out"
    except Exception as e:
        return False, str(e)


def _python_copy(src_unc: str, dst: Path, log: Callable[[str], None]) -> tuple[bool, int, str]:
    src = Path(src_unc)
    if not src.exists():
        return False, 0, f"SMB path not accessible: {src_unc}"
    copied = 0
    try:
        for src_file in src.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(src)
                dst_file = dst / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_file), str(dst_file))
                copied += 1
        return True, copied, ""
    except Exception as e:
        return False, copied, str(e)


def sync_smb_share(name: str, source_path: str, local_path: Path,
                   log: Optional[Callable[[str], None]] = None) -> SMBSyncResult:
    log = log or (lambda msg: None)
    log(f"[{name}] Syncing from {source_path}…")

    if IS_WINDOWS:
        ok, err = _robocopy(source_path, local_path, log)
        if not ok:
            return SMBSyncResult(name=name, success=False, error=f"robocopy failed: {err}")
        return SMBSyncResult(name=name, success=True)
    else:
        ok, count, err = _python_copy(source_path, local_path, log)
        if not ok:
            return SMBSyncResult(name=name, success=False, error=err)
        return SMBSyncResult(name=name, success=True, files_copied=count)


def sync_all_shares(shares: list[dict], sources_dir: Path,
                    log: Optional[Callable[[str], None]] = None) -> list[SMBSyncResult]:
    results = []
    for share in shares:
        name = share.get("name", "unknown")
        source_path = share.get("source_path", "")
        local_path = Path(share.get("local_path", str(sources_dir / "smb" / name)))
        result = sync_smb_share(name=name, source_path=source_path,
                                local_path=local_path, log=log)
        results.append(result)
    return results
