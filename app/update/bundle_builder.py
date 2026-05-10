from __future__ import annotations
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import yaml

from app.update.checksum_manifest import write_checksum_manifest
from app.core.bundle import validate_bundle


class BundleBuildError(Exception):
    pass


def _copy_tree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(str(dst))
    shutil.copytree(str(src), str(dst))


def build_bundle(
    sources_gitlab_dir: Path,
    sources_smb_dir: Path,
    existing_bundle_dir: Path,
    output_bundle_dir: Path,
    gitlab_commits: dict[str, Optional[str]],
    settings_sources: dict,
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Build a normalized config bundle from synced sources.
    Works atomically: writes to a temp dir, validates, then replaces output_bundle_dir.
    """
    log = log or (lambda msg: None)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "bundle"
        tmp_path.mkdir()

        log("Copying profiles from existing bundle…")
        existing_profiles = existing_bundle_dir / "profiles"
        if existing_profiles.exists():
            _copy_tree(existing_profiles, tmp_path / "profiles")
        else:
            (tmp_path / "profiles").mkdir()

        # Copy mission_planner configs from GitLab source if available
        for repo in settings_sources.get("gitlab", {}).get("repositories", []):
            name = repo.get("name", "")
            local_path = Path(repo.get("local_path", str(sources_gitlab_dir / name)))
            if local_path.exists():
                log(f"Integrating GitLab source: {name}…")
                # Copy any known sub-directories into the bundle
                for sub in ["mission_planner", "external_configs", "profiles"]:
                    src_sub = local_path / sub
                    if src_sub.exists():
                        dst_sub = tmp_path / sub
                        if dst_sub.exists():
                            shutil.rmtree(str(dst_sub))
                        shutil.copytree(str(src_sub), str(dst_sub))

        # Copy SMB sources
        for share in settings_sources.get("smb", {}).get("shares", []):
            name = share.get("name", "")
            local_path = Path(share.get("local_path", str(sources_smb_dir / name)))
            if local_path.exists():
                log(f"Integrating SMB source: {name}…")
                for item in local_path.iterdir():
                    dst_item = tmp_path / item.name
                    if item.is_dir():
                        if dst_item.exists():
                            shutil.rmtree(str(dst_item))
                        shutil.copytree(str(item), str(dst_item))
                    else:
                        shutil.copy2(str(item), str(dst_item))

        # Generate bundle manifest
        log("Generating bundle manifest…")
        _write_manifest(tmp_path, settings_sources, gitlab_commits)

        # Generate checksum manifest
        log("Generating checksum manifest…")
        write_checksum_manifest(tmp_path)

        # Validate before replacing active bundle
        log("Validating bundle…")
        ok, err = validate_bundle(tmp_path)
        if not ok:
            raise BundleBuildError(f"Bundle validation failed: {err}")

        # Atomic replace: rename existing to .old, move new in
        log("Replacing active bundle…")
        old_bundle = output_bundle_dir.parent / (output_bundle_dir.name + ".old")
        if old_bundle.exists():
            shutil.rmtree(str(old_bundle))
        if output_bundle_dir.exists():
            output_bundle_dir.rename(old_bundle)
        shutil.copytree(str(tmp_path), str(output_bundle_dir))
        if old_bundle.exists():
            shutil.rmtree(str(old_bundle))

        log("Bundle built successfully.")
        return output_bundle_dir


def _write_manifest(bundle_dir: Path, settings_sources: dict, gitlab_commits: dict):
    version = datetime.now().strftime("%Y.%m.%d-%H%M")
    gitlab_sources = []
    for repo in settings_sources.get("gitlab", {}).get("repositories", []):
        gitlab_sources.append({
            "name": repo.get("name"),
            "url": repo.get("url"),
            "branch": repo.get("branch", "main"),
            "commit": gitlab_commits.get(repo.get("name"), "UNKNOWN"),
        })
    smb_sources = []
    for share in settings_sources.get("smb", {}).get("shares", []):
        smb_sources.append({
            "name": share.get("name"),
            "source_path": share.get("source_path"),
        })

    profiles = []
    profiles_dir = bundle_dir / "profiles"
    if profiles_dir.exists():
        for f in sorted(profiles_dir.glob("*.yaml")):
            try:
                with open(f) as fh:
                    d = yaml.safe_load(fh) or {}
                pid = d.get("profile", {}).get("id", f.stem)
                pname = d.get("profile", {}).get("display_name", pid)
                profiles.append({"id": pid, "display_name": pname, "file": f"profiles/{f.name}"})
            except Exception:
                pass

    manifest = {
        "bundle": {
            "name": "Ground Station Config Bundle",
            "version": version,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": "1.0",
        },
        "sources": {
            "gitlab": gitlab_sources,
            "smb": smb_sources,
        },
        "profiles": profiles,
    }
    with open(bundle_dir / "bundle_manifest.yaml", "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
