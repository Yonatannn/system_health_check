from __future__ import annotations
import sys
from typing import Optional

from app.core.models import InterfaceSpec, CheckResult, Profile
from app.core.result import make_pass, make_fail, make_warning, make_skipped

CATEGORY = "Network Interfaces"
IS_WINDOWS = sys.platform == "win32"


def _get_interfaces_windows() -> list[dict]:
    """Return list of dicts with keys: name, mac, description, ipv4_addresses (list of (addr, prefix))."""
    import subprocess
    import json

    ps_script = """
$adapters = Get-NetAdapter | Where-Object { $_.Status -ne 'Not Present' }
$result = @()
foreach ($a in $adapters) {
    $ips = Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    $ipList = @()
    foreach ($ip in $ips) {
        $ipList += @{ address = $ip.IPAddress; prefix = $ip.PrefixLength }
    }
    $result += @{
        name        = $a.Name
        mac         = $a.MacAddress
        description = $a.InterfaceDescription
        status      = $a.Status
        index       = $a.InterfaceIndex
        ipv4        = $ipList
    }
}
ConvertTo-Json -Depth 4 $result
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception:
        return []


def _get_interfaces_mock() -> list[dict]:
    """Mock data for development/testing on non-Windows."""
    return [
        {
            "name": "Ethernet 1",
            "mac": "AA-BB-CC-DD-EE-01",
            "description": "Intel(R) Ethernet Connection",
            "status": "Up",
            "index": 1,
            "ipv4": [{"address": "192.168.1.100", "prefix": 24}],
        },
        {
            "name": "Ethernet 2",
            "mac": "AA-BB-CC-DD-EE-02",
            "description": "USB Ethernet Adapter",
            "status": "Up",
            "index": 2,
            "ipv4": [{"address": "192.168.1.200", "prefix": 24}],
        },
    ]


def get_interfaces() -> list[dict]:
    if IS_WINDOWS:
        return _get_interfaces_windows()
    return _get_interfaces_mock()


def _prefix_to_mask(prefix: int) -> str:
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return ".".join(str((mask >> (8 * i)) & 0xFF) for i in reversed(range(4)))


def _match_interface(spec: InterfaceSpec, interfaces: list[dict]) -> Optional[dict]:
    rule = spec.match_by
    # Priority 1: MAC address
    if rule.mac_address:
        mac_norm = rule.mac_address.upper().replace(":", "-")
        for iface in interfaces:
            iface_mac = (iface.get("mac") or "").upper().replace(":", "-")
            if iface_mac == mac_norm:
                return iface

    # Priority 2: Adapter name
    if rule.adapter_name:
        for iface in interfaces:
            if iface.get("name", "").lower() == rule.adapter_name.lower():
                return iface

    # Priority 3: Description contains
    if rule.description_contains:
        needle = rule.description_contains.lower()
        for iface in interfaces:
            if needle in (iface.get("description") or "").lower():
                return iface

    return None


def _not_found_details(spec: InterfaceSpec) -> str:
    rule = spec.match_by
    if rule.adapter_name:
        identifier = f"adapter named '{rule.adapter_name}'"
    elif rule.mac_address:
        identifier = f"adapter with MAC address '{rule.mac_address}'"
    elif rule.description_contains:
        identifier = f"adapter whose description contains '{rule.description_contains}'"
    else:
        identifier = "the configured adapter"
    return (
        f"Could not find {identifier}. "
        "If using a USB network adapter, unplug it and plug it back in, then re-run the check. "
        "To verify the adapter name: Win+X → Device Manager → Network Adapters."
    )


def _not_up_details(adapter_name: str) -> str:
    return (
        f"Adapter '{adapter_name}' was found but is not connected or is disabled. "
        "Check that the network cable is firmly plugged in on both ends. "
        "To enable a disabled adapter: Win+R → type 'ncpa.cpl' → "
        f"right-click '{adapter_name}' → Enable."
    )


def _ip_mismatch_details(adapter_name: str, exp_addr: str, exp_prefix: int) -> str:
    mask = _prefix_to_mask(exp_prefix)
    return (
        f"Adapter '{adapter_name}' has the wrong IP address. "
        f"To fix: Win+R → type 'ncpa.cpl' → right-click '{adapter_name}' → Properties → "
        f"Internet Protocol Version 4 (TCP/IPv4) → Properties → "
        f"select 'Use the following IP address' → "
        f"set IP Address to {exp_addr}, Subnet mask to {mask}."
    )


def check_interface(spec: InterfaceSpec, interfaces: list[dict]) -> list[CheckResult]:
    results = []
    matched = _match_interface(spec, interfaces)

    if matched is None:
        results.append(make_fail(
            id=f"iface_{spec.id}_exists",
            category=CATEGORY,
            title=f"{spec.display_name} — Not Found",
            details=_not_found_details(spec),
            blocking=spec.required,
        ))
        return results

    results.append(make_pass(
        id=f"iface_{spec.id}_exists",
        category=CATEGORY,
        title=f"{spec.display_name} — Found",
        actual=matched.get("name", ""),
    ))

    adapter_name = matched.get("name", "")
    status = (matched.get("status") or "").lower()
    if status == "up":
        results.append(make_pass(
            id=f"iface_{spec.id}_up",
            category=CATEGORY,
            title=f"{spec.display_name} — Enabled",
            actual="Up",
        ))
    else:
        results.append(make_fail(
            id=f"iface_{spec.id}_up",
            category=CATEGORY,
            title=f"{spec.display_name} — Not Connected",
            expected="Up",
            actual=status or "unknown",
            details=_not_up_details(adapter_name),
            blocking=spec.required,
        ))

    if spec.expected_ipv4:
        exp_addr = spec.expected_ipv4.address
        exp_prefix = spec.expected_ipv4.prefix_length
        ipv4_list = matched.get("ipv4") or []

        found_match = False
        actual_ip_str = "no IPv4 assigned"
        if ipv4_list:
            actual_ip_str = ", ".join(
                f"{ip['address']}/{ip['prefix']}" for ip in ipv4_list
            )
            for ip in ipv4_list:
                if ip["address"] == exp_addr and int(ip["prefix"]) == exp_prefix:
                    found_match = True
                    break

        if found_match:
            results.append(make_pass(
                id=f"iface_{spec.id}_ipv4",
                category=CATEGORY,
                title=f"{spec.display_name} — IPv4 Correct",
                expected=f"{exp_addr}/{exp_prefix}",
                actual=f"{exp_addr}/{exp_prefix}",
            ))
        else:
            results.append(make_fail(
                id=f"iface_{spec.id}_ipv4",
                category=CATEGORY,
                title=f"{spec.display_name} — Wrong IP Address",
                expected=f"{exp_addr}/{exp_prefix}",
                actual=actual_ip_str,
                details=_ip_mismatch_details(adapter_name, exp_addr, exp_prefix),
                blocking=spec.required,
            ))

    return results


def run_interface_checks(profile: Profile) -> list[CheckResult]:
    interfaces = get_interfaces()
    results = []
    for spec in profile.windows_interfaces:
        results.extend(check_interface(spec, interfaces))
    return results
