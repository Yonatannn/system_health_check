from __future__ import annotations
import sys
import json
from dataclasses import dataclass, field
from typing import Optional

from app.windows.powershell import run_ps

IS_WINDOWS = sys.platform == "win32"


@dataclass
class IPv4Address:
    address: str
    prefix_length: int


@dataclass
class InterfaceSnapshot:
    """Full snapshot of an interface's IP configuration for safe restore."""
    name: str
    index: int
    dhcp_enabled: bool
    ipv4_addresses: list[IPv4Address] = field(default_factory=list)
    gateway: Optional[str] = None
    dns_servers: list[str] = field(default_factory=list)


def snapshot_interface(iface_name: str) -> Optional[InterfaceSnapshot]:
    """Capture current interface configuration before modifying."""
    if not IS_WINDOWS:
        return InterfaceSnapshot(
            name=iface_name, index=0, dhcp_enabled=False,
            ipv4_addresses=[IPv4Address("192.168.10.100", 24)],
            gateway="192.168.10.1", dns_servers=["8.8.8.8"],
        )

    ps = f"""
$iface = Get-NetAdapter -Name '{iface_name}' -ErrorAction Stop
$ip = Get-NetIPAddress -InterfaceIndex $iface.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
$cfg = Get-NetIPConfiguration -InterfaceIndex $iface.InterfaceIndex -ErrorAction SilentlyContinue
$dhcp = (Get-NetIPInterface -InterfaceIndex $iface.InterfaceIndex -AddressFamily IPv4).Dhcp

$ipList = @()
foreach ($i in $ip) {{ $ipList += @{{ address = $i.IPAddress; prefix = [int]$i.PrefixLength }} }}

$dns = (Get-DnsClientServerAddress -InterfaceIndex $iface.InterfaceIndex -AddressFamily IPv4).ServerAddresses

@{{
    name    = $iface.Name
    index   = [int]$iface.InterfaceIndex
    dhcp    = ($dhcp -eq 'Enabled')
    ips     = $ipList
    gateway = if ($cfg.IPv4DefaultGateway) {{ $cfg.IPv4DefaultGateway.NextHop }} else {{ $null }}
    dns     = if ($dns) {{ $dns }} else {{ @() }}
}} | ConvertTo-Json -Depth 3
"""
    result = run_ps(ps, timeout=15)
    if not result.success:
        return None
    try:
        d = json.loads(result.stdout)
        return InterfaceSnapshot(
            name=d["name"],
            index=int(d["index"]),
            dhcp_enabled=bool(d["dhcp"]),
            ipv4_addresses=[IPv4Address(i["address"], int(i["prefix"])) for i in (d.get("ips") or [])],
            gateway=d.get("gateway"),
            dns_servers=d.get("dns") or [],
        )
    except Exception:
        return None


def switch_to_dhcp(iface_name: str) -> tuple[bool, str]:
    """Switch interface to DHCP. Returns (success, message)."""
    if not IS_WINDOWS:
        return True, "Mock: switched to DHCP"
    ps = f"""
$idx = (Get-NetAdapter -Name '{iface_name}').InterfaceIndex
Set-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -Dhcp Enabled
Remove-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue
"""
    result = run_ps(ps, timeout=20)
    if result.success:
        return True, "Switched to DHCP"
    return False, result.stderr.strip() or "Failed to switch to DHCP"


def restore_interface(snapshot: InterfaceSnapshot) -> tuple[bool, str]:
    """Restore an interface to a previously snapshotted state."""
    if not IS_WINDOWS:
        return True, "Mock: restored interface"

    if snapshot.dhcp_enabled:
        return switch_to_dhcp(snapshot.name)

    # Restore static configuration
    parts = [
        f"$idx = {snapshot.index}",
        f"Set-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -Dhcp Disabled -ErrorAction SilentlyContinue",
        f"Remove-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue",
    ]
    for addr in snapshot.ipv4_addresses:
        gw = f"-DefaultGateway '{snapshot.gateway}'" if snapshot.gateway else ""
        parts.append(
            f"New-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 "
            f"-IPAddress '{addr.address}' -PrefixLength {addr.prefix_length} {gw} -ErrorAction SilentlyContinue"
        )
    if snapshot.dns_servers:
        dns_csv = ",".join(f"'{s}'" for s in snapshot.dns_servers)
        parts.append(f"Set-DnsClientServerAddress -InterfaceIndex $idx -ServerAddresses @({dns_csv})")

    ps = "\n".join(parts)
    result = run_ps(ps, timeout=30)
    if result.success:
        return True, "Interface restored"
    return False, result.stderr.strip() or "Restore command failed"


def wait_for_dhcp(iface_name: str, timeout_seconds: int = 30) -> tuple[bool, str]:
    """Wait until the interface gets a DHCP-assigned (non-APIPA) address."""
    if not IS_WINDOWS:
        return True, "Mock: DHCP assigned 192.168.1.50"
    import time
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        ps = f"""
$idx = (Get-NetAdapter -Name '{iface_name}' -ErrorAction SilentlyContinue).InterfaceIndex
$ips = Get-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue |
       Where-Object {{ $_.IPAddress -notlike '169.254.*' }}
if ($ips) {{ $ips[0].IPAddress }} else {{ '' }}
"""
        result = run_ps(ps, timeout=10)
        addr = result.stdout.strip()
        if addr:
            return True, f"DHCP assigned: {addr}"
        time.sleep(2)
    return False, "Timed out waiting for DHCP address"
