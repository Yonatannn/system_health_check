from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import yaml


class AppSettings:
    def __init__(self, data: dict):
        self._data = data

    def get(self, *keys, default=None):
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k)
            if node is None:
                return default
        return node

    @property
    def app_version(self) -> str:
        return self.get("app", "version", default="1.0.0")

    @property
    def app_name(self) -> str:
        return self.get("app", "name", default="Ground Station Precheck Manager")

    @property
    def server_ip(self) -> str:
        return self.get("sync", "server_ip", default="192.168.1.1")

    @property
    def data_dir(self) -> Optional[str]:
        return self.get("paths", "data_dir")

    @property
    def config_bundle_dir(self) -> Optional[str]:
        return self.get("paths", "config_bundle_dir")

    @property
    def mission_planner_dir(self) -> Optional[str]:
        return self.get("paths", "mission_planner_dir")

    @property
    def git_executable(self) -> str:
        return self.get("tools", "git_executable", default="git")

    @property
    def enable_gitlab_sync(self) -> bool:
        return bool(self.get("features", "enable_gitlab_sync", default=True))

    @property
    def enable_smb_sync(self) -> bool:
        return bool(self.get("features", "enable_smb_sync", default=True))

    @property
    def temporarily_switch_to_dhcp(self) -> bool:
        return bool(self.get("sync", "temporarily_switch_interface_to_dhcp", default=True))

    @property
    def restore_interface_after_sync(self) -> bool:
        return bool(self.get("sync", "restore_interface_after_sync", default=True))

    @property
    def dhcp_wait_timeout(self) -> int:
        return int(self.get("sync", "dhcp_wait_timeout_seconds", default=30))

    @property
    def server_reachability_timeout(self) -> int:
        return int(self.get("sync", "server_reachability_timeout_seconds", default=10))

    @property
    def sync_interface_match(self) -> dict:
        return self.get("network", "sync_interface", "match_by", default={})

    @property
    def gitlab_repositories(self) -> list[dict]:
        return self.get("sources", "gitlab", "repositories", default=[])

    @property
    def smb_shares(self) -> list[dict]:
        return self.get("sources", "smb", "shares", default=[])

    def raw(self) -> dict:
        return self._data


def load_app_settings(settings_path: Path) -> AppSettings:
    if not settings_path.exists():
        return AppSettings({})
    with open(settings_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AppSettings(data)


def save_app_settings(settings_path: Path, data: dict):
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
