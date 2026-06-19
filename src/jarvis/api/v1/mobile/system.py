from fastapi import APIRouter
import platform
from .models import CommandRequest, CommandResponse, SystemInfo
from .utils import run_command

router = APIRouter()

@router.get("/commands/ping", response_model=CommandResponse)
async def ping():
    """Ping endpoint to test connectivity."""
    return CommandResponse(
        status="success",
        message="pong - JARVIS backend is running"
    )

@router.post("/system/run", response_model=CommandResponse)
async def run_system_command(request: CommandRequest):
    """Execute a system command."""
    if not request.command.strip():
        return CommandResponse(status="error", message="Empty command")
    return await run_command(request.command)

@router.get("/system/info", response_model=SystemInfo)
async def get_system_info():
    """Get system information."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    return SystemInfo(
        status="ok",
        platform=platform.system(),
        platform_version=platform.version(),
        hostname=platform.node(),
        cpu_percent=cpu_percent,
        memory_total_gb=round(memory.total / (1024**3), 2),
        memory_used_gb=round(memory.used / (1024**3), 2),
        memory_percent=memory.percent,
        disk_total_gb=round(disk.total / (1024**3), 2),
        disk_used_gb=round(disk.used / (1024**3), 2),
        disk_percent=disk.percent,
    )
