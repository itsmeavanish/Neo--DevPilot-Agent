"""
Device API endpoints.

Endpoints for device registration, management, and task distribution.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from jarvis.devices.registry import get_device_registry
from jarvis.devices.distributor import get_task_distributor, LoadBalanceStrategy
from jarvis.devices.protocol import DeviceProtocol, DeviceMessage
from jarvis.devices.models.device import Device, DeviceCapabilities

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class DeviceRegistration(BaseModel):
    """Request to register a device."""
    name: str = Field(..., description="Device name")
    device_type: str = Field(default="desktop", description="Device type")
    role: str = Field(default="worker", description="Device role")
    host: str = Field(default="localhost", description="Device host")
    port: int = Field(default=8765, description="Device port")
    platform: str = Field(default="unknown", description="Platform")
    capabilities: dict[str, Any] | None = Field(default=None, description="Device capabilities")
    tags: list[str] = Field(default_factory=list, description="Device tags")


class DeviceResponse(BaseModel):
    """Device information response."""
    id: str
    name: str
    device_type: str
    role: str
    status: str
    host: str
    port: int
    platform: str
    is_available: bool
    capabilities: dict[str, Any]
    metrics: dict[str, Any]
    tags: list[str]


class TaskRequest(BaseModel):
    """Request to distribute a task."""
    tool_name: str = Field(..., description="Tool to execute")
    params: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority")
    target_device: str | None = Field(default=None, description="Specific device to target")
    timeout: float | None = Field(default=None, description="Task timeout in seconds")


class TaskResponse(BaseModel):
    """Task distribution response."""
    success: bool
    task_id: str
    device_id: str | None
    device_name: str | None
    error: str | None
    queued: bool


class StrategyRequest(BaseModel):
    """Request to set load balancing strategy."""
    strategy: str = Field(..., description="Strategy name")


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def get_registry():
    return get_device_registry()


def get_distributor():
    return get_task_distributor()


# ═══════════════════════════════════════════════════════════════
# Device Management Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=list[DeviceResponse])
async def list_devices(
    status: str | None = Query(default=None, description="Filter by status"),
    role: str | None = Query(default=None, description="Filter by role"),
    available_only: bool = Query(default=False, description="Only available devices"),
):
    """
    List all registered devices.
    """
    registry = get_registry()
    devices = registry.get_all()

    # Apply filters
    if status:
        devices = [d for d in devices if d.status.value == status]
    if role:
        devices = [d for d in devices if d.role.value == role]
    if available_only:
        devices = [d for d in devices if d.is_available]

    return [d.to_dict() for d in devices]


@router.get("/local", response_model=DeviceResponse)
async def get_local_device():
    """
    Get information about the local device.
    """
    registry = get_registry()
    if not registry.local_device:
        raise HTTPException(status_code=500, detail="Local device not initialized")

    return registry.local_device.to_dict()


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str):
    """
    Get information about a specific device.
    """
    registry = get_registry()
    device = registry.get(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device.to_dict()


@router.post("/register", response_model=DeviceResponse)
async def register_device(registration: DeviceRegistration):
    """
    Register a new device with the orchestrator.
    """
    registry = get_registry()

    # Build capabilities
    caps = DeviceCapabilities()
    if registration.capabilities:
        caps = DeviceCapabilities.from_dict(registration.capabilities)

    device = Device(
        name=registration.name,
        device_type=registration.device_type,
        role=registration.role,
        host=registration.host,
        port=registration.port,
        platform=registration.platform,
        capabilities=caps,
        tags=registration.tags,
    )

    registry.register(device)
    return device.to_dict()


@router.delete("/{device_id}")
async def unregister_device(device_id: str):
    """
    Unregister a device from the orchestrator.
    """
    registry = get_registry()

    if not registry.unregister(device_id):
        raise HTTPException(status_code=404, detail="Device not found or cannot be removed")

    return {"removed": device_id}


@router.post("/{device_id}/heartbeat")
async def device_heartbeat(device_id: str, metrics: dict[str, Any] | None = None):
    """
    Update device heartbeat and optionally metrics.
    """
    registry = get_registry()

    if not registry.update_heartbeat(device_id):
        raise HTTPException(status_code=404, detail="Device not found")

    if metrics:
        registry.update_metrics(device_id, metrics)

    return {"acknowledged": True}


# ═══════════════════════════════════════════════════════════════
# Task Distribution Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/tasks/distribute", response_model=TaskResponse)
async def distribute_task(request: TaskRequest):
    """
    Distribute a task to the best available device.
    """
    distributor = get_distributor()

    result = await distributor.distribute(
        tool_name=request.tool_name,
        params=request.params,
        priority=request.priority,
        target_device=request.target_device,
        timeout=request.timeout,
    )

    return result.to_dict()


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """
    Get task status and result.
    """
    distributor = get_distributor()
    task = distributor.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()


@router.get("/tasks")
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by status"),
    device_id: str | None = Query(default=None, description="Filter by device"),
):
    """
    List all active tasks.
    """
    distributor = get_distributor()
    tasks = distributor.get_active_tasks()

    if status:
        tasks = [t for t in tasks if t.status == status]
    if device_id:
        tasks = [t for t in tasks if t.device_id == device_id]

    return [t.to_dict() for t in tasks]


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a task.
    """
    distributor = get_distributor()

    if not await distributor.cancel_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found or already completed")

    return {"cancelled": task_id}


# ═══════════════════════════════════════════════════════════════
# Configuration Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/config/strategy")
async def get_strategy():
    """
    Get current load balancing strategy.
    """
    distributor = get_distributor()
    return {
        "strategy": distributor.strategy.value,
        "available": [s.value for s in LoadBalanceStrategy],
    }


@router.post("/config/strategy")
async def set_strategy(request: StrategyRequest):
    """
    Set load balancing strategy.
    """
    distributor = get_distributor()

    try:
        strategy = LoadBalanceStrategy(request.strategy)
        distributor.set_strategy(strategy)
        return {"strategy": strategy.value}
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy. Available: {[s.value for s in LoadBalanceStrategy]}",
        )


# ═══════════════════════════════════════════════════════════════
# WebSocket Endpoint
# ═══════════════════════════════════════════════════════════════

# Track active connections
_ws_connections: dict[str, WebSocket] = {}


@router.websocket("/ws/{device_id}")
async def device_websocket(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for real-time device communication.
    """
    await websocket.accept()
    _ws_connections[device_id] = websocket

    registry = get_registry()
    protocol = DeviceProtocol(registry)

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = DeviceMessage.from_json(data)

            # Handle message
            response = await protocol.handle_message(message)

            # Send response if any
            if response:
                response.sender_id = registry.local_device.id if registry.local_device else "controller"
                await websocket.send_text(response.to_json())

    except WebSocketDisconnect:
        _ws_connections.pop(device_id, None)
        device = registry.get(device_id)
        if device:
            device.set_offline()

    except Exception as e:
        _ws_connections.pop(device_id, None)
        device = registry.get(device_id)
        if device:
            device.set_offline()


async def send_to_device(device_id: str, message: DeviceMessage) -> bool:
    """Send a message to a device via WebSocket."""
    if device_id in _ws_connections:
        try:
            websocket = _ws_connections[device_id]
            await websocket.send_text(message.to_json())
            return True
        except Exception:
            return False
    return False


# Wire up send function
distributor = get_task_distributor()
distributor.set_send_function(send_to_device)


__all__ = ["router"]
