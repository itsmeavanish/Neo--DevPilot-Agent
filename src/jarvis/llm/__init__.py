"""
LLM module for JARVIS.

Provides unified interface for multiple LLM providers.
"""

from jarvis.llm.client import LLMClient, create_llm_client
from jarvis.llm.providers.ollama import OllamaClient

__all__ = [
    "LLMClient",
    "create_llm_client",
    "OllamaClient",
]
