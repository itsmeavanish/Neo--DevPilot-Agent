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
        agent = RegisteredAgent(
            device_id=device_id,
            hostname=hostname,
            platform=platform,
            registered_at=datetime.utcnow().isoformat(),
            websocket=websocket,
            status="online"
        )
        self.agents[device_id] = agent
        logger.info(f"Agent registered: {hostname} ({device_id}) on {platform}")
        return agent

    def get_agent(self, device_id: str) -> Optional[RegisteredAgent]:
        return self.agents.get(device_id)

    def list_agents(self) -> list:
        return list(self.agents.values())

    def unregister_agent(self, device_id: str) -> bool:
        if device_id in self.agents:
            agent = self.agents[device_id]
            # Cancel any pending responses
            for future in agent.pending_responses.values():
                if not future.done():
                    future.cancel()
            del self.agents[device_id]
            logger.info(f"Agent unregistered: {device_id}")
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

    async def send_command_to_agent(
        self,
        device_id: str,
        command: str,
        timeout: int = 60
    ) -> dict:
        """Send a command to an agent and wait for response."""
        agent = self.get_agent(device_id)
        if not agent:
            return {"success": False, "error": f"Agent {device_id} not found", "stdout": "", "stderr": "", "exit_code": -1}

        if agent.status != "online":
            return {"success": False, "error": f"Agent is {agent.status}", "stdout": "", "stderr": "", "exit_code": -1}

        try:
            req_id = str(uuid.uuid4())[:12]

            # Create a future for the response
            loop = asyncio.get_event_loop()
            response_future = loop.create_future()
            
            if not isinstance(agent.pending_responses, dict):
                logger.error(f"agent.pending_responses is not a dict: {type(agent.pending_responses)}")
                agent.pending_responses = {}
                
            agent.pending_responses[req_id] = response_future

            # Send command to agent
            message = {
                "type": "execute",
                "command": command,
                "timeout": timeout,
                "request_id": req_id
            }
            await agent.websocket.send_text(json.dumps(message))

            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(response_future, timeout=timeout + 5)
                self.update_heartbeat(device_id)

                # Ensure response is always a dictionary
                if isinstance(response, str):
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        return {"success": False, "error": f"Invalid JSON response: {response}", "stdout": "", "stderr": "", "exit_code": -1}

                # Ensure required fields exist
                if not isinstance(response, dict):
                    return {"success": False, "error": f"Invalid response type: {type(response)}", "stdout": "", "stderr": "", "exit_code": -1}

                # Normalize response format to match expected structure
                if "success" not in response:
                    response["success"] = response.get("type") != "error"

                return response
            except asyncio.TimeoutError:
                agent.pending_responses.pop(req_id, None)
                return {"success": False, "error": f"Command timeout after {timeout}s", "stdout": "", "stderr": "", "exit_code": -1}
            except asyncio.CancelledError:
                return {"success": False, "error": "Request cancelled", "stdout": "", "stderr": "", "exit_code": -1}

        except Exception as e:
            logger.error(f"Error sending command to agent: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e), "stdout": "", "stderr": "", "exit_code": -1}


# Global instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


__all__ = ["RegisteredAgent", "AgentRegistry", "get_agent_registry"]
