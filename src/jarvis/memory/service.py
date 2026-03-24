"""
Memory Service for JARVIS.

Unified facade for short-term and long-term memory operations.
"""

from typing import Any

from jarvis.core.logging import get_logger
from jarvis.core.constants import MemoryType
from jarvis.memory.short_term import ShortTermMemory, get_short_term_memory
from jarvis.memory.long_term import LongTermMemory, get_long_term_memory
from jarvis.memory.embedder import Embedder, get_embedder
from jarvis.memory.models.memory_item import MemoryItem, SearchResult, MemoryStats

logger = get_logger("jarvis.memory.service")


class MemoryService:
    """
    Unified memory service combining short-term and long-term memory.

    Provides a clean interface for:
    - Storing context, errors, patterns, and preferences
    - Semantic search across all memories
    - Session-scoped temporary storage
    - Project-specific memory retrieval
    """

    def __init__(
        self,
        short_term: ShortTermMemory | None = None,
        long_term: LongTermMemory | None = None,
        embedder: Embedder | None = None,
    ):
        """
        Initialize the memory service.

        Args:
            short_term: Short-term memory instance
            long_term: Long-term memory instance
            embedder: Embedder for generating vectors
        """
        self.short_term = short_term or get_short_term_memory()
        self.long_term = long_term or get_long_term_memory()
        self.embedder = embedder or get_embedder()
        self.logger = get_logger("jarvis.memory.service")

    # ═══════════════════════════════════════════════════════════
    # Short-term Memory Operations
    # ═══════════════════════════════════════════════════════════

    async def set_context(
        self,
        key: str,
        value: Any,
        session_id: str | None = None,
        ttl: int = 3600,
    ) -> bool:
        """
        Store temporary context data.

        Args:
            key: Context key
            value: Context value
            session_id: Session for namespacing
            ttl: Time-to-live in seconds

        Returns:
            True if stored successfully
        """
        return await self.short_term.set(
            f"context:{key}",
            value,
            ttl=ttl,
            session_id=session_id,
        )

    async def get_context(
        self,
        key: str,
        session_id: str | None = None,
        default: Any = None,
    ) -> Any:
        """Get temporary context data."""
        return await self.short_term.get(
            f"context:{key}",
            session_id=session_id,
            default=default,
        )

    async def add_to_history(
        self,
        entry: dict,
        history_type: str = "command",
        session_id: str | None = None,
        max_entries: int = 100,
    ) -> int:
        """
        Add entry to session history.

        Args:
            entry: History entry (command, output, etc.)
            history_type: Type of history (command, error, etc.)
            session_id: Session ID
            max_entries: Maximum entries to keep

        Returns:
            Current history length
        """
        return await self.short_term.push_list(
            f"history:{history_type}",
            entry,
            max_length=max_entries,
            session_id=session_id,
        )

    async def get_history(
        self,
        history_type: str = "command",
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent history entries."""
        entries = await self.short_term.get_list(
            f"history:{history_type}",
            start=-limit,
            end=-1,
            session_id=session_id,
        )
        return entries

    async def clear_session(self, session_id: str) -> int:
        """Clear all session data."""
        return await self.short_term.clear_session(session_id)

    # ═══════════════════════════════════════════════════════════
    # Long-term Memory Operations
    # ═══════════════════════════════════════════════════════════

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.CONTEXT,
        project_id: str | None = None,
        file_path: str | None = None,
        metadata: dict | None = None,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        """
        Store a long-term memory.

        Args:
            content: Text content to remember
            memory_type: Type of memory
            project_id: Associated project
            file_path: Associated file
            metadata: Additional context
            importance: Importance score (0-1)
            tags: Categorization tags

        Returns:
            Created MemoryItem
        """
        return await self.long_term.store(
            content=content,
            memory_type=memory_type,
            project_id=project_id,
            file_path=file_path,
            metadata=metadata,
            importance=importance,
            tags=tags,
        )

    async def remember_error(
        self,
        error: str,
        context: dict | None = None,
        fix: str | None = None,
        project_id: str | None = None,
    ) -> MemoryItem:
        """
        Remember an error and optionally its fix.

        Args:
            error: Error message/description
            context: Context when error occurred
            fix: How the error was fixed (if resolved)
            project_id: Project where error occurred

        Returns:
            Created MemoryItem
        """
        memory_type = MemoryType.ERROR_FIX if fix else MemoryType.ERROR
        metadata = context or {}
        if fix:
            metadata["fix"] = fix

        return await self.remember(
            content=error,
            memory_type=memory_type,
            project_id=project_id,
            metadata=metadata,
            importance=0.8 if fix else 0.6,
            tags=["error", "fix"] if fix else ["error"],
        )

    async def remember_pattern(
        self,
        description: str,
        steps: list[dict],
        project_id: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        """
        Remember a successful execution pattern.

        Args:
            description: What this pattern accomplishes
            steps: Sequence of tool calls that worked
            project_id: Associated project
            tags: Pattern tags

        Returns:
            Created MemoryItem
        """
        return await self.remember(
            content=description,
            memory_type=MemoryType.PATTERN,
            project_id=project_id,
            metadata={"steps": steps},
            importance=0.7,
            tags=tags or ["pattern"],
        )

    async def set_preference(
        self,
        key: str,
        value: Any,
        user_id: str = "default",
    ) -> MemoryItem:
        """
        Store a user preference.

        Args:
            key: Preference key
            value: Preference value
            user_id: User identifier

        Returns:
            Created MemoryItem
        """
        return await self.remember(
            content=f"Preference: {key}",
            memory_type=MemoryType.PREFERENCE,
            metadata={"key": key, "value": value, "user_id": user_id},
            importance=0.9,  # High importance for preferences
            tags=["preference", key],
        )

    # ═══════════════════════════════════════════════════════════
    # Search Operations
    # ═══════════════════════════════════════════════════════════

    async def search(
        self,
        query: str,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        project_id: str | None = None,
        min_similarity: float = 0.5,
    ) -> list[SearchResult]:
        """
        Search memories by semantic similarity.

        Args:
            query: Search query
            limit: Maximum results
            types: Filter by memory types
            project_id: Filter by project
            min_similarity: Minimum similarity threshold

        Returns:
            List of SearchResults sorted by relevance
        """
        return await self.long_term.search(
            query=query,
            limit=limit,
            type_filter=types,
            project_id=project_id,
            min_similarity=min_similarity,
        )

    async def find_similar_errors(
        self,
        error: str,
        limit: int = 5,
        project_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Find similar past errors and their fixes.

        Args:
            error: Error to find matches for
            limit: Maximum results
            project_id: Filter by project

        Returns:
            Similar errors with potential fixes
        """
        return await self.search(
            query=error,
            limit=limit,
            types=[MemoryType.ERROR, MemoryType.ERROR_FIX],
            project_id=project_id,
            min_similarity=0.6,
        )

    async def find_patterns(
        self,
        intent: str,
        limit: int = 5,
        project_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Find execution patterns matching an intent.

        Args:
            intent: What the user wants to do
            limit: Maximum results
            project_id: Filter by project

        Returns:
            Matching patterns with step sequences
        """
        return await self.search(
            query=intent,
            limit=limit,
            types=[MemoryType.PATTERN],
            project_id=project_id,
            min_similarity=0.5,
        )

    async def get_project_context(
        self,
        project_id: str,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """
        Get all context memories for a project.

        Args:
            project_id: Project identifier
            limit: Maximum items

        Returns:
            Project context memories
        """
        results = await self.search(
            query=f"project context {project_id}",
            limit=limit,
            types=[MemoryType.CONTEXT],
            project_id=project_id,
            min_similarity=0.3,  # Lower threshold for context
        )
        return [r.item for r in results]

    # ═══════════════════════════════════════════════════════════
    # Management Operations
    # ═══════════════════════════════════════════════════════════

    async def get_memory(self, memory_id: str) -> MemoryItem | None:
        """Get a specific memory by ID."""
        return await self.long_term.get(memory_id)

    async def forget(self, memory_id: str) -> bool:
        """Delete a memory."""
        return await self.long_term.delete(memory_id)

    async def get_stats(self) -> MemoryStats:
        """Get memory system statistics."""
        return await self.long_term.get_stats()

    async def is_healthy(self) -> dict:
        """Check health of memory services."""
        health = {
            "short_term": await self.short_term.is_available(),
            "long_term": {
                "initialized": self.long_term._initialized,
                "postgres": self.long_term._pool is not None,
                "sqlite": self.long_term._sqlite_conn is not None,
            },
            "embedder": await self.embedder.is_available(),
        }
        health["healthy"] = (
            health["embedder"] and
            (health["short_term"] or True) and  # Short-term has fallback
            health["long_term"]["initialized"]
        )
        return health

    async def initialize(self) -> bool:
        """Initialize all memory services."""
        await self.long_term.initialize()
        return True

    async def close(self) -> None:
        """Close all connections."""
        await self.short_term.close()
        await self.long_term.close()


# Global instance
_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    """Get global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


__all__ = ["MemoryService", "get_memory_service"]
