"""
JARVIS Configuration.

Loads settings from environment variables and .env file.
"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # API Settings
    api_key: str = Field(default="", description="API key for authentication")
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    debug: bool = Field(default=False, description="Debug mode")

    # LLM Settings
    llm_provider: str = Field(default="ollama", description="LLM provider: ollama, copilot, openai")
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field(default="llama3.2:1b", description="Default Ollama model (use :1b for low RAM)")
    embedding_model: str = Field(default="nomic-embed-text", description="Embedding model")

    # Copilot Settings
    copilot_timeout: int = Field(default=120, description="Copilot CLI timeout in seconds")

    # OpenAI Settings (for cloud deployment)
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")

    # Gemini Settings
    gemini_api_key: str = Field(default="", description="Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Gemini model to use")

    # Database Settings (Phase 2)
    database_url: str | None = Field(
        default="postgresql://jarvis:jarvis_secret@localhost:5432/jarvis",
        description="PostgreSQL connection URL"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # Kafka Settings
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers"
    )
    kafka_enabled: bool = Field(
        default=True,
        description="Enable Kafka event streaming"
    )

    # Execution Settings
    command_timeout: int = Field(default=60, description="Default command timeout (seconds)")
    max_plan_steps: int = Field(default=20, description="Maximum steps in a plan")

    # Security Settings
    sandbox_enabled: bool = Field(default=True, description="Enable command sandboxing")
    approval_required: bool = Field(default=True, description="Require approval for high-risk ops")

    # Paths
    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {
        "env_prefix": "JARVIS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    s = Settings()
    try:
        import json
        from pathlib import Path
        config_path = Path.home() / ".jarvis" / "llm_runtime.json"
        if config_path.exists():
            runtime = json.loads(config_path.read_text(encoding="utf-8"))
            for k, v in runtime.items():
                if hasattr(s, k) and v is not None:
                    setattr(s, k, v)
    except Exception:
        pass
    return s


__all__ = ["Settings", "get_settings"]
