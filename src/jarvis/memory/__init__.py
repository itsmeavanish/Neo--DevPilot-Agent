"""
Memory module for JARVIS.

Provides persistent and session-scoped memory with semantic search.
"""

from jarvis.memory.service import MemoryService, get_memory_service
from jarvis.memory.embedder import Embedder, get_embedder
from jarvis.memory.short_term import ShortTermMemory, get_short_term_memory
from jarvis.memory.long_term import LongTermMemory, get_long_term_memory
from jarvis.memory.models.memory_item import MemoryItem, SearchResult, MemoryStats

__all__ = [
    "MemoryService",
    "get_memory_service",
    "Embedder",
    "get_embedder",
    "ShortTermMemory",
    "get_short_term_memory",
    "LongTermMemory",
    "get_long_term_memory",
    "MemoryItem",
    "SearchResult",
    "MemoryStats",
]
