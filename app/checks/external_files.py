from __future__ import annotations
from pathlib import Path

from app.core.models import CheckResult, Profile
from app.checks.file_checks import check_file_spec

CATEGORY = "External Config Files"


def run_external_file_checks(profile: Profile, bundle_dir: Path) -> list[CheckResult]:
    return [
        result
        for spec in profile.external_files
        for result in check_file_spec(spec, bundle_dir, CATEGORY)
    ]
