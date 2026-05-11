from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml

from app.core.models import BundleManifest, BundleSource


def load_bundle_manifest(bundle_dir: Path) -> Optional[BundleManifest]:
    manifest_path = bundle_dir / "bundle_manifest.yaml"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        bundle_meta = data.get("bundle", {})
        sources = data.get("sources", {})
        profiles_raw = data.get("profiles", [])

        gitlab_sources = [
            BundleSource(
                name=s.get("name", ""),
                url=s.get("url"),
                branch=s.get("branch"),
                commit=s.get("commit"),
            )
            for s in sources.get("gitlab", [])
        ]

        return BundleManifest(
            name=bundle_meta.get("name", "Unknown"),
            version=bundle_meta.get("version", "UNKNOWN"),
            created_at=bundle_meta.get("created_at", ""),
            schema_version=bundle_meta.get("schema_version", "1.0"),
            gitlab_sources=gitlab_sources,
            profile_ids=[p.get("id", "") for p in profiles_raw],
            is_valid=True,
        )
    except Exception as e:
        return BundleManifest(
            name="Invalid Bundle",
            version="ERROR",
            created_at="",
            schema_version="",
            is_valid=False,
            validation_error=str(e),
        )


def validate_bundle(bundle_dir: Path) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    manifest_path = bundle_dir / "bundle_manifest.yaml"
    if not manifest_path.exists():
        return False, "bundle_manifest.yaml not found"

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            yaml.safe_load(f)
    except Exception as e:
        return False, f"bundle_manifest.yaml is not valid YAML: {e}"

    profiles_dir = bundle_dir / "profiles"
    if not profiles_dir.exists():
        return False, "profiles/ directory not found in bundle"

    profile_files = list(profiles_dir.glob("*.yaml"))
    if not profile_files:
        return False, "No profile files found in bundle"

    for pf in profile_files:
        try:
            with open(pf, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as e:
            return False, f"Profile {pf.name} is not valid YAML: {e}"

    checksums_path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    if checksums_path.exists():
        try:
            with open(checksums_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as e:
            return False, f"sha256_manifest.yaml is not valid YAML: {e}"

    return True, ""
