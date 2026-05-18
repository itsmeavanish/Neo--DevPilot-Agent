"""
GitHub Copilot CLI Provider.

Uses GitHub Copilot CLI through `gh copilot` command - no manual tokens needed!
Supports all available models and seamless GitHub authentication.
"""

import asyncio
import json
import subprocess
from typing import Optional, List, Dict
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.llm.copilot_cli")

# Available Copilot models (from CLI help output)
COPILOT_MODELS = [
    "claude-sonnet-4.6",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "claude-opus-4.6",
    "claude-opus-4.6-fast",
    "claude-opus-4.5",
    "claude-sonnet-4",
    "gemini-3-pro-preview",
    "gpt-5.3-codex",
    "gpt-5.2-codex",
    "gpt-5.2",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex",
    "gpt-5.1",
    "gpt-5.1-codex-mini",
    "gpt-5-mini",
    "gpt-4.1"
]

# Default model
DEFAULT_MODEL = "gpt-5.2-codex"

# Model categories for UI
MODEL_CATEGORIES = {
    "GPT Models": [
        "gpt-5.3-codex",
        "gpt-5.2-codex",
        "gpt-5.2",
        "gpt-5.1-codex-max",
        "gpt-5.1-codex",
        "gpt-5.1",
        "gpt-5.1-codex-mini",
        "gpt-5-mini",
        "gpt-4.1"
    ],
    "Claude Models": [
        "claude-sonnet-4.6",
        "claude-sonnet-4.5",
        "claude-haiku-4.5",
        "claude-opus-4.6",
        "claude-opus-4.6-fast",
        "claude-opus-4.5",
        "claude-sonnet-4"
    ],
    "Other Models": [
        "gemini-3-pro-preview"
    ]
}


class CopilotCLIProvider:
    """
    GitHub Copilot CLI Provider.

    Uses GitHub CLI with Copilot extension - no manual token management needed!
    Automatically uses the user's existing GitHub authentication.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        """
        Initialize the Copilot CLI provider.

        Args:
            model: The model to use for responses (default: gpt-5.2-codex)
        """
        self.model = model
        self._auth_status = None

    def set_model(self, model: str):
        """Set the AI model to use for responses."""
        if model in COPILOT_MODELS:
            self.model = model
            logger.info(f"Copilot model set to: {model}")
        else:
            logger.warning(f"Unknown model: {model}. Using default: {DEFAULT_MODEL}")
            self.model = DEFAULT_MODEL

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models organized by category."""
        return MODEL_CATEGORIES

    def get_current_model(self) -> str:
        """Get the currently selected model."""
        return self.model

    async def _run_command(self, cmd: List[str], timeout: int = 60) -> tuple[bool, str]:
        """
        Run a command asynchronously with proper Windows path handling.

        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds

        Returns:
            (success, output) tuple
        """
        try:
            # On Windows, handle paths with spaces properly
            import platform
            if platform.system() == "Windows":
                # Use shell=True for Windows to handle paths with spaces
                cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=None
                )
            else:
                # Unix systems can use exec directly
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=None
                )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            success = process.returncode == 0
            output = stdout.decode('utf-8', errors='ignore') if success else stderr.decode('utf-8', errors='ignore')

            return success, output.strip()

        except asyncio.TimeoutError:
            return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            return False, f"Command failed: {str(e)}"

    async def check_github_auth(self) -> tuple[bool, str]:
        """Check GitHub CLI authentication status."""
        if self._auth_status is not None:
            return self._auth_status

        success, output = await self._run_command(["gh", "auth", "status"])

        if success and "✓ Logged in" in output:
            # Extract username
            lines = output.split('\n')
            username = "unknown"
            for line in lines:
                if "account:" in line and "(" in line:
                    username = line.split('account:')[1].split('(')[0].strip()
                    break

            self._auth_status = (True, f"Authenticated as @{username}")
            return self._auth_status
        else:
            self._auth_status = (False, "Not authenticated with GitHub CLI")
            return self._auth_status

    async def check_copilot_access(self) -> tuple[bool, str]:
        """Check if Copilot CLI access is available."""
        # First check GitHub auth
        auth_ok, auth_msg = await self.check_github_auth()
        if not auth_ok:
            return False, f"GitHub authentication required: {auth_msg}"

        # Test Copilot access with a simple command
        success, output = await self._run_command([
            "gh", "copilot", "--",
            "--prompt", "test",
            "--silent",
            "--allow-all-tools"
        ], timeout=30)

        if success:
            return True, f"Copilot CLI ready ({auth_msg})"
        elif "subscription" in output.lower() or "copilot" in output.lower():
            return False, "Copilot subscription required. Please ensure you have GitHub Copilot access."
        else:
            return False, f"Copilot CLI error: {output}"

    async def check_available(self) -> tuple[bool, str]:
        """Check if Copilot CLI is available and accessible."""
        return await self.check_copilot_access()

    async def chat(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Send a chat request to Copilot CLI.

        Args:
            prompt: User's question or request
            context: Optional code context
            system_prompt: Optional system instructions
            model: Optional model override

        Returns:
            Copilot's response text
        """
        # Check authentication first
        auth_ok, auth_msg = await self.check_github_auth()
        if not auth_ok:
            return f"Error: GitHub authentication required. Please run 'gh auth login' first.\n{auth_msg}"

        # Use specified model or default
        use_model = model or self.model

        # Build the full prompt
        full_prompt = ""

        if system_prompt:
            full_prompt += f"System: {system_prompt}\n\n"

        if context:
            full_prompt += f"Code Context:\n```\n{context}\n```\n\n"

        full_prompt += f"User: {prompt}"

        # Build command
        cmd = [
            "gh", "copilot", "--",
            "--prompt", full_prompt,
            "--model", use_model,
            "--silent",
            "--allow-all-tools"
        ]

        # Run the command
        success, output = await self._run_command(cmd, timeout=120)

        if success:
            return output.strip()
        else:
            # Handle common errors
            if "subscription" in output.lower():
                return "Error: GitHub Copilot subscription required. Please ensure you have an active Copilot subscription."
            elif "authentication" in output.lower() or "login" in output.lower():
                self._auth_status = None  # Reset auth cache
                return "Error: Authentication failed. Please run 'gh auth login' and try again."
            elif "model" in output.lower() and "invalid" in output.lower():
                return f"Error: Invalid model '{use_model}'. Available models: {', '.join(COPILOT_MODELS[:5])}..."
            else:
                return f"Error: Copilot CLI failed - {output}"

    async def explain_code(self, code: str, language: Optional[str] = None) -> str:
        """
        Ask Copilot to explain code.

        Args:
            code: Code to explain
            language: Programming language (optional)

        Returns:
            Explanation of the code
        """
        lang_hint = f" ({language})" if language else ""
        prompt = f"Please explain this code{lang_hint}:\n\n```\n{code}\n```"

        return await self.chat(
            prompt=prompt,
            system_prompt="You are a helpful coding assistant. Explain code clearly and concisely."
        )

    async def suggest_improvements(self, code: str, language: Optional[str] = None) -> str:
        """
        Ask Copilot to suggest code improvements.

        Args:
            code: Code to improve
            language: Programming language (optional)

        Returns:
            Suggested improvements
        """
        lang_hint = f" ({language})" if language else ""
        prompt = f"Please suggest improvements for this code{lang_hint}:\n\n```\n{code}\n```"

        return await self.chat(
            prompt=prompt,
            system_prompt="You are a helpful coding assistant. Suggest practical improvements for code quality, performance, and maintainability."
        )

    async def fix_code(self, code: str, error: str, language: Optional[str] = None) -> str:
        """
        Ask Copilot to fix code with an error.

        Args:
            code: Code with error
            error: Error message
            language: Programming language (optional)

        Returns:
            Fixed code with explanation
        """
        lang_hint = f" ({language})" if language else ""
        prompt = f"Please fix this code{lang_hint} that has an error:\n\nCode:\n```\n{code}\n```\n\nError:\n{error}"

        return await self.chat(
            prompt=prompt,
            system_prompt="You are a helpful coding assistant. Fix the code and explain what was wrong and how you fixed it."
        )


# Global instance
_copilot_cli: Optional[CopilotCLIProvider] = None


def get_copilot_cli() -> CopilotCLIProvider:
    """Get the global Copilot CLI provider instance."""
    global _copilot_cli
    if _copilot_cli is None:
        _copilot_cli = CopilotCLIProvider()
    return _copilot_cli


def set_copilot_model(model: str):
    """Set the Copilot model to use."""
    provider = get_copilot_cli()
    provider.set_model(model)


def get_copilot_models() -> Dict[str, List[str]]:
    """Get available Copilot models organized by category."""
    provider = get_copilot_cli()
    return provider.get_available_models()


def get_current_copilot_model() -> str:
    """Get the currently selected Copilot model."""
    provider = get_copilot_cli()
    return provider.get_current_model()


__all__ = [
    "CopilotCLIProvider",
    "get_copilot_cli",
    "set_copilot_model",
    "get_copilot_models",
    "get_current_copilot_model",
    "COPILOT_MODELS",
    "DEFAULT_MODEL"
]