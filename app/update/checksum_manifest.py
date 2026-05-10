from __future__ import annotations
import hashlib
from pathlib import Path
import yaml


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_checksum_manifest(bundle_dir: Path) -> dict[str, str]:
    """Walk bundle_dir and compute SHA256 for every file (except the manifest itself)."""
    checksums = {}
    manifest_path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    for path in sorted(bundle_dir.rglob("*")):
        if path == manifest_path or not path.is_file():
            continue
        rel = path.relative_to(bundle_dir).as_posix()
        checksums[rel] = sha256_file(path)
    return checksums


def write_checksum_manifest(bundle_dir: Path) -> Path:
    checksums = build_checksum_manifest(bundle_dir)
    out_path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(checksums, f, default_flow_style=False)
    return out_path


def verify_checksums(bundle_dir: Path) -> tuple[bool, list[str]]:
    """Check all files against recorded checksums. Returns (ok, list_of_errors)."""
    manifest_path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    if not manifest_path.exists():
        return False, ["sha256_manifest.yaml not found"]

    with open(manifest_path, "r", encoding="utf-8") as f:
        recorded = yaml.safe_load(f) or {}

    errors = []
    for rel_path, expected_hash in recorded.items():
        full = bundle_dir / rel_path
        if not full.exists():
            errors.append(f"Missing: {rel_path}")
            continue
        actual = sha256_file(full)
        if actual != expected_hash:
            errors.append(f"Hash mismatch: {rel_path}")

    return len(errors) == 0, errors
