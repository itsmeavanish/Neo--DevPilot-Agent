"""
WebSocket handler for remote agents.

Agents connect via WebSocket to receive commands and send status updates.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocketDisconnect, WebSocket
from pydantic import BaseModel, Field

from jarvis.devices.agent_registry import get_agent_registry
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.agent_ws")

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _norm_id(device_id: str) -> str:
    return device_id.strip().upper()


@router.websocket("/agents/{device_id}")
async def agent_websocket_endpoint(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for remote agents.

    Agent connects here and receives commands from server.
    """
    registry = get_agent_registry()
    did = _norm_id(device_id)

    try:
        await websocket.accept()
        logger.info(f"Agent connection attempt: {did} (path={device_id!r})")

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
            device_id=did,
            hostname=hostname,
            platform=platform,
            websocket=websocket
        )

        # Send confirmation with HMAC secret for message signing
        await websocket.send_text(json.dumps({
            "type": "registered",
            "device_id": did,
            "message": f"Welcome {hostname}",
            "session_token": agent.session_token,
            "hmac_secret": agent.hmac_secret,
            "capabilities": ["shell", "read_fs", "write_fs", "git", "network"]
        }))

        logger.info(f"Agent {hostname} registered successfully (HMAC enabled)")

        # Main message loop
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # HMAC verification for signed messages
            if agent.hmac_secret and message.get("_hmac_signature"):
                from jarvis.security.hmac_auth import verify_message
                valid, reason = verify_message(message, agent.hmac_secret)
                if not valid:
                    logger.warning(f"HMAC verification failed for {hostname}: {reason}")
                    if reason != "missing_hmac_fields":
                        continue  # drop messages with bad signatures
            elif agent.hmac_secret and not message.get("_hmac_signature"):
                # Backward-compatible: warn but accept unsigned messages during transition
                logger.debug(f"Unsigned message from {hostname} (HMAC not enforced yet)")

            msg_type = message.get("type")

            if msg_type == "pong":
                registry.update_heartbeat(did)
                logger.debug(f"Heartbeat from {hostname}")

            elif msg_type in [
                "result",
                "command_response",
                "file_content",
                "file_result",
                "directory_listing",
                "project_info_result",
                "telemetry_result",
                "search_result",
            ]:
                registry.handle_agent_response(did, message)
                logger.debug(f"Command response from {hostname}")

            elif msg_type == "error":
                error = message.get("error")
                logger.warning(f"Agent error from {hostname}: {error}")
                registry.handle_agent_response(did, message)

            else:
                logger.debug(f"Unknown message from {hostname}: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"Agent disconnected: {did}")
        current_agent = registry.get_agent(did)
        if current_agent and current_agent.websocket == websocket:
            registry.unregister_agent(did)

    except Exception as e:
        logger.error(f"WebSocket error with agent {did}: {e}")
        current_agent = registry.get_agent(did)
        if current_agent and current_agent.websocket == websocket:
            registry.unregister_agent(did)
        try:
            await websocket.close()
        except Exception as close_err:
            logger.debug("WebSocket close after error: %s", close_err)


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
    agent = registry.get_agent(_norm_id(device_id))

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
        device_id.strip().upper(),
        command,
        timeout
    )

    return result


class FsListBody(BaseModel):
    path: str
    show_hidden: bool = False


class FsReadBody(BaseModel):
    path: str
    max_lines: int = Field(default=500, ge=1, le=50_000)


class FsWriteBody(BaseModel):
    path: str
    content: str
    create_backup: bool = True


class FsInfoBody(BaseModel):
    path: str


def _agent_unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=503, detail=detail)


@router.post("/agents/{device_id}/fs/list")
async def agent_fs_list(device_id: str, body: FsListBody) -> dict[str, Any]:
    """List a directory on the paired laptop (remote agent filesystem)."""
    registry = get_agent_registry()
    did = _norm_id(device_id)
    raw = await registry.send_agent_request(
        did,
        {
            "type": "directory_list",
            "path": body.path,
            "show_hidden": body.show_hidden,
        },
        wait_timeout=120,
    )
    if raw.get("_offline"):
        raise _agent_unavailable(
            "Paired laptop is offline or the agent is not connected. Open the agent on that PC."
        )
    if not raw.get("success"):
        err = raw.get("error") or "Directory listing failed"
        return {
            "path": body.path,
            "files": [],
            "count": 0,
            "error": err,
        }
    files = raw.get("files") or []
    return {
        "path": raw.get("path") or body.path,
        "files": files,
        "count": int(raw.get("count") if raw.get("count") is not None else len(files)),
        "error": raw.get("error"),
    }


@router.post("/agents/{device_id}/fs/read")
async def agent_fs_read(device_id: str, body: FsReadBody) -> dict[str, Any]:
    """Read a text file on the paired laptop (remote agent filesystem)."""
    registry = get_agent_registry()
    did = _norm_id(device_id)
    raw = await registry.send_agent_request(
        did,
        {
            "type": "file_read",
            "path": body.path,
            "max_lines": body.max_lines,
        },
        wait_timeout=120,
    )
    if raw.get("_offline"):
        raise _agent_unavailable(
            "Paired laptop is offline or the agent is not connected. Open the agent on that PC."
        )
    if not raw.get("success"):
        return {
            "path": body.path,
            "content": "",
            "lines": 0,
            "language": "text",
            "size": 0,
            "error": raw.get("error") or "Failed to read file",
        }
    return {
        "path": raw.get("path") or body.path,
        "content": raw.get("content") or "",
        "lines": int(raw.get("lines") or 0),
        "language": raw.get("language") or "text",
        "size": int(raw.get("size") or 0),
        "error": raw.get("error"),
    }


@router.post("/agents/{device_id}/fs/write")
async def agent_fs_write(device_id: str, body: FsWriteBody) -> dict[str, Any]:
    """Write a text file on the paired laptop (remote agent filesystem)."""
    registry = get_agent_registry()
    did = _norm_id(device_id)
    raw = await registry.send_agent_request(
        did,
        {
            "type": "file_write",
            "path": body.path,
            "content": body.content,
            "create_backup": body.create_backup,
        },
        wait_timeout=120,
    )
    if raw.get("_offline"):
        raise _agent_unavailable(
            "Paired laptop is offline or the agent is not connected. Open the agent on that PC."
        )
    if not raw.get("success"):
        return {
            "success": False,
            "path": body.path,
            "message": raw.get("error") or "Failed to write file",
            "backup_path": raw.get("backup_path"),
        }
    return {
        "success": True,
        "path": raw.get("path") or body.path,
        "message": raw.get("message") or "File saved successfully",
        "backup_path": raw.get("backup_path"),
        "bytes_written": int(raw.get("bytes_written") or 0),
    }


@router.post("/agents/{device_id}/fs/info")
async def agent_fs_info(device_id: str, body: FsInfoBody) -> dict[str, Any]:
    """Project/folder metadata on the paired laptop."""
    registry = get_agent_registry()
    did = _norm_id(device_id)
    raw = await registry.send_agent_request(
        did,
        {"type": "project_info", "path": body.path},
        wait_timeout=120,
    )
    if raw.get("_offline"):
        raise _agent_unavailable(
            "Paired laptop is offline or the agent is not connected. Open the agent on that PC."
        )
    if not raw.get("success"):
        return {
            "path": body.path,
            "name": "",
            "type": "Unknown",
            "code_files": 0,
            "has_git": False,
            "has_package_json": False,
            "has_requirements": False,
            "error": raw.get("error") or "Failed to read project info",
        }
    return {
        "path": raw.get("path") or body.path,
        "name": raw.get("name") or "",
        "type": raw.get("project_type") or raw.get("type") or "Unknown",
        "code_files": int(raw.get("code_files") or 0),
        "has_git": bool(raw.get("has_git")),
        "has_package_json": bool(raw.get("has_package_json")),
        "has_requirements": bool(raw.get("has_requirements")),
        "error": raw.get("error"),
    }


class FsSearchBody(BaseModel):
    query: str
    path: str
    max_results: int = Field(default=50, ge=1, le=500)
    case_sensitive: bool = False
    file_pattern: str | None = None


@router.post("/agents/{device_id}/fs/search")
async def agent_fs_search(device_id: str, body: FsSearchBody) -> dict[str, Any]:
    """Search files on the paired laptop for a text pattern."""
    registry = get_agent_registry()
    did = _norm_id(device_id)
    raw = await registry.send_agent_request(
        did,
        {
            "type": "file_search",
            "query": body.query,
            "path": body.path,
            "max_results": body.max_results,
            "case_sensitive": body.case_sensitive,
            "file_pattern": body.file_pattern,
        },
        wait_timeout=120,
    )
    if raw.get("_offline"):
        raise _agent_unavailable(
            "Paired laptop is offline or the agent is not connected."
        )
    if not raw.get("success"):
        return {
            "results": [],
            "total_matches": 0,
            "error": raw.get("error") or "Search failed",
        }
    return {
        "results": raw.get("results") or [],
        "total_matches": int(raw.get("total_matches") or 0),
        "error": raw.get("error"),
    }


__all__ = ["router"]
