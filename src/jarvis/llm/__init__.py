"""
LLM module for JARVIS.

Provides unified interface for FreeLLM provider.
"""

from jarvis.llm.client import LLMClient, create_llm_client

__all__ = [
    "LLMClient",
    "create_llm_client",
]
