"""
V1 API Router.

Main router aggregating all v1 endpoints.
"""

from fastapi import APIRouter

from jarvis.api.v1 import (
    agent, chat, tools, system, memory, self_heal,
    devices, workflows, ide, observability,
)

router = APIRouter(prefix="/api/v1")

# Include sub-routers
router.include_router(agent.router, prefix="/agent", tags=["Agent"])
router.include_router(chat.router, prefix="/agent", tags=["Chat"])
router.include_router(tools.router, prefix="/tools", tags=["Tools"])
router.include_router(system.router, prefix="/system", tags=["System"])
router.include_router(memory.router, prefix="/memory", tags=["Memory"])
router.include_router(self_heal.router, prefix="/self-heal", tags=["Self-Heal"])
router.include_router(devices.router, prefix="/devices", tags=["Devices"])
router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
router.include_router(ide.router, prefix="/ide", tags=["IDE"])
router.include_router(observability.router, prefix="/observability", tags=["Observability"])

__all__ = ["router"]
