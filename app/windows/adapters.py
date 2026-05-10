from __future__ import annotations
import sys
import json
from dataclasses import dataclass, field
from typing import Optional

from app.windows.powershell import run_ps

IS_WINDOWS = sys.platform == "win32"


@dataclass
class AdapterInfo:
    name: str
    index: int
    mac: str
    description: str
    status: str
    ipv4_addresses: list[tuple[str, int]] = field(default_factory=list)


def list_adapters() -> list[AdapterInfo]:
    if not IS_WINDOWS:
        return [
            AdapterInfo("Ethernet", 1, "AA-BB-CC-DD-EE-01", "Intel Ethernet", "Up",
                        [("192.168.10.100", 24)]),
            AdapterInfo("Ethernet 2", 2, "AA-BB-CC-DD-EE-02", "USB Ethernet Adapter", "Up",
                        [("169.254.12.33", 16)]),
            AdapterInfo("Wi-Fi", 3, "AA-BB-CC-DD-EE-03", "Wireless LAN Adapter", "Disconnected", []),
        ]

    ps = """
$adapters = Get-NetAdapter
$result = @()
foreach ($a in $adapters) {
    $ips = Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    $ipList = @()
    foreach ($ip in $ips) { $ipList += @{ address=$ip.IPAddress; prefix=[int]$ip.PrefixLength } }
    $result += @{
        name        = $a.Name
        index       = [int]$a.InterfaceIndex
        mac         = $a.MacAddress
        description = $a.InterfaceDescription
        status      = $a.Status
        ipv4        = $ipList
    }
}
ConvertTo-Json -Depth 3 $result
"""
    result = run_ps(ps, timeout=15)
    if not result.success:
        return []
    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        adapters = []
        for d in data:
            ipv4 = [(i["address"], int(i["prefix"])) for i in (d.get("ipv4") or [])]
            adapters.append(AdapterInfo(
                name=d.get("name", ""),
                index=int(d.get("index", 0)),
                mac=d.get("mac", ""),
                description=d.get("description", ""),
                status=d.get("status", ""),
                ipv4_addresses=ipv4,
            ))
        return adapters
    except Exception:
        return []


def find_adapter_by_match(match_by: dict) -> Optional[AdapterInfo]:
    adapters = list_adapters()
    if mac := match_by.get("adapter_name"):
        for a in adapters:
            if a.name.lower() == mac.lower():
                return a
    if name := match_by.get("mac_address"):
        norm = name.upper().replace(":", "-")
        for a in adapters:
            if a.mac.upper().replace(":", "-") == norm:
                return a
    if desc := match_by.get("description_contains"):
        for a in adapters:
            if desc.lower() in a.description.lower():
                return a
    return None
