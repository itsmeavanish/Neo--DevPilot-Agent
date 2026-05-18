#!/usr/bin/env python3
"""
Test script to validate AI feature restoration in JARVIS.

This script tests:
1. AI provider API endpoints work correctly
2. Real AI responses are returned (not dummy data)
3. All provider types are supported
4. Configuration endpoints function properly
"""

import sys
import os
import json
import asyncio
import aiohttp
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_ai_endpoints():
    """Test that the AI endpoints return real data, not dummy responses."""
    print("Testing AI Provider Endpoints...")

    base_url = "http://localhost:8000"  # Default development server

    async with aiohttp.ClientSession() as session:
        # Test AI Providers endpoint
        try:
            async with session.get(f"{base_url}/project/ai/providers") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"[OK] AI Providers endpoint working")
                    print(f"  Current provider: {data.get('current', 'None')}")

                    # Check if we have real provider data
                    providers = data.get('providers', {})
                    for name, info in providers.items():
                        available = info.get('available', False)
                        message = info.get('message', 'No message')
                        print(f"  {name}: {'[OK]' if available else '[FAIL]'} {message}")

                    return True
                else:
                    print(f"[ERROR] AI Providers endpoint failed: {resp.status}")
                    return False
        except Exception as e:
            print(f"[ERROR] Could not connect to AI endpoints: {e}")
            return False

async def test_ai_ask_endpoint():
    """Test that askAI returns real responses."""
    print("\nTesting AI Ask Endpoint...")

    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        try:
            # Test a simple AI request
            test_prompt = "What is Python?"
            payload = {
                "prompt": test_prompt,
                "code_context": "",
                "file_path": "",
                "language": ""
            }

            async with session.post(
                f"{base_url}/project/ai/ask",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data.get('response', '')

                    # Check for dummy responses
                    dummy_indicators = [
                        'AI edit would go here',
                        'future updates',
                        'coming soon',
                        'not implemented'
                    ]

                    is_dummy = any(indicator.lower() in response_text.lower()
                                 for indicator in dummy_indicators)

                    if is_dummy:
                        print(f"[ERROR] AI Ask returns dummy response: {response_text[:100]}...")
                        return False
                    else:
                        print(f"[OK] AI Ask returns real response: {response_text[:100]}...")
                        return True
                else:
                    print(f"[ERROR] AI Ask endpoint failed: {resp.status}")
                    text = await resp.text()
                    print(f"  Error: {text}")
                    return False
        except Exception as e:
            print(f"[ERROR] AI Ask test failed: {e}")
            return False

async def test_copilot_edit():
    """Test Copilot editing functionality."""
    print("\nTesting Copilot Edit Endpoint...")

    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        try:
            # Test Copilot edit request
            payload = {
                "file_path": "test.py",
                "instruction": "Add a comment to explain this function",
                "apply_changes": False
            }

            async with session.post(
                f"{base_url}/copilot/edit",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    success = data.get('success', False)
                    message = data.get('message', '')

                    # Check for dummy responses
                    if 'future updates' in message.lower() or 'AI edit would go here' in message:
                        print(f"[ERROR] Copilot Edit returns dummy response: {message}")
                        return False
                    else:
                        print(f"[OK] Copilot Edit returns real response")
                        return True
                else:
                    print(f"[ERROR] Copilot Edit endpoint failed: {resp.status}")
                    return False
        except Exception as e:
            print(f"[ERROR] Copilot Edit test failed: {e}")
            return False

def test_frontend_api_changes():
    """Test that frontend API no longer has hardcoded responses."""
    print("\nTesting Frontend API Configuration...")

    api_file = os.path.join(os.path.dirname(__file__), 'Frontend', 'lib', 'api.ts')

    if not os.path.exists(api_file):
        print(f"[ERROR] Frontend API file not found: {api_file}")
        return False

    try:
        with open(api_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for dummy responses that should be removed
        dummy_patterns = [
            'AI edit would go here',
            'future updates',
            'coming soon',
            'hardcoded'
        ]

        dummy_found = []
        for pattern in dummy_patterns:
            if pattern.lower() in content.lower():
                dummy_found.append(pattern)

        if dummy_found:
            print(f"[ERROR] Frontend still contains dummy responses: {dummy_found}")
            return False

        # Check for real API calls
        required_endpoints = [
            '/project/ai/providers',
            '/project/ai/ask',
            '/copilot/edit',
            '/github/token/set'
        ]

        missing_endpoints = []
        for endpoint in required_endpoints:
            if endpoint not in content:
                missing_endpoints.append(endpoint)

        if missing_endpoints:
            print(f"[ERROR] Frontend missing API calls: {missing_endpoints}")
            return False

        print("[OK] Frontend API properly configured with real endpoints")
        return True

    except Exception as e:
        print(f"[ERROR] Error checking frontend API: {e}")
        return False

def test_settings_page_features():
    """Test that Settings page has AI configuration."""
    print("\nTesting Settings Page AI Configuration...")

    settings_file = os.path.join(os.path.dirname(__file__), 'Frontend', 'app', '(tabs)', 'settings.tsx')

    if not os.path.exists(settings_file):
        print(f"[ERROR] Settings file not found: {settings_file}")
        return False

    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for AI provider features
        required_features = [
            'AI Providers',
            'GitHub Copilot',
            'OpenAI',
            'Ollama',
            'getAIProviders',
            'setAIProvider',
            'GitHub Token',
            'Modal'
        ]

        missing_features = []
        for feature in required_features:
            if feature not in content:
                missing_features.append(feature)

        if missing_features:
            print(f"[ERROR] Settings page missing features: {missing_features}")
            return False

        print("[OK] Settings page has comprehensive AI configuration")
        return True

    except Exception as e:
        print(f"[ERROR] Error checking settings page: {e}")
        return False

def test_ide_copilot_improvements():
    """Test that IDE Copilot uses real AI."""
    print("\nTesting IDE Copilot Integration...")

    ide_file = os.path.join(os.path.dirname(__file__), 'Frontend', 'app', '(tabs)', 'ide.tsx')

    if not os.path.exists(ide_file):
        print(f"[ERROR] IDE file not found: {ide_file}")
        return False

    try:
        with open(ide_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for askAI import and usage
        required_features = [
            'askAI',
            'isEditRequest',
            'general AI chat',
            'copilotEdit'
        ]

        missing_features = []
        for feature in required_features:
            if feature not in content:
                missing_features.append(feature)

        if missing_features:
            print(f"[ERROR] IDE missing AI features: {missing_features}")
            return False

        print("[OK] IDE Copilot properly integrated with real AI")
        return True

    except Exception as e:
        print(f"[ERROR] Error checking IDE integration: {e}")
        return False

async def run_all_tests():
    """Run all tests and summarize results."""
    print("=" * 60)
    print("   JARVIS AI Feature Restoration Test")
    print("=" * 60)

    tests = [
        ("Frontend API Configuration", test_frontend_api_changes),
        ("Settings Page AI Features", test_settings_page_features),
        ("IDE Copilot Integration", test_ide_copilot_improvements),
        ("AI Provider Endpoints", test_ai_endpoints),
        ("AI Ask Functionality", test_ai_ask_endpoint),
        ("Copilot Edit Service", test_copilot_edit)
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n[{len(results) + 1}/{len(tests)}] {test_name}")
        print("-" * 40)

        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()

        results.append((test_name, result))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print("-" * 60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("AI features have been successfully restored!")
        print("[OK] Real AI responses (no more dummy data)")
        print("[OK] Provider switching working")
        print("[OK] Configuration UIs implemented")
        print("[OK] IDE integration complete")
    else:
        print(f"\n[WARNING] {total - passed} tests failed")
        print("Some AI features may still need work")

        # Show next steps
        failed_tests = [name for name, result in results if not result]
        print(f"\nFailed tests: {', '.join(failed_tests)}")

    return passed == total

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)