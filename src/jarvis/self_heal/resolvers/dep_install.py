"""
Dependency installation resolver.

Handles missing or broken dependencies for Node.js and Python projects.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import ClassVar

from jarvis.self_heal.resolvers.base import BaseResolver
from jarvis.self_heal.models.issue import Issue, IssueCategory


class DependencyInstallResolver(BaseResolver):
    """Resolver for dependency issues."""

    name: ClassVar[str] = "dep_install"
    description: ClassVar[str] = "Installs missing or fixes broken dependencies"
    handles: ClassVar[list[IssueCategory]] = [IssueCategory.DEPENDENCY]

    async def _execute(self, issue: Issue) -> tuple[bool, str, list[dict]]:
        """Execute dependency installation."""
        steps = []

        resource = issue.affected_resource
        project_path = issue.details.get("path", ".")

        if resource in ("node_modules", "npm", "package-lock.json"):
            return await self._fix_node_deps(project_path, issue, steps)
        elif resource == "pip":
            return await self._fix_python_deps(project_path, issue, steps)
        else:
            return False, f"Unknown dependency type: {resource}", steps

    async def _fix_node_deps(
        self, project_path: str, issue: Issue, steps: list[dict]
    ) -> tuple[bool, str, list[dict]]:
        """Fix Node.js dependencies."""
        path = Path(project_path)

        # Determine the appropriate command
        if "node_modules" in issue.title.lower() or "not installed" in issue.title.lower():
            # Fresh install needed
            cmd = ["npm", "install"]
            action = "npm install (fresh)"
        elif "lock" in issue.title.lower():
            # Lock file out of sync
            cmd = ["npm", "install"]
            action = "npm install (sync lock)"
        elif "audit" in issue.suggested_resolution.lower() if issue.suggested_resolution else False:
            # Security issues
            cmd = ["npm", "audit", "fix"]
            action = "npm audit fix"
        else:
            # General dependency issues
            cmd = ["npm", "install"]
            action = "npm install"

        # Execute npm command
        install_step = await self._run_npm_command(cmd, path, action)
        steps.append(install_step)

        if not install_step["success"]:
            # Try with --force if regular install failed
            force_step = await self._run_npm_command(
                ["npm", "install", "--force"],
                path,
                "npm install --force (retry)"
            )
            steps.append(force_step)
            return force_step["success"], force_step["output"], steps

        return install_step["success"], install_step["output"], steps

    async def _fix_python_deps(
        self, project_path: str, issue: Issue, steps: list[dict]
    ) -> tuple[bool, str, list[dict]]:
        """Fix Python dependencies."""
        path = Path(project_path)

        # Check for requirements.txt
        requirements = path / "requirements.txt"
        pyproject = path / "pyproject.toml"

        if requirements.exists():
            # Install from requirements.txt
            cmd = ["pip", "install", "-r", str(requirements)]
            install_step = await self._run_pip_command(
                cmd, path, "pip install -r requirements.txt"
            )
            steps.append(install_step)

            if not install_step["success"]:
                # Try upgrading pip first
                upgrade_step = await self._run_pip_command(
                    ["pip", "install", "--upgrade", "pip"],
                    path,
                    "upgrade pip"
                )
                steps.append(upgrade_step)

                # Retry installation
                retry_step = await self._run_pip_command(
                    cmd, path, "pip install -r requirements.txt (retry)"
                )
                steps.append(retry_step)
                return retry_step["success"], retry_step["output"], steps

            return install_step["success"], install_step["output"], steps

        elif pyproject.exists():
            # Install from pyproject.toml
            cmd = ["pip", "install", "-e", "."]
            install_step = await self._run_pip_command(
                cmd, path, "pip install -e ."
            )
            steps.append(install_step)
            return install_step["success"], install_step["output"], steps

        return False, "No requirements.txt or pyproject.toml found", steps

    async def _run_npm_command(
        self, cmd: list[str], cwd: Path, action: str
    ) -> dict:
        """Run an npm command."""
        step = {
            "action": action,
            "command": " ".join(cmd),
            "success": False,
            "output": "",
        }

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout for npm install
            )

            step["success"] = result.returncode == 0
            step["output"] = result.stdout if result.returncode == 0 else result.stderr

            if step["success"]:
                step["output"] = "Dependencies installed successfully"

        except subprocess.TimeoutExpired:
            step["output"] = "npm command timed out (5 minutes)"
        except FileNotFoundError:
            step["output"] = "npm not found in PATH"
        except Exception as e:
            step["output"] = str(e)

        return step

    async def _run_pip_command(
        self, cmd: list[str], cwd: Path, action: str
    ) -> dict:
        """Run a pip command."""
        step = {
            "action": action,
            "command": " ".join(cmd),
            "success": False,
            "output": "",
        }

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
            )

            step["success"] = result.returncode == 0
            step["output"] = result.stdout if result.returncode == 0 else result.stderr

            if step["success"]:
                step["output"] = "Dependencies installed successfully"

        except subprocess.TimeoutExpired:
            step["output"] = "pip command timed out (5 minutes)"
        except FileNotFoundError:
            step["output"] = "pip not found in PATH"
        except Exception as e:
            step["output"] = str(e)

        return step

    def estimate_risk(self, issue: Issue) -> str:
        """Estimate risk of dependency installation."""
        # Installing dependencies is generally low-medium risk
        if "force" in str(issue.suggested_resolution).lower():
            return "medium"
        return "low"


__all__ = ["DependencyInstallResolver"]
