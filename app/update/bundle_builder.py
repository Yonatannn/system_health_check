from __future__ import annotations
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import yaml

from app.update.checksum_manifest import sha256_file, write_checksum_manifest
from app.core.bundle import validate_bundle

TRACKED_SUBDIRS = ("mission_planner", "external_configs")


class BundleBuildError(Exception):
    pass


def _copy_tree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(str(dst))
    shutil.copytree(str(src), str(dst))


def _compute_source_checksums(
    sources_gitlab_dir: Path,
    repos: list[dict],
    log: Callable[[str], None],
) -> dict[str, str]:
    checksums: dict[str, str] = {}

    log(f"Source root: {sources_gitlab_dir.resolve()}")

    if not sources_gitlab_dir.exists():
        log(f"  ERROR: source root does not exist — no repos have been cloned yet")
        return checksums

    for repo in repos:
        name = repo.get("name", "")
        local_path = sources_gitlab_dir / name
        log(f"Scanning repo '{name}' at {local_path.resolve()}")

        if not local_path.exists():
            log(f"  MISSING: repo directory not found — sync may have failed")
            continue

        found_any_subdir = False
        for sub in TRACKED_SUBDIRS:
            src_sub = local_path / sub
            if not src_sub.exists():
                log(f"  Subdir '{sub}/' not found in repo (skipping)")
                continue

            found_any_subdir = True
            files = sorted(f for f in src_sub.rglob("*") if f.is_file())
            log(f"  Subdir '{sub}/' — {len(files)} file(s) found")
            for file_path in files:
                rel = file_path.relative_to(local_path).as_posix()
                checksums[rel] = sha256_file(file_path)
                log(f"    hashed: {rel}")

        if not found_any_subdir:
            log(f"  WARNING: neither 'mission_planner/' nor 'external_configs/' found "
                f"in repo root — check that the repo has the expected directory structure")

    log(f"Total checksums computed: {len(checksums)}")
    return checksums


def build_bundle(
    sources_gitlab_dir: Path,
    repos: list[dict],
    existing_bundle_dir: Path,
    output_bundle_dir: Path,
    gitlab_commits: dict[str, Optional[str]],
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    log = log or (lambda msg: None)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "bundle"
        tmp_path.mkdir()

        log("--- Computing checksums ---")
        checksums = _compute_source_checksums(sources_gitlab_dir, repos, log)

        if not checksums:
            log("WARNING: no files were hashed — bundle will have empty checksum manifest")

        log("--- Writing bundle manifest ---")
        _write_manifest(tmp_path, repos, gitlab_commits)

        log("--- Writing checksum manifest ---")
        write_checksum_manifest(tmp_path, checksums)

        log("--- Validating bundle ---")
        ok, err = validate_bundle(tmp_path)
        if not ok:
            raise BundleBuildError(f"Bundle validation failed: {err}")

        log("--- Replacing active bundle ---")
        log(f"Output bundle dir: {output_bundle_dir.resolve()}")
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
        "sources": {
            "gitlab": gitlab_sources,
        },
    }
    with open(bundle_dir / "bundle_manifest.yaml", "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
