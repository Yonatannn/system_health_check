from __future__ import annotations
import pytest
from unittest.mock import patch, call

from app.core.config_loader import AppSettings
from app.core.models import CheckStatus
from app.checks.network_components import (
    ComponentPingSpec,
    _load_specs,
    _ping_spec,
    run_component_ping_checks,
)

_SETTINGS_DATA = {
    "network_components": {
        "ping_timeout_seconds": 3,
        "subnet_source_ips": {0: "192.168.10.100", 1: "192.168.20.100"},
        "components": [
            {"name": "Autopilot", "ip": "192.168.10.1", "subnet": 0, "required": True},
            {"name": "GCS Video Receiver", "ip": "192.168.10.50", "subnet": 0, "required": False},
            {"name": "Payload Computer", "ip": "192.168.20.1", "subnet": 1, "required": True},
            {"name": "Camera Control Unit", "ip": "192.168.20.10", "subnet": 1, "required": False},
        ],
    }
}


def _settings(data=None) -> AppSettings:
    return AppSettings(data if data is not None else _SETTINGS_DATA)


# ---------------------------------------------------------------------------
# _load_specs
# ---------------------------------------------------------------------------

class TestLoadSpecs:
    def test_loads_all_components(self):
        assert len(_load_specs(_settings())) == 4

    def test_component_fields(self):
        specs = _load_specs(_settings())
        ap = next(s for s in specs if s.name == "Autopilot")
        assert ap.ip == "192.168.10.1"
        assert ap.subnet == 0
        assert ap.required is True

    def test_optional_component(self):
        specs = _load_specs(_settings())
        vid = next(s for s in specs if s.name == "GCS Video Receiver")
        assert vid.required is False

    def test_empty_when_no_config(self):
        assert _load_specs(_settings({})) == []

    def test_empty_components_list(self):
        data = {"network_components": {"components": []}}
        assert _load_specs(_settings(data)) == []


# ---------------------------------------------------------------------------
# _ping_spec
# ---------------------------------------------------------------------------

class TestPingSpec:
    def _spec(self, required=True):
        return ComponentPingSpec(name="Test Device", ip="192.168.10.5", subnet=0, required=required)

    def test_reachable_gives_pass(self):
        with patch("app.checks.network_components.ping_host", return_value=True):
            result = _ping_spec(self._spec(), source_ip="192.168.10.100", timeout=5)
        assert result.status == CheckStatus.PASS

    def test_unreachable_required_gives_blocking_fail(self):
        with patch("app.checks.network_components.ping_host", return_value=False):
            result = _ping_spec(self._spec(required=True), source_ip=None, timeout=5)
        assert result.status == CheckStatus.FAIL
        assert result.blocking is True

    def test_unreachable_optional_gives_nonblocking_fail(self):
        with patch("app.checks.network_components.ping_host", return_value=False):
            result = _ping_spec(self._spec(required=False), source_ip=None, timeout=5)
        assert result.status == CheckStatus.FAIL
        assert result.blocking is False

    def test_result_id_derived_from_name(self):
        with patch("app.checks.network_components.ping_host", return_value=True):
            result = _ping_spec(self._spec(), source_ip=None, timeout=5)
        assert result.id == "component_ping_test_device"

    def test_source_ip_forwarded_to_ping_host(self):
        with patch("app.checks.network_components.ping_host", return_value=True) as mock_ping:
            _ping_spec(self._spec(), source_ip="192.168.10.100", timeout=3)
        mock_ping.assert_called_once_with("192.168.10.5", timeout_seconds=3, source_ip="192.168.10.100")


# ---------------------------------------------------------------------------
# run_component_ping_checks
# ---------------------------------------------------------------------------

class TestRunComponentPingChecks:
    def test_returns_empty_when_no_components(self):
        results = run_component_ping_checks(_settings({}))
        assert results == []

    def test_result_count_matches_component_count(self):
        with patch("app.checks.network_components.ping_host", return_value=True):
            results = run_component_ping_checks(_settings())
        assert len(results) == 4

    def test_subnet_0_pinged_before_subnet_1(self):
        """All subnet-0 hosts must be pinged before any subnet-1 host."""
        call_order: list[str] = []

        def recording_ping(host, timeout_seconds=5, source_ip=None):
            call_order.append(host)
            return True

        with patch("app.checks.network_components.ping_host", side_effect=recording_ping):
            run_component_ping_checks(_settings())

        subnet0_hosts = {"192.168.10.1", "192.168.10.50"}
        subnet1_hosts = {"192.168.20.1", "192.168.20.10"}

        last_subnet0 = max(i for i, h in enumerate(call_order) if h in subnet0_hosts)
        first_subnet1 = min(i for i, h in enumerate(call_order) if h in subnet1_hosts)
        assert last_subnet0 < first_subnet1

    def test_correct_source_ip_per_subnet(self):
        """Each component must be pinged from the source IP of its subnet."""
        calls: list[dict] = []

        def recording_ping(host, timeout_seconds=5, source_ip=None):
            calls.append({"host": host, "source_ip": source_ip})
            return True

        with patch("app.checks.network_components.ping_host", side_effect=recording_ping):
            run_component_ping_checks(_settings())

        for c in calls:
            if c["host"].startswith("192.168.10."):
                assert c["source_ip"] == "192.168.10.100", f"Wrong source for {c['host']}"
            elif c["host"].startswith("192.168.20."):
                assert c["source_ip"] == "192.168.20.100", f"Wrong source for {c['host']}"

    def test_all_pass_when_all_reachable(self):
        with patch("app.checks.network_components.ping_host", return_value=True):
            results = run_component_ping_checks(_settings())
        assert all(r.status == CheckStatus.PASS for r in results)

    def test_all_fail_when_none_reachable(self):
        with patch("app.checks.network_components.ping_host", return_value=False):
            results = run_component_ping_checks(_settings())
        assert all(r.status == CheckStatus.FAIL for r in results)

    def test_blocking_only_for_required_components(self):
        with patch("app.checks.network_components.ping_host", return_value=False):
            results = run_component_ping_checks(_settings())

        for r in results:
            # Required components that failed must be blocking
            if r.id in ("component_ping_autopilot", "component_ping_payload_computer"):
                assert r.blocking is True, f"{r.id} should be blocking"
            else:
                assert r.blocking is False, f"{r.id} should not be blocking"

    def test_timeout_from_config(self):
        with patch("app.checks.network_components.ping_host", return_value=True) as mock_ping:
            run_component_ping_checks(_settings())
        for c in mock_ping.call_args_list:
            assert c.kwargs["timeout_seconds"] == 3

    def test_no_source_ip_when_subnet_not_mapped(self):
        data = {
            "network_components": {
                "ping_timeout_seconds": 5,
                "subnet_source_ips": {},
                "components": [
                    {"name": "Device", "ip": "10.0.0.1", "subnet": 0, "required": True},
                ],
            }
        }
        with patch("app.checks.network_components.ping_host", return_value=True) as mock_ping:
            run_component_ping_checks(_settings(data))
        mock_ping.assert_called_once_with("10.0.0.1", timeout_seconds=5, source_ip=None)
