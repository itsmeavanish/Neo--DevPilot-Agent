"""
Device Pairing API for Phone Connection.

Phone users get a pairing code to connect to the server.
Once paired, phone can control any connected laptop.
"""

import json
import secrets
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field

from jarvis.api.middleware.security import verify_api_key
from jarvis.devices.agent_registry import get_agent_registry
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.pairing")

router = APIRouter(prefix="/pairing", tags=["Device Pairing"])


# Models
class PairingCodeResponse(BaseModel):
    """Response when generating pairing code."""
    pairing_code: str
    expires_in_seconds: int
    message: str


class DeviceInfo(BaseModel):
    """Information about a device (laptop/agent)."""
    device_id: str
    name: str
    hostname: str
    platform: str
    status: str
    last_seen: Optional[str] = None


class PairedDeviceResponse(BaseModel):
    """Response with paired device info."""
    paired: bool
    phone_id: str
    server_name: str
    available_devices: list[DeviceInfo]


class ExecuteCommandRequest(BaseModel):
    """Request to execute command on a device."""
    device_id: str
    command: str
    timeout: int = 60


@dataclass
class PairingSession:
    """A phone pairing session."""
    phone_id: str
    pairing_code: str
    created_at: str
    expires_at: str
    verified: bool = False
    websocket: Optional[WebSocket] = None
    last_activity: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class PairingManager:
    """Manages phone pairing sessions."""

    def __init__(self, code_timeout_seconds: int = 300):
        self.sessions: Dict[str, PairingSession] = {}
        self.code_to_phone: Dict[str, str] = {}
        self.code_timeout = code_timeout_seconds

    def generate_pairing_code(self) -> tuple[str, str]:
        """Generate a new pairing code and phone ID."""
        import uuid
        phone_id = str(uuid.uuid4())[:12]
        pairing_code = secrets.token_hex(4).upper()  # 8-char code like "A1B2C3D4"

        now = datetime.utcnow()
        session = PairingSession(
            phone_id=phone_id,
            pairing_code=pairing_code,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.code_timeout)).isoformat()
        )

        self.sessions[phone_id] = session
        self.code_to_phone[pairing_code] = phone_id

        logger.info(f"Generated pairing code {pairing_code} for phone {phone_id}")
        return pairing_code, phone_id

    def verify_pairing_code(self, pairing_code: str) -> Optional[str]:
        """Verify a pairing code and return phone ID."""
        phone_id = self.code_to_phone.get(pairing_code)
        if not phone_id:
            logger.warning(f"Invalid pairing code: {pairing_code}")
            return None

        session = self.sessions.get(phone_id)
        if not session:
            return None

        # Check if code has expired
        expires_at = datetime.fromisoformat(session.expires_at)
        if datetime.utcnow() > expires_at:
            logger.warning(f"Pairing code expired: {pairing_code}")
            self.remove_session(phone_id)
            return None

        session.verified = True
        session.last_activity = datetime.utcnow().isoformat()

        logger.info(f"Pairing verified for phone {phone_id}")
        return phone_id

    def get_session(self, phone_id: str) -> Optional[PairingSession]:
        """Get a pairing session."""
        session = self.sessions.get(phone_id)
        if session:
            session.last_activity = datetime.utcnow().isoformat()
        return session

    def remove_session(self, phone_id: str) -> bool:
        """Remove a pairing session."""
        session = self.sessions.pop(phone_id, None)
        if session:
            self.code_to_phone.pop(session.pairing_code, None)
            logger.info(f"Removed pairing session for phone {phone_id}")
            return True
        return False

    def list_sessions(self) -> list[PairingSession]:
        """List all active sessions."""
        return list(self.sessions.values())


# Global instance
_pairing_manager: Optional[PairingManager] = None


def get_pairing_manager() -> PairingManager:
    """Get the global pairing manager."""
    global _pairing_manager
    if _pairing_manager is None:
        _pairing_manager = PairingManager()
    return _pairing_manager


# Endpoints

@router.post("/generate-code", response_model=PairingCodeResponse)
async def generate_pairing_code(_: bool = Depends(verify_api_key)):
    """Generate a new pairing code for phone."""
    manager = get_pairing_manager()
    code, phone_id = manager.generate_pairing_code()

    return {
        "pairing_code": code,
        "expires_in_seconds": manager.code_timeout,
        "message": f"Share this code with phone user: {code}"
    }


@router.post("/verify")
async def verify_pairing(request: dict):
    """
    Verify pairing code from phone.

    Phone sends the pairing code to complete handshake.
    """
    pairing_code = request.get("pairing_code")
    if not pairing_code:
        raise HTTPException(status_code=400, detail="pairing_code is required")

    manager = get_pairing_manager()
    phone_id = manager.verify_pairing_code(pairing_code)

    if not phone_id:
        raise HTTPException(status_code=401, detail="Invalid or expired pairing code")

    return {
        "success": True,
        "phone_id": phone_id,
        "message": "Device paired successfully"
    }


@router.get("/sessions", response_model=list[dict])
async def list_pairing_sessions(_: bool = Depends(verify_api_key)):
    """List all pairing sessions (admin only)."""
    manager = get_pairing_manager()
    sessions = manager.list_sessions()

    return [
        {
            "phone_id": s.phone_id,
            "pairing_code": s.pairing_code,
            "verified": s.verified,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "last_activity": s.last_activity
        }
        for s in sessions
    ]


@router.get("/devices")
async def get_available_devices(phone_id: str):
    """Get list of devices available to this phone."""
    manager = get_pairing_manager()
    session = manager.get_session(phone_id)

    if not session or not session.verified:
        raise HTTPException(status_code=401, detail="Phone not paired or verified")

    registry = get_agent_registry()
    agents = registry.list_agents()

    devices = [
        DeviceInfo(
            device_id=agent.device_id,
            name=agent.hostname,
            hostname=agent.hostname,
            platform=agent.platform,
            status=agent.status,
            last_seen=agent.last_heartbeat
        )
        for agent in agents
    ]

    return {
        "phone_id": phone_id,
        "device_count": len(devices),
        "devices": devices
    }


@router.post("/devices/{device_id}/execute")
async def execute_on_device(
    device_id: str,
    request: ExecuteCommandRequest,
    phone_id: str
):
    """Execute command on a device from phone."""
    manager = get_pairing_manager()
    session = manager.get_session(phone_id)

    if not session or not session.verified:
        raise HTTPException(status_code=401, detail="Phone not paired or verified")

    registry = get_agent_registry()
    result = await registry.send_command_to_agent(
        device_id,
        request.command,
        request.timeout
    )

    return result


@router.websocket("/ws/phone/{phone_id}")
async def phone_websocket(websocket: WebSocket, phone_id: str):
    """
    WebSocket connection for phone.

    Phone maintains persistent connection to receive notifications.
    """
    manager = get_pairing_manager()
    session = manager.get_session(phone_id)

    if not session:
        await websocket.close(code=1008, reason="Phone not paired")
        return

    try:
        await websocket.accept()
        session.websocket = websocket

        logger.info(f"Phone connected: {phone_id}")

        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Jarvis server",
            "phone_id": phone_id
        })

        # Main loop - listen for commands from phone
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "get_devices":
                registry = get_agent_registry()
                agents = registry.list_agents()
                devices = [
                    {
                        "device_id": agent.device_id,
                        "hostname": agent.hostname,
                        "platform": agent.platform,
                        "status": agent.status
                    }
                    for agent in agents
                ]
                await websocket.send_json({
                    "type": "devices_list",
                    "devices": devices
                })

            elif msg_type == "execute":
                device_id = data.get("device_id")
                command = data.get("command")
                request_id = data.get("request_id")

                registry = get_agent_registry()
                result = await registry.send_command_to_agent(
                    device_id,
                    command
                )

                await websocket.send_json({
                    "type": "command_response",
                    "request_id": request_id,
                    **result
                })

    except WebSocketDisconnect:
        logger.info(f"Phone disconnected: {phone_id}")

    except Exception as e:
        logger.error(f"Error with phone {phone_id}: {e}")

    finally:
        manager.remove_session(phone_id)


__all__ = ["router", "get_pairing_manager"]
