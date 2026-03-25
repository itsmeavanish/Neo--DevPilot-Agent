"""
Universal Laptop Controller API Endpoints.

Control any laptop from your phone:
- Add laptops with IP, MAC address, SSH credentials
- Wake up sleeping laptops (Wake-on-LAN)
- Execute commands via SSH or Agent
- Check laptop status
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from jarvis.devices.universal_controller import (
    get_laptop_controller,
    AccessMethod,
)
from jarvis.api.middleware.security import verify_api_key
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.laptops")

router = APIRouter(prefix="/laptops", tags=["Universal Laptops"])


# Request/Response Models

class AddLaptopRequest(BaseModel):
    """Request to add a new laptop."""
    name: str
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    mac_address: Optional[str] = None  # For Wake-on-LAN
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None


class UpdateLaptopRequest(BaseModel):
    """Request to update laptop settings."""
    name: Optional[str] = None
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None


class ExecuteRequest(BaseModel):
    """Request to execute a command."""
    command: str
    timeout: int = 60


class LaptopResponse(BaseModel):
    """Laptop information response."""
    id: str
    name: str
    ip_address: Optional[str]
    hostname: Optional[str]
    status: str
    last_seen: Optional[str]
    platform: Optional[str]
    has_ssh: bool
    has_wol: bool
    has_agent: bool


# Endpoints

@router.get("", response_model=list[LaptopResponse])
async def list_laptops(_: bool = Depends(verify_api_key)):
    """List all configured laptops."""
    controller = get_laptop_controller()
    return [LaptopResponse(**laptop.to_dict()) for laptop in controller.list_laptops()]


@router.post("", response_model=LaptopResponse)
async def add_laptop(
    request: AddLaptopRequest,
    _: bool = Depends(verify_api_key)
):
    """
    Add a new laptop to control.

    Provide at least one of:
    - ip_address: For direct connection
    - mac_address: For Wake-on-LAN capability
    - ssh_username/password: For SSH access
    """
    controller = get_laptop_controller()
    laptop = controller.add_laptop(
        name=request.name,
        ip_address=request.ip_address,
        hostname=request.hostname,
        mac_address=request.mac_address,
        ssh_username=request.ssh_username,
        ssh_password=request.ssh_password,
    )
    return LaptopResponse(**laptop.to_dict())


@router.get("/{laptop_id}", response_model=LaptopResponse)
async def get_laptop(
    laptop_id: str,
    _: bool = Depends(verify_api_key)
):
    """Get laptop details."""
    controller = get_laptop_controller()
    laptop = controller.get_laptop(laptop_id)
    if not laptop:
        raise HTTPException(status_code=404, detail="Laptop not found")
    return LaptopResponse(**laptop.to_dict())


@router.put("/{laptop_id}", response_model=LaptopResponse)
async def update_laptop(
    laptop_id: str,
    request: UpdateLaptopRequest,
    _: bool = Depends(verify_api_key)
):
    """Update laptop settings."""
    controller = get_laptop_controller()
    updates = {k: v for k, v in request.dict().items() if v is not None}
    laptop = controller.update_laptop(laptop_id, **updates)
    if not laptop:
        raise HTTPException(status_code=404, detail="Laptop not found")
    return LaptopResponse(**laptop.to_dict())


@router.delete("/{laptop_id}")
async def remove_laptop(
    laptop_id: str,
    _: bool = Depends(verify_api_key)
):
    """Remove a laptop."""
    controller = get_laptop_controller()
    if not controller.remove_laptop(laptop_id):
        raise HTTPException(status_code=404, detail="Laptop not found")
    return {"success": True, "message": "Laptop removed"}


@router.get("/{laptop_id}/status")
async def check_laptop_status(
    laptop_id: str,
    _: bool = Depends(verify_api_key)
):
    """
    Check if a laptop is online and how to access it.

    Returns:
    - status: online/offline
    - method: how the laptop can be accessed
    - wol_available: if Wake-on-LAN is configured
    """
    controller = get_laptop_controller()
    laptop = controller.get_laptop(laptop_id)
    if not laptop:
        raise HTTPException(status_code=404, detail="Laptop not found")

    status = await controller.check_laptop_status(laptop_id)
    return {
        "laptop_id": laptop_id,
        "name": laptop.name,
        **status
    }


@router.post("/{laptop_id}/wake")
async def wake_laptop(
    laptop_id: str,
    _: bool = Depends(verify_api_key)
):
    """
    Send Wake-on-LAN packet to wake up a sleeping laptop.

    Requirements:
    - MAC address must be configured for this laptop
    - Laptop must have WOL enabled in BIOS
    - For WOL over internet, router must support WOL forwarding

    Note: Laptop may take 10-30 seconds to fully wake up.
    """
    controller = get_laptop_controller()
    laptop = controller.get_laptop(laptop_id)
    if not laptop:
        raise HTTPException(status_code=404, detail="Laptop not found")

    result = await controller.wake_laptop(laptop_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{laptop_id}/execute")
async def execute_command(
    laptop_id: str,
    request: ExecuteRequest,
    _: bool = Depends(verify_api_key)
):
    """
    Execute a command on a laptop.

    Tries methods in this order:
    1. Agent (WebSocket) - if remote agent is running
    2. SSH - if SSH credentials are configured
    3. Wake-on-LAN + retry - if laptop is sleeping

    Returns command output or error.
    """
    controller = get_laptop_controller()
    laptop = controller.get_laptop(laptop_id)
    if not laptop:
        raise HTTPException(status_code=404, detail="Laptop not found")

    result = await controller.execute_on_laptop(
        laptop_id,
        request.command,
        timeout=request.timeout
    )

    return result


@router.post("/{laptop_id}/wake-and-execute")
async def wake_and_execute(
    laptop_id: str,
    request: ExecuteRequest,
    _: bool = Depends(verify_api_key)
):
    """
    Wake up a laptop and execute a command.

    This is a convenience endpoint that:
    1. Sends Wake-on-LAN packet
    2. Waits for laptop to come online (up to 60 seconds)
    3. Executes the command

    Useful for "turn on my laptop and run X" scenarios.
    """
    controller = get_laptop_controller()
    laptop = controller.get_laptop(laptop_id)
    if not laptop:
        raise HTTPException(status_code=404, detail="Laptop not found")

    # Wake up the laptop
    wake_result = await controller.wake_laptop(laptop_id)
    if not wake_result["success"]:
        raise HTTPException(status_code=400, detail=wake_result["error"])

    # Wait for it to come online
    import asyncio
    for i in range(12):  # Try for 60 seconds (12 x 5s)
        await asyncio.sleep(5)
        status = await controller.check_laptop_status(laptop_id)
        if status["status"] == "online":
            break
    else:
        return {
            "success": False,
            "error": "Laptop did not come online within 60 seconds",
            "wol_sent": True
        }

    # Execute the command
    result = await controller.execute_on_laptop(
        laptop_id,
        request.command,
        timeout=request.timeout
    )

    return {
        "wol_sent": True,
        "laptop_online": True,
        **result
    }


__all__ = ["router"]
