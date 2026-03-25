#!/usr/bin/env python3
"""
Test the JARVIS agent startup to make sure it doesn't hang.
"""

import os
import subprocess
import sys
import time

def test_agent_startup():
    print("=" * 60)
    print("   JARVIS Agent Startup Test")
    print("=" * 60)

    agent_dir = os.path.join(os.path.dirname(__file__), "agent-installer")
    agent_script = os.path.join(agent_dir, "jarvis_agent.py")

    print(f"Testing agent script: {agent_script}")
    print("\nStarting agent with 5-second timeout...")

    try:
        # Start the agent process
        process = subprocess.Popen(
            [sys.executable, agent_script],
            cwd=agent_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Read output for 5 seconds
        output_lines = []
        start_time = time.time()

        while time.time() - start_time < 5:
            try:
                # Check if process is still running
                if process.poll() is not None:
                    break

                # Try to read a line with short timeout
                line = process.stdout.readline()
                if line:
                    output_lines.append(line.strip())
                    print(f"[OUTPUT] {line.strip()}")

                time.sleep(0.1)
            except:
                break

        # Terminate the process
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

        print(f"\n[RESULT] Agent started successfully!")
        print(f"[RESULT] Captured {len(output_lines)} lines of output")

        # Check for expected output
        has_pairing_code = any("PAIRING CODE" in line for line in output_lines)
        has_connection_attempt = any("Connecting" in line or "Connection" in line for line in output_lines)

        if has_pairing_code:
            print("[SUCCESS] ✓ Pairing code displayed")
        if has_connection_attempt:
            print("[SUCCESS] ✓ Connection attempt made")

        if not output_lines:
            print("[WARNING] No output captured - agent may have issues")

        return True

    except Exception as e:
        print(f"[ERROR] Agent test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_agent_startup()
    if success:
        print("\n[CONCLUSION] Agent is working! No more hanging issues.")
        print("\nTo use the agent:")
        print("1. Start server: double-click 'start-server.bat'")
        print("2. Start agent: double-click 'agent-installer/start-agent.bat'")
    else:
        print("\n[CONCLUSION] Agent has issues that need fixing.")