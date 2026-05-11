from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class OverallStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY WITH WARNINGS"
    NOT_READY = "NOT READY"


@dataclass
class CheckResult:
    id: str
    category: str
    title: str
    status: CheckStatus
    expected: Optional[str] = None
    actual: Optional[str] = None
    details: str = ""
    blocking: bool = True

    @property
    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    @property
    def failed(self) -> bool:
        return self.status == CheckStatus.FAIL

    @property
    def is_warning(self) -> bool:
        return self.status == CheckStatus.WARNING


@dataclass
class CheckCategory:
    name: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def overall_status(self) -> CheckStatus:
        if any(r.status == CheckStatus.FAIL and r.blocking for r in self.results):
            return CheckStatus.FAIL
        if any(r.status == CheckStatus.WARNING for r in self.results):
            return CheckStatus.WARNING
        if all(r.status in (CheckStatus.PASS, CheckStatus.SKIPPED) for r in self.results):
            return CheckStatus.PASS
        return CheckStatus.PASS


@dataclass
class PrecheckReport:
    profile_id: str
    profile_name: str
    categories: list[CheckCategory] = field(default_factory=list)

    @property
    def all_results(self) -> list[CheckResult]:
        return [r for cat in self.categories for r in cat.results]

    @property
    def overall_status(self) -> OverallStatus:
        results = self.all_results
        if any(r.status == CheckStatus.FAIL and r.blocking for r in results):
            return OverallStatus.NOT_READY
        if any(r.status == CheckStatus.WARNING for r in results):
            return OverallStatus.READY_WITH_WARNINGS
        return OverallStatus.READY


@dataclass
class InterfaceMatchRule:
    adapter_name: Optional[str] = None
    mac_address: Optional[str] = None
    description_contains: Optional[str] = None


@dataclass
class ExpectedIPv4:
    address: str
    prefix_length: int


@dataclass
class InterfaceSpec:
    id: str
    display_name: str
    required: bool
    match_by: InterfaceMatchRule
    expected_ipv4: Optional[ExpectedIPv4] = None


@dataclass
class FileCheckSpec:
    id: str
    display_name: str
    target_path: str
    expected_file: str
    required: bool = True
    file_type: str = "generic"
    check_exists: bool = True
    check_valid_xml: bool = False
    check_sha256: bool = True


@dataclass
class MissionPlannerSpec:
    base_path: str
    files: list[FileCheckSpec]


@dataclass
class NetworkComponentSpec:
    name: str
    ip: str
    interface_id: str
    required: bool = True


@dataclass
class NetworkComponentsConfig:
    ping_timeout_seconds: int = 5
    components: list[NetworkComponentSpec] = field(default_factory=list)


@dataclass
class Profile:
    id: str
    display_name: str
    description: str = ""
    windows_interfaces: list[InterfaceSpec] = field(default_factory=list)
    network_components: Optional[NetworkComponentsConfig] = None
    mission_planner: Optional[MissionPlannerSpec] = None
    external_files: list[FileCheckSpec] = field(default_factory=list)


@dataclass
class BundleSource:
    name: str
    url: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None


@dataclass
class BundleManifest:
    name: str
    version: str
    created_at: str
    schema_version: str
    gitlab_sources: list[BundleSource] = field(default_factory=list)
    is_valid: bool = True
    validation_error: Optional[str] = None
