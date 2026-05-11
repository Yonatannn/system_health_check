from __future__ import annotations
import hashlib
import os
from pathlib import Path

from app.core.models import FileCheckSpec, CheckResult
from app.core.result import make_pass, make_fail, make_skipped
from app.checks.xml_validation import is_valid_xml


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_file_spec(
    spec: FileCheckSpec,
    sha256_manifest: dict[str, str],
    category: str,
    base_path: str = "",
) -> list[CheckResult]:
    results = []
    target = (
        Path(os.path.expandvars(base_path)) / spec.target_path
        if base_path
        else Path(os.path.expandvars(spec.target_path))
    )

    expected_hash = sha256_manifest.get(spec.expected_file)

    if expected_hash is None:
        if spec.required:
            results.append(make_fail(
                id=f"{spec.id}_baseline",
                category=category,
                title=f"{spec.display_name} — Not in Bundle",
                details=(
                    f"No approved baseline found for '{spec.display_name}' in the configuration bundle. "
                    "Connect to the configuration server and use the Update Bundle tab to download the latest bundle."
                ),
            ))
        else:
            results.append(make_skipped(
                id=f"{spec.id}_baseline",
                category=category,
                title=f"{spec.display_name} — Not Configured",
            ))
        return results

    if not target.exists():
        results.append(make_fail(
            id=f"{spec.id}_exists",
            category=category,
            title=f"{spec.display_name} — File Missing",
            expected=str(target),
            actual="file not found",
            details=(
                f"Expected file not found at: {target}\n"
                "Click 'Apply Profile' to copy the correct file from the bundle. "
                "If Apply Profile is unavailable, run an Update Bundle sync first."
            ),
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
                title=f"{spec.display_name} — XML Corrupted",
                details=(
                    f"The file at {target} is not valid XML and cannot be read by Mission Planner. "
                    f"Parse error: {err}\n"
                    "Click 'Apply Profile' to restore the correct version from the bundle."
                ),
                blocking=spec.required,
            ))

    if spec.check_sha256:
        actual_hash = sha256_file(target)
        if actual_hash == expected_hash:
            results.append(make_pass(
                id=f"{spec.id}_sha256", category=category,
                title=f"{spec.display_name} — Content Verified",
            ))
        else:
            results.append(make_fail(
                id=f"{spec.id}_sha256", category=category,
                title=f"{spec.display_name} — Wrong Version",
                expected=expected_hash[:16] + "…",
                actual=actual_hash[:16] + "…",
                details=(
                    f"The file at {target} does not match the approved version — "
                    "it may have been changed manually or belong to a different profile. "
                    "Click 'Apply Profile' to overwrite it with the correct version. "
                    "A timestamped backup will be created automatically before overwriting."
                ),
                blocking=spec.required,
            ))

    return results
