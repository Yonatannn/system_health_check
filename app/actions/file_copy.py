from __future__ import annotations
import shutil
import os
from pathlib import Path


def copy_file(src: Path, dst: Path):
    """Copy src to dst, creating parent directories as needed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))


def expand_path(path_str: str) -> Path:
    return Path(os.path.expandvars(path_str))
