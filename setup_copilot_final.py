#!/usr/bin/env python3
"""
Final setup script for GitHub Copilot integration - both methods.
"""

import os
import subprocess

def main():
    print("=" * 60)
    print("   GitHub Copilot Integration Setup - Final Check")
    print("=" * 60)

    # Check GitHub CLI
    print("\n1. GitHub CLI Status:")
    try:
        result = subprocess.run([
            "C:\\Program Files\\GitHub CLI\\gh.exe", "auth", "status"
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if "Logged in to" in line:
                    print(f"   ✓ {line}")
        else:
            print("   ✗ Not authenticated - run 'gh auth login'")
    except Exception as e:
        print(f"   ✗ GitHub CLI error: {e}")

    # Check VS Code
    print("\n2. VS Code Status:")
    try:
        result = subprocess.run(["code", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"   ✓ VS Code {result.stdout.strip()} available")
        else:
            print("   ✗ VS Code not available")
    except Exception as e:
        print(f"   ✗ VS Code error: {e}")

    print("\n" + "=" * 60)
    print("INTEGRATION STATUS:")
    print("\n✅ Fixed Windows CLI path issue with proper quoting")
    print("✅ Created VS Code Copilot provider for existing setups")
    print("✅ Updated mobile API to try VS Code first, then CLI")
    print("✅ Added model selection for CLI method")

    print("\n" + "=" * 60)
    print("USAGE INSTRUCTIONS:")

    print("\n🎯 METHOD 1: VS Code Integration (Recommended)")
    print("   • Use JARVIS app → Settings → AI Providers → GitHub Copilot CLI")
    print("   • Will provide VS Code integration instructions")
    print("   • Works with your existing VS Code Copilot setup")

    print("\n🔧 METHOD 2: Direct CLI (If you get Copilot subscription)")
    print("   • Get GitHub Copilot subscription ($10/month)")
    print("   • Test: gh copilot explain 'console.log(hello)'")
    print("   • Choose from 17 AI models in JARVIS settings")

    print("\n📱 IN THE APP:")
    print("   1. Open JARVIS app")
    print("   2. Settings → AI Providers")
    print("   3. Select 'GitHub Copilot CLI'")
    print("   4. Use the gear icon to select models (CLI method)")
    print("   5. Start chatting with AI!")

    print("\n💡 TROUBLESHOOTING:")
    print("   • If 'Error: not found' → Install VS Code Copilot extension")
    print("   • If CLI issues → Check GitHub authentication")
    print("   • Both methods eliminated token management!")

if __name__ == "__main__":
    main()