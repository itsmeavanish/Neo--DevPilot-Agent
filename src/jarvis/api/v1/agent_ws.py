"""
WebSocket handler for remote agents.

Agents connect via WebSocket to receive commands and send status updates.
"""

import json
import logging
from fastapi import APIRouter, WebSocketDisconnect, WebSocket
from jarvis.devices.agent_registry import get_agent_registry
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.agent_ws")

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/agents/{device_id}")
async def agent_websocket_endpoint(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for remote agents.

    Agent connects here and receives commands from server.
    """
    registry = get_agent_registry()

    try:
        await websocket.accept()
        logger.info(f"Agent connection attempt: {device_id}")

        # Wait for registration message
        registration_msg = await websocket.receive_text()
        reg_data = json.loads(registration_msg)

        if reg_data.get("type") != "register":
            await websocket.send_text(json.dumps({
                "error": "First message must be registration"
            }))
            await websocket.close()
            return

        # Register the agent
        hostname = reg_data.get("hostname", "unknown")
        platform = reg_data.get("platform", "unknown")

        agent = registry.register_agent(
            device_id=device_id,
            hostname=hostname,
            platform=platform,
            websocket=websocket
        )

        # Send confirmation
        await websocket.send_text(json.dumps({
            "type": "registered",
            "device_id": device_id,
            "message": f"Welcome {hostname}"
        }))

        logger.info(f"Agent {hostname} registered successfully")

        # Main message loop
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "pong":
                registry.update_heartbeat(device_id)
                logger.debug(f"Heartbeat from {hostname}")

            elif msg_type in ["result", "command_response"]:
                # Route command responses to the registry
                registry.handle_agent_response(device_id, message)
                logger.debug(f"Command response from {hostname}")

            elif msg_type == "error":
                error = message.get("error")
                logger.warning(f"Agent error from {hostname}: {error}")
                # Also route errors as responses
                registry.handle_agent_response(device_id, message)

            else:
                logger.debug(f"Unknown message from {hostname}: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"Agent disconnected: {device_id}")
        registry.unregister_agent(device_id)

    except Exception as e:
        logger.error(f"WebSocket error with agent {device_id}: {e}")
        registry.unregister_agent(device_id)
        try:
            await websocket.close()
        except:
            pass


@router.get("/agents")
async def list_agents():
    """List all connected agents."""
    registry = get_agent_registry()
    agents = registry.list_agents()
    return {
        "count": len(agents),
        "agents": [agent.to_dict() for agent in agents]
    }


@router.get("/agents/{device_id}")
async def get_agent_status(device_id: str):
    """Get status of a specific agent."""
    registry = get_agent_registry()
    agent = registry.get_agent(device_id)

    if not agent:
        return {
            "success": False,
            "error": "Agent not found"
        }

    return {
        "success": True,
        "agent": agent.to_dict()
    }


@router.post("/agents/{device_id}/execute")
async def execute_on_agent(device_id: str, request: dict):
    """Execute command on a specific agent."""
    registry = get_agent_registry()

    command = request.get("command")
    timeout = request.get("timeout", 60)

    if not command:
        return {
            "success": False,
            "error": "command is required"
        }

    result = await registry.send_command_to_agent(
        device_id,
        command,
        timeout
    )

    return result


__all__ = ["router"]
