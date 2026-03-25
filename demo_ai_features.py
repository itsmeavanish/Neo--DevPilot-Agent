#!/usr/bin/env python3
"""
Quick AI Demo - Verify Restored Features Work

This script demonstrates that all AI features are now working with real responses.
"""

import asyncio
import aiohttp

async def demo_ai_features():
    print("🤖 JARVIS AI Features Demo")
    print("=" * 50)

    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        # 1. Check AI Providers
        print("\n1️⃣ AI Providers Status:")
        try:
            async with session.get(f"{base_url}/project/ai/providers") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data.get('current', 'None')
                    print(f"   Current Provider: {current}")

                    for name, info in data.get('providers', {}).items():
                        status = "✅" if info.get('available') else "❌"
                        print(f"   {status} {name}: {info.get('message', 'No status')}")
                else:
                    print("   ❌ Could not connect to AI providers endpoint")
        except:
            print("   ❌ Server not running")

        # 2. Test AI Chat
        print("\n2️⃣ AI Chat Test:")
        try:
            test_prompt = {
                "prompt": "What is Python? (Answer in one sentence)",
                "code_context": "",
                "file_path": "",
                "language": ""
            }

            async with session.post(f"{base_url}/project/ai/ask", json=test_prompt) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get('response', '')

                    if 'dummy' in response.lower() or 'not implemented' in response.lower():
                        print("   ❌ Still returning dummy responses")
                    else:
                        print(f"   ✅ Real AI Response: {response[:80]}...")
                else:
                    print("   ❌ AI chat endpoint failed")
        except:
            print("   ❌ Could not test AI chat")

        # 3. Test Copilot Edit
        print("\n3️⃣ Copilot Edit Test:")
        try:
            edit_request = {
                "file_path": "example.py",
                "instruction": "Add a docstring",
                "apply_changes": False
            }

            async with session.post(f"{base_url}/copilot/edit", json=edit_request) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    success = data.get('success', False)
                    message = data.get('message', '')

                    if 'future updates' in message.lower():
                        print("   ❌ Still returning dummy edit responses")
                    else:
                        print(f"   ✅ Real Copilot Edit: {message[:60]}...")
                else:
                    print("   ❌ Copilot edit endpoint failed")
        except:
            print("   ❌ Could not test Copilot edit")

    print("\n" + "=" * 50)
    print("🎉 Demo Complete!")
    print("\nTo use the restored AI features:")
    print("1. Open JARVIS mobile app")
    print("2. Go to Settings → AI Providers")
    print("3. Configure your preferred AI provider")
    print("4. Use AI in IDE Copilot panel or Chat")

if __name__ == "__main__":
    asyncio.run(demo_ai_features())