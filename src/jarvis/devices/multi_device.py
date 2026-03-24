"""
Device Registry for Multi-Laptop Support.

Manages multiple devices (laptops) that can connect to JARVIS.
Each device has a unique token and can be selected from the mobile app.
"""

import os
import secrets
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.devices.registry")


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"


@dataclass
class Device:
    """Represents a registered device (laptop)."""
    id: str
    name: str
    token: str  # Secret token for this device
    created_at: str
    last_seen: Optional[str] = None
    status: DeviceStatus = DeviceStatus.OFFLINE
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    platform: Optional[str] = None
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "status": self.status.value,
            "hostname": self.hostname,
            "platform": self.platform,
            "capabilities": self.capabilities,
        }

    def to_dict_with_token(self) -> dict:
        """Include token (only for device owner)."""
        data = self.to_dict()
        data["token"] = self.token
        return data


class DeviceRegistry:
    """
    Registry for managing multiple devices.

    Devices are stored in a JSON file for persistence.
    In production, use Redis or PostgreSQL.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("data/devices.json")
        self.devices: dict[str, Device] = {}
        self.active_connections: dict[str, asyncio.Queue] = {}
        self._load()

    def _load(self):
        """Load devices from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for device_data in data.get("devices", []):
                        device_data["status"] = DeviceStatus(device_data.get("status", "offline"))
                        self.devices[device_data["id"]] = Device(**device_data)
                logger.info(f"Loaded {len(self.devices)} devices from storage")
            except Exception as e:
                logger.error(f"Failed to load devices: {e}")
                self.devices = {}
        else:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _save(self):
        """Save devices to storage."""
        try:
            data = {
                "devices": [
                    {**asdict(d), "status": d.status.value}
                    for d in self.devices.values()
                ]
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save devices: {e}")

    def generate_device_token(self) -> str:
        """Generate a secure device token."""
        return f"jdv_{secrets.token_urlsafe(32)}"

    def register_device(self, name: str, capabilities: list[str] = None) -> Device:
        """Register a new device and return its credentials."""
        device_id = f"dev_{secrets.token_hex(8)}"
        token = self.generate_device_token()

        device = Device(
            id=device_id,
            name=name,
            token=token,
            created_at=datetime.utcnow().isoformat(),
            capabilities=capabilities or ["shell", "file", "git"],
        )

        self.devices[device_id] = device
        self._save()

        logger.info(f"Registered new device: {name} ({device_id})")
        return device

    def get_device(self, device_id: str) -> Optional[Device]:
        """Get a device by ID."""
        return self.devices.get(device_id)

    def get_device_by_token(self, token: str) -> Optional[Device]:
        """Get a device by its token."""
        for device in self.devices.values():
            if device.token == token:
                return device
        return None

    def list_devices(self) -> list[Device]:
        """List all registered devices."""
        return list(self.devices.values())

    def update_device_status(
        self,
        device_id: str,
        status: DeviceStatus,
        ip_address: str = None,
        hostname: str = None,
        platform: str = None,
    ):
        """Update device status (called when agent connects/disconnects)."""
        device = self.devices.get(device_id)
        if device:
            device.status = status
            device.last_seen = datetime.utcnow().isoformat()
            if ip_address:
                device.ip_address = ip_address
            if hostname:
                device.hostname = hostname
            if platform:
                device.platform = platform
            self._save()

    def delete_device(self, device_id: str) -> bool:
        """Delete a device."""
        if device_id in self.devices:
            del self.devices[device_id]
            self._save()
            logger.info(f"Deleted device: {device_id}")
            return True
        return False

    def rotate_token(self, device_id: str) -> Optional[str]:
        """Generate a new token for a device (security feature)."""
        device = self.devices.get(device_id)
        if device:
            device.token = self.generate_device_token()
            self._save()
            logger.info(f"Rotated token for device: {device_id}")
            return device.token
        return None

    # Connection management for real-time communication
    def register_connection(self, device_id: str) -> asyncio.Queue:
        """Register an active WebSocket connection for a device."""
        queue = asyncio.Queue()
        self.active_connections[device_id] = queue
        self.update_device_status(device_id, DeviceStatus.ONLINE)
        return queue

    def unregister_connection(self, device_id: str):
        """Unregister a device connection."""
        if device_id in self.active_connections:
            del self.active_connections[device_id]
        self.update_device_status(device_id, DeviceStatus.OFFLINE)

    async def send_to_device(self, device_id: str, message: dict) -> bool:
        """Send a message to a connected device."""
        if device_id in self.active_connections:
            await self.active_connections[device_id].put(message)
            return True
        return False

    def is_device_online(self, device_id: str) -> bool:
        """Check if a device is currently connected."""
        return device_id in self.active_connections


# Global registry instance
_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """Get the global device registry instance."""
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry


__all__ = ["Device", "DeviceStatus", "DeviceRegistry", "get_device_registry"]
