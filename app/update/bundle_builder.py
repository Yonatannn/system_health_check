from __future__ import annotations
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import yaml

from app.core.models import Profile
from app.update.checksum_manifest import sha256_file, write_checksum_manifest
from app.core.bundle import validate_bundle


class BundleBuildError(Exception):
    pass


def _compute_source_checksums(
    sources_gitlab_dir: Path,
    profiles: list[Profile],
    log: Callable[[str], None],
) -> dict[str, str]:
    checksums: dict[str, str] = {}

    log(f"Source root: {sources_gitlab_dir.resolve()}")

    for profile in profiles:
        if not profile.source_repo:
            log(f"[{profile.display_name}] No source_repo defined — skipping")
            continue

        repo_dir = sources_gitlab_dir / profile.source_repo.name
        log(f"[{profile.display_name}] Repo dir: {repo_dir.resolve()}")

        if not repo_dir.exists():
            log(f"[{profile.display_name}] ERROR: repo directory not found — was sync successful?")
            continue

        # Collect every expected_file referenced by this profile
        expected_files: list[str] = []
        if profile.mission_planner:
            for f in profile.mission_planner.files:
                expected_files.append(f.expected_file)
        for f in profile.external_files:
            expected_files.append(f.expected_file)

        log(f"[{profile.display_name}] {len(expected_files)} expected file(s) to hash")

        for rel in expected_files:
            full_path = repo_dir / rel
            key = f"{profile.source_repo.name}/{rel}"
            if full_path.exists():
                checksums[key] = sha256_file(full_path)
                log(f"  OK   {key}")
            else:
                log(f"  MISS {key}  (not found at {full_path})")

    log(f"Total checksums computed: {len(checksums)}")
    return checksums


def build_bundle(
    sources_gitlab_dir: Path,
    profiles: list[Profile],
    repos: list[dict],
    output_bundle_dir: Path,
    gitlab_commits: dict[str, Optional[str]],
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    log = log or (lambda msg: None)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "bundle"
        tmp_path.mkdir()

        log("--- Computing checksums ---")
        checksums = _compute_source_checksums(sources_gitlab_dir, profiles, log)

        if not checksums:
            log("WARNING: no files were hashed — check that expected_file paths match the repo structure")

        log("--- Writing bundle manifest ---")
        _write_manifest(tmp_path, repos, gitlab_commits)

        log("--- Writing checksum manifest ---")
        write_checksum_manifest(tmp_path, checksums)

        log("--- Validating bundle ---")
        ok, err = validate_bundle(tmp_path)
        if not ok:
            raise BundleBuildError(f"Bundle validation failed: {err}")

        log("--- Replacing active bundle ---")
        log(f"Output: {output_bundle_dir.resolve()}")
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


def _write_manifest(bundle_dir: Path, repos: list[dict], gitlab_commits: dict):
    version = datetime.now().strftime("%Y.%m.%d-%H%M")
    gitlab_sources = [
        {
            "name": r.get("name"),
            "url": r.get("url"),
            "branch": r.get("branch", "main"),
            "commit": gitlab_commits.get(r.get("name"), "UNKNOWN"),
        }
        for r in repos
    ]
    manifest = {
        "bundle": {
            "name": "Ground Station Config Bundle",
            "version": version,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": "1.0",
        },
        "sources": {"gitlab": gitlab_sources},
    }
    with open(bundle_dir / "bundle_manifest.yaml", "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
