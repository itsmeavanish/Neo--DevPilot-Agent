"""
JARVIS Main Application.

FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jarvis import __version__
from jarvis.config import get_settings
from jarvis.api.v1.router import router as v1_router
from jarvis.api.v1.mobile import router as mobile_router
from jarvis.api.v1.device_management import router as device_router
from jarvis.api.middleware.auth import APIKeyMiddleware
from jarvis.api.middleware.security import SecurityMiddleware, get_rate_limiter
from jarvis.core.logging import setup_logging, get_logger

logger = get_logger("jarvis.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()

    # Startup
    setup_logging(level=settings.log_level)
    logger.info(f"Starting JARVIS v{__version__}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Ollama: {settings.ollama_host}")

    # Initialize tools
    from jarvis.tools.registry import load_builtin_tools
    load_builtin_tools()
    logger.info("Tools loaded successfully")

    from jarvis.auth.github_token_store import get_stored_github_token

    if get_stored_github_token():
        logger.info("GitHub token loaded for Copilot API")

    from jarvis.runtime_llm import (
        DEFAULT_OLLAMA_MODEL,
        set_runtime_ai_provider,
        set_runtime_ollama,
    )

    set_runtime_ollama(model=DEFAULT_OLLAMA_MODEL)
    set_runtime_ai_provider("auto")
    logger.info(
        "AI: provider=auto, Ollama model=%s (avoids OOM from large llama3.x)",
        DEFAULT_OLLAMA_MODEL,
    )

    yield

    # Shutdown
    logger.info("Shutting down JARVIS")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="JARVIS",
        description="Autonomous Developer Operating System",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    # allow_credentials=True with allow_origins=["*"] is invalid for browsers; mobile clients use headers, not cookies
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API key authentication
    app.add_middleware(APIKeyMiddleware)

    # Security middleware (rate limiting)
    app.add_middleware(SecurityMiddleware, rate_limiter=get_rate_limiter())

    # Include routers
    app.include_router(v1_router)

    # Include mobile compatibility routes at root level
    app.include_router(mobile_router, tags=["Mobile"])

    # Include device management routes
    app.include_router(device_router, tags=["Devices"])

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with system info."""
        return {
            "status": "ok",
            "agent": "JARVIS",
            "version": __version__,
            "name": "JARVIS",
            "description": "Autonomous Developer Operating System",
            "docs": "/docs",
            "api": "/api/v1",
        }

    # Health endpoint at root level
    @app.get("/health", tags=["Health"])
    async def health():
        """Quick health check."""
        return {"status": "ok", "version": __version__}

    return app


# Create application instance
app = create_app()


def run():
    """Run the application with uvicorn."""
    import uvicorn
    settings = get_settings()

    uvicorn.run(
        "jarvis.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
