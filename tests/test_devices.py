"""
Tests for the multi-device orchestration system.
"""

import pytest
from datetime import datetime


class TestDeviceImports:
    """Test device module imports."""

    def test_import_models(self):
        from jarvis.devices.models.device import (
            DeviceType,
            DeviceRole,
            DeviceStatus,
            DeviceCapabilities,
            DeviceMetrics,
            Device,
        )
        assert DeviceType is not None
        assert Device is not None

    def test_import_registry(self):
        from jarvis.devices.registry import DeviceRegistry
        assert DeviceRegistry is not None

    def test_import_protocol(self):
        from jarvis.devices.protocol import (
            MessageType,
            DeviceMessage,
            DeviceProtocol,
        )
        assert MessageType is not None
        assert DeviceMessage is not None

    def test_import_distributor(self):
        from jarvis.devices.distributor import (
            LoadBalanceStrategy,
            TaskDistributor,
        )
        assert LoadBalanceStrategy is not None
        assert TaskDistributor is not None


class TestDeviceModels:
    """Test device model creation."""

    def test_create_device_capabilities(self):
        from jarvis.devices.models.device import DeviceCapabilities

        caps = DeviceCapabilities(
            tools=["shell_execute", "file_read"],
            max_concurrent_tasks=4,
            gpu_available=True,
            memory_mb=16384,
            cpu_cores=8,
        )

        assert "shell_execute" in caps.tools
        assert caps.gpu_available is True
        assert caps.cpu_cores == 8

    def test_create_device(self):
        from jarvis.devices.models.device import (
            Device,
            DeviceType,
            DeviceRole,
            DeviceStatus,
            DeviceCapabilities,
            DeviceMetrics,
        )

        device = Device(
            id="dev-001",
            name="Test Device",
            device_type=DeviceType.DESKTOP,
            role=DeviceRole.WORKER,
            status=DeviceStatus.ONLINE,
            host="localhost",
            port=8080,
            capabilities=DeviceCapabilities(
                tools=["shell_execute"],
                max_concurrent_tasks=2,
            ),
            metrics=DeviceMetrics(),
        )

        assert device.id == "dev-001"
        assert device.device_type == DeviceType.DESKTOP
        assert device.status == DeviceStatus.ONLINE


class TestDeviceRegistry:
    """Test device registry functionality."""

    def test_registry_creation(self):
        from jarvis.devices.registry import DeviceRegistry

        registry = DeviceRegistry()
        assert registry is not None

    def test_registry_singleton(self):
        from jarvis.devices.registry import DeviceRegistry

        r1 = DeviceRegistry()
        r2 = DeviceRegistry()
        assert r1 is r2

    def test_local_device(self):
        from jarvis.devices.registry import get_device_registry

        registry = get_device_registry()
        local = registry.local_device
        assert local is not None
        assert local.host in ["localhost", "127.0.0.1"]


class TestLoadBalancing:
    """Test load balancing strategies."""

    def test_strategy_enum(self):
        from jarvis.devices.distributor import LoadBalanceStrategy

        assert LoadBalanceStrategy.ROUND_ROBIN is not None
        assert LoadBalanceStrategy.LEAST_LOADED is not None
        assert LoadBalanceStrategy.CAPABILITY_MATCH is not None
        assert LoadBalanceStrategy.LOCAL_PREFERRED is not None

    def test_distributor_creation(self):
        from jarvis.devices.distributor import TaskDistributor, LoadBalanceStrategy

        distributor = TaskDistributor(strategy=LoadBalanceStrategy.ROUND_ROBIN)
        assert distributor is not None
        assert distributor.strategy == LoadBalanceStrategy.ROUND_ROBIN


class TestDeviceProtocol:
    """Test device communication protocol."""

    def test_message_types(self):
        from jarvis.devices.protocol import MessageType

        assert MessageType.HELLO is not None
        assert MessageType.HEARTBEAT is not None
        assert MessageType.TASK_ASSIGN is not None
        assert MessageType.TASK_RESULT is not None

    def test_create_message(self):
        from jarvis.devices.protocol import DeviceMessage, MessageType

        msg = DeviceMessage(
            msg_type=MessageType.HELLO,
            payload={"device_id": "test-001"},
        )

        assert msg.msg_type == MessageType.HELLO
        assert msg.payload["device_id"] == "test-001"
        assert msg.timestamp is not None
