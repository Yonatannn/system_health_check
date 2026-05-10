from __future__ import annotations
from pathlib import Path

from app.core.models import CheckResult, Profile
from app.checks.file_checks import check_file_spec

CATEGORY = "Mission Planner Files"


def run_mission_planner_checks(profile: Profile, bundle_dir: Path) -> list[CheckResult]:
    if not profile.mission_planner:
        return []
    mp = profile.mission_planner
    return [
        result
        for spec in mp.files
        for result in check_file_spec(spec, bundle_dir, CATEGORY, base_path=mp.base_path)
    ]
