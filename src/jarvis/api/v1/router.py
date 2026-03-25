"""
V1 API Router.

Main router aggregating all v1 endpoints.
"""

from fastapi import APIRouter

from jarvis.api.v1 import (
    agent, tools, system, memory, self_heal,
    devices, workflows, ide, observability,
    agent_ws, pairing,
)

router = APIRouter(prefix="/api/v1")

# Include sub-routers
router.include_router(agent.router, prefix="/agent", tags=["Agent"])
router.include_router(tools.router, prefix="/tools", tags=["Tools"])
router.include_router(system.router, prefix="/system", tags=["System"])
router.include_router(memory.router, prefix="/memory", tags=["Memory"])
router.include_router(self_heal.router, prefix="/self-heal", tags=["Self-Heal"])
router.include_router(devices.router, prefix="/devices", tags=["Devices"])
router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
router.include_router(ide.router, prefix="/ide", tags=["IDE"])
router.include_router(observability.router, prefix="/observability", tags=["Observability"])

# New routers for remote agents and phone pairing
router.include_router(agent_ws.router)
router.include_router(pairing.router, prefix="/pairing", tags=["Pairing"])

__all__ = ["router"]
