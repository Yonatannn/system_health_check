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

    checksums_path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    if checksums_path.exists():
        try:
            with open(checksums_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as e:
            return False, f"sha256_manifest.yaml is not valid YAML: {e}"

    return True, ""
