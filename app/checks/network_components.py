from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.core.config_loader import AppSettings
from app.core.models import CheckResult
from app.core.result import make_pass, make_fail
from app.windows.powershell import ping_host

CATEGORY = "Network Components"


@dataclass
class ComponentPingSpec:
    name: str
    ip: str
    subnet: int
    required: bool = True


def _load_specs(settings: AppSettings) -> list[ComponentPingSpec]:
    raw = settings.get("network_components", "components", default=[]) or []
    return [
        ComponentPingSpec(
            name=item.get("name", "Unknown"),
            ip=item.get("ip", ""),
            subnet=int(item.get("subnet", 0)),
            required=bool(item.get("required", True)),
        )
        for item in raw
    ]


def _ping_spec(spec: ComponentPingSpec, source_ip: Optional[str], timeout: int) -> CheckResult:
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
    return make_fail(
        id=result_id,
        category=CATEGORY,
        title=f"{spec.name} — Unreachable",
        expected=f"{spec.ip} reachable",
        actual="no response",
        blocking=spec.required,
    )


def run_component_ping_checks(settings: AppSettings) -> list[CheckResult]:
    specs = _load_specs(settings)
    if not specs:
        return []

    timeout = int(settings.get("network_components", "ping_timeout_seconds", default=5))
    raw_source_ips = settings.get("network_components", "subnet_source_ips", default={}) or {}
    subnet_source_ips: dict[int, str] = {int(k): v for k, v in raw_source_ips.items()}

    by_subnet: dict[int, list[ComponentPingSpec]] = {}
    for spec in specs:
        by_subnet.setdefault(spec.subnet, []).append(spec)

    results: list[CheckResult] = []
    for subnet_idx in sorted(by_subnet.keys()):
        source_ip = subnet_source_ips.get(subnet_idx)
        for spec in by_subnet[subnet_idx]:
            results.append(_ping_spec(spec, source_ip, timeout))

    return results
