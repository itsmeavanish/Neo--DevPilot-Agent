"""
Tests for the self-healing system.
"""

import pytest
from datetime import datetime


class TestSelfHealImports:
    """Test self-healing module imports."""

    def test_import_models(self):
        from jarvis.self_heal.models.issue import (
            IssueSeverity,
            IssueType,
            IssueStatus,
            Issue,
        )
        assert IssueSeverity is not None
        assert IssueType is not None
        assert Issue is not None

    def test_import_monitors(self):
        from jarvis.self_heal.monitors.base import BaseMonitor
        from jarvis.self_heal.monitors.port import PortMonitor
        from jarvis.self_heal.monitors.disk import DiskMonitor
        assert BaseMonitor is not None
        assert PortMonitor is not None
        assert DiskMonitor is not None

    def test_import_resolvers(self):
        from jarvis.self_heal.resolvers.base import BaseResolver
        from jarvis.self_heal.resolvers.port_free import PortFreeResolver
        from jarvis.self_heal.resolvers.cleanup import CleanupResolver
        assert BaseResolver is not None
        assert PortFreeResolver is not None
        assert CleanupResolver is not None

    def test_import_engine(self):
        from jarvis.self_heal.engine import SelfHealEngine
        assert SelfHealEngine is not None


class TestIssueModel:
    """Test the Issue model."""

    def test_create_issue(self):
        from jarvis.self_heal.models.issue import (
            Issue,
            IssueSeverity,
            IssueType,
            IssueStatus,
        )

        issue = Issue(
            id="test-001",
            issue_type=IssueType.PORT_CONFLICT,
            severity=IssueSeverity.HIGH,
            source="test",
            description="Test issue",
            context={"port": 3000},
        )

        assert issue.id == "test-001"
        assert issue.issue_type == IssueType.PORT_CONFLICT
        assert issue.severity == IssueSeverity.HIGH
        assert issue.status == IssueStatus.DETECTED

    def test_issue_severity_levels(self):
        from jarvis.self_heal.models.issue import IssueSeverity

        assert IssueSeverity.LOW.value == "low"
        assert IssueSeverity.MEDIUM.value == "medium"
        assert IssueSeverity.HIGH.value == "high"
        assert IssueSeverity.CRITICAL.value == "critical"


class TestMonitors:
    """Test monitor functionality."""

    def test_port_monitor_creation(self):
        from jarvis.self_heal.monitors.port import PortMonitor

        monitor = PortMonitor(ports_to_check=[3000, 8080])
        assert monitor.name == "port_monitor"
        assert 3000 in monitor.ports_to_check

    def test_disk_monitor_creation(self):
        from jarvis.self_heal.monitors.disk import DiskMonitor

        monitor = DiskMonitor(threshold_percent=80.0)
        assert monitor.name == "disk_monitor"
        assert monitor.threshold_percent == 80.0


class TestResolvers:
    """Test resolver functionality."""

    def test_resolver_can_handle(self):
        from jarvis.self_heal.resolvers.port_free import PortFreeResolver
        from jarvis.self_heal.models.issue import Issue, IssueType, IssueSeverity

        resolver = PortFreeResolver()

        port_issue = Issue(
            id="port-001",
            issue_type=IssueType.PORT_CONFLICT,
            severity=IssueSeverity.HIGH,
            source="test",
            description="Port conflict",
            context={},
        )

        assert resolver.can_handle(port_issue) is True

    def test_resolver_requires_approval(self):
        from jarvis.self_heal.resolvers.port_free import PortFreeResolver

        resolver = PortFreeResolver()
        assert resolver.requires_approval is True


class TestSelfHealEngine:
    """Test the self-healing engine."""

    def test_engine_creation(self):
        from jarvis.self_heal.engine import SelfHealEngine

        engine = SelfHealEngine()
        assert engine is not None
        assert hasattr(engine, "monitors")
        assert hasattr(engine, "resolvers")

    @pytest.mark.asyncio
    async def test_engine_check_health(self):
        from jarvis.self_heal.engine import SelfHealEngine

        engine = SelfHealEngine()
        # Should return list of issues (may be empty)
        issues = await engine.check_health()
        assert isinstance(issues, list)
