"""
Dependency monitor for self-healing system.

Detects missing or outdated dependencies.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import ClassVar

from jarvis.self_heal.monitors.base import BaseMonitor
from jarvis.self_heal.models.issue import Issue, IssueCategory, IssueSeverity


class DependencyMonitor(BaseMonitor):
    """Monitor for project dependencies."""

    name: ClassVar[str] = "dependency"
    description: ClassVar[str] = "Monitors project dependencies for issues"

    # Project root to check
    project_root: Path | None = None

    async def check(self) -> list[Issue]:
        """Check for dependency issues."""
        issues = []

        root = self.project_root or Path.cwd()

        # Check for Node.js dependencies
        package_json = root / "package.json"
        if package_json.exists():
            node_issues = await self._check_node_deps(root)
            issues.extend(node_issues)

        # Check for Python dependencies
        requirements = root / "requirements.txt"
        pyproject = root / "pyproject.toml"
        if requirements.exists() or pyproject.exists():
            python_issues = await self._check_python_deps(root)
            issues.extend(python_issues)

        return issues

    async def _check_node_deps(self, root: Path) -> list[Issue]:
        """Check Node.js dependencies."""
        issues = []

        # Check if node_modules exists
        node_modules = root / "node_modules"
        if not node_modules.exists():
            issues.append(Issue(
                category=IssueCategory.DEPENDENCY,
                severity=IssueSeverity.ERROR,
                title="Node modules not installed",
                description="node_modules directory is missing",
                details={"path": str(root)},
                source=self.name,
                affected_resource="node_modules",
                suggested_resolution="Run: npm install",
                auto_resolvable=True,
                requires_approval=True,
            ))
            return issues

        # Try to run npm ls to check for issues
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["npm", "ls", "--json", "--depth=0"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                try:
                    data = json.loads(result.stdout)
                    problems = data.get("problems", [])
                    if problems:
                        issues.append(Issue(
                            category=IssueCategory.DEPENDENCY,
                            severity=IssueSeverity.WARNING,
                            title="NPM dependency issues",
                            description=f"{len(problems)} dependency problem(s) found",
                            details={
                                "problems": problems[:5],
                                "total": len(problems),
                            },
                            source=self.name,
                            affected_resource="npm",
                            suggested_resolution="Run: npm install or npm audit fix",
                            auto_resolvable=True,
                        ))
                except json.JSONDecodeError:
                    pass

        except FileNotFoundError:
            self.logger.debug("npm not found")
        except subprocess.TimeoutExpired:
            self.logger.debug("npm ls timed out")
        except Exception as e:
            self.logger.debug(f"Error checking npm deps: {e}")

        # Check for package-lock sync
        package_lock = root / "package-lock.json"
        package_json = root / "package.json"
        if package_lock.exists() and package_json.exists():
            lock_mtime = package_lock.stat().st_mtime
            json_mtime = package_json.stat().st_mtime
            if json_mtime > lock_mtime:
                issues.append(Issue(
                    category=IssueCategory.DEPENDENCY,
                    severity=IssueSeverity.WARNING,
                    title="Package lock out of sync",
                    description="package.json is newer than package-lock.json",
                    details={"path": str(root)},
                    source=self.name,
                    affected_resource="package-lock.json",
                    suggested_resolution="Run: npm install",
                    auto_resolvable=True,
                ))

        return issues

    async def _check_python_deps(self, root: Path) -> list[Issue]:
        """Check Python dependencies."""
        issues = []

        # Check if in a virtual environment
        venv_paths = [
            root / "venv",
            root / ".venv",
            root / "env",
        ]
        has_venv = any(p.exists() for p in venv_paths)

        # Check for missing dependencies
        requirements = root / "requirements.txt"
        if requirements.exists():
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["pip", "check"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode != 0 and result.stdout:
                    issues.append(Issue(
                        category=IssueCategory.DEPENDENCY,
                        severity=IssueSeverity.WARNING,
                        title="Python dependency issues",
                        description="Incompatible or missing packages detected",
                        details={
                            "output": result.stdout[:500],
                            "has_venv": has_venv,
                        },
                        source=self.name,
                        affected_resource="pip",
                        suggested_resolution="Run: pip install -r requirements.txt",
                        auto_resolvable=True,
                    ))

            except FileNotFoundError:
                self.logger.debug("pip not found")
            except subprocess.TimeoutExpired:
                self.logger.debug("pip check timed out")
            except Exception as e:
                self.logger.debug(f"Error checking pip deps: {e}")

        return issues

    def set_project_root(self, path: str | Path) -> None:
        """Set the project root to monitor."""
        self.project_root = Path(path)


__all__ = ["DependencyMonitor"]
