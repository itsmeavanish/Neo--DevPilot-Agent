import os
import platform
import asyncio
from pathlib import Path
from .models import CommandResponse

async def run_command(command: str, timeout: int = 30) -> CommandResponse:
    """Execute a shell command."""
    try:
        if platform.system() == "Windows":
            shell = True
        else:
            shell = True

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
