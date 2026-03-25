"""
VS Code Copilot Provider.

Uses VS Code's existing GitHub Copilot authentication and integration.
Perfect for users who already have Copilot working in VS Code!
"""

import asyncio
import json
import os
import tempfile
from typing import Optional, Dict, List
from pathlib import Path
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.llm.vscode_copilot")

class VSCodeCopilotProvider:
    """
    VS Code Copilot Provider.

    Uses VS Code's existing Copilot integration - no separate authentication needed!
    Perfect for users who already have GitHub Copilot working in VS Code.
    """

    def __init__(self):
        """Initialize the VS Code Copilot provider."""
        self._vscode_path = None
        self._vscode_available = None

    async def _find_vscode_path(self) -> Optional[str]:
        """Find VS Code installation path."""
        if self._vscode_path is not None:
            return self._vscode_path

        # Common VS Code paths
        possible_paths = [
            r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(os.environ.get('USERNAME', '')),
            r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\bin\code".format(os.environ.get('USERNAME', '')),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
            "code",  # If in PATH
        ]

        for path in possible_paths:
            try:
                if path == "code":
                    # Test if 'code' command works
                    process = await asyncio.create_subprocess_shell(
                        "code --version",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
                    if process.returncode == 0:
                        self._vscode_path = "code"
                        return self._vscode_path
                elif os.path.exists(path):
                    self._vscode_path = f'"{path}"'
                    return self._vscode_path
            except Exception:
                continue

        return None

    async def check_vscode_available(self) -> tuple[bool, str]:
        """Check if VS Code is available."""
        if self._vscode_available is not None:
            return self._vscode_available

        vscode_path = await self._find_vscode_path()
        if not vscode_path:
            self._vscode_available = (False, "VS Code not found. Please install VS Code.")
            return self._vscode_available

        try:
            # Test VS Code availability
            process = await asyncio.create_subprocess_shell(
                f"{vscode_path} --version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)

            if process.returncode == 0:
                version_lines = stdout.decode('utf-8').strip().split('\n')
                version = version_lines[0] if version_lines else "unknown"
                self._vscode_available = (True, f"VS Code {version} found")
                return self._vscode_available
            else:
                self._vscode_available = (False, f"VS Code error: {stderr.decode('utf-8')}")
                return self._vscode_available

        except Exception as e:
            self._vscode_available = (False, f"VS Code test failed: {str(e)}")
            return self._vscode_available

    async def check_copilot_extension(self) -> tuple[bool, str]:
        """Check if GitHub Copilot extension is installed in VS Code."""
        vscode_path = await self._find_vscode_path()
        if not vscode_path:
            return False, "VS Code not available"

        try:
            # List VS Code extensions
            process = await asyncio.create_subprocess_shell(
                f"{vscode_path} --list-extensions",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)

            if process.returncode == 0:
                extensions = stdout.decode('utf-8').lower()
                if 'github.copilot' in extensions:
                    return True, "GitHub Copilot extension found in VS Code"
                else:
                    return False, "GitHub Copilot extension not installed. Install it from VS Code marketplace."
            else:
                return False, f"Failed to list extensions: {stderr.decode('utf-8')}"

        except Exception as e:
            return False, f"Extension check failed: {str(e)}"

    async def check_available(self) -> tuple[bool, str]:
        """Check if VS Code Copilot is available."""
        # Check VS Code
        vscode_ok, vscode_msg = await self.check_vscode_available()
        if not vscode_ok:
            return False, vscode_msg

        # Check Copilot extension
        copilot_ok, copilot_msg = await self.check_copilot_extension()
        if not copilot_ok:
            return False, copilot_msg

        return True, f"VS Code Copilot ready ({vscode_msg}, {copilot_msg})"

    async def chat_via_comment(self, prompt: str, context: Optional[str] = None) -> str:
        """
        Use VS Code Copilot via code comments technique.

        This creates a temporary file with a comment containing the prompt,
        then uses VS Code to get Copilot suggestions.
        """
        vscode_path = await self._find_vscode_path()
        if not vscode_path:
            return "Error: VS Code not available"

        try:
            # Create temporary file with prompt as comment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                temp_file = f.name

                # Write context and prompt as comments
                f.write("# GitHub Copilot Chat Request\n")
                if context:
                    f.write(f"# Context: {context}\n")
                f.write(f"# Question: {prompt}\n")
                f.write("# Copilot, please provide a detailed response:\n")
                f.write("\n")
                f.write('"""\n')
                f.write("Response:\n")
                f.write('"""\n')

            # Open file in VS Code and wait for user interaction
            process = await asyncio.create_subprocess_shell(
                f"{vscode_path} {temp_file} --wait",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for VS Code to close (user saves and closes)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)  # 5 minute timeout

            # Read the modified file
            try:
                with open(temp_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract response from the file
                if '"""' in content:
                    parts = content.split('"""')
                    if len(parts) >= 3:
                        response_part = parts[1].strip()
                        if response_part and response_part != "Response:":
                            return response_part.replace("Response:", "").strip()

                return "No Copilot response found. Make sure to use Copilot suggestions in VS Code (Ctrl+I or Copilot chat)."

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except:
                    pass

        except asyncio.TimeoutError:
            return "Timeout: Please close VS Code to continue, or use Copilot inline suggestions."
        except Exception as e:
            return f"VS Code Copilot error: {str(e)}"

    async def chat_via_workspace(self, prompt: str, context: Optional[str] = None) -> str:
        """
        Alternative method: Create a chat request file in current workspace.
        """
        try:
            # Find current working directory or create in temp
            workspace_dir = os.getcwd()

            # Create a copilot chat file
            chat_file = os.path.join(workspace_dir, ".copilot_chat.md")

            with open(chat_file, 'w', encoding='utf-8') as f:
                f.write("# Copilot Chat Request\n\n")
                if context:
                    f.write(f"## Context\n{context}\n\n")
                f.write(f"## Question\n{prompt}\n\n")
                f.write("## Response\n")
                f.write("_Please use GitHub Copilot Chat in VS Code to answer the question above._\n")
                f.write("_Instructions: Open this file in VS Code, select the question, and use Ctrl+I or Copilot Chat._\n")

            return f"Created chat request file: {chat_file}\n\nNext steps:\n1. Open '{chat_file}' in VS Code\n2. Select the question text\n3. Use Ctrl+I or GitHub Copilot Chat\n4. Copy the response back to JARVIS"

        except Exception as e:
            return f"Error creating chat file: {str(e)}"

    async def chat(self, prompt: str, context: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        """
        Chat with Copilot via VS Code integration.

        This method provides instructions for using VS Code Copilot manually,
        since direct API access requires the user's VS Code session.
        """
        # Check if VS Code Copilot is available
        available, status_msg = await self.check_available()
        if not available:
            return f"Error: {status_msg}"

        # For now, provide instructions for manual VS Code Copilot usage
        instructions = f"""
🤖 **VS Code Copilot Integration**

Since GitHub Copilot works in your VS Code, here's how to get AI assistance:

**📝 Your Question:** {prompt}

**🔧 Method 1 - VS Code Copilot Chat:**
1. Open VS Code
2. Press `Ctrl + Shift + I` (or Cmd + Shift + I on Mac)
3. Type your question: "{prompt}"
4. Get instant AI response!

**🔧 Method 2 - Inline Copilot:**
1. Open any code file in VS Code
2. Type a comment: `// {prompt}`
3. Press Enter and wait for Copilot suggestions
4. Accept with Tab

**💡 Alternative - Create Chat File:**
"""

        # Also create a chat file for convenience
        chat_result = await self.chat_via_workspace(prompt, context)

        return instructions + "\n" + chat_result

    async def explain_code(self, code: str, language: Optional[str] = None) -> str:
        """Ask VS Code Copilot to explain code."""
        lang_hint = f" ({language})" if language else ""
        prompt = f"Please explain this code{lang_hint}:\n\n```\n{code}\n```"
        return await self.chat(prompt)

    async def suggest_improvements(self, code: str, language: Optional[str] = None) -> str:
        """Ask VS Code Copilot to suggest improvements."""
        lang_hint = f" ({language})" if language else ""
        prompt = f"Please suggest improvements for this code{lang_hint}:\n\n```\n{code}\n```"
        return await self.chat(prompt)


# Global instance
_vscode_copilot: Optional[VSCodeCopilotProvider] = None


def get_vscode_copilot() -> VSCodeCopilotProvider:
    """Get the global VS Code Copilot provider instance."""
    global _vscode_copilot
    if _vscode_copilot is None:
        _vscode_copilot = VSCodeCopilotProvider()
    return _vscode_copilot


__all__ = ["VSCodeCopilotProvider", "get_vscode_copilot"]