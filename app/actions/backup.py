from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


def create_backup(files: list[Path], backup_root: Path) -> Optional[Path]:
    """
    Back up the given files under backup_root/<timestamp>/.
    Returns the backup directory path, or None if no files existed to back up.
    """
    existing = [f for f in files if f.exists()]
    if not existing:
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    backup_dir = backup_root / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    for src in existing:
        dst = backup_dir / src.name
        shutil.copy2(str(src), str(dst))

    return backup_dir
