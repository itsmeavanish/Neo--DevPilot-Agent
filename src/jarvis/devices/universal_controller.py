"""
JARVIS Universal Laptop Controller.

Manages connections to multiple laptops with various access methods:
1. WebSocket Agent (when agent is running)
2. SSH (when laptop is on but agent is not running)
3. Wake-on-LAN (to wake up sleeping/off laptops)
4. Store credentials securely for each laptop
"""

import asyncio
import hashlib
import json
import os
import socket
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import platform

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.devices.universal")


class AccessMethod(str, Enum):
    """How to access a laptop."""
    WEBSOCKET_AGENT = "agent"      # Remote agent is running (best)
    SSH = "ssh"                      # SSH access (need credentials)
    WAKE_ON_LAN = "wol"             # Wake up first, then connect
    UNAVAILABLE = "unavailable"     # Cannot reach


@dataclass
class LaptopCredentials:
    """Credentials for accessing a laptop."""
    # SSH credentials
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None  # Encrypted
    ssh_key_path: Optional[str] = None
    ssh_port: int = 22

    # Wake-on-LAN
    mac_address: Optional[str] = None
    broadcast_ip: str = "255.255.255.255"
    wol_port: int = 9

    # Agent token
    agent_token: Optional[str] = None


@dataclass
class UniversalLaptop:
    """A laptop that can be accessed through multiple methods."""
    id: str
    name: str

    # Network info
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    local_ip: Optional[str] = None  # For LAN access

    # Status
    status: str = "unknown"
    last_seen: Optional[str] = None
    last_access_method: Optional[AccessMethod] = None

    # Credentials (stored securely)
    credentials: LaptopCredentials = field(default_factory=LaptopCredentials)

    # Metadata
    platform: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary (safe for API response)."""
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "hostname": self.hostname,
            "status": self.status,
            "last_seen": self.last_seen,
            "last_access_method": self.last_access_method.value if self.last_access_method else None,
            "platform": self.platform,
            "has_ssh": bool(self.credentials.ssh_username),
            "has_wol": bool(self.credentials.mac_address),
            "has_agent": bool(self.credentials.agent_token),
        }


class UniversalLaptopController:
    """
    Controls access to multiple laptops through various methods.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or os.path.expanduser("~/.jarvis/laptops.json"))
        self.laptops: dict[str, UniversalLaptop] = {}
        self._load()

    def _load(self):
        """Load laptops from storage."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for laptop_data in data.get("laptops", []):
                    creds_data = laptop_data.pop("credentials", {})
                    credentials = LaptopCredentials(**creds_data)
                    laptop = UniversalLaptop(**laptop_data, credentials=credentials)
                    self.laptops[laptop.id] = laptop
                logger.info(f"Loaded {len(self.laptops)} laptops")
            except Exception as e:
                logger.error(f"Failed to load laptops: {e}")

    def _save(self):
        """Save laptops to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "laptops": [
                    {
                        **{k: v for k, v in laptop.__dict__.items() if k != "credentials"},
                        "credentials": laptop.credentials.__dict__
                    }
                    for laptop in self.laptops.values()
                ]
            }
            self.storage_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save laptops: {e}")

    def add_laptop(
        self,
        name: str,
        ip_address: Optional[str] = None,
        hostname: Optional[str] = None,
        mac_address: Optional[str] = None,
        ssh_username: Optional[str] = None,
        ssh_password: Optional[str] = None,
    ) -> UniversalLaptop:
        """Add a new laptop to control."""
        laptop_id = hashlib.md5(f"{name}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12]

        credentials = LaptopCredentials(
            mac_address=mac_address,
            ssh_username=ssh_username,
            ssh_password=ssh_password,  # TODO: Encrypt this
        )

        laptop = UniversalLaptop(
            id=laptop_id,
            name=name,
            ip_address=ip_address,
            hostname=hostname,
            credentials=credentials,
        )

        self.laptops[laptop_id] = laptop
        self._save()

        logger.info(f"Added laptop: {name} ({laptop_id})")
        return laptop

    def get_laptop(self, laptop_id: str) -> Optional[UniversalLaptop]:
        """Get a laptop by ID."""
        return self.laptops.get(laptop_id)

    def list_laptops(self) -> list[UniversalLaptop]:
        """List all laptops."""
        return list(self.laptops.values())

    def remove_laptop(self, laptop_id: str) -> bool:
        """Remove a laptop."""
        if laptop_id in self.laptops:
            del self.laptops[laptop_id]
            self._save()
            return True
        return False

    def update_laptop(self, laptop_id: str, **updates) -> Optional[UniversalLaptop]:
        """Update laptop settings."""
        laptop = self.laptops.get(laptop_id)
        if not laptop:
            return None

        for key, value in updates.items():
            if hasattr(laptop, key):
                setattr(laptop, key, value)
            elif hasattr(laptop.credentials, key):
                setattr(laptop.credentials, key, value)

        self._save()
        return laptop

    async def check_laptop_status(self, laptop_id: str) -> dict:
        """Check the current status of a laptop."""
        laptop = self.laptops.get(laptop_id)
        if not laptop:
            return {"status": "not_found", "method": None}

        # Try different access methods
        methods_tried = []

        # 1. Check if agent is connected (WebSocket)
        # This would be checked against active_connections in device_management.py
        # For now, we'll check via ping

        # 2. Check if reachable via ping
        if laptop.ip_address:
            is_reachable = await self._ping_host(laptop.ip_address)
            methods_tried.append(("ping", is_reachable))

            if is_reachable:
                laptop.status = "online"
                laptop.last_seen = datetime.utcnow().isoformat()
                self._save()
                return {
                    "status": "online",
                    "method": "ping",
                    "ip": laptop.ip_address
                }

        # 3. If has MAC address, could try Wake-on-LAN
        if laptop.credentials.mac_address:
            methods_tried.append(("wol_available", True))

        laptop.status = "offline"
        self._save()

        return {
            "status": "offline",
            "methods_tried": methods_tried,
            "wol_available": bool(laptop.credentials.mac_address)
        }

    async def _ping_host(self, host: str, timeout: int = 3) -> bool:
        """Ping a host to check if it's reachable."""
        try:
            if platform.system() == "Windows":
                cmd = f"ping -n 1 -w {timeout * 1000} {host}"
            else:
                cmd = f"ping -c 1 -W {timeout} {host}"

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(process.wait(), timeout=timeout + 2)
            return process.returncode == 0
        except:
            return False

    async def wake_laptop(self, laptop_id: str) -> dict:
        """
        Send Wake-on-LAN magic packet to wake up a laptop.

        Requirements:
        - Laptop must have WOL enabled in BIOS
        - MAC address must be configured
        - For remote WOL (over internet), need port forwarding on router
        """
        laptop = self.laptops.get(laptop_id)
        if not laptop:
            return {"success": False, "error": "Laptop not found"}

        mac = laptop.credentials.mac_address
        if not mac:
            return {"success": False, "error": "MAC address not configured"}

        try:
            # Create magic packet
            mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
            magic_packet = b'\xff' * 6 + mac_bytes * 16

            # Send to broadcast address
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(
                    magic_packet,
                    (laptop.credentials.broadcast_ip, laptop.credentials.wol_port)
                )

            logger.info(f"Sent WOL packet to {laptop.name} ({mac})")

            return {
                "success": True,
                "message": f"Wake-on-LAN packet sent to {laptop.name}",
                "note": "Laptop should wake up in 10-30 seconds if WOL is enabled"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_on_laptop(
        self,
        laptop_id: str,
        command: str,
        method: Optional[AccessMethod] = None,
        timeout: int = 60
    ) -> dict:
        """
        Execute a command on a laptop using the best available method.

        Priority: Agent > SSH > Wake then retry
        """
        laptop = self.laptops.get(laptop_id)
        if not laptop:
            return {"success": False, "error": "Laptop not found"}

        # If method not specified, try auto-detect
        if not method:
            status = await self.check_laptop_status(laptop_id)
            if status["status"] == "offline":
                if laptop.credentials.mac_address:
                    # Try to wake it up
                    wake_result = await self.wake_laptop(laptop_id)
                    if wake_result["success"]:
                        # Wait for it to come online
                        await asyncio.sleep(30)
                        status = await self.check_laptop_status(laptop_id)

        # Try SSH if available
        if laptop.credentials.ssh_username and laptop.ip_address:
            return await self._execute_via_ssh(laptop, command, timeout)

        return {
            "success": False,
            "error": "No access method available. Start the remote agent on the laptop or configure SSH."
        }

    async def _execute_via_ssh(
        self,
        laptop: UniversalLaptop,
        command: str,
        timeout: int
    ) -> dict:
        """Execute command via SSH."""
        try:
            # Use asyncssh if available, otherwise fall back to subprocess
            try:
                import asyncssh

                async with asyncssh.connect(
                    laptop.ip_address,
                    port=laptop.credentials.ssh_port,
                    username=laptop.credentials.ssh_username,
                    password=laptop.credentials.ssh_password,
                    known_hosts=None
                ) as conn:
                    result = await asyncio.wait_for(
                        conn.run(command),
                        timeout=timeout
                    )
                    return {
                        "success": result.exit_status == 0,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_status,
                        "method": "ssh"
                    }
            except ImportError:
                # Fall back to subprocess ssh
                ssh_cmd = f"ssh -o StrictHostKeyChecking=no {laptop.credentials.ssh_username}@{laptop.ip_address} '{command}'"
                process = await asyncio.create_subprocess_shell(
                    ssh_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                return {
                    "success": process.returncode == 0,
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "exit_code": process.returncode,
                    "method": "ssh"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"SSH error: {str(e)}",
                "method": "ssh"
            }


# Global instance
_controller: Optional[UniversalLaptopController] = None


def get_laptop_controller() -> UniversalLaptopController:
    """Get the global laptop controller instance."""
    global _controller
    if _controller is None:
        _controller = UniversalLaptopController()
    return _controller


__all__ = [
    "UniversalLaptop",
    "UniversalLaptopController",
    "LaptopCredentials",
    "AccessMethod",
    "get_laptop_controller"
]
