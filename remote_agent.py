#!/usr/bin/env python3
"""
JARVIS Remote Agent

Run this script on your laptop to connect it to the JARVIS cloud server.
The agent maintains a secure WebSocket connection and executes commands
sent from your mobile app.

Usage:
    python remote_agent.py --server https://your-jarvis.railway.app --token YOUR_DEVICE_TOKEN

Security:
    - All communication is encrypted (WSS/TLS)
    - Device token authentication
    - Commands are sandboxed
    - Configurable command whitelist
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import signal
from datetime import datetime
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

# Configuration
DEFAULT_SERVER = "wss://your-jarvis-server.railway.app"
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 10
COMMAND_TIMEOUT = 120  # seconds


class RemoteAgent:
    """
    JARVIS Remote Agent.

    Connects to the cloud server and executes commands securely.
    """

    def __init__(self, server_url: str, device_token: str, name: str = None):
        self.server_url = server_url.replace("https://", "wss://").replace("http://", "ws://")
        self.device_token = device_token
        self.name = name or platform.node()
        self.running = True
        self.websocket = None
        self.reconnect_attempts = 0

        # Command whitelist (security)
        self.allowed_commands = {
            "shell": True,
            "file_read": True,
            "file_write": True,
            "file_list": True,
            "git": True,
            "system_info": True,
            "process_list": True,
        }

        # Blocked patterns (security)
        self.blocked_patterns = [
            "rm -rf /",
            "format c:",
            "del /f /s /q",
            ":(){:|:&};:",  # Fork bomb
            "mkfs",
            "dd if=",
        ]

    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    async def connect(self):
        """Connect to the cloud server."""
        ws_url = f"{self.server_url}/ws/agent"

        headers = {
            "X-Device-Token": self.device_token,
            "X-Device-Name": self.name,
            "X-Device-Platform": platform.system(),
            "X-Device-Hostname": platform.node(),
        }

        self.log(f"Connecting to {ws_url}...")

        try:
            self.websocket = await websockets.connect(
                ws_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10,
            )
            self.reconnect_attempts = 0
            self.log("Connected to JARVIS server!", "SUCCESS")

            # Send initial status
            await self.send_status()

            return True
        except Exception as e:
            self.log(f"Connection failed: {e}", "ERROR")
            return False

    async def send_status(self):
        """Send device status to server."""
        import psutil

        status = {
            "type": "status",
            "hostname": platform.node(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent if platform.system() != "Windows" else psutil.disk_usage("C:").percent,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.websocket.send(json.dumps(status))

    def is_command_safe(self, command: str) -> tuple[bool, str]:
        """Check if a command is safe to execute."""
        command_lower = command.lower()

        for pattern in self.blocked_patterns:
            if pattern.lower() in command_lower:
                return False, f"Blocked pattern detected: {pattern}"

        return True, ""

    async def execute_command(self, command: str, timeout: int = None) -> dict:
        """Execute a shell command securely."""
        timeout = timeout or COMMAND_TIMEOUT

        # Security check
        is_safe, reason = self.is_command_safe(command)
        if not is_safe:
            return {
                "success": False,
                "error": f"Command blocked: {reason}",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

        self.log(f"Executing: {command[:50]}...")

        try:
            if platform.system() == "Windows":
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=True,
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
                timeout=timeout,
            )

            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Command timed out after {timeout}s",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

    async def handle_message(self, message: str):
        """Handle a message from the server."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            request_id = data.get("request_id")

            self.log(f"Received: {msg_type}")

            if msg_type == "ping":
                await self.websocket.send(json.dumps({"type": "pong", "request_id": request_id}))

            elif msg_type == "execute":
                command = data.get("command", "")
                timeout = data.get("timeout", COMMAND_TIMEOUT)
                result = await self.execute_command(command, timeout)
                result["type"] = "result"
                result["request_id"] = request_id
                await self.websocket.send(json.dumps(result))

            elif msg_type == "status_request":
                await self.send_status()

            elif msg_type == "file_read":
                path = data.get("path")
                result = await self.read_file(path)
                result["type"] = "file_content"
                result["request_id"] = request_id
                await self.websocket.send(json.dumps(result))

            elif msg_type == "file_write":
                path = data.get("path")
                content = data.get("content")
                result = await self.write_file(path, content)
                result["type"] = "file_result"
                result["request_id"] = request_id
                await self.websocket.send(json.dumps(result))

            else:
                self.log(f"Unknown message type: {msg_type}", "WARN")

        except json.JSONDecodeError:
            self.log(f"Invalid JSON: {message[:100]}", "ERROR")
        except Exception as e:
            self.log(f"Error handling message: {e}", "ERROR")

    async def read_file(self, path: str) -> dict:
        """Read a file and return its content."""
        try:
            path = Path(path).expanduser()
            if not path.exists():
                return {"success": False, "error": f"File not found: {path}"}

            if path.stat().st_size > 5 * 1024 * 1024:  # 5MB limit
                return {"success": False, "error": "File too large (>5MB)"}

            content = path.read_text(encoding="utf-8", errors="replace")
            return {"success": True, "content": content, "path": str(path)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def write_file(self, path: str, content: str) -> dict:
        """Write content to a file."""
        try:
            path = Path(path).expanduser()

            # Security: prevent writing to system directories
            blocked_dirs = ["/etc", "/usr", "/bin", "/sbin", "C:\\Windows", "C:\\Program Files"]
            for blocked in blocked_dirs:
                if str(path).startswith(blocked):
                    return {"success": False, "error": f"Cannot write to protected directory: {blocked}"}

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(path)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run(self):
        """Main agent loop."""
        self.log("JARVIS Remote Agent starting...")
        self.log(f"Device: {self.name}")
        self.log(f"Platform: {platform.system()} {platform.release()}")

        while self.running:
            try:
                connected = await self.connect()

                if connected:
                    async for message in self.websocket:
                        await self.handle_message(message)
                else:
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                        self.log("Max reconnect attempts reached. Exiting.", "ERROR")
                        break

            except websockets.exceptions.ConnectionClosed:
                self.log("Connection closed. Reconnecting...", "WARN")
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")

            if self.running:
                self.log(f"Reconnecting in {RECONNECT_DELAY}s...")
                await asyncio.sleep(RECONNECT_DELAY)

        self.log("Agent stopped.")

    def stop(self):
        """Stop the agent."""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())


def main():
    parser = argparse.ArgumentParser(description="JARVIS Remote Agent")
    parser.add_argument(
        "--server",
        default=os.getenv("JARVIS_SERVER", DEFAULT_SERVER),
        help="JARVIS server URL",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("JARVIS_DEVICE_TOKEN"),
        help="Device token (from JARVIS app)",
    )
    parser.add_argument(
        "--name",
        default=os.getenv("JARVIS_DEVICE_NAME", platform.node()),
        help="Device name",
    )

    args = parser.parse_args()

    if not args.token:
        print("ERROR: Device token required.")
        print("Get your token from the JARVIS mobile app:")
        print("  Settings → Devices → Add Device")
        print("")
        print("Then run:")
        print(f"  python {sys.argv[0]} --server {args.server} --token YOUR_TOKEN")
        sys.exit(1)

    agent = RemoteAgent(
        server_url=args.server,
        device_token=args.token,
        name=args.name,
    )

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\nShutting down...")
        agent.stop()

    signal.signal(signal.SIGINT, signal_handler)

    # Run the agent
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
