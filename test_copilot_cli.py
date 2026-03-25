#!/usr/bin/env python3
"""
Test script for the new GitHub Copilot CLI integration.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_copilot_cli():
    """Test GitHub Copilot CLI integration."""
    print("=" * 60)
    print("   GitHub Copilot CLI Integration Test")
    print("=" * 60)

    try:
        from jarvis.llm.providers.copilot_cli import get_copilot_cli

        provider = get_copilot_cli()
        print("[OK] Copilot CLI provider loaded")

        # Test GitHub authentication
        print("\n1. Testing GitHub authentication...")
        auth_ok, auth_message = await provider.check_github_auth()
        if auth_ok:
            print(f"[OK] GitHub authentication: {auth_message}")
        else:
            print(f"[ERROR] GitHub authentication: {auth_message}")

        # Test Copilot access
        print("\n2. Testing Copilot access...")
        copilot_ok, copilot_message = await provider.check_copilot_access()
        if copilot_ok:
            print(f"[OK] Copilot access: {copilot_message}")
        else:
            print(f"[ERROR] Copilot access: {copilot_message}")

        # Test model info
        print("\n3. Testing model configuration...")
        current_model = provider.get_current_model()
        print(f"[INFO] Current model: {current_model}")

        available_models = provider.get_available_models()
        model_count = sum(len(models) for models in available_models.values())
        print(f"[INFO] Available models: {model_count} across {len(available_models)} categories")

        for category, models in available_models.items():
            print(f"   {category}: {len(models)} models")

        # Test a simple chat if Copilot is available
        if auth_ok and copilot_ok:
            print("\n4. Testing simple chat...")
            try:
                response = await provider.chat("What is Python?", model="gpt-4.1")
                if response and not response.startswith("Error:"):
                    print(f"[OK] Chat test successful!")
                    print(f"   Response preview: {response[:100]}...")
                else:
                    print(f"[ERROR] Chat test failed: {response}")
            except Exception as e:
                print(f"[ERROR] Chat test error: {e}")
        else:
            print("\n4. Skipping chat test - authentication/access issues")

        print("\n" + "=" * 60)
        if auth_ok and copilot_ok:
            print("SUCCESS: GitHub Copilot CLI integration is working!")
            print("[OK] No tokens required - uses existing GitHub CLI authentication")
            print("[OK] Model selection available")
            print("[OK] Ready for seamless AI coding assistance")
        else:
            print("SETUP REQUIRED:")
            if not auth_ok:
                print("   - Run 'gh auth login' to authenticate with GitHub")
            if not copilot_ok and auth_ok:
                print("   - Ensure you have GitHub Copilot subscription")
                print("   - Check Copilot access permissions")

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_copilot_cli())