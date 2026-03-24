"""
Device Management API Endpoints.

Endpoints for managing multiple devices (laptops) from the mobile app.
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel

from jarvis.devices.multi_device import (
    Device,
    DeviceStatus,
    DeviceRegistry,
    get_device_registry,
)
from jarvis.api.middleware.security import verify_api_key
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.devices")

router = APIRouter(prefix="/devices", tags=["Devices"])


# Request/Response Models

class RegisterDeviceRequest(BaseModel):
    """Request to register a new device."""
    name: str
    capabilities: list[str] = ["shell", "file", "git"]


class DeviceResponse(BaseModel):
    """Device info response (without token)."""
    id: str
    name: str
    status: str
    hostname: Optional[str]
    platform: Optional[str]
    last_seen: Optional[str]
    capabilities: list[str]


class DeviceWithTokenResponse(DeviceResponse):
    """Device info with token (only shown once on registration)."""
    token: str


class ExecuteCommandRequest(BaseModel):
    """Request to execute a command on a device."""
    command: str
    timeout: int = 120


class CommandResultResponse(BaseModel):
    """Command execution result."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    error: Optional[str] = None


# Active WebSocket connections
active_connections: dict[str, WebSocket] = {}
pending_requests: dict[str, asyncio.Future] = {}


# API Endpoints

@router.get("", response_model=list[DeviceResponse])
async def list_devices(_: bool = Depends(verify_api_key)):
    """List all registered devices."""
    registry = get_device_registry()
    devices = registry.list_devices()
    return [
        DeviceResponse(
            id=d.id,
            name=d.name,
            status=d.status.value,
            hostname=d.hostname,
            platform=d.platform,
            last_seen=d.last_seen,
            capabilities=d.capabilities,
        )
        for d in devices
    ]


@router.post("", response_model=DeviceWithTokenResponse)
async def register_device(
    request: RegisterDeviceRequest,
    _: bool = Depends(verify_api_key),
):
    """
    Register a new device (laptop).

    Returns the device token - save this! It's only shown once.
    """
    registry = get_device_registry()
    device = registry.register_device(
        name=request.name,
        capabilities=request.capabilities,
    )

    return DeviceWithTokenResponse(
        id=device.id,
        name=device.name,
        status=device.status.value,
        hostname=device.hostname,
        platform=device.platform,
        last_seen=device.last_seen,
        capabilities=device.capabilities,
        token=device.token,
    )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    _: bool = Depends(verify_api_key),
):
    """Get device details."""
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse(
        id=device.id,
        name=device.name,
        status=device.status.value,
        hostname=device.hostname,
        platform=device.platform,
        last_seen=device.last_seen,
        capabilities=device.capabilities,
    )


@router.delete("/{device_id}")
async def delete_device(
    device_id: str,
    _: bool = Depends(verify_api_key),
):
    """Delete a device."""
    registry = get_device_registry()

    if not registry.delete_device(device_id):
        raise HTTPException(status_code=404, detail="Device not found")

    # Disconnect if connected
    if device_id in active_connections:
        await active_connections[device_id].close()
        del active_connections[device_id]

    return {"success": True, "message": f"Device {device_id} deleted"}


@router.post("/{device_id}/rotate-token")
async def rotate_device_token(
    device_id: str,
    _: bool = Depends(verify_api_key),
):
    """
    Generate a new token for a device.

    Use this if you think the token was compromised.
    The old token will stop working immediately.
    """
    registry = get_device_registry()
    new_token = registry.rotate_token(device_id)

    if not new_token:
        raise HTTPException(status_code=404, detail="Device not found")

    # Disconnect the device (it needs to reconnect with new token)
    if device_id in active_connections:
        await active_connections[device_id].close()
        del active_connections[device_id]

    return {"success": True, "token": new_token, "message": "Token rotated. Update the agent with the new token."}


@router.post("/{device_id}/execute", response_model=CommandResultResponse)
async def execute_on_device(
    device_id: str,
    request: ExecuteCommandRequest,
    _: bool = Depends(verify_api_key),
):
    """
    Execute a command on a specific device.

    The device must be online (agent running).
    """
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device_id not in active_connections:
        raise HTTPException(
            status_code=503,
            detail=f"Device '{device.name}' is offline. Start the agent on that machine.",
        )

    # Send command to device
    ws = active_connections[device_id]
    request_id = f"req_{asyncio.get_event_loop().time()}"

    try:
        # Create a future for the response
        future = asyncio.get_event_loop().create_future()
        pending_requests[request_id] = future

        # Send command
        await ws.send_json({
            "type": "execute",
            "command": request.command,
            "timeout": request.timeout,
            "request_id": request_id,
        })

        # Wait for response with timeout
        result = await asyncio.wait_for(future, timeout=request.timeout + 5)

        return CommandResultResponse(
            success=result.get("success", False),
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            exit_code=result.get("exit_code", -1),
            error=result.get("error"),
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pending_requests.pop(request_id, None)


@router.get("/{device_id}/status")
async def get_device_status(
    device_id: str,
    _: bool = Depends(verify_api_key),
):
    """Get real-time status of a device."""
    registry = get_device_registry()
    device = registry.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    is_online = device_id in active_connections

    return {
        "device_id": device_id,
        "name": device.name,
        "online": is_online,
        "status": "online" if is_online else "offline",
        "last_seen": device.last_seen,
    }


# WebSocket endpoint for agent connections

@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for remote agents.

    Agents connect here and receive commands from the mobile app.
    """
    # Get device token from headers
    device_token = websocket.headers.get("x-device-token")

    if not device_token:
        await websocket.close(code=4001, reason="Device token required")
        return

    # Validate device
    registry = get_device_registry()
    device = registry.get_device_by_token(device_token)

    if not device:
        await websocket.close(code=4003, reason="Invalid device token")
        return

    # Accept connection
    await websocket.accept()
    device_id = device.id
    active_connections[device_id] = websocket

    # Update device status
    registry.update_device_status(
        device_id,
        DeviceStatus.ONLINE,
        hostname=websocket.headers.get("x-device-hostname"),
        platform=websocket.headers.get("x-device-platform"),
    )

    logger.info(f"Device connected: {device.name} ({device_id})")

    try:
        while True:
            # Receive messages from agent
            data = await websocket.receive_json()
            msg_type = data.get("type")
            request_id = data.get("request_id")

            if msg_type == "status":
                # Agent sending status update
                registry.update_device_status(device_id, DeviceStatus.ONLINE)
                logger.debug(f"Status update from {device.name}")

            elif msg_type == "result" and request_id:
                # Agent sending command result
                if request_id in pending_requests:
                    pending_requests[request_id].set_result(data)

            elif msg_type == "pong":
                # Ping response
                pass

    except WebSocketDisconnect:
        logger.info(f"Device disconnected: {device.name} ({device_id})")
    except Exception as e:
        logger.error(f"WebSocket error for {device.name}: {e}")
    finally:
        # Clean up
        active_connections.pop(device_id, None)
        registry.update_device_status(device_id, DeviceStatus.OFFLINE)


__all__ = ["router"]
