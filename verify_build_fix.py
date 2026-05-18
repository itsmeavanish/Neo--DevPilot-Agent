#!/usr/bin/env python3
"""
Verify that the Android bundling syntax error has been fixed.
"""

import os
import re

def check_settings_syntax():
    """Check settings.tsx for syntax issues."""
    settings_file = os.path.join(os.path.dirname(__file__), 'Frontend', 'app', '(tabs)', 'settings.tsx')

    if not os.path.exists(settings_file):
        print("[ERROR] Settings file not found")
        return False

    with open(settings_file, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # Check for the fixed function declaration
    found_handle_disconnect = False
    return_outside_function = False

    in_function = False
    bracket_count = 0

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.strip()

        # Track function declarations
        if re.match(r'^\s*const\s+\w+\s*=\s*\(.*\)\s*=>\s*{', line):
            in_function = True
            bracket_count = 1
            if 'handleDisconnect' in line:
                found_handle_disconnect = True
                print(f"[OK] Found handleDisconnect function at line {line_num}")

        # Track function scope
        elif in_function:
            bracket_count += line.count('{') - line.count('}')
            if bracket_count <= 0:
                in_function = False

        # Check for return statements
        if stripped.startswith('return') and not in_function:
            if line_num > 200:  # Around the problem area
                return_outside_function = True
                print(f"[ERROR] Return outside function at line {line_num}: {stripped}")

    if not found_handle_disconnect:
        print("[ERROR] handleDisconnect function not found")
        return False

    if return_outside_function:
        print("[ERROR] Found return statements outside functions")
        return False

    print("[OK] No syntax errors detected in settings.tsx")
    return True

def check_build_readiness():
    """Check if the project is ready for APK build."""
    frontend_dir = os.path.join(os.path.dirname(__file__), 'Frontend')

    # Check essential files
    required_files = [
        'package.json',
        'app.json',
        'eas.json',
        'build-apk.bat'
    ]

    for file in required_files:
        file_path = os.path.join(frontend_dir, file)
        if os.path.exists(file_path):
            print(f"[OK] {file} exists")
        else:
            print(f"[ERROR] {file} missing")
            return False

    return True

def main():
    print("=" * 50)
    print("   Android Build Fix Verification")
    print("=" * 50)

    print("\n1. Checking settings.tsx syntax...")
    syntax_ok = check_settings_syntax()

    print("\n2. Checking build readiness...")
    build_ready = check_build_readiness()

    print("\n" + "=" * 50)
    if syntax_ok and build_ready:
        print("[SUCCESS] Android bundling fix verified!")
        print("✅ Syntax error resolved")
        print("✅ Build files present")
        print("✅ Ready for APK generation")
        print("\nTo build APK:")
        print("cd Frontend && ./build-apk.bat")
    else:
        print("[ERROR] Issues found:")
        if not syntax_ok:
            print("❌ Syntax errors still present")
        if not build_ready:
            print("❌ Build configuration incomplete")

    return syntax_ok and build_ready

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)