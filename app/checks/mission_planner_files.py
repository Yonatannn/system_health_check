from __future__ import annotations
import hashlib
import os
from pathlib import Path
from typing import Optional

from app.core.models import FileCheckSpec, CheckResult, CheckStatus, Profile
from app.core.result import make_pass, make_fail, make_warning, make_skipped
from app.core.paths import AppPaths
from app.checks.xml_validation import is_valid_xml

CATEGORY = "Mission Planner Files"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_target(base_path: str, target_path: str) -> Path:
    base = Path(os.path.expandvars(base_path))
    return base / target_path


def check_file(spec: FileCheckSpec, bundle_dir: Path, mp_base_path: str) -> list[CheckResult]:
    results = []
    target = _resolve_target(mp_base_path, spec.target_path)
    expected = bundle_dir / spec.expected_file

    # Check expected baseline exists in bundle
    if not expected.exists():
        results.append(make_fail(
            id=f"{spec.id}_baseline",
            category=CATEGORY,
            title=f"{spec.display_name} — Baseline Missing",
            expected=str(expected),
            actual="not found",
            details="Expected baseline file not found in config bundle.",
            blocking=spec.required,
        ))
        return results

    # Check target exists
    if not target.exists():
        results.append(make_fail(
            id=f"{spec.id}_exists",
            category=CATEGORY,
            title=f"{spec.display_name} — Not Found",
            expected=str(target),
            actual="not found",
            details="Target file does not exist.",
            blocking=spec.required,
        ))
        return results

    results.append(make_pass(
        id=f"{spec.id}_exists",
        category=CATEGORY,
        title=f"{spec.display_name} — Exists",
        expected=str(target),
        actual=str(target),
    ))

    # XML validity
    if spec.check_valid_xml:
        ok, err = is_valid_xml(target)
        if ok:
            results.append(make_pass(
                id=f"{spec.id}_xml",
                category=CATEGORY,
                title=f"{spec.display_name} — XML Valid",
            ))
        else:
            results.append(make_fail(
                id=f"{spec.id}_xml",
                category=CATEGORY,
                title=f"{spec.display_name} — XML Invalid",
                details=err,
                blocking=spec.required,
            ))

        ok_exp, err_exp = is_valid_xml(expected)
        if not ok_exp:
            results.append(make_warning(
                id=f"{spec.id}_baseline_xml",
                category=CATEGORY,
                title=f"{spec.display_name} — Baseline XML Invalid",
                details=f"Baseline in bundle is not valid XML: {err_exp}",
            ))

    # SHA256 match
    if spec.check_sha256:
        actual_hash = _sha256(target)
        expected_hash = _sha256(expected)
        if actual_hash == expected_hash:
            results.append(make_pass(
                id=f"{spec.id}_sha256",
                category=CATEGORY,
                title=f"{spec.display_name} — SHA256 Match",
                expected=expected_hash[:16] + "…",
                actual=actual_hash[:16] + "…",
            ))
        else:
            results.append(make_fail(
                id=f"{spec.id}_sha256",
                category=CATEGORY,
                title=f"{spec.display_name} — SHA256 Mismatch",
                expected=expected_hash[:16] + "…",
                actual=actual_hash[:16] + "…",
                details="File content does not match the expected baseline.",
                blocking=spec.required,
            ))

    return results


def run_mission_planner_checks(profile: Profile, bundle_dir: Path) -> list[CheckResult]:
    if not profile.mission_planner:
        return []
    mp = profile.mission_planner
    results = []
    for spec in mp.files:
        results.extend(check_file(spec, bundle_dir, mp.base_path))
    return results
