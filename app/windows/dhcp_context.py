from __future__ import annotations
from contextlib import contextmanager
from typing import Generator, Optional, Callable

from app.windows.ip_config import snapshot_interface, switch_to_dhcp, restore_interface, wait_for_dhcp, InterfaceSnapshot


class DHCPSwitchError(Exception):
    pass


class DHCPContext:
    """
    Manages temporary DHCP switch for sync and guarantees interface restore
    even when an error occurs mid-sync.
    """

    def __init__(self, iface_name: str, dhcp_wait_timeout: int = 30,
                 log_callback: Optional[Callable[[str], None]] = None):
        self.iface_name = iface_name
        self.dhcp_wait_timeout = dhcp_wait_timeout
        self.log = log_callback or (lambda msg: None)
        self._snapshot: Optional[InterfaceSnapshot] = None

    def prepare(self) -> InterfaceSnapshot:
        """Snapshot and switch to DHCP. Returns snapshot for reference."""
        self.log(f"Snapshotting interface '{self.iface_name}' configuration…")
        snapshot = snapshot_interface(self.iface_name)
        if snapshot is None:
            raise DHCPSwitchError(f"Could not read configuration of interface '{self.iface_name}'")
        self._snapshot = snapshot

        self.log("Switching interface to DHCP…")
        ok, msg = switch_to_dhcp(self.iface_name)
        if not ok:
            raise DHCPSwitchError(f"Failed to switch to DHCP: {msg}")

        self.log("Waiting for DHCP address assignment…")
        ok, msg = wait_for_dhcp(self.iface_name, self.dhcp_wait_timeout)
        if not ok:
            self._restore_best_effort()
            raise DHCPSwitchError(f"DHCP address not assigned: {msg}")

        self.log(f"DHCP ready: {msg}")
        return snapshot

    def restore(self) -> tuple[bool, str]:
        """Restore interface to saved snapshot. Safe to call even if prepare() failed."""
        if self._snapshot is None:
            return True, "Nothing to restore"
        self.log("Restoring interface configuration…")
        ok, msg = restore_interface(self._snapshot)
        self.log(f"Restore: {msg}")
        return ok, msg

    def _restore_best_effort(self):
        try:
            self.restore()
        except Exception:
            pass

    @contextmanager
    def managed(self) -> Generator[InterfaceSnapshot, None, None]:
        """Context manager: prepares DHCP, yields snapshot, always restores on exit."""
        snapshot = self.prepare()
        try:
            yield snapshot
        finally:
            self._restore_best_effort()
