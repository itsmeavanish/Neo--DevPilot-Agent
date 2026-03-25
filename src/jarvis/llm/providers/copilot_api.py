"""
GitHub Copilot API Provider.

Uses GitHub Copilot API directly with OAuth token - works from cloud!
"""

import aiohttp
from typing import Optional
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.llm.copilot_api")

# GitHub Copilot API endpoint
COPILOT_API_URL = "https://api.githubcopilot.com/chat/completions"
GITHUB_TOKEN_URL = "https://api.github.com/user"


class CopilotAPIProvider:
    """
    GitHub Copilot API Provider.

    Uses the Copilot API directly with OAuth tokens.
    Works from cloud deployment - no local CLI needed!
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the Copilot API provider.

        Args:
            github_token: GitHub OAuth token with Copilot access
        """
        self.github_token = github_token
        self._copilot_token: Optional[str] = None

    def set_token(self, token: str):
        """Set the GitHub OAuth token."""
        self.github_token = token
        self._copilot_token = None  # Reset copilot token

    async def _get_copilot_token(self) -> Optional[str]:
        """
        Exchange GitHub token for Copilot API token.

        GitHub Copilot requires a special token obtained through OAuth flow.
        """
        if not self.github_token:
            return None

        if self._copilot_token:
            return self._copilot_token

        try:
            # Get Copilot token from GitHub
            async with aiohttp.ClientSession() as session:
                # First, verify the GitHub token
                headers = {
                    "Authorization": f"Bearer {self.github_token}",
                    "Accept": "application/json",
                }

                async with session.get(GITHUB_TOKEN_URL, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error("Invalid GitHub token")
                        return None

                    user_data = await resp.json()
                    logger.info(f"Authenticated as: {user_data.get('login')}")

                # Get Copilot token
                copilot_token_url = "https://api.github.com/copilot_internal/v2/token"
                async with session.get(copilot_token_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._copilot_token = data.get("token")
                        return self._copilot_token
                    else:
                        # Try alternative endpoint
                        logger.debug("Trying alternative Copilot token endpoint")
                        return self.github_token  # Use GitHub token directly

        except Exception as e:
            logger.error(f"Failed to get Copilot token: {e}")
            return None

    async def check_available(self) -> tuple[bool, str]:
        """Check if Copilot API is available."""
        if not self.github_token:
            return False, "GitHub token not configured. Add token in Settings."

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.github_token}",
                    "Accept": "application/json",
                }

                async with session.get(GITHUB_TOKEN_URL, headers=headers) as resp:
                    if resp.status == 200:
                        user_data = await resp.json()
                        username = user_data.get("login", "unknown")
                        return True, f"Authenticated as @{username}"
                    else:
                        return False, "Invalid GitHub token"

        except Exception as e:
            return False, f"Connection error: {str(e)}"

    async def chat(
        self,
        prompt: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to Copilot API.

        Args:
            prompt: User's question or request
            context: Optional code context
            system_prompt: Optional system instructions

        Returns:
            Copilot's response text
        """
        token = await self._get_copilot_token()
        if not token:
            return "Error: GitHub authentication required. Please add your GitHub token in Settings."

        messages = []

        # Add system prompt
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        else:
            messages.append({
                "role": "system",
                "content": "You are a helpful AI coding assistant powered by GitHub Copilot. Help the user with their programming questions."
            })

        # Add context if provided
        if context:
            messages.append({
                "role": "user",
                "content": f"Here's the relevant code context:\n\n```\n{context}\n```"
            })

        # Add the actual prompt
        messages.append({
            "role": "user",
            "content": prompt
        })

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Editor-Version": "vscode/1.85.0",
                    "Editor-Plugin-Version": "copilot-chat/0.12.0",
                    "Openai-Organization": "github-copilot",
                    "User-Agent": "GitHubCopilotChat/0.12.0",
                }

                payload = {
                    "messages": messages,
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "top_p": 1,
                    "n": 1,
                    "stream": False,
                }

                async with session.post(
                    COPILOT_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "No response")
                        return "No response from Copilot"

                    elif resp.status == 401:
                        self._copilot_token = None  # Reset token
                        return "Error: Authentication failed. Please re-authenticate with GitHub."

                    elif resp.status == 403:
                        return "Error: Copilot access denied. Make sure you have an active Copilot subscription."

                    else:
                        error_text = await resp.text()
                        logger.error(f"Copilot API error {resp.status}: {error_text}")
                        return f"Error: Copilot API returned {resp.status}"

        except aiohttp.ClientError as e:
            logger.error(f"Copilot API request failed: {e}")
            return f"Error: Network error - {str(e)}"
        except Exception as e:
            logger.error(f"Copilot API error: {e}")
            return f"Error: {str(e)}"


# Global instance
_copilot_api: Optional[CopilotAPIProvider] = None


def get_copilot_api() -> CopilotAPIProvider:
    """Get the global Copilot API provider instance."""
    global _copilot_api
    if _copilot_api is None:
        _copilot_api = CopilotAPIProvider()
    return _copilot_api


def set_copilot_token(token: str):
    """Set the GitHub token for Copilot API."""
    provider = get_copilot_api()
    provider.set_token(token)


__all__ = ["CopilotAPIProvider", "get_copilot_api", "set_copilot_token"]
