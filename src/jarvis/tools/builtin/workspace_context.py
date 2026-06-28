"""
Workspace context gathering for full-folder awareness.

Collects the project structure (file tree, key files, metadata) and provides
it to the LLM so it can reason about the entire project — not just one file.
Works both locally and on paired remote laptops via the agent WebSocket.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.tools.workspace_context")

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".nuxt",
    "dist", "build", ".venv", "venv", "env", ".env",
    ".idea", ".vscode", ".DS_Store", "coverage",
    ".expo", ".turbo", "target", "out", ".output",
    "vendor", "packages", ".cache", ".parcel-cache",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".o", ".obj", ".exe", ".dll",
    ".so", ".dylib", ".lock", ".log", ".map", ".min.js",
    ".min.css", ".woff", ".woff2", ".ttf", ".eot",
    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".pdf",
}

PROJECT_METADATA_FILES = [
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
    "requirements.txt", "Pipfile", "Gemfile", "pom.xml",
    "build.gradle", "Makefile", "CMakeLists.txt",
    "docker-compose.yml", "Dockerfile",
    ".gitignore", "tsconfig.json", "vite.config.ts",
    "next.config.js", "next.config.ts",
]

MAX_TREE_ENTRIES = 500
MAX_FILE_PREVIEW_BYTES = 4096


def _should_ignore(name: str, is_dir: bool) -> bool:
    if is_dir:
        return name in IGNORE_DIRS or name.startswith(".")
    ext = os.path.splitext(name)[1].lower()
    return ext in IGNORE_EXTENSIONS


def gather_local_folder_context(workspace_root: str, max_depth: int = 4) -> dict[str, Any]:
    """
    Gather folder structure from a local workspace path.
    Returns a dict with tree, metadata files content, and summary.
    """
    root = Path(workspace_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return {"error": f"Workspace not found: {workspace_root}"}

    tree_lines: list[str] = []
    file_count = 0
    dir_count = 0
    metadata_contents: dict[str, str] = {}

    def walk(path: Path, prefix: str, depth: int):
        nonlocal file_count, dir_count

        if depth > max_depth:
            return
        if len(tree_lines) >= MAX_TREE_ENTRIES:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and not _should_ignore(e.name, True)]
        files = [e for e in entries if e.is_file() and not _should_ignore(e.name, False)]

        for i, d in enumerate(dirs):
            if len(tree_lines) >= MAX_TREE_ENTRIES:
                break
            is_last_dir = (i == len(dirs) - 1) and not files
            connector = "└── " if is_last_dir else "├── "
            tree_lines.append(f"{prefix}{connector}{d.name}/")
            dir_count += 1
            child_prefix = prefix + ("    " if is_last_dir else "│   ")
            walk(d, child_prefix, depth + 1)

        for i, f in enumerate(files):
            if len(tree_lines) >= MAX_TREE_ENTRIES:
                break
            is_last = i == len(files) - 1
            connector = "└── " if is_last else "├── "
            size = _format_size(f.stat().st_size) if f.exists() else ""
            tree_lines.append(f"{prefix}{connector}{f.name}  ({size})")
            file_count += 1

            # Capture metadata file contents
            if f.name in PROJECT_METADATA_FILES:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if len(content) > MAX_FILE_PREVIEW_BYTES:
                        content = content[:MAX_FILE_PREVIEW_BYTES] + "\n... (truncated)"
                    metadata_contents[str(f.relative_to(root))] = content
                except (PermissionError, OSError):
                    pass

    walk(root, "", 0)

    tree_str = f"{root.name}/\n" + "\n".join(tree_lines)
    if len(tree_lines) >= MAX_TREE_ENTRIES:
        tree_str += "\n... (tree truncated)"

    return {
        "workspace_root": str(root),
        "tree": tree_str,
        "file_count": file_count,
        "dir_count": dir_count,
        "metadata": metadata_contents,
    }


async def gather_remote_folder_context(
    pairing_code: str,
    workspace_root: str,
    max_depth: int = 3,
) -> dict[str, Any]:
    """
    Gather folder structure from a paired remote laptop via WebSocket agent.
    Uses the standard directory_list command and walks subdirectories.
    """
    from jarvis.devices.agent_registry import get_agent_registry

    registry = get_agent_registry()

    all_entries: list[dict] = []
    dirs_to_visit = [(workspace_root, 0)]
    visited = set()

    while dirs_to_visit and len(all_entries) < MAX_TREE_ENTRIES:
        current_path, depth = dirs_to_visit.pop(0)
        if depth > max_depth or current_path in visited:
            continue
        visited.add(current_path)

        try:
            raw = await registry.send_agent_request(
                pairing_code,
                {"type": "directory_list", "path": current_path, "show_hidden": False},
                wait_timeout=15,
            )
        except Exception:
            continue

        if raw.get("_offline"):
            return {"error": "Paired laptop is offline"}
        if not raw.get("success"):
            continue

        files = raw.get("files") or []
        for entry in files:
            name = entry.get("name", "")
            ftype = entry.get("type", "file")

            if _should_ignore(os.path.basename(name), ftype == "dir"):
                continue

            # Make path relative to workspace root
            rel_path = name
            if current_path != workspace_root:
                prefix = current_path.replace(workspace_root, "").lstrip("/").lstrip("\\")
                rel_path = f"{prefix}/{name}" if prefix else name

            all_entries.append({"name": rel_path, "type": ftype})

            if ftype == "dir" and depth < max_depth:
                sep = "/" if "/" in workspace_root else "\\"
                dirs_to_visit.append((f"{current_path}{sep}{name}", depth + 1))

    # Build tree from collected entries
    tree_str = _build_tree_from_flat_list(all_entries, workspace_root)

    # Try reading key metadata files
    metadata_contents: dict[str, str] = {}
    sep = "/" if "/" in workspace_root else "\\"
    for meta_file in PROJECT_METADATA_FILES[:5]:
        try:
            file_raw = await registry.send_agent_request(
                pairing_code,
                {"type": "file_read", "path": f"{workspace_root}{sep}{meta_file}", "max_lines": 100},
                wait_timeout=10,
            )
            if file_raw.get("success") and file_raw.get("content"):
                content = file_raw["content"]
                if len(content) > MAX_FILE_PREVIEW_BYTES:
                    content = content[:MAX_FILE_PREVIEW_BYTES] + "\n... (truncated)"
                metadata_contents[meta_file] = content
        except Exception:
            pass

    file_count = len([e for e in all_entries if e.get("type") == "file"])
    dir_count = len([e for e in all_entries if e.get("type") == "dir"])

    return {
        "workspace_root": workspace_root,
        "tree": tree_str,
        "file_count": file_count,
        "dir_count": dir_count,
        "metadata": metadata_contents,
    }


async def gather_workspace_context(
    workspace_root: str | None,
    pairing_code: str | None = None,
) -> dict[str, Any] | None:
    """
    Main entry point: gather workspace context either locally or remotely.
    Returns None if no workspace_root is available.
    """
    if not workspace_root:
        return None

    try:
        if pairing_code:
            return await gather_remote_folder_context(pairing_code, workspace_root)
        else:
            return gather_local_folder_context(workspace_root)
    except Exception as e:
        logger.warning(f"Failed to gather workspace context: {e}")
        return None


def format_context_for_prompt(ctx: dict[str, Any] | None) -> str:
    """Format the gathered context into a string suitable for LLM system prompts."""
    if not ctx or ctx.get("error"):
        return ""

    parts = [
        f"## Project Workspace: {ctx.get('workspace_root', 'unknown')}",
        f"Files: {ctx.get('file_count', 0)} | Directories: {ctx.get('dir_count', 0)}",
        "",
        "### File Structure:",
        "```",
        ctx.get("tree", "(empty)"),
        "```",
    ]

    metadata = ctx.get("metadata", {})
    if metadata:
        parts.append("")
        parts.append("### Key Project Files:")
        for filename, content in metadata.items():
            parts.append(f"\n**{filename}:**")
            parts.append(f"```")
            parts.append(content)
            parts.append("```")

    return "\n".join(parts)


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def _build_tree_from_flat_list(files: list, workspace_root: str) -> str:
    """Build an indented tree string from a flat list of file entries."""
    if not files:
        return "(empty)"

    if isinstance(files, list) and files and isinstance(files[0], dict):
        # Structured entries: [{name, type, size?}]
        lines = []
        for entry in files[:MAX_TREE_ENTRIES]:
            name = entry.get("name", "")
            ftype = entry.get("type", "file")
            suffix = "/" if ftype == "dir" else ""
            depth = name.count("/") + name.count("\\")
            indent = "  " * depth
            basename = os.path.basename(name) or name
            lines.append(f"{indent}{basename}{suffix}")
        return "\n".join(lines)

    # Simple string list
    return "\n".join(str(f) for f in files[:MAX_TREE_ENTRIES])
