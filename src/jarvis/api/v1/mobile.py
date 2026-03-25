"""
Mobile API endpoints.

Compatibility layer for the React Native/Expo frontend.
Maps mobile app API calls to JARVIS backend functionality.
"""

import os
import platform
import subprocess
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class CommandRequest(BaseModel):
    """Shell command request."""
    command: str


class CommandResponse(BaseModel):
    """Command execution response."""
    status: str  # 'success', 'error', 'info'
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    message: Optional[str] = None


class SystemInfo(BaseModel):
    """System information."""
    status: str
    platform: str
    platform_version: str
    hostname: str
    cpu_percent: Optional[float] = None
    memory_total_gb: Optional[float] = None
    memory_used_gb: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_percent: Optional[float] = None


class DirectoryRequest(BaseModel):
    """Directory listing request."""
    path: str
    show_hidden: bool = False


class FileInfo(BaseModel):
    """File information."""
    name: str
    path: str
    is_dir: bool
    size: int
    extension: str


class DirectoryListing(BaseModel):
    """Directory listing response."""
    path: str
    files: list[FileInfo]
    count: int
    error: Optional[str] = None


class FileReadRequest(BaseModel):
    """File read request."""
    path: str
    max_lines: int = 500


class FileContent(BaseModel):
    """File content response."""
    path: str
    content: str
    lines: int
    language: str
    size: int
    error: Optional[str] = None


class ProjectInfoRequest(BaseModel):
    """Project info request."""
    path: str


class ProjectInfo(BaseModel):
    """Project information."""
    path: str
    name: str
    type: str
    code_files: int
    has_git: bool
    has_package_json: bool
    has_requirements: bool
    error: Optional[str] = None


class OpenPathRequest(BaseModel):
    """Open path request."""
    path: str


class AIProviderStatus(BaseModel):
    """AI provider status."""
    available: bool
    message: str
    selected: bool


class AIProvidersResponse(BaseModel):
    """AI providers response."""
    current: str
    providers: dict


class SetProviderRequest(BaseModel):
    """Set AI provider request."""
    provider: str


class AIAskRequest(BaseModel):
    """AI ask request."""
    prompt: str
    code_context: Optional[str] = None
    file_path: Optional[str] = None
    language: Optional[str] = None


class AIResponse(BaseModel):
    """AI response."""
    status: str
    response: str
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

async def run_command(command: str, timeout: int = 30) -> CommandResponse:
    """Execute a shell command."""
    try:
        if platform.system() == "Windows":
            shell = True
            executable = None
        else:
            shell = True
            executable = "/bin/bash"

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=shell,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

            return CommandResponse(
                status="success" if process.returncode == 0 else "error",
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode,
                message="Command executed successfully" if process.returncode == 0 else "Command failed"
            )
        except asyncio.TimeoutError:
            process.kill()
            return CommandResponse(
                status="error",
                message=f"Command timed out after {timeout}s",
                exit_code=-1
            )
    except Exception as e:
        return CommandResponse(
            status="error",
            message=str(e),
            exit_code=-1
        )


def get_file_extension(filename: str) -> str:
    """Get file extension."""
    ext = os.path.splitext(filename)[1]
    return ext if ext else ""


def detect_language(path: str) -> str:
    """Detect file language from extension."""
    ext = get_file_extension(path).lower()
    languages = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.json': 'json',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.sh': 'shell',
        '.bash': 'shell',
        '.sql': 'sql',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.rb': 'ruby',
        '.php': 'php',
        '.txt': 'text',
    }
    return languages.get(ext, 'text')


def detect_project_type(path: str) -> str:
    """Detect project type from files."""
    p = Path(path)

    if (p / 'package.json').exists():
        return 'Node.js'
    elif (p / 'requirements.txt').exists() or (p / 'pyproject.toml').exists():
        return 'Python'
    elif (p / 'go.mod').exists():
        return 'Go'
    elif (p / 'Cargo.toml').exists():
        return 'Rust'
    elif (p / 'pom.xml').exists():
        return 'Java/Maven'
    elif (p / 'build.gradle').exists():
        return 'Java/Gradle'
    elif (p / '.csproj').exists():
        return 'C#/.NET'
    else:
        return 'Unknown'


# ═══════════════════════════════════════════════════════════════
# Commands Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/commands/ping", response_model=CommandResponse)
async def ping():
    """Ping endpoint to test connectivity."""
    return CommandResponse(
        status="success",
        message="pong - JARVIS backend is running"
    )


# ═══════════════════════════════════════════════════════════════
# System Endpoints
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
# Git Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/git/run", response_model=CommandResponse)
async def run_git_command(request: CommandRequest):
    """Execute a git command."""
    cmd = request.command.strip()
    if not cmd.lower().startswith('git'):
        cmd = f"git {cmd}"
    return await run_command(cmd)


# ═══════════════════════════════════════════════════════════════
# VS Code Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/vscode/open", response_model=CommandResponse)
async def open_vscode():
    """Launch VS Code."""
    if platform.system() == "Windows":
        cmd = "code"
    else:
        cmd = "code"
    return await run_command(cmd)


@router.post("/vscode/open-project", response_model=CommandResponse)
async def open_vscode_project(request: OpenPathRequest):
    """Open a project in VS Code."""
    path = request.path
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    cmd = f'code "{path}"'
    return await run_command(cmd)


# ═══════════════════════════════════════════════════════════════
# Project/Files Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/project/list", response_model=DirectoryListing)
async def list_directory(request: DirectoryRequest):
    """List directory contents."""
    path = request.path

    # Handle Windows paths
    if platform.system() == "Windows" and path.startswith("~"):
        path = os.path.expanduser(path)

    if not os.path.exists(path):
        return DirectoryListing(
            path=path,
            files=[],
            count=0,
            error=f"Path not found: {path}"
        )

    if not os.path.isdir(path):
        return DirectoryListing(
            path=path,
            files=[],
            count=0,
            error=f"Not a directory: {path}"
        )

    try:
        entries = os.listdir(path)
        files = []

        for entry in sorted(entries):
            # Skip hidden files unless requested
            if entry.startswith('.') and not request.show_hidden:
                continue

            full_path = os.path.join(path, entry)
            try:
                is_dir = os.path.isdir(full_path)
                size = 0 if is_dir else os.path.getsize(full_path)
                ext = "" if is_dir else get_file_extension(entry)

                files.append(FileInfo(
                    name=entry,
                    path=full_path,
                    is_dir=is_dir,
                    size=size,
                    extension=ext
                ))
            except (PermissionError, OSError):
                continue

        # Sort: directories first, then files
        files.sort(key=lambda f: (not f.is_dir, f.name.lower()))

        return DirectoryListing(
            path=os.path.abspath(path),
            files=files,
            count=len(files)
        )
    except PermissionError:
        return DirectoryListing(
            path=path,
            files=[],
            count=0,
            error="Permission denied"
        )
    except Exception as e:
        return DirectoryListing(
            path=path,
            files=[],
            count=0,
            error=str(e)
        )


@router.post("/project/read", response_model=FileContent)
async def read_file(request: FileReadRequest):
    """Read file contents."""
    path = request.path

    if not os.path.exists(path):
        return FileContent(
            path=path,
            content="",
            lines=0,
            language="text",
            size=0,
            error=f"File not found: {path}"
        )

    if os.path.isdir(path):
        return FileContent(
            path=path,
            content="",
            lines=0,
            language="text",
            size=0,
            error="Cannot read directory"
        )

    try:
        size = os.path.getsize(path)

        # Check if file is too large
        if size > 5 * 1024 * 1024:  # 5MB limit
            return FileContent(
                path=path,
                content="",
                lines=0,
                language=detect_language(path),
                size=size,
                error="File too large (>5MB)"
            )

        # Read file content
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            lines = all_lines[:request.max_lines]
            content = ''.join(lines)

            if len(all_lines) > request.max_lines:
                content += f"\n... (truncated, showing {request.max_lines}/{len(all_lines)} lines)"

        return FileContent(
            path=os.path.abspath(path),
            content=content,
            lines=len(all_lines),
            language=detect_language(path),
            size=size
        )
    except Exception as e:
        return FileContent(
            path=path,
            content="",
            lines=0,
            language="text",
            size=0,
            error=str(e)
        )


@router.post("/project/info", response_model=ProjectInfo)
async def get_project_info(request: ProjectInfoRequest):
    """Get project information."""
    path = request.path

    if not os.path.exists(path):
        return ProjectInfo(
            path=path,
            name="",
            type="Unknown",
            code_files=0,
            has_git=False,
            has_package_json=False,
            has_requirements=False,
            error=f"Path not found: {path}"
        )

    p = Path(path)

    # Count code files
    code_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.rb', '.php', '.c', '.cpp', '.h'}
    code_files = 0
    try:
        for item in p.rglob('*'):
            if item.is_file() and item.suffix.lower() in code_extensions:
                code_files += 1
                if code_files > 1000:  # Limit scanning
                    break
    except (PermissionError, OSError):
        pass

    return ProjectInfo(
        path=str(path),
        name=p.name,
        type=detect_project_type(path),
        code_files=code_files,
        has_git=(p / '.git').exists(),
        has_package_json=(p / 'package.json').exists(),
        has_requirements=(p / 'requirements.txt').exists() or (p / 'pyproject.toml').exists()
    )


@router.post("/project/open-cursor", response_model=CommandResponse)
async def open_in_cursor(request: OpenPathRequest):
    """Open path in Cursor IDE."""
    path = request.path
    if not os.path.exists(path):
        return CommandResponse(status="error", message=f"Path not found: {path}")
    cmd = f'cursor "{path}"'
    return await run_command(cmd)


# ═══════════════════════════════════════════════════════════════
# AI Provider Endpoints
# ═══════════════════════════════════════════════════════════════

# Global AI provider state
_current_ai_provider = "ollama"

async def _check_ollama_available() -> tuple[bool, str]:
    """Check if Ollama is available."""
    from jarvis.config import get_settings
    settings = get_settings()

    try:
        from jarvis.llm.providers.ollama import OllamaClient
        client = OllamaClient(host=settings.ollama_host)
        is_available = await client.is_available()
        if is_available:
            return True, f"Local LLM via Ollama ({settings.ollama_model})"
        else:
            return False, "Ollama not running. Start with: ollama serve"
    except Exception as e:
        return False, f"Ollama error: {str(e)}"


async def _check_copilot_available() -> tuple[bool, str]:
    """Check if GitHub Copilot is available (VS Code or CLI)."""
    from jarvis.core.logging import get_logger
    logger = get_logger("jarvis.api.mobile")

    # Try VS Code Copilot first (more reliable if user has VS Code setup)
    try:
        from jarvis.llm.providers.vscode_copilot import get_vscode_copilot
        vscode_provider = get_vscode_copilot()
        vscode_available, vscode_message = await vscode_provider.check_available()
        if vscode_available:
            return True, f"VS Code Copilot: {vscode_message}"
    except Exception as e:
        logger.debug(f"VS Code Copilot check failed: {e}")

    # Fallback to CLI method
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        cli_provider = get_copilot_cli()
        cli_available, cli_message = await cli_provider.check_available()
        if cli_available:
            return True, f"CLI Copilot: {cli_message}"
        else:
            # Return helpful message for setup
            return False, "GitHub Copilot not available. Install GitHub Copilot extension in VS Code, or fix GitHub CLI authentication."
    except Exception as e:
        return False, f"Copilot error: {str(e)}"


async def _check_openai_available() -> tuple[bool, str]:
    """Check if OpenAI API is available."""
    from jarvis.config import get_settings
    settings = get_settings()

    if not settings.openai_api_key:
        return False, "OpenAI API key not configured"

    try:
        from jarvis.llm.providers.openai import OpenAIClient
        client = OpenAIClient(api_key=settings.openai_api_key)
        is_available = await client.is_available()
        if is_available:
            return True, f"OpenAI API ({settings.openai_model})"
        else:
            return False, "OpenAI API key invalid or expired"
    except Exception as e:
        return False, f"OpenAI error: {str(e)}"


@router.get("/project/ai/providers", response_model=AIProvidersResponse)
async def get_ai_providers():
    """Get available AI providers with real availability checks."""
    # Check provider availability
    ollama_available, ollama_message = await _check_ollama_available()
    copilot_available, copilot_message = await _check_copilot_available()
    openai_available, openai_message = await _check_openai_available()

    providers = {
        "ollama": AIProviderStatus(
            available=ollama_available,
            message=ollama_message,
            selected=_current_ai_provider == "ollama"
        ),
        "copilot": AIProviderStatus(
            available=copilot_available,
            message=copilot_message,
            selected=_current_ai_provider == "copilot"
        ),
        "openai": AIProviderStatus(
            available=openai_available,
            message=openai_message,
            selected=_current_ai_provider == "openai"
        ),
        "cursor": AIProviderStatus(
            available=False,
            message="Cursor AI (coming soon)",
            selected=_current_ai_provider == "cursor"
        )
    }

    return AIProvidersResponse(
        current=_current_ai_provider,
        providers=providers
    )


@router.post("/project/ai/set-provider")
async def set_ai_provider(request: SetProviderRequest):
    """Set the current AI provider."""
    global _current_ai_provider

    valid_providers = ["ollama", "copilot", "openai", "cursor"]
    if request.provider not in valid_providers:
        return {"success": False, "provider": request.provider, "message": f"Invalid provider. Choose from: {valid_providers}"}

    _current_ai_provider = request.provider
    return {"success": True, "provider": request.provider, "message": f"AI provider set to {request.provider}"}


# ═══════════════════════════════════════════════════════════════
# Copilot Model Selection Endpoints
# ═══════════════════════════════════════════════════════════════

class CopilotModelRequest(BaseModel):
    """Request to set Copilot model."""
    model: str


class CopilotModelsResponse(BaseModel):
    """Available Copilot models response."""
    current: str
    models: dict[str, list[str]]  # Category -> list of models


@router.get("/copilot/models", response_model=CopilotModelsResponse)
async def get_copilot_models():
    """Get available Copilot models organized by category."""
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        provider = get_copilot_cli()

        return CopilotModelsResponse(
            current=provider.get_current_model(),
            models=provider.get_available_models()
        )
    except Exception as e:
        return CopilotModelsResponse(
            current="gpt-5.2-codex",
            models={
                "Error": [f"Failed to load models: {str(e)}"]
            }
        )


@router.post("/copilot/models/set")
async def set_copilot_model(request: CopilotModelRequest):
    """Set the current Copilot model."""
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        provider = get_copilot_cli()
        provider.set_model(request.model)

        return {
            "success": True,
            "model": request.model,
            "message": f"Copilot model set to {request.model}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to set model: {str(e)}"
        }


@router.get("/copilot/status")
async def get_copilot_status():
    """Get detailed Copilot status including authentication and model."""
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        provider = get_copilot_cli()

        # Check authentication
        auth_ok, auth_message = await provider.check_github_auth()

        # Check Copilot access
        copilot_ok, copilot_message = await provider.check_copilot_access()

        return {
            "authentication": {
                "status": "authenticated" if auth_ok else "not_authenticated",
                "message": auth_message
            },
            "copilot": {
                "status": "available" if copilot_ok else "unavailable",
                "message": copilot_message
            },
            "model": {
                "current": provider.get_current_model(),
                "available_count": len([model for models in provider.get_available_models().values() for model in models])
            }
        }
    except Exception as e:
        return {
            "authentication": {"status": "error", "message": f"Error: {str(e)}"},
            "copilot": {"status": "error", "message": f"Error: {str(e)}"},
            "model": {"current": "unknown", "available_count": 0}
        }


@router.post("/project/ai/ask", response_model=AIResponse)
async def ask_ai(request: AIAskRequest):
    """Ask AI for help using the selected provider."""
    from jarvis.config import get_settings
    from jarvis.core.exceptions import LLMConnectionError, LLMResponseError

    settings = get_settings()

    # Build prompt with context
    full_prompt = request.prompt
    if request.code_context:
        full_prompt = f"Code context from {request.file_path or 'unknown file'} ({request.language or 'unknown language'}):\n\n```\n{request.code_context}\n```\n\nQuestion: {request.prompt}"

    system_prompt = "You are a helpful AI coding assistant. Provide clear, concise answers."

    # Use the selected provider
    if _current_ai_provider == "copilot":
        # Try VS Code Copilot first, then fallback to CLI

        # Method 1: VS Code Copilot (preferred - works with existing VS Code setup)
        try:
            from jarvis.llm.providers.vscode_copilot import get_vscode_copilot
            vscode_provider = get_vscode_copilot()
            vscode_available, vscode_message = await vscode_provider.check_available()

            if vscode_available:
                response = await vscode_provider.chat(
                    prompt=full_prompt,
                    context=request.code_context,
                    system_prompt=system_prompt
                )

                if not response.startswith("Error:"):
                    return AIResponse(
                        status="success",
                        response=response
                    )
        except Exception as e:
            logger.debug(f"VS Code Copilot failed: {e}")

        # Method 2: GitHub CLI Copilot (fallback)
        try:
            from jarvis.llm.providers.copilot_cli import get_copilot_cli
            cli_provider = get_copilot_cli()

            # Check if available
            cli_available, cli_message = await cli_provider.check_available()
            if cli_available:
                response = await cli_provider.chat(
                    prompt=full_prompt,
                    context=request.code_context,
                    system_prompt=system_prompt
                )

                if not response.startswith("Error:"):
                    return AIResponse(
                        status="success",
                        response=response
                    )
                else:
                    return AIResponse(
                        status="error",
                        response="",
                        error=response
                    )
            else:
                return AIResponse(
                    status="error",
                    response="",
                    error=f"GitHub Copilot not available: {cli_message}"
                )
        except Exception as e:
            return AIResponse(status="error", response="", error=f"Copilot CLI error: {str(e)}")

        # If both methods failed
        return AIResponse(
            status="error",
            response="",
            error="GitHub Copilot not available. Please install GitHub Copilot extension in VS Code or authenticate with GitHub CLI."
        )

    elif _current_ai_provider == "openai":
        if not settings.openai_api_key:
            return AIResponse(
                status="error",
                response="",
                error="OpenAI API key not configured. Set JARVIS_OPENAI_API_KEY in environment."
            )

        try:
            from jarvis.llm.providers.openai import OpenAIClient

            client = OpenAIClient(
                api_key=settings.openai_api_key,
                model=settings.openai_model
            )

            if not await client.is_available():
                return AIResponse(
                    status="error",
                    response="",
                    error="OpenAI API not available. Check your API key."
                )

            response = await client.generate(
                prompt=full_prompt,
                system=system_prompt
            )

            return AIResponse(
                status="success",
                response=response
            )
        except LLMConnectionError as e:
            return AIResponse(status="error", response="", error=str(e))
        except LLMResponseError as e:
            return AIResponse(status="error", response="", error=str(e))
        except Exception as e:
            return AIResponse(status="error", response="", error=f"OpenAI error: {str(e)}")

    else:  # Default to Ollama
        if not settings.ollama_host:
            return AIResponse(
                status="error",
                response="",
                error="Ollama not configured. Set JARVIS_OLLAMA_HOST in environment."
            )

        try:
            from jarvis.llm.providers.ollama import OllamaClient

            client = OllamaClient(host=settings.ollama_host)

            if not await client.is_available():
                return AIResponse(
                    status="error",
                    response="",
                    error=(
                        "Cannot connect to Ollama. Please ensure Ollama is running:\n"
                        "1. Open a terminal and run: ollama serve\n"
                        "2. Or start Ollama from the system tray\n"
                        f"3. Expected at: {settings.ollama_host}"
                    )
                )

            response = await client.generate(
                prompt=full_prompt,
                model=settings.ollama_model,
                system=system_prompt
            )

            return AIResponse(
                status="success",
                response=response
            )
        except LLMConnectionError as e:
            return AIResponse(status="error", response="", error=str(e))
        except LLMResponseError as e:
            return AIResponse(status="error", response="", error=str(e))
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "connect" in error_msg.lower():
                error_msg = (
                    "Cannot connect to Ollama. Please ensure:\n"
                    "1. Ollama is installed (https://ollama.ai)\n"
                    "2. Ollama is running (ollama serve)\n"
                    "3. The model is downloaded (ollama pull llama3.2)"
                )
            elif "500" in error_msg:
                error_msg = (
                    f"Ollama server error. The model '{settings.ollama_model}' may not be available.\n"
                    f"Try: ollama pull {settings.ollama_model}"
                )
            return AIResponse(status="error", response="", error=error_msg)


# ═══════════════════════════════════════════════════════════════
# GitHub Authentication Endpoints
# ═══════════════════════════════════════════════════════════════

# Store GitHub token in memory (in production, use secure storage)
_github_token: Optional[str] = None
_github_username: Optional[str] = None


class GitHubAuthStatus(BaseModel):
    """GitHub authentication status."""
    authenticated: bool
    username: Optional[str] = None
    account_type: Optional[str] = None
    scopes: list[str] = []
    message: str
    has_token: bool = False  # Whether a token is stored for API access


class GitHubLoginResponse(BaseModel):
    """GitHub login response."""
    success: bool
    message: str
    auth_url: Optional[str] = None


def _get_gh_path() -> str:
    """Get the path to the GitHub CLI executable."""
    import shutil
    if platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\GitHub CLI\gh.exe",
            r"C:\Program Files (x86)\GitHub CLI\gh.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return f'"{path}"'
        gh_path = shutil.which("gh")
        if gh_path:
            return f'"{gh_path}"'
        return "gh"
    else:
        return shutil.which("gh") or "gh"


@router.get("/github/auth/status", response_model=GitHubAuthStatus)
async def get_github_auth_status():
    """Get GitHub authentication status."""
    gh_path = _get_gh_path()

    try:
        if platform.system() == "Windows":
            cmd = f'cmd.exe /c {gh_path} auth status'
        else:
            cmd = f'{gh_path} auth status'

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        output = (stdout.decode() + stderr.decode()).strip()

        if process.returncode == 0:
            # Parse the output to extract username and scopes
            username = None
            scopes = []

            # Look for username pattern: "Logged in to github.com account USERNAME"
            import re
            username_match = re.search(r'account\s+(\S+)', output)
            if username_match:
                username = username_match.group(1)

            # Look for scopes pattern: "Token scopes: 'scope1', 'scope2'"
            scopes_match = re.search(r"Token scopes:\s*'([^']+)'", output)
            if scopes_match:
                scopes = [s.strip().strip("'") for s in scopes_match.group(0).replace("Token scopes:", "").split(",")]

            return GitHubAuthStatus(
                authenticated=True,
                username=username,
                account_type="user",
                scopes=scopes,
                message="Authenticated with GitHub"
            )
        else:
            return GitHubAuthStatus(
                authenticated=False,
                message="Not authenticated. Run 'gh auth login' to authenticate."
            )
    except asyncio.TimeoutError:
        return GitHubAuthStatus(
            authenticated=False,
            message="Timeout checking GitHub auth status"
        )
    except Exception as e:
        return GitHubAuthStatus(
            authenticated=False,
            message=f"GitHub CLI not available: {str(e)}"
        )


@router.post("/github/auth/login", response_model=GitHubLoginResponse)
async def github_login():
    """
    Initiate GitHub login.

    Note: This returns instructions since gh auth login is interactive.
    The user needs to run this command manually on the host machine.
    """
    gh_path = _get_gh_path()

    # Check if gh is installed
    try:
        if platform.system() == "Windows":
            cmd = f'cmd.exe /c {gh_path} --version'
        else:
            cmd = f'{gh_path} --version'

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(process.communicate(), timeout=5)

        if process.returncode != 0:
            return GitHubLoginResponse(
                success=False,
                message="GitHub CLI (gh) is not installed. Please install it first."
            )
    except Exception:
        return GitHubLoginResponse(
            success=False,
            message="GitHub CLI (gh) is not installed. Please install it first."
        )

    # Return instructions for login
    return GitHubLoginResponse(
        success=True,
        message="To authenticate, run 'gh auth login' in a terminal on the host machine. This is an interactive process that requires browser access.",
        auth_url="https://github.com/login/device"
    )


@router.post("/github/auth/logout")
async def github_logout():
    """Logout from GitHub."""
    global _github_token, _github_username

    # Clear stored token
    _github_token = None
    _github_username = None

    gh_path = _get_gh_path()

    try:
        if platform.system() == "Windows":
            cmd = f'cmd.exe /c {gh_path} auth logout --hostname github.com'
        else:
            cmd = f'{gh_path} auth logout --hostname github.com'

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        # Send 'Y' to confirm logout
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=b'Y\n'),
            timeout=10
        )

        return {"success": True, "message": "Logged out from GitHub"}
    except Exception as e:
        return {"success": False, "message": f"Logout failed: {str(e)}"}


# ═══════════════════════════════════════════════════════════════
# GitHub Token Management (for Cloud Copilot API)
# ═══════════════════════════════════════════════════════════════

class GitHubTokenRequest(BaseModel):
    """Request to set GitHub token."""
    token: str


class GitHubTokenResponse(BaseModel):
    """Response for GitHub token operations."""
    success: bool
    message: str
    username: Optional[str] = None


@router.post("/github/token/set", response_model=GitHubTokenResponse)
async def set_github_token(request: GitHubTokenRequest):
    """
    Set GitHub Personal Access Token for Copilot API access.

    This allows using GitHub Copilot from cloud deployment!

    To create a token:
    1. Go to https://github.com/settings/tokens
    2. Create a new token (classic) with 'copilot' scope
    3. Copy and paste it here
    """
    global _github_token, _github_username

    token = request.token.strip()
    if not token:
        return GitHubTokenResponse(
            success=False,
            message="Token cannot be empty"
        )

    # Validate token by checking GitHub API
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
            async with session.get("https://api.github.com/user", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    username = data.get("login", "unknown")

                    # Store the token
                    _github_token = token
                    _github_username = username

                    # Also set it in the Copilot API provider
                    try:
                        from jarvis.llm.providers.copilot_api import set_copilot_token
                        set_copilot_token(token)
                    except ImportError:
                        pass

                    return GitHubTokenResponse(
                        success=True,
                        message=f"Token saved! Authenticated as @{username}",
                        username=username
                    )
                elif resp.status == 401:
                    return GitHubTokenResponse(
                        success=False,
                        message="Invalid token. Please check and try again."
                    )
                else:
                    return GitHubTokenResponse(
                        success=False,
                        message=f"GitHub API error: {resp.status}"
                    )
    except Exception as e:
        return GitHubTokenResponse(
            success=False,
            message=f"Connection error: {str(e)}"
        )


@router.get("/github/token/status", response_model=GitHubTokenResponse)
async def get_github_token_status():
    """Check if a GitHub token is configured."""
    global _github_token, _github_username

    if _github_token:
        return GitHubTokenResponse(
            success=True,
            message=f"Token configured for @{_github_username}",
            username=_github_username
        )
    else:
        return GitHubTokenResponse(
            success=False,
            message="No token configured. Add your GitHub token in Settings."
        )


@router.post("/github/token/clear")
async def clear_github_token():
    """Clear the stored GitHub token."""
    global _github_token, _github_username

    _github_token = None
    _github_username = None

    return {"success": True, "message": "Token cleared"}


# ═══════════════════════════════════════════════════════════════
# Copilot Legacy Endpoint
# ═══════════════════════════════════════════════════════════════

@router.post("/copilot/run", response_model=CommandResponse)
async def run_copilot(request: CommandRequest):
    """Legacy Copilot CLI endpoint."""
    # Try running gh copilot suggest
    cmd = f'gh copilot suggest "{request.command}"'
    return await run_command(cmd)


# ═══════════════════════════════════════════════════════════════
# File Write/Edit Endpoints
# ═══════════════════════════════════════════════════════════════

class FileWriteRequest(BaseModel):
    """File write request."""
    path: str
    content: str
    create_backup: bool = True


class FileWriteResponse(BaseModel):
    """File write response."""
    success: bool
    path: str
    message: str
    backup_path: Optional[str] = None


class CopilotEditRequest(BaseModel):
    """Copilot edit request - ask Copilot to modify code."""
    file_path: str
    instruction: str
    apply_changes: bool = False  # If True, apply changes directly


class CopilotEditResponse(BaseModel):
    """Copilot edit response."""
    success: bool
    original_content: str
    suggested_content: str
    diff: str
    message: str
    applied: bool = False


@router.post("/project/write", response_model=FileWriteResponse)
async def write_file(request: FileWriteRequest):
    """Write content to a file."""
    path = request.path

    try:
        # Create backup if file exists
        backup_path = None
        if request.create_backup and os.path.exists(path):
            backup_path = f"{path}.backup"
            import shutil
            shutil.copy2(path, backup_path)

        # Write the file
        with open(path, 'w', encoding='utf-8') as f:
            f.write(request.content)

        return FileWriteResponse(
            success=True,
            path=os.path.abspath(path),
            message="File saved successfully",
            backup_path=backup_path
        )
    except PermissionError:
        return FileWriteResponse(
            success=False,
            path=path,
            message="Permission denied"
        )
    except Exception as e:
        return FileWriteResponse(
            success=False,
            path=path,
            message=str(e)
        )


@router.post("/copilot/edit", response_model=CopilotEditResponse)
async def copilot_edit(request: CopilotEditRequest):
    """Ask Copilot to edit a file based on instructions."""
    file_path = request.file_path

    # Read the original file
    if not os.path.exists(file_path):
        return CopilotEditResponse(
            success=False,
            original_content="",
            suggested_content="",
            diff="",
            message=f"File not found: {file_path}"
        )

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            original_content = f.read()
    except Exception as e:
        return CopilotEditResponse(
            success=False,
            original_content="",
            suggested_content="",
            diff="",
            message=f"Failed to read file: {e}"
        )

    # Detect language
    language = detect_language(file_path)

    # Build the Copilot prompt
    prompt = f"""I have this {language} code:

```{language}
{original_content}
```

Please modify it to: {request.instruction}

Return ONLY the complete modified code, no explanations."""

    # Try GitHub Copilot CLI first
    safe_prompt = prompt.replace('"', '\\"').replace('\n', ' ')[:2000]
    result = await run_command(f'gh copilot suggest "{safe_prompt}"', timeout=60)

    suggested_content = ""
    if result.status == "success" and result.stdout:
        # Extract code from response
        suggested_content = result.stdout
        # Try to extract code block if present
        if "```" in suggested_content:
            import re
            code_blocks = re.findall(r'```(?:\w+)?\n?(.*?)```', suggested_content, re.DOTALL)
            if code_blocks:
                suggested_content = code_blocks[0].strip()
    else:
        # Fall back to Ollama
        from jarvis.config import get_settings
        settings = get_settings()

        try:
            from jarvis.llm.providers.ollama import OllamaClient
            client = OllamaClient(host=settings.ollama_host)

            response = await client.generate(
                prompt=prompt,
                model=settings.ollama_model,
                system="You are a code editor. Return ONLY the modified code, no explanations or markdown."
            )
            suggested_content = response.strip()

            # Try to extract code block if wrapped
            if suggested_content.startswith("```"):
                import re
                code_blocks = re.findall(r'```(?:\w+)?\n?(.*?)```', suggested_content, re.DOTALL)
                if code_blocks:
                    suggested_content = code_blocks[0].strip()
        except Exception as e:
            return CopilotEditResponse(
                success=False,
                original_content=original_content,
                suggested_content="",
                diff="",
                message=f"AI error: {e}"
            )

    if not suggested_content:
        return CopilotEditResponse(
            success=False,
            original_content=original_content,
            suggested_content="",
            diff="",
            message="No suggestions received from AI"
        )

    # Generate diff
    diff = generate_diff(original_content, suggested_content, file_path)

    # Apply changes if requested
    applied = False
    if request.apply_changes:
        try:
            # Create backup
            backup_path = f"{file_path}.backup"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)

            # Write new content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(suggested_content)

            applied = True
        except Exception as e:
            return CopilotEditResponse(
                success=False,
                original_content=original_content,
                suggested_content=suggested_content,
                diff=diff,
                message=f"Failed to apply changes: {e}"
            )

    return CopilotEditResponse(
        success=True,
        original_content=original_content,
        suggested_content=suggested_content,
        diff=diff,
        message="Changes suggested" + (" and applied" if applied else " - review and apply"),
        applied=applied
    )


def generate_diff(original: str, modified: str, filename: str) -> str:
    """Generate a unified diff between original and modified content."""
    import difflib

    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{os.path.basename(filename)}",
        tofile=f"b/{os.path.basename(filename)}",
        lineterm=""
    )

    return ''.join(diff)


__all__ = ["router"]
