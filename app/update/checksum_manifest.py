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


def write_checksum_manifest(bundle_dir: Path, checksums: dict[str, str]) -> Path:
    out_path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(checksums, f, default_flow_style=False)
    return out_path


def load_checksum_manifest(bundle_dir: Path) -> dict[str, str]:
    path = bundle_dir / "checksums" / "sha256_manifest.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
