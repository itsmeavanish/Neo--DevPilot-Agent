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
SERVER_URL = os.getenv("JARVIS_SERVER", "http://localhost:8000")
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
class JarvisAgent:
    def __init__(self):
        base_url = SERVER_URL.replace("https://", "wss://").replace("http://", "ws://")
        # Use pairing code as device ID - this links app to this specific laptop
        self.ws_url = f"{base_url}/api/v1/ws/agents/{PAIRING_CODE}"
        self.name = DEVICE_NAME
        self.running = True
        self.ws = None

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{level}] {msg}")
    async def connect(self):
        self.log(f"Connecting to JARVIS server...")
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
                self.log(f"Connected! {data.get('message', '')}", "SUCCESS")
                return True
            else:
                self.log(f"Registration failed: {data}", "ERROR")
                return False
        except asyncio.TimeoutError:
            self.log("Connection timeout - JARVIS server may not be running", "ERROR")
            return False
        except Exception as e:
            self.log(f"Connection failed: {e}", "ERROR")
            return False
    async def send_status(self):
        status = {
            "type": "status",
            "hostname": platform.node(),
            "platform": platform.system(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.ws.send(json.dumps(status))
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

    async def handle_message(self, msg):
        try:
            data = json.loads(msg)
            msg_type = data.get("type")
            request_id = data.get("request_id")

            if msg_type == "ping":
                await self.ws.send(json.dumps({"type": "pong", "request_id": request_id}))

            elif msg_type == "execute":
                result = await self.execute(data.get("command", ""), data.get("timeout", 120))
                result["type"] = "result"
                result["request_id"] = request_id
                await self.ws.send(json.dumps(result))

            elif msg_type == "status_request":
                await self.send_status()

            elif msg_type == "file_read":
                path = Path(data.get("path", "")).expanduser()
                if path.exists() and path.stat().st_size < 5*1024*1024:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    await self.ws.send(json.dumps({"type": "file_content", "request_id": request_id, "success": True, "content": content}))
                else:
                    await self.ws.send(json.dumps({"type": "file_content", "request_id": request_id, "success": False, "error": "File not found or too large"}))

        except Exception as e:
            self.log(f"Error: {e}", "ERROR")

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
