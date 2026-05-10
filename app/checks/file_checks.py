from __future__ import annotations
import hashlib
import os
from pathlib import Path

from app.core.models import FileCheckSpec, CheckResult
from app.core.result import make_pass, make_fail, make_skipped, make_warning
from app.checks.xml_validation import is_valid_xml


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_file_spec(
    spec: FileCheckSpec,
    bundle_dir: Path,
    category: str,
    base_path: str = "",
) -> list[CheckResult]:
    """Check a single file spec: baseline present, target exists, XML valid, SHA256 match."""
    results = []
    target = (
        Path(os.path.expandvars(base_path)) / spec.target_path
        if base_path
        else Path(os.path.expandvars(spec.target_path))
    )
    expected = bundle_dir / spec.expected_file

    if not expected.exists():
        if spec.required:
            results.append(make_fail(
                id=f"{spec.id}_baseline",
                category=category,
                title=f"{spec.display_name} — Baseline Missing",
                details="Expected baseline not found in bundle.",
            ))
        else:
            results.append(make_skipped(
                id=f"{spec.id}_baseline",
                category=category,
                title=f"{spec.display_name} — Baseline Not Configured",
            ))
        return results

    if not target.exists():
        results.append(make_fail(
            id=f"{spec.id}_exists",
            category=category,
            title=f"{spec.display_name} — Not Found",
            expected=str(target),
            actual="not found",
            blocking=spec.required,
        ))
        return results

    results.append(make_pass(
        id=f"{spec.id}_exists",
        category=category,
        title=f"{spec.display_name} — Exists",
        actual=str(target),
    ))

    if spec.check_valid_xml:
        ok, err = is_valid_xml(target)
        if ok:
            results.append(make_pass(
                id=f"{spec.id}_xml", category=category,
                title=f"{spec.display_name} — XML Valid",
            ))
        else:
            results.append(make_fail(
                id=f"{spec.id}_xml", category=category,
                title=f"{spec.display_name} — XML Invalid",
                details=err, blocking=spec.required,
            ))
        ok_exp, err_exp = is_valid_xml(expected)
        if not ok_exp:
            results.append(make_warning(
                id=f"{spec.id}_baseline_xml", category=category,
                title=f"{spec.display_name} — Baseline XML Invalid",
                details=f"Baseline in bundle is not valid XML: {err_exp}",
            ))

    if spec.check_sha256:
        actual_hash = sha256_file(target)
        expected_hash = sha256_file(expected)
        if actual_hash == expected_hash:
            results.append(make_pass(
                id=f"{spec.id}_sha256", category=category,
                title=f"{spec.display_name} — SHA256 Match",
            ))
        else:
            results.append(make_fail(
                id=f"{spec.id}_sha256", category=category,
                title=f"{spec.display_name} — SHA256 Mismatch",
                expected=expected_hash[:16] + "…",
                actual=actual_hash[:16] + "…",
                blocking=spec.required,
            ))

    return results
