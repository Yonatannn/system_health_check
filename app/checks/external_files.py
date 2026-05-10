from __future__ import annotations
import hashlib
import os
from pathlib import Path

from app.core.models import FileCheckSpec, CheckResult, Profile
from app.core.result import make_pass, make_fail, make_skipped

CATEGORY = "External Config Files"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_external_file(spec: FileCheckSpec, bundle_dir: Path) -> list[CheckResult]:
    results = []
    target = Path(os.path.expandvars(spec.target_path))
    expected = bundle_dir / spec.expected_file

    if not expected.exists():
        if spec.required:
            results.append(make_fail(
                id=f"{spec.id}_baseline",
                category=CATEGORY,
                title=f"{spec.display_name} — Baseline Missing",
                details="Expected baseline not found in bundle.",
                blocking=spec.required,
            ))
        else:
            results.append(make_skipped(
                id=f"{spec.id}_baseline",
                category=CATEGORY,
                title=f"{spec.display_name} — Baseline Not Configured",
            ))
        return results

    if not target.exists():
        results.append(make_fail(
            id=f"{spec.id}_exists",
            category=CATEGORY,
            title=f"{spec.display_name} — Not Found",
            expected=str(target),
            actual="not found",
            blocking=spec.required,
        ))
        return results

    results.append(make_pass(
        id=f"{spec.id}_exists",
        category=CATEGORY,
        title=f"{spec.display_name} — Exists",
        actual=str(target),
    ))

    if spec.check_sha256:
        actual_hash = _sha256(target)
        expected_hash = _sha256(expected)
        if actual_hash == expected_hash:
            results.append(make_pass(
                id=f"{spec.id}_sha256",
                category=CATEGORY,
                title=f"{spec.display_name} — SHA256 Match",
            ))
        else:
            results.append(make_fail(
                id=f"{spec.id}_sha256",
                category=CATEGORY,
                title=f"{spec.display_name} — SHA256 Mismatch",
                expected=_sha256(expected)[:16] + "…",
                actual=actual_hash[:16] + "…",
                blocking=spec.required,
            ))

    return results


def run_external_file_checks(profile: Profile, bundle_dir: Path) -> list[CheckResult]:
    results = []
    for spec in profile.external_files:
        results.extend(check_external_file(spec, bundle_dir))
    return results
