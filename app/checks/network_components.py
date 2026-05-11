from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from app.core.models import CheckResult, Profile, NetworkComponentSpec
from app.core.result import make_pass, make_fail, make_skipped
from app.windows.powershell import ping_host

CATEGORY = "Network Components"


def _ping_spec(spec: NetworkComponentSpec, source_ip: Optional[str], timeout: int) -> CheckResult:
    result_id = f"component_ping_{spec.name.lower().replace(' ', '_')}"
    reachable = ping_host(spec.ip, timeout_seconds=timeout, source_ip=source_ip)
    if reachable:
        return make_pass(
            id=result_id,
            category=CATEGORY,
            title=f"{spec.name} — Reachable",
            expected=spec.ip,
            actual=spec.ip,
        )

    if spec.required:
        details = (
            f"No response from {spec.name} at {spec.ip}. "
            "Check that the device is powered on and connected with a network cable. "
            "Verify that the ground station adapter for this subnet has the correct IP address."
        )
    else:
        details = (
            f"No response from {spec.name} at {spec.ip}. "
            "This device is optional — the mission can continue, but verify the device is intentionally offline."
        )

    return make_fail(
        id=result_id,
        category=CATEGORY,
        title=f"{spec.name} — Not Responding",
        expected=f"{spec.ip} reachable",
        actual="no response",
        details=details,
        blocking=spec.required,
    )


def make_skipped_ping_checks(profile: Profile) -> list[CheckResult]:
    """Return SKIPPED results for all components — used when interfaces are misconfigured."""
    if not profile.network_components:
        return []
    return [
        make_skipped(
            id=f"component_ping_{spec.name.lower().replace(' ', '_')}",
            category=CATEGORY,
            title=f"{spec.name} — Skipped",
            details=(
                f"Ping to {spec.name} ({spec.ip}) was skipped because the network adapter "
                "does not have the correct IP address. Fix the adapter IP first, then re-run the check."
            ),
        )
        for spec in profile.network_components.components
    ]


def run_component_ping_checks(profile: Profile) -> list[CheckResult]:
    if not profile.network_components:
        return []

    comp_config = profile.network_components
    timeout = comp_config.ping_timeout_seconds

    # Derive source IP for each interface from its expected_ipv4 address
    iface_source_ips: dict[str, str] = {
        iface.id: iface.expected_ipv4.address
        for iface in profile.windows_interfaces
        if iface.expected_ipv4
    }

    components = comp_config.components
    results: list[Optional[CheckResult]] = [None] * len(components)

    def _ping_one(idx: int, spec: NetworkComponentSpec) -> tuple[int, CheckResult]:
        source_ip = iface_source_ips.get(spec.interface_id)
        return idx, _ping_spec(spec, source_ip, timeout)

    # Ping all components in parallel — subnet 0 and subnet 1 fire simultaneously
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(_ping_one, i, spec): i for i, spec in enumerate(components)}
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return [r for r in results if r is not None]
