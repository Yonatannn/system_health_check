from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from app.core.config_loader import AppSettings
from app.core.paths import AppPaths
from app.windows.admin import is_admin
from app.windows.powershell import ping_host
from app.windows.adapters import find_adapter_by_match
from app.windows.dhcp_context import DHCPContext, DHCPSwitchError
from app.update.gitlab_sync import sync_all_repositories, GitSyncResult
from app.update.smb_sync import sync_all_shares, SMBSyncResult
from app.update.bundle_builder import build_bundle, BundleBuildError


@dataclass
class SyncReport:
    success: bool
    messages: list[str] = field(default_factory=list)
    git_results: list[GitSyncResult] = field(default_factory=list)
    smb_results: list[SMBSyncResult] = field(default_factory=list)
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

    def run_sync(self) -> SyncReport:
        report = SyncReport(success=False)

        # Check admin if DHCP switching is required
        if self.settings.temporarily_switch_to_dhcp and not is_admin():
            report.error = (
                "Administrator privileges are required to temporarily switch "
                "the network interface to DHCP for sync."
            )
            return report

        # Find sync interface
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
        gitlab_commits: dict[str, Optional[str]] = {}

        # GitLab sync
        if self.settings.enable_gitlab_sync:
            repos = self.settings.gitlab_repositories
            if repos:
                self.log("Starting GitLab sync…")
                results = sync_all_repositories(
                    repos=repos,
                    sources_dir=self.paths.sources_dir,
                    git_exe=self.settings.git_executable,
                    log=self.log,
                )
                report.git_results = results
                for r in results:
                    if r.success:
                        report.messages.append(f"GitLab [{r.name}]: OK (commit: {r.commit or 'unknown'})")
                        gitlab_commits[r.name] = r.commit
                    else:
                        report.messages.append(f"GitLab [{r.name}]: FAILED — {r.error}")

        # SMB sync
        if self.settings.enable_smb_sync:
            shares = self.settings.smb_shares
            if shares:
                self.log("Starting SMB sync…")
                results = sync_all_shares(
                    shares=shares,
                    sources_dir=self.paths.sources_dir,
                    log=self.log,
                )
                report.smb_results = results
                for r in results:
                    if r.success:
                        report.messages.append(f"SMB [{r.name}]: OK")
                    else:
                        report.messages.append(f"SMB [{r.name}]: FAILED — {r.error}")

        # Build bundle
        any_git_success = any(r.success for r in report.git_results) if report.git_results else True
        any_smb_success = any(r.success for r in report.smb_results) if report.smb_results else True

        if any_git_success or any_smb_success:
            self.log("Building config bundle…")
            try:
                build_bundle(
                    sources_gitlab_dir=self.paths.gitlab_sources_dir,
                    sources_smb_dir=self.paths.smb_sources_dir,
                    existing_bundle_dir=self.paths.config_bundle_dir,
                    output_bundle_dir=self.paths.config_bundle_dir,
                    gitlab_commits=gitlab_commits,
                    settings_sources=self.settings.raw().get("sources", {}),
                    log=self.log,
                )
                report.bundle_built = True
                report.success = True
            except BundleBuildError as e:
                report.error = f"Bundle build failed: {e}"
        else:
            report.error = "All sync sources failed; bundle not updated."

        return report
