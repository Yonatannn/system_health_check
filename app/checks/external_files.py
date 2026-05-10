from __future__ import annotations

from app.core.models import CheckResult, Profile
from app.checks.file_checks import check_file_spec

CATEGORY = "External Config Files"


def run_external_file_checks(profile: Profile, sha256_manifest: dict[str, str]) -> list[CheckResult]:
    return [
        result
        for spec in profile.external_files
        for result in check_file_spec(spec, sha256_manifest, CATEGORY)
    ]
