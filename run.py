#!/usr/bin/env python3
"""
JARVIS Quick Start Script

Usage:
    python run.py              # Start the server
    python run.py --dev        # Start with hot reload
    python run.py --check      # Check if everything is ready
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def check_requirements():
    """Check if all requirements are installed."""
    missing = []
    
    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")
    
    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")
    
    try:
        import pydantic
    except ImportError:
        missing.append("pydantic")
    
    try:
        import httpx
    except ImportError:
        missing.append("httpx")
    
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print(f"\nInstall with: pip install -r src/requirements.txt")
        return False
    
    return True


def check_ollama():
    """Check if Ollama is running."""
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"Ollama: Running ({len(models)} models available)")
            return True
    except Exception:
        pass
    
    print("Ollama: Not running (optional, for AI planning)")
    return False


def run_checks():
    """Run all pre-flight checks."""
    print("=" * 50)
    print("JARVIS Pre-flight Checks")
    print("=" * 50)
    
    # Check Python version
    py_version = sys.version_info
    if py_version >= (3, 11):
        print(f"Python: {py_version.major}.{py_version.minor}.{py_version.micro} ✓")
    else:
        print(f"Python: {py_version.major}.{py_version.minor} (3.11+ recommended)")
    
    # Check packages
    if check_requirements():
        print("Packages: All installed ✓")
    else:
        return False
    
    # Check Ollama
    check_ollama()
    
    # Check .env
    env_path = os.path.join(os.path.dirname(__file__), 'src', '.env')
    if os.path.exists(env_path):
        print(f".env: Found ✓")
    else:
        print(f".env: Not found (using defaults)")
        print(f"  Copy src/.env.example to src/.env to configure")
    
    print("=" * 50)
    print("All checks passed! Ready to start.")
    print("=" * 50)
    return True


def main():
    args = sys.argv[1:]
    
    if "--check" in args:
        run_checks()
        return
    
    if not check_requirements():
        sys.exit(1)
    
    # Change to src directory for proper module resolution
    os.chdir(os.path.join(os.path.dirname(__file__), 'src'))
    
    # Import and run
    import uvicorn
    
    reload = "--dev" in args or "--reload" in args
    host = os.environ.get("JARVIS_API_HOST", "0.0.0.0")
    port = int(os.environ.get("JARVIS_API_PORT", "8000"))
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║     JARVIS - Autonomous Developer Operating System        ║
    ║                      v2.0.0                               ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  API:  http://{host}:{port}                               ║
    ║  Docs: http://{host}:{port}/docs                          ║
    ║                                                           ║
    ║  Press Ctrl+C to stop                                     ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "jarvis.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
