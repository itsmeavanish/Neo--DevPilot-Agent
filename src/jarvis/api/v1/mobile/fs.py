import os
import asyncio
import platform
from pathlib import Path
from fastapi import APIRouter
from .models import (
    DirectoryRequest, DirectoryListing, FileInfo,
    FileReadRequest, FileContent, ProjectInfoRequest,
    ProjectInfo, SearchRequest, SearchResponse,
    FileWriteRequest, FileWriteResponse
)
from .utils import get_file_extension, detect_language, detect_project_type

router = APIRouter()

@router.post("/project/list", response_model=DirectoryListing)
async def list_directory(request: DirectoryRequest):
    """List directory contents."""
    path = request.path
    if platform.system() == "Windows" and path.startswith("~"):
        path = os.path.expanduser(path)
    if not os.path.exists(path):
        return DirectoryListing(path=path, files=[], count=0, error=f"Path not found: {path}")
    if not os.path.isdir(path):
        return DirectoryListing(path=path, files=[], count=0, error=f"Not a directory: {path}")

    try:
        entries = os.listdir(path)
        files = []
        for entry in sorted(entries):
            if entry.startswith('.') and not request.show_hidden:
                continue
            full_path = os.path.join(path, entry)
            try:
                is_dir = os.path.isdir(full_path)
                size = 0 if is_dir else os.path.getsize(full_path)
                ext = "" if is_dir else get_file_extension(entry)
                files.append(FileInfo(name=entry, path=full_path, is_dir=is_dir, size=size, extension=ext))
            except (PermissionError, OSError):
                continue

        files.sort(key=lambda f: (not f.is_dir, f.name.lower()))
        return DirectoryListing(path=os.path.abspath(path), files=files, count=len(files))
    except PermissionError:
        return DirectoryListing(path=path, files=[], count=0, error="Permission denied")
    except Exception as e:
        return DirectoryListing(path=path, files=[], count=0, error=str(e))

@router.post("/project/read", response_model=FileContent)
async def read_file(request: FileReadRequest):
    """Read file contents."""
    path = request.path
    if not os.path.exists(path):
        return FileContent(path=path, content="", lines=0, language="text", size=0, error=f"File not found: {path}")
    if os.path.isdir(path):
        return FileContent(path=path, content="", lines=0, language="text", size=0, error="Cannot read directory")

    try:
        size = os.path.getsize(path)
        if size > 5 * 1024 * 1024:
            return FileContent(path=path, content="", lines=0, language=detect_language(path), size=size, error="File too large (>5MB)")

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            lines = all_lines[:request.max_lines]
            content = ''.join(lines)
            if len(all_lines) > request.max_lines:
                content += f"\n... (truncated, showing {request.max_lines}/{len(all_lines)} lines)"

        return FileContent(path=os.path.abspath(path), content=content, lines=len(all_lines), language=detect_language(path), size=size)
    except Exception as e:
        return FileContent(path=path, content="", lines=0, language="text", size=0, error=str(e))

@router.post("/project/info", response_model=ProjectInfo)
async def get_project_info(request: ProjectInfoRequest):
    """Get project information."""
    path = request.path
    if not os.path.exists(path):
        return ProjectInfo(path=path, name="", type="Unknown", code_files=0, has_git=False, has_package_json=False, has_requirements=False, error=f"Path not found: {path}")
    
    p = Path(path)
    code_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.rb', '.php', '.c', '.cpp', '.h'}
    code_files = 0
    try:
        for item in p.rglob('*'):
            if item.is_file() and item.suffix.lower() in code_extensions:
                code_files += 1
                if code_files > 1000:
                    break
    except (PermissionError, OSError):
        pass

    return ProjectInfo(
        path=str(path), name=p.name, type=detect_project_type(path), code_files=code_files,
        has_git=(p / '.git').exists(), has_package_json=(p / 'package.json').exists(),
        has_requirements=(p / 'requirements.txt').exists() or (p / 'pyproject.toml').exists()
    )

@router.post("/project/search", response_model=SearchResponse)
async def search_files(request: SearchRequest):
    """Search files in the given path for a text pattern."""
    query = request.query
    search_path = request.path
    max_results = request.max_results
    case_sensitive = request.case_sensitive
    file_pattern = request.file_pattern or "*.*"

    p = Path(search_path).expanduser().resolve()
    if not p.exists():
        return SearchResponse(results=[], total_matches=0, error=f"Path not found: {search_path}")

    results = []
    try:
        import shutil
        rg_path = shutil.which("rg")
        grep_path = shutil.which("grep")

        cmd = None
        if rg_path:
            cmd = [rg_path, "--line-number", "--no-heading", "--color=never", f"--max-count={max_results}"]
            if not case_sensitive:
                cmd.append("--ignore-case")
            if request.file_pattern:
                cmd.extend(["--glob", request.file_pattern])
            cmd.extend([query, str(p)])
        elif grep_path:
            cmd = [grep_path, "-rn", "--color=never", f"--max-count={max_results}"]
            if not case_sensitive:
                cmd.append("-i")
            if request.file_pattern:
                cmd.extend(["--include", request.file_pattern])
            cmd.extend([query, str(p)])
        
        if cmd:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="replace")
            for line in output.splitlines()[:max_results]:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    results.append({
                        "file": parts[0],
                        "line": int(parts[1]) if parts[1].isdigit() else 0,
                        "content": parts[2].strip(),
                        "match_start": 0,
                        "match_end": 0,
                    })
        else:
            count = 0
            for item in p.rglob(file_pattern):
                if item.is_file():
                    try:
                        text = item.read_text(encoding="utf-8", errors="ignore")
                        lines = text.splitlines()
                        for i, line in enumerate(lines):
                            if (query in line) if case_sensitive else (query.lower() in line.lower()):
                                results.append({
                                    "file": str(item),
                                    "line": i + 1,
                                    "content": line.strip(),
                                    "match_start": 0,
                                    "match_end": 0,
                                })
                                count += 1
                                if count >= max_results:
                                    break
                    except Exception:
                        pass
                if count >= max_results:
                    break

        return SearchResponse(results=results, total_matches=len(results))
    except Exception as e:
        return SearchResponse(results=[], total_matches=0, error=str(e))

@router.post("/project/write", response_model=FileWriteResponse)
async def write_file(request: FileWriteRequest):
    """Write content to a file."""
    path = request.path
    try:
        backup_path = None
        if request.create_backup and os.path.exists(path):
            backup_path = f"{path}.backup"
            import shutil
            shutil.copy2(path, backup_path)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(request.content)

        return FileWriteResponse(
            success=True, path=os.path.abspath(path), message="File saved successfully", backup_path=backup_path
        )
    except PermissionError:
        return FileWriteResponse(success=False, path=path, message="Permission denied")
    except Exception as e:
        return FileWriteResponse(success=False, path=path, message=str(e))
