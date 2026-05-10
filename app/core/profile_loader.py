from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml

from app.core.models import (
    Profile, InterfaceSpec, InterfaceMatchRule, ExpectedIPv4,
    MissionPlannerSpec, FileCheckSpec
)


def _load_interface(d: dict) -> InterfaceSpec:
    match_raw = d.get("match_by", {})
    match_by = InterfaceMatchRule(
        adapter_name=match_raw.get("adapter_name"),
        mac_address=match_raw.get("mac_address"),
        description_contains=match_raw.get("description_contains"),
    )
    ipv4_raw = d.get("expected_ipv4")
    expected_ipv4 = None
    if ipv4_raw:
        expected_ipv4 = ExpectedIPv4(
            address=ipv4_raw["address"],
            prefix_length=int(ipv4_raw["prefix_length"]),
        )
    return InterfaceSpec(
        id=d["id"],
        display_name=d.get("display_name", d["id"]),
        required=d.get("required", True),
        match_by=match_by,
        expected_ipv4=expected_ipv4,
    )


def _load_file_spec(d: dict, file_type: str = "generic") -> FileCheckSpec:
    checks = d.get("checks", {})
    apply_cfg = d.get("apply", {})
    t = d.get("type", file_type)
    return FileCheckSpec(
        id=d["id"],
        display_name=d.get("display_name", d["id"]),
        target_path=d["target_path"],
        expected_file=d["expected_file"],
        required=d.get("required", True),
        file_type=t,
        check_exists=checks.get("exists", True),
        check_valid_xml=checks.get("valid_xml", t == "xml"),
        check_sha256=checks.get("sha256_match", True),
        apply_enabled=apply_cfg.get("enabled", True),
        backup_before_replace=apply_cfg.get("backup_before_replace", True),
    )


def _load_mission_planner(d: dict) -> MissionPlannerSpec:
    files = [_load_file_spec(f, file_type="xml") for f in d.get("files", [])]
    return MissionPlannerSpec(
        base_path=d.get("base_path", "%USERPROFILE%/Documents/Mission Planner"),
        files=files,
    )


def load_profile(profile_path: Path) -> Profile:
    with open(profile_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    prof_meta = data.get("profile", {})
    interfaces_raw = data.get("windows_interfaces", [])
    mp_raw = data.get("mission_planner")
    ext_raw = data.get("external_files", [])

    return Profile(
        id=prof_meta.get("id", profile_path.stem),
        display_name=prof_meta.get("display_name", profile_path.stem),
        description=prof_meta.get("description", ""),
        windows_interfaces=[_load_interface(i) for i in interfaces_raw],
        mission_planner=_load_mission_planner(mp_raw) if mp_raw else None,
        external_files=[_load_file_spec(f) for f in ext_raw],
    )


def load_all_profiles(profiles_dir: Path) -> list[Profile]:
    profiles = []
    if not profiles_dir.exists():
        return profiles
    for yaml_file in sorted(profiles_dir.glob("*.yaml")):
        try:
            profiles.append(load_profile(yaml_file))
        except Exception:
            pass
    return profiles
