from __future__ import annotations

from app.core.models import CheckResult, Profile
from app.checks.file_checks import check_file_spec

CATEGORY = "Mission Planner Files"


def run_mission_planner_checks(profile: Profile, sha256_manifest: dict[str, str]) -> list[CheckResult]:
    if not profile.mission_planner:
        return []
    mp = profile.mission_planner
    return [
        result
        for spec in mp.files
        for result in check_file_spec(spec, sha256_manifest, CATEGORY, base_path=mp.base_path)
    ]
