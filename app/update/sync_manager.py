from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from app.core.config_loader import AppSettings
from app.core.paths import AppPaths
from app.core.profile_loader import load_all_profiles
from app.windows.admin import is_admin
from app.windows.powershell import ping_host
from app.windows.adapters import find_adapter_by_match
from app.windows.dhcp_context import DHCPContext, DHCPSwitchError
from app.update.gitlab_sync import sync_all_repositories, GitSyncResult
from app.update.bundle_builder import build_bundle, BundleBuildError


@dataclass
class SyncReport:
    success: bool
    messages: list[str] = field(default_factory=list)
    git_results: list[GitSyncResult] = field(default_factory=list)
    bundle_built: bool = False
    error: Optional[str] = None
    interface_restored: bool = True

    @property
    def summary(self) -> str:
        if self.success:
            return "Sync completed successfully."
        return f"Sync failed: {self.error or 'unknown error'}"


class SyncManager:
    def __init__(self, paths: AppPaths, settings: AppSettings,
                 log: Optional[Callable[[str], None]] = None):
        self.paths = paths
        self.settings = settings
        self.log = log or (lambda msg: None)

    def _collect_repos(self) -> list[dict]:
        profiles = load_all_profiles(self.paths.profiles_dir)
        seen: set[str] = set()
        repos = []
        for p in profiles:
            if p.source_repo and p.source_repo.name not in seen:
                seen.add(p.source_repo.name)
                repos.append({
                    "name": p.source_repo.name,
                    "url": p.source_repo.url,
                    "branch": p.source_repo.branch,
                })
        return repos

    def run_sync(self) -> SyncReport:
        report = SyncReport(success=False)

        if self.settings.temporarily_switch_to_dhcp and not is_admin():
            report.error = (
                "Administrator privileges are required to temporarily switch "
                "the network interface to DHCP for sync."
            )
            return report

        iface_match = self.settings.sync_interface_match
        if not iface_match:
            report.messages.append("No sync interface configured — skipping DHCP switch.")
            return self._run_sync_operations(report)

        adapter = find_adapter_by_match(iface_match)
        if adapter is None:
            report.messages.append("Sync interface not found — skipping DHCP switch.")
            return self._run_sync_operations(report)

        iface_name = adapter.name
        self.log(f"Sync interface: {iface_name}")

        if not self.settings.temporarily_switch_to_dhcp:
            return self._run_sync_operations(report)

        ctx = DHCPContext(
            iface_name=iface_name,
            dhcp_wait_timeout=self.settings.dhcp_wait_timeout,
            log_callback=self.log,
        )
        try:
            with ctx.managed():
                if not self._check_server_reachable(report):
                    return report
                self._run_sync_operations(report)
        except DHCPSwitchError as e:
            report.error = str(e)
            report.interface_restored = False
        except Exception as e:
            report.error = f"Unexpected sync error: {e}"

        return report

    def _check_server_reachable(self, report: SyncReport) -> bool:
        server = self.settings.server_ip
        self.log(f"Checking reachability of {server}…")
        reachable = ping_host(server, timeout_seconds=self.settings.server_reachability_timeout)
        if not reachable:
            report.error = (
                f"Sync failed: configuration server {server} is not reachable.\n"
                f"No local configuration files were changed.\n"
                f"The previous network configuration was restored."
            )
            return False
        self.log(f"Server {server} is reachable.")
        return True

    def _run_sync_operations(self, report: SyncReport) -> SyncReport:
        repos = self._collect_repos()
        self.log(f"Profiles dir: {self.paths.profiles_dir.resolve()}")
        self.log(f"Repos to sync: {[r['name'] for r in repos] or '(none found in profiles)'}")
        self.log(f"GitLab sources dir: {self.paths.gitlab_sources_dir.resolve()}")
        gitlab_commits: dict[str, Optional[str]] = {}

        if self.settings.enable_gitlab_sync and repos:
            self.log("Starting GitLab sync…")
            results = sync_all_repositories(
                repos=repos,
                sources_dir=self.paths.sources_dir,
                log=self.log,
            )
            report.git_results = results
            for r in results:
                if r.success:
                    report.messages.append(f"GitLab [{r.name}]: OK (commit: {r.commit or 'unknown'})")
                    gitlab_commits[r.name] = r.commit
                else:
                    report.messages.append(f"GitLab [{r.name}]: FAILED — {r.error}")

        any_git_success = any(r.success for r in report.git_results) if report.git_results else True

        if any_git_success:
            self.log("Building config bundle…")
            try:
                build_bundle(
                    sources_gitlab_dir=self.paths.gitlab_sources_dir,
                    repos=repos,
                    existing_bundle_dir=self.paths.config_bundle_dir,
                    output_bundle_dir=self.paths.config_bundle_dir,
                    gitlab_commits=gitlab_commits,
                    log=self.log,
                )
                report.bundle_built = True
                report.success = True
            except BundleBuildError as e:
                report.error = f"Bundle build failed: {e}"
        else:
            report.error = "All sync sources failed; bundle not updated."

        return report
