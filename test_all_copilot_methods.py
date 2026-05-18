#!/usr/bin/env python3
"""
Test both GitHub Copilot integration methods.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_all_copilot_methods():
    """Test both CLI and VS Code Copilot integration methods."""
    print("=" * 70)
    print("   GitHub Copilot Integration Test - All Methods")
    print("=" * 70)

    # Test 1: CLI Method (with fixed Windows paths)
    print("\n[CLI] METHOD 1: GitHub CLI Copilot")
    print("-" * 40)
    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli
        cli_provider = get_copilot_cli()

        auth_ok, auth_message = await cli_provider.check_github_auth()
        print(f"[AUTH] {auth_message}")

        copilot_ok, copilot_message = await cli_provider.check_copilot_access()
        print(f"[ACCESS] {copilot_message}")

        if auth_ok and copilot_ok:
            print("[STATUS] CLI Method Ready")
        else:
            print("[STATUS] CLI Method Not Available")

    except Exception as e:
        print(f"[ERROR] CLI Method Failed: {e}")

    # Test 2: VS Code method
    print("\n[VSCODE] METHOD 2: VS Code Copilot")
    print("-" * 40)
    try:
        from jarvis.llm.providers.vscode_copilot import get_vscode_copilot
        vscode_provider = get_vscode_copilot()

        vscode_ok, vscode_message = await vscode_provider.check_vscode_available()
        print(f"[VS CODE] {vscode_message}")

        if vscode_ok:
            copilot_ok, copilot_message = await vscode_provider.check_copilot_extension()
            print(f"[COPILOT] {copilot_message}")

            if copilot_ok:
                print("[STATUS] VS Code Method Ready")
            else:
                print("[STATUS] Copilot Extension Missing")
        else:
            print("[STATUS] VS Code Not Available")

    except Exception as e:
        print(f"[ERROR] VS Code Method Failed: {e}")

    # Test 3: Mobile API Integration
    print("\n[API] METHOD 3: Mobile API (Combined)")
    print("-" * 40)
    try:
        from jarvis.api.v1.mobile import _check_copilot_available

        available, message = await _check_copilot_available()
        print(f"[API] {message}")

        if available:
            print("[STATUS] Mobile API Integration Ready")
        else:
            print("[STATUS] Mobile API Integration Not Available")

    except Exception as e:
        print(f"[ERROR] Mobile API Test Failed: {e}")

    print("\n" + "=" * 70)
    print("RECOMMENDATIONS:")
    print("\n1. If VS Code Copilot works: Use VS Code method (most reliable)")
    print("2. If you have GitHub CLI: Use CLI method")
    print("3. The Mobile API tries VS Code first, then CLI")

    print("\nSETUP TIPS:")
    print("- VS Code: Install 'GitHub Copilot' extension")
    print("- CLI: Run 'gh auth login' and get Copilot subscription")
    print("- Both methods use your existing GitHub authentication")

if __name__ == "__main__":
    asyncio.run(test_all_copilot_methods())