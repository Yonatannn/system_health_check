from __future__ import annotations
import os
import sys
from pathlib import Path


def _app_root() -> Path:
    # When frozen by PyInstaller, sys.executable is the .exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # Otherwise, two levels up from this file: app/core/paths.py -> project root
    return Path(__file__).parent.parent.parent


class AppPaths:
    def __init__(self, root: Path = None):
        self.root = root or _app_root()

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def config_bundle_dir(self) -> Path:
        return self.data_dir / "config_bundle"

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def gitlab_sources_dir(self) -> Path:
        return self.sources_dir / "gitlab"

    @property
    def smb_sources_dir(self) -> Path:
        return self.sources_dir / "smb"

    @property
    def embedded_bundle_dir(self) -> Path:
        return self.root / "embedded_default_bundle"

    def resolve_env(self, path_str: str) -> Path:
        """Expand environment variables like %USERPROFILE% in a path string."""
        expanded = os.path.expandvars(path_str)
        return Path(expanded)

    def ensure_dirs(self):
        for d in [self.config_dir, self.data_dir, self.config_bundle_dir,
                  self.sources_dir, self.gitlab_sources_dir, self.smb_sources_dir]:
            d.mkdir(parents=True, exist_ok=True)
