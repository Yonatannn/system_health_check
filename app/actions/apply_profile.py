from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from app.core.models import Profile
from app.actions.file_copy import copy_file, expand_path
from app.actions.backup import create_backup


@dataclass
class ApplyItem:
    display_name: str
    src: Path
    dst: Path
    backup: bool = True


@dataclass
class ApplyResult:
    success: bool
    applied: list[str]
    errors: list[str]
    backup_dir: Optional[Path] = None


def _build_apply_items(profile: Profile, bundle_dir: Path) -> list[ApplyItem]:
    items = []

    if profile.mission_planner:
        mp = profile.mission_planner
        base = expand_path(mp.base_path)
        for spec in mp.files:
            if not spec.apply_enabled:
                continue
            src = bundle_dir / spec.expected_file
            dst = base / spec.target_path
            items.append(ApplyItem(
                display_name=spec.display_name,
                src=src,
                dst=dst,
                backup=spec.backup_before_replace,
            ))

    for spec in profile.external_files:
        if not spec.apply_enabled:
            continue
        src = bundle_dir / spec.expected_file
        dst = expand_path(spec.target_path)
        items.append(ApplyItem(
            display_name=spec.display_name,
            src=src,
            dst=dst,
            backup=spec.backup_before_replace,
        ))

    return items


def preview_apply(profile: Profile, bundle_dir: Path) -> list[ApplyItem]:
    """Return what would be applied without touching any files."""
    return [item for item in _build_apply_items(profile, bundle_dir) if item.src.exists()]


def apply_profile(profile: Profile, bundle_dir: Path, backup_root: Path) -> ApplyResult:
    """Apply all files defined in the profile from bundle to their target locations."""
    items = _build_apply_items(profile, bundle_dir)
    to_backup = [item.dst for item in items if item.backup]

    backup_dir = None
    if to_backup:
        backup_dir = create_backup(to_backup, backup_root)

    applied = []
    errors = []

    for item in items:
        if not item.src.exists():
            errors.append(f"{item.display_name}: source not found in bundle ({item.src})")
            continue
        try:
            copy_file(item.src, item.dst)
            applied.append(f"{item.display_name}: {item.dst}")
        except Exception as e:
            errors.append(f"{item.display_name}: {e}")

    return ApplyResult(
        success=len(errors) == 0,
        applied=applied,
        errors=errors,
        backup_dir=backup_dir,
    )
