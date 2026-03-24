"""
GitHub Copilot CLI Provider.

Uses the GitHub Copilot CLI (gh copilot) to interact with Copilot.
Requires:
- GitHub CLI installed (gh)
- Authentication: gh auth login
- GitHub Copilot subscription
"""

import asyncio
import os
import platform
import re
import shutil
from typing import AsyncIterator

from jarvis.llm.client import LLMClient, LLMResponse
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import LLMConnectionError, LLMResponseError

logger = get_logger("jarvis.llm.providers.copilot")


def _get_gh_path() -> str:
    """Get the path to the GitHub CLI executable."""
    if platform.system() == "Windows":
        # Check common Windows installation paths
        common_paths = [
            r"C:\Program Files\GitHub CLI\gh.exe",
            r"C:\Program Files (x86)\GitHub CLI\gh.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return f'"{path}"'
        # Fall back to PATH
        gh_path = shutil.which("gh")
        if gh_path:
            return f'"{gh_path}"'
        return "gh"
    else:
        return shutil.which("gh") or "gh"


class CopilotClient(LLMClient):
    """GitHub Copilot CLI client."""

    def __init__(self, timeout: int = 120):
        """
        Initialize Copilot CLI client.

        Args:
            timeout: Command timeout in seconds
        """
        self.timeout = timeout
        self._available: bool | None = None
        self._gh_path = _get_gh_path()

    async def _run_command(self, command: str) -> tuple[str, str, int]:
        """Run a shell command and return stdout, stderr, exit_code."""
        try:
            if platform.system() == "Windows":
                # Use cmd.exe on Windows for proper path handling
                full_command = f'cmd.exe /c {command}'
                process = await asyncio.create_subprocess_shell(
                    full_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    executable="/bin/bash",
                )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )

            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                process.returncode or 0
            )
        except asyncio.TimeoutError:
            raise LLMResponseError(f"Copilot command timed out after {self.timeout}s")
        except Exception as e:
            raise LLMConnectionError(f"Failed to run Copilot command: {e}")

    async def is_available(self) -> bool:
        """Check if GitHub Copilot CLI is available."""
        if self._available is not None:
            return self._available

        try:
            # Check if gh is installed and get version
            stdout, stderr, code = await self._run_command(f"{self._gh_path} --version")
            if code != 0 or not stdout.strip():
                logger.warning("GitHub CLI (gh) not found")
                self._available = False
                return False

            # Check if authenticated
            stdout, stderr, code = await self._run_command(f"{self._gh_path} auth status")
            if code != 0:
                logger.warning("Not authenticated with GitHub. Run: gh auth login")
                self._available = False
                return False

            # Check if copilot command works (it's built-in now)
            stdout, stderr, code = await self._run_command(f"{self._gh_path} copilot --help")
            if code != 0:
                logger.warning("GitHub Copilot CLI not available")
                self._available = False
                return False

            self._available = True
            return True

        except Exception as e:
            logger.warning(f"Copilot availability check failed: {e}")
            self._available = False
            return False

    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Send a chat message to GitHub Copilot CLI.

        Args:
            messages: List of messages with 'role' and 'content'
            system: Optional system prompt (prepended to user message)
            **kwargs: Additional options

        Returns:
            Copilot's response
        """
        if not await self.is_available():
            raise LLMConnectionError(
                "GitHub Copilot CLI not available. Ensure:\n"
                "1. GitHub CLI is installed (gh)\n"
                "2. You're authenticated: gh auth login\n"
                "3. You have a GitHub Copilot subscription"
            )

        # Build prompt from messages
        prompt_parts = []
        if system:
            prompt_parts.append(f"[System]: {system}")

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                prompt_parts.append(content)
            elif role == "assistant":
                prompt_parts.append(f"[Previous response]: {content}")

        full_prompt = "\n\n".join(prompt_parts)

        return await self.generate(prompt=full_prompt)

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a response using GitHub Copilot CLI.

        Args:
            prompt: The prompt to send
            model: Ignored (Copilot uses its own model)
            system: Optional system context
            **kwargs: Additional options

        Returns:
            Copilot's response
        """
        if not await self.is_available():
            raise LLMConnectionError(
                "GitHub Copilot CLI not available. Ensure:\n"
                "1. GitHub CLI is installed (gh)\n"
                "2. You're authenticated: gh auth login\n"
                "3. You have a GitHub Copilot subscription"
            )

        # Build the full prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        else:
            full_prompt = prompt

        # Escape the prompt for shell - handle Windows cmd.exe escaping
        if platform.system() == "Windows":
            # For Windows cmd.exe, escape special characters
            safe_prompt = full_prompt.replace('"', '\\"').replace("%", "%%")
        else:
            safe_prompt = full_prompt.replace('"', '\\"').replace("$", "\\$")

        # Limit prompt length to avoid shell issues
        if len(safe_prompt) > 4000:
            safe_prompt = safe_prompt[:4000] + "... (truncated)"

        # Use the new gh copilot syntax with -p flag
        command = f'{self._gh_path} copilot -p "{safe_prompt}"'

        logger.debug(f"Running Copilot command...")

        stdout, stderr, code = await self._run_command(command)

        if code != 0:
            error_msg = stderr or stdout
            raise LLMResponseError(f"Copilot CLI error: {error_msg}")

        response = stdout.strip()

        if not response:
            raise LLMResponseError("Copilot returned empty response")

        # Clean up ANSI escape codes if present
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        response = ansi_escape.sub('', response)

        return response

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Copilot CLI doesn't support streaming, so we return the full response.
        """
        response = await self.chat(messages, system, **kwargs)
        yield response

    async def list_models(self) -> list[str]:
        """List available models (Copilot uses a fixed model)."""
        return ["copilot"]

    def reset_availability_cache(self):
        """Reset the availability cache to force re-check."""
        self._available = None


__all__ = ["CopilotClient"]
