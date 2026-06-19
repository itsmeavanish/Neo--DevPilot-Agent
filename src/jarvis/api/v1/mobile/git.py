import os
import platform
import asyncio
from fastapi import APIRouter
from .models import (
    CommandRequest, CommandResponse, GitHubAuthStatus,
    GitHubLoginResponse, GitHubTokenRequest, GitHubTokenResponse
)
from .utils import run_command
from jarvis.devices.agent_registry import get_agent_registry
from jarvis.core.logging import get_logger
from jarvis.auth.github_token_store import (
    clear_github_token as _clear_token_store,
    get_stored_github_token,
    get_stored_github_username,
    save_github_token,
)

logger = get_logger("jarvis.api.mobile.git")
router = APIRouter()

@router.post("/git/run", response_model=CommandResponse)
async def run_git_command(request: CommandRequest):
    """Execute a git command."""
    cmd = request.command.strip()
    if not cmd.lower().startswith('git'):
        cmd = f"git {cmd}"
    return await run_command(cmd)

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
    token = get_stored_github_token()
    if token:
        return GitHubAuthStatus(
            authenticated=True,
            username=get_stored_github_username() or "Copilot User",
            message="Using GitHub token from Settings",
            has_token=True,
        )

    reg = get_agent_registry()
    agents = reg.list_agents()
    if agents:
        agent = agents[0]
        try:
            res = await reg.send_command_to_agent(agent.device_id, "gh auth token", timeout=10)
            if res.get("success") and res.get("stdout"):
                tok = res["stdout"].strip()
                if tok:
                    user_res = await reg.send_command_to_agent(agent.device_id, "gh api user --jq .login", timeout=10)
                    username = user_res.get("stdout", "").strip() if user_res.get("success") else "Copilot User"
                    save_github_token(tok, username)
                    return GitHubAuthStatus(
                        authenticated=True,
                        username=username,
                        message="Authenticated using token synced from paired laptop",
                        has_token=True,
                    )
        except Exception as e:
            logger.debug("Failed to retrieve gh auth token from laptop: %s", e)

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
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        output = (stdout.decode() + stderr.decode()).strip()

        if process.returncode == 0:
            username = None
            scopes = []
            import re
            username_match = re.search(r'account\s+(\S+)', output)
            if username_match:
                username = username_match.group(1)
            scopes_match = re.search(r"Token scopes:\s*'([^']+)'", output)
            if scopes_match:
                scopes = [s.strip().strip("'") for s in scopes_match.group(0).replace("Token scopes:", "").split(",")]

            return GitHubAuthStatus(
                authenticated=True,
                username=username,
                account_type="user",
                scopes=scopes,
                message="Authenticated with GitHub CLI on this PC",
                has_token=bool(get_stored_github_token()),
            )
    except Exception:
        pass

    return GitHubAuthStatus(
        authenticated=False,
        message="Not authenticated. Add token in Settings, or run `gh auth login` on your paired laptop.",
        has_token=False,
    )

@router.post("/github/auth/login", response_model=GitHubLoginResponse)
async def github_login():
    """Initiate GitHub login."""
    gh_path = _get_gh_path()
    try:
        if platform.system() == "Windows":
            cmd = f'cmd.exe /c {gh_path} --version'
        else:
            cmd = f'{gh_path} --version'
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(process.communicate(), timeout=5)
        if process.returncode != 0:
            return GitHubLoginResponse(success=False, message="GitHub CLI (gh) is not installed.")
    except Exception:
        return GitHubLoginResponse(success=False, message="GitHub CLI (gh) is not installed.")
    return GitHubLoginResponse(
        success=True,
        message="To authenticate, run 'gh auth login' in a terminal on the host machine. This is an interactive process.",
        auth_url="https://github.com/login/device"
    )

@router.post("/github/auth/logout")
async def github_logout():
    """Logout from GitHub."""
    _clear_token_store()
    gh_path = _get_gh_path()
    try:
        if platform.system() == "Windows":
            cmd = f'cmd.exe /c {gh_path} auth logout --hostname github.com'
        else:
            cmd = f'{gh_path} auth logout --hostname github.com'
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(input=b'Y\n'), timeout=10)
        return {"success": True, "message": "Logged out from GitHub"}
    except Exception as e:
        return {"success": False, "message": f"Logout failed: {str(e)}"}

@router.post("/github/token/set", response_model=GitHubTokenResponse)
async def set_github_token(request: GitHubTokenRequest):
    """Set GitHub Personal Access Token."""
    token = request.token.strip()
    if not token:
        return GitHubTokenResponse(success=False, message="Token cannot be empty")
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            async with session.get("https://api.github.com/user", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    username = data.get("login", "unknown")
                    save_github_token(token, username)
                    return GitHubTokenResponse(success=True, message=f"Token saved! Authenticated as @{username}.", username=username)
                elif resp.status == 401:
                    return GitHubTokenResponse(success=False, message="Invalid token.")
                else:
                    return GitHubTokenResponse(success=False, message=f"GitHub API error: {resp.status}")
    except Exception as e:
        return GitHubTokenResponse(success=False, message=f"Connection error: {str(e)}")

@router.get("/github/token/status", response_model=GitHubTokenResponse)
async def get_github_token_status():
    """Check if a GitHub token is configured."""
    token = get_stored_github_token()
    username = get_stored_github_username()
    if token:
        return GitHubTokenResponse(success=True, message=f"Token configured for @{username}", username=username)
    return GitHubTokenResponse(success=False, message="No token configured.")

@router.post("/github/token/clear")
async def clear_github_token():
    """Clear the stored GitHub token."""
    _clear_token_store()
    return {"success": True, "message": "Token cleared"}
