from fastapi import APIRouter
from . import system, fs, git, ide, ai, agent_stream

router = APIRouter()

router.include_router(system.router, tags=["Mobile - System"])
router.include_router(fs.router, tags=["Mobile - File System"])
router.include_router(git.router, tags=["Mobile - Git"])
router.include_router(ide.router, tags=["Mobile - IDE"])
router.include_router(ai.router, tags=["Mobile - AI"])
router.include_router(agent_stream.router, tags=["Mobile - Agent"])

__all__ = ["router"]
