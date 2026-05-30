"""
Agent Registration and Connection Management.

When remote agents connect via WebSocket, they register themselves.
Phone can then communicate with these agents.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.devices.agent_registry")


def normalize_agent_device_id(device_id: str) -> str:
    """Pairing codes are case-insensitive; registry keys are always uppercased."""
    return (device_id or "").strip().upper()


@dataclass
class RegisteredAgent:
    """A registered remote agent (laptop/desktop)."""
    device_id: str
    hostname: str
    platform: str
    registered_at: str
    last_heartbeat: Optional[str] = None
    websocket: Any = None
    status: str = "online"
    metadata: Dict = field(default_factory=dict)
    # Store pending command responses
    pending_responses: Dict[str, asyncio.Future] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "hostname": self.hostname,
            "platform": self.platform,
            "status": self.status,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }


class AgentRegistry:
    """Registry of all connected remote agents."""

    def __init__(self):
        self.agents: Dict[str, RegisteredAgent] = {}

    def register_agent(
        self,
        device_id: str,
        hostname: str,
        platform: str,
        websocket
    ) -> RegisteredAgent:
        did = normalize_agent_device_id(device_id)

        # If there is already an agent connection, proactively close the old websocket
        if did in self.agents:
            old_agent = self.agents[did]
            logger.info(f"Closing old agent connection for {did} before registering new one")
            try:
                # websocket.close() is async, schedule it as a task on the running loop
                asyncio.create_task(old_agent.websocket.close())
            except Exception as e:
                logger.warning(f"Error closing old websocket for {did}: {e}")

        agent = RegisteredAgent(
            device_id=did,
            hostname=hostname,
            platform=platform,
            registered_at=datetime.utcnow().isoformat(),
            websocket=websocket,
            status="online"
        )
        self.agents[did] = agent
        logger.info(f"Agent registered: {hostname} ({did}) on {platform}")
        return agent

    def get_agent(self, device_id: str) -> Optional[RegisteredAgent]:
        did = normalize_agent_device_id(device_id)
        return self.agents.get(did)

    def list_agents(self) -> list:
        return list(self.agents.values())

    def unregister_agent(self, device_id: str) -> bool:
        did = normalize_agent_device_id(device_id)
        if did in self.agents:
            agent = self.agents[did]
            # Cancel any pending responses
            for future in agent.pending_responses.values():
                if not future.done():
                    future.cancel()
            del self.agents[did]
            logger.info(f"Agent unregistered: {did}")
            return True
        return False

    def update_heartbeat(self, device_id: str) -> bool:
        agent = self.get_agent(device_id)
        if agent:
            agent.last_heartbeat = datetime.utcnow().isoformat()
            return True
        return False

    def handle_agent_response(self, device_id: str, response):
        """Handle a response from an agent (called by websocket handler)."""
        # Handle case where response is a string instead of dict
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response from agent: {response}")
                return

        agent = self.get_agent(device_id)
        if not agent:
            return

        request_id = response.get("request_id")
        if request_id and request_id in agent.pending_responses:
            future = agent.pending_responses.pop(request_id)
            if not future.done():
                future.set_result(response)

    async def send_agent_request(
        self,
        device_id: str,
        payload: dict,
        wait_timeout: Optional[int] = None,
    ) -> dict:
        """
        Send a typed WebSocket message to an agent and wait for the matching response.

        payload must include \"type\". request_id is assigned here — do not pass it.
        """
        agent = self.get_agent(device_id)
        if not agent:
            return {"success": False, "error": f"Agent {device_id} not found", "_offline": True}

        if agent.status != "online":
            return {"success": False, "error": f"Agent is {agent.status}", "_offline": True}

        msg_type = payload.get("type")
        if wait_timeout is None:
            if msg_type == "execute":
                wait_timeout = int(payload.get("timeout", 60)) + 10
            else:
                wait_timeout = 120

        try:
            req_id = str(uuid.uuid4())[:12]
            loop = asyncio.get_event_loop()
            response_future = loop.create_future()

            if not isinstance(agent.pending_responses, dict):
                logger.error("agent.pending_responses is not a dict: %s", type(agent.pending_responses))
                agent.pending_responses = {}

            agent.pending_responses[req_id] = response_future

            message = {**payload, "request_id": req_id}
            await agent.websocket.send_text(json.dumps(message))

            try:
                response = await asyncio.wait_for(response_future, timeout=wait_timeout)
                self.update_heartbeat(device_id)

                if isinstance(response, str):
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        return {"success": False, "error": f"Invalid JSON response: {response}"}

                if not isinstance(response, dict):
                    return {"success": False, "error": f"Invalid response type: {type(response)}"}

                if "success" not in response:
                    response["success"] = response.get("type") != "error"

                return response
            except asyncio.TimeoutError:
                agent.pending_responses.pop(req_id, None)
                return {"success": False, "error": f"Agent request timeout after {wait_timeout}s"}
            except asyncio.CancelledError:
                return {"success": False, "error": "Request cancelled"}

        except Exception as e:
            logger.error("Error sending message to agent: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

    async def send_command_to_agent(
        self,
        device_id: str,
        command: str,
        timeout: int = 60
    ) -> dict:
        """Send a shell command to an agent and wait for response."""
        response = await self.send_agent_request(
            device_id,
            {"type": "execute", "command": command, "timeout": timeout},
            wait_timeout=timeout + 10,
        )

        if response.get("_offline"):
            return {
                "success": False,
                "error": response.get("error", "Agent unavailable"),
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

        if not isinstance(response, dict):
            return {
                "success": False,
                "error": f"Invalid response type: {type(response)}",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

        if "success" not in response:
            response["success"] = response.get("type") != "error"

        return response


# Global instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


__all__ = ["RegisteredAgent", "AgentRegistry", "get_agent_registry", "normalize_agent_device_id"]
