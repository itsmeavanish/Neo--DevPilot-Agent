#!/usr/bin/env python3
"""
JARVIS Remote Agent - Lightweight Edition
Connect your laptop to JARVIS mobile app.
"""
import asyncio
import json
import os
import platform
import subprocess
import sys
import secrets
from datetime import datetime
from pathlib import Path
# Auto-install dependencies
for pkg in ["websockets", "psutil"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
import websockets
import psutil

# Configuration
SERVER_URL = os.getenv("JARVIS_SERVER", "https://neo-api-oths.onrender.com")
DEVICE_NAME = os.getenv("JARVIS_DEVICE_NAME", platform.node())
# Generate or load pairing code (unique per laptop)
CONFIG_DIR = Path.home() / ".jarvis"
CONFIG_DIR.mkdir(exist_ok=True)
PAIRING_CODE_FILE = CONFIG_DIR / "pairing_code"
def get_pairing_code():
    """Generate or load the unique pairing code for this laptop."""
    if PAIRING_CODE_FILE.exists():
        return PAIRING_CODE_FILE.read_text().strip()
    # Generate 6-character uppercase code (easy to type on phone)
    code = secrets.token_hex(3).upper()  # e.g., "A1B2C3"
    PAIRING_CODE_FILE.write_text(code)
    return code
PAIRING_CODE = get_pairing_code()


def _file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return os.path.splitext(filename)[1]


def _detect_language(path: str) -> str:
    ext = _file_extension(path).lower()
    languages = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".json": "json",
        ".html": "html",
        ".css": "css",
        ".md": "markdown",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".sh": "shell",
        ".sql": "sql",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".txt": "text",
    }
    return languages.get(ext, "text")


def _detect_project_type(p: Path) -> str:
    if (p / "package.json").exists():
        return "Node.js"
    if (p / "requirements.txt").exists() or (p / "pyproject.toml").exists():
        return "Python"
    if (p / "go.mod").exists():
        return "Go"
    if (p / "Cargo.toml").exists():
        return "Rust"
    return "Unknown"


def _hmac_sign_message(payload: dict, shared_secret: str) -> dict:
    """Sign a message with HMAC-SHA256 (inline to avoid import dependencies)."""
    import hashlib
    import hmac as _hmac
    import time as _time
    timestamp = str(int(_time.time()))
    filtered = {k: v for k, v in payload.items() if not k.startswith("_hmac_")}
    canonical = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
    sign_input = f"{timestamp}.{canonical}"
    signature = _hmac.new(
        shared_secret.encode(), sign_input.encode(), hashlib.sha256
    ).hexdigest()
    return {**payload, "_hmac_timestamp": timestamp, "_hmac_signature": signature}


class JarvisAgent:
    def __init__(self):
        base_url = SERVER_URL.replace("https://", "wss://").replace("http://", "ws://")
        # Use pairing code as device ID - this links app to this specific laptop
        self.ws_url = f"{base_url}/api/v1/ws/agents/{PAIRING_CODE}"
        self.name = DEVICE_NAME
        self.running = True
        self.ws = None
        self.session_token = None
        self.hmac_secret = None
        self.capabilities = []

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{level}] {msg}")
    async def connect(self):
        self.log(f"Connecting to JARVIS server at {self.ws_url} ...")
        try:
            # Add connection timeout to prevent hanging
            self.ws = await asyncio.wait_for(
                websockets.connect(self.ws_url, ping_interval=30),
                timeout=10
            )
            # Send registration message with pairing code
            reg_msg = {
                "type": "register",
                "hostname": self.name,
                "platform": platform.system(),
                "device_id": PAIRING_CODE,
                "pairing_code": PAIRING_CODE
            }
            await self.ws.send(json.dumps(reg_msg))
            # Wait for confirmation
            response = await asyncio.wait_for(self.ws.recv(), timeout=5)
            data = json.loads(response)
            if data.get("type") == "registered":
                self.session_token = data.get("session_token")
                self.hmac_secret = data.get("hmac_secret")
                self.capabilities = data.get("capabilities", [])
                hmac_status = "HMAC enabled" if self.hmac_secret else "no HMAC"
                self.log(f"Connected! {data.get('message', '')} ({hmac_status})", "SUCCESS")
                return True
            else:
                self.log(f"Registration failed: {data}", "ERROR")
                return False
        except asyncio.TimeoutError:
            self.log(f"Connection timeout - JARVIS server may not be running at {self.ws_url}", "ERROR")
            return False
        except Exception as e:
            self.log(f"Connection failed to {self.ws_url}: {e}", "ERROR")
            return False
    async def _send(self, payload: dict):
        """Send a message, signing it with HMAC if secret is available."""
        if self.hmac_secret:
            payload = _hmac_sign_message(payload, self.hmac_secret)
        await self.ws.send(json.dumps(payload))

    async def send_status(self):
        status = {
            "type": "status",
            "hostname": platform.node(),
            "platform": platform.system(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._send(status)
    async def execute(self, cmd, timeout=120):
        self.log(f"Running: {cmd[:60]}...")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "stdout": "", "stderr": "", "exit_code": -1}
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": "", "exit_code": -1}

    async def _reply_directory_list(self, data: dict, request_id: str | None):
        raw = (data.get("path") or "").strip()
        show_hidden = bool(data.get("show_hidden", False))
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except OSError:
            pass

        if not path.exists():
            await self._send({
                "type": "directory_listing",
                "request_id": request_id,
                "success": False,
                "error": f"Path not found: {raw}",
                "path": raw,
                "files": [],
                "count": 0,
            })
            return
        if not path.is_dir():
            await self._send({
                "type": "directory_listing",
                "request_id": request_id,
                "success": False,
                "error": f"Not a directory: {path}",
                "path": str(path),
                "files": [],
                "count": 0,
            })
            return

        files_out = []
        try:
            for entry in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                name = entry.name
                if name.startswith(".") and not show_hidden:
                    continue
                try:
                    is_dir = entry.is_dir()
                    size = 0 if is_dir else entry.stat().st_size
                    ext = "" if is_dir else _file_extension(name)
                    files_out.append(
                        {
                            "name": name,
                            "path": str(entry),
                            "is_dir": is_dir,
                            "size": size,
                            "extension": ext,
                        }
                    )
                except (OSError, PermissionError):
                    continue
        except PermissionError:
            await self._send({
                "type": "directory_listing",
                "request_id": request_id,
                "success": False,
                "error": "Permission denied",
                "path": str(path),
                "files": [],
                "count": 0,
            })
            return

        await self._send({
            "type": "directory_listing",
            "request_id": request_id,
            "success": True,
            "path": str(path),
            "files": files_out,
            "count": len(files_out),
        })

    async def _reply_file_read(self, data: dict, request_id: str | None):
        raw = (data.get("path") or "").strip()
        max_lines = int(data.get("max_lines") or 500)
        max_lines = max(1, min(max_lines, 50_000))
        path = Path(raw).expanduser()

        if not path.exists() or not path.is_file():
            await self._send({
                        "type": "file_content",
                        "request_id": request_id,
                        "success": False,
                        "path": raw,
                        "content": "",
                        "lines": 0,
                        "language": "text",
                        "size": 0,
                        "error": f"File not found: {raw}",
                    })
            return

        try:
            size = path.stat().st_size
        except OSError as e:
            await self._send({
                        "type": "file_content",
                        "request_id": request_id,
                        "success": False,
                        "path": raw,
                        "error": str(e),
                    })
            return

        if size > 5 * 1024 * 1024:
            await self._send({
                        "type": "file_content",
                        "request_id": request_id,
                        "success": False,
                        "path": str(path),
                        "content": "",
                        "lines": 0,
                        "language": _detect_language(str(path)),
                        "size": size,
                        "error": "File too large (>5MB)",
                    })
            return

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            await self._send({
                        "type": "file_content",
                        "request_id": request_id,
                        "success": False,
                        "path": str(path),
                        "error": str(e),
                    })
            return

        all_lines = text.splitlines(keepends=True)
        shown = all_lines[:max_lines]
        content = "".join(shown)
        if len(all_lines) > max_lines:
            content += f"\n... (truncated, showing {max_lines}/{len(all_lines)} lines)"

        await self._send({
                    "type": "file_content",
                    "request_id": request_id,
                    "success": True,
                    "path": str(path.resolve() if path.exists() else path),
                    "content": content,
                    "lines": len(all_lines),
                    "language": _detect_language(str(path)),
                    "size": size,
                })

    def _path_write_blocked(self, path: Path) -> str | None:
        norm = str(path).replace("/", "\\").lower()
        blocked = [
            "c:\\windows",
            "c:\\program files",
            "c:\\program files (x86)",
            "/etc",
            "/usr",
            "/bin",
            "/sbin",
        ]
        for prefix in blocked:
            if norm.startswith(prefix.replace("/", "\\")):
                return f"Cannot write to protected directory: {prefix}"
        return None

    async def _reply_file_write(self, data: dict, request_id: str | None):
        raw = (data.get("path") or "").strip()
        content = data.get("content")
        create_backup = bool(data.get("create_backup", True))

        if content is None:
            await self._send({
                        "type": "file_result",
                        "request_id": request_id,
                        "success": False,
                        "path": raw,
                        "error": "content is required",
                    })
            return

        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except OSError:
            pass

        blocked = self._path_write_blocked(path)
        if blocked:
            await self._send({
                        "type": "file_result",
                        "request_id": request_id,
                        "success": False,
                        "path": raw,
                        "error": blocked,
                    })
            return

        backup_path = None
        try:
            if create_backup and path.is_file():
                import shutil

                backup_path = str(path) + ".backup"
                shutil.copy2(path, backup_path)

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(content), encoding="utf-8")
            nbytes = len(str(content).encode("utf-8"))

            await self._send({
                        "type": "file_result",
                        "request_id": request_id,
                        "success": True,
                        "path": str(path),
                        "message": "File saved successfully",
                        "backup_path": backup_path,
                        "bytes_written": nbytes,
                    })
        except PermissionError:
            await self._send({
                        "type": "file_result",
                        "request_id": request_id,
                        "success": False,
                        "path": str(path),
                        "error": "Permission denied",
                    })
        except OSError as e:
            await self._send({
                        "type": "file_result",
                        "request_id": request_id,
                        "success": False,
                        "path": raw,
                        "error": str(e),
                    })

    async def _reply_project_info(self, data: dict, request_id: str | None):
        raw = (data.get("path") or "").strip()
        path = Path(raw).expanduser()
        if not path.exists() or not path.is_dir():
            await self._send({
                        "type": "project_info_result",
                        "request_id": request_id,
                        "success": False,
                        "path": raw,
                        "error": f"Path not found: {raw}",
                    })
            return

        p = path
        code_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".c",
            ".cpp",
            ".h",
        }
        code_files = 0
        try:
            for item in p.rglob("*"):
                if item.is_file() and item.suffix.lower() in code_extensions:
                    code_files += 1
                    if code_files > 1000:
                        break
        except (OSError, PermissionError):
            pass

        await self._send({
                    "type": "project_info_result",
                    "request_id": request_id,
                    "success": True,
                    "path": str(p),
                    "name": p.name,
                    "project_type": _detect_project_type(p),
                    "code_files": code_files,
                    "has_git": (p / ".git").exists(),
                    "has_package_json": (p / "package.json").exists(),
                    "has_requirements": (p / "requirements.txt").exists() or (p / "pyproject.toml").exists(),
                })

    async def _reply_file_search(self, data: dict, request_id: str | None):
        """Search files for a text pattern using subprocess grep/findstr."""
        query = (data.get("query") or "").strip()
        search_path = (data.get("path") or ".").strip()
        max_results = int(data.get("max_results") or 50)
        case_sensitive = bool(data.get("case_sensitive", False))
        file_pattern = data.get("file_pattern")  # e.g. "*.py"

        if not query:
            await self._send({
                "type": "search_result",
                "request_id": request_id,
                "success": False,
                "error": "Empty search query",
                "results": [],
                "total_matches": 0,
            })
            return

        path = Path(search_path).expanduser()
        if not path.exists():
            await self._send({
                "type": "search_result",
                "request_id": request_id,
                "success": False,
                "error": f"Path not found: {search_path}",
                "results": [],
                "total_matches": 0,
            })
            return

        results = []
        try:
            # Try ripgrep first, fall back to grep/findstr
            import shutil as _shutil
            rg_path = _shutil.which("rg")
            grep_path = _shutil.which("grep")

            if rg_path:
                cmd = [rg_path, "--line-number", "--no-heading", "--color=never",
                       f"--max-count={max_results}"]
                if not case_sensitive:
                    cmd.append("--ignore-case")
                if file_pattern:
                    cmd.extend(["--glob", file_pattern])
                cmd.extend([query, str(path)])
            elif grep_path:
                cmd = [grep_path, "-rn", "--color=never",
                       f"--max-count={max_results}"]
                if not case_sensitive:
                    cmd.append("-i")
                if file_pattern:
                    cmd.extend(["--include", file_pattern])
                cmd.extend([query, str(path)])
            elif platform.system() == "Windows":
                # Fallback: findstr on Windows
                flags = "/S /N"
                if not case_sensitive:
                    flags += " /I"
                cmd_str = f'findstr {flags} "{query}" "{str(path)}\\*.*"'
                proc = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = stdout.decode("utf-8", errors="replace")
                for line in output.splitlines()[:max_results]:
                    # findstr: filename:linenum:content
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        results.append({
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "content": parts[2].strip(),
                            "match_start": 0,
                            "match_end": 0,
                        })
                await self._send({
                    "type": "search_result",
                    "request_id": request_id,
                    "success": True,
                    "results": results,
                    "total_matches": len(results),
                })
                return
            else:
                cmd = ["grep", "-rn", query, str(path)]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="replace")

            for line in output.splitlines()[:max_results]:
                # rg/grep: filename:linenum:content
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    results.append({
                        "file": parts[0],
                        "line": int(parts[1]) if parts[1].isdigit() else 0,
                        "content": parts[2].strip(),
                        "match_start": 0,
                        "match_end": 0,
                    })

        except asyncio.TimeoutError:
            await self._send({
                "type": "search_result",
                "request_id": request_id,
                "success": False,
                "error": "Search timed out after 30s",
                "results": [],
                "total_matches": 0,
            })
            return
        except Exception as e:
            await self._send({
                "type": "search_result",
                "request_id": request_id,
                "success": False,
                "error": str(e),
                "results": [],
                "total_matches": 0,
            })
            return

        await self._send({
            "type": "search_result",
            "request_id": request_id,
            "success": True,
            "results": results,
            "total_matches": len(results),
        })

    async def handle_message(self, msg):
        try:
            data = json.loads(msg)
            msg_type = data.get("type")
            request_id = data.get("request_id")

            # Authenticate message
            if data.get("session_token") != self.session_token:
                self.log(f"Unauthorized message received (invalid token): {msg_type}", "ERROR")
                # Still reply with an error if there's a request_id
                if request_id:
                    await self._send({
                        "type": "error",
                        "request_id": request_id,
                        "success": False,
                        "error": "Unauthorized: invalid session token"
                    })
                return

            if msg_type == "ping":
                await self._send({"type": "pong", "request_id": request_id})

            elif msg_type == "execute":
                result = await self.execute(data.get("command", ""), data.get("timeout", 120))
                result["type"] = "result"
                result["request_id"] = request_id
                await self._send(result)

            elif msg_type == "status_request":
                await self.send_status()

            elif msg_type == "directory_list":
                await self._reply_directory_list(data, request_id)

            elif msg_type == "project_info":
                await self._reply_project_info(data, request_id)

            elif msg_type == "file_read":
                await self._reply_file_read(data, request_id)

            elif msg_type == "file_write":
                await self._reply_file_write(data, request_id)

            elif msg_type == "file_search":
                await self._reply_file_search(data, request_id)

            elif msg_type == "telemetry_request":
                await self._reply_telemetry(request_id)

        except Exception as e:
            self.log(f"Error: {e}", "ERROR")

    async def _reply_telemetry(self, request_id):
        """Mission-control snapshot: CPU, memory, disk, top processes."""
        try:
            du = psutil.disk_usage(str(Path.home()))
            disk_p = float(du.percent)
        except Exception:
            disk_p = 0.0
        top = []
        try:
            procs = []
            for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent"]):
                try:
                    procs.append(p.info)
                except (psutil.Error, TypeError):
                    continue
            procs.sort(key=lambda i: float(i.get("cpu_percent") or 0), reverse=True)
            for info in procs[:8]:
                top.append(
                    {
                        "pid": info.get("pid"),
                        "name": str(info.get("name") or "")[:48],
                        "cpu_percent": round(float(info.get("cpu_percent") or 0), 1),
                    }
                )
        except Exception:
            pass
        telemetry = {
            "cpu_percent": float(psutil.cpu_percent(interval=0.12)),
            "memory_percent": float(psutil.virtual_memory().percent),
            "disk_percent": disk_p,
            "hostname": platform.node(),
            "platform": platform.system(),
            "top_processes": top,
        }
        await self._send({
                    "type": "telemetry_result",
                    "request_id": request_id,
                    "success": True,
                    "telemetry": telemetry,
                })

    async def run(self):
        print("\n" + "="*50)
        print("       JARVIS Remote Agent")
        print("="*50)
        print(f"Laptop: {self.name}")
        print(f"Server: {SERVER_URL}")
        print("="*50)
        print("")
        print("  YOUR PAIRING CODE:")
        print("")
        print(f"     >>> {PAIRING_CODE} <<<")
        print("")
        print("  Enter this code in your JARVIS app")
        print("  to connect to THIS laptop only.")
        print("")
        print("="*50 + "\n")

        # First check if server is reachable
        self.log("Checking if JARVIS server is running...")

        retry_count = 0
        max_retries = 3

        while self.running and retry_count < max_retries:
            try:
                if await self.connect():
                    self.log("Connected successfully! Waiting for commands...", "SUCCESS")
                    retry_count = 0  # Reset retry count on successful connection
                    async for msg in self.ws:
                        await self.handle_message(msg)
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        self.log(f"Retrying connection ({retry_count}/{max_retries})...", "WARN")
                    else:
                        self.log("Max retries reached. Please check if JARVIS server is running:", "ERROR")
                        self.log("1. Open new terminal", "INFO")
                        self.log("2. cd C:\\Users\\7CIN\\Desktop\\Jarvis", "INFO")
                        self.log("3. python -m src.jarvis.main", "INFO")
                        self.log("4. Then restart this agent", "INFO")
                        break

            except websockets.exceptions.ConnectionClosed:
                self.log("Connection lost. Reconnecting...", "WARN")
                retry_count = 0  # Don't count connection drops as retries
            except KeyboardInterrupt:
                self.log("Stopping agent...", "INFO")
                self.running = False
                break
            except Exception as e:
                self.log(f"Unexpected error: {e}", "ERROR")
                retry_count += 1

            if self.running:
                await asyncio.sleep(5)

def main():
    agent = JarvisAgent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nStopping agent...")

if __name__ == "__main__":
    main()
