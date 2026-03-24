"""
Long-term memory for JARVIS.

Uses PostgreSQL with pgvector extension for persistent semantic memory.
"""

import json
from datetime import datetime
from typing import Any, Sequence
from uuid import uuid4

from jarvis.core.logging import get_logger
from jarvis.core.constants import MemoryType
from jarvis.memory.models.memory_item import MemoryItem, SearchResult, MemoryStats
from jarvis.memory.embedder import Embedder, get_embedder
from jarvis.config import get_settings

logger = get_logger("jarvis.memory.long_term")


class LongTermMemory:
    """
    Persistent semantic memory using PostgreSQL + pgvector.

    Stores:
    - Project structure and context
    - Error patterns and their fixes
    - Execution patterns (successful workflows)
    - User preferences
    - Command history with outcomes

    Supports semantic search using vector embeddings.
    """

    def __init__(
        self,
        database_url: str | None = None,
        embedder: Embedder | None = None,
    ):
        """
        Initialize long-term memory.

        Args:
            database_url: PostgreSQL connection URL
            embedder: Embedder for generating vectors
        """
        self.database_url = database_url
        self.embedder = embedder or get_embedder()
        self.logger = get_logger("jarvis.memory.long_term")
        self._pool = None
        self._initialized = False

        # Fallback to SQLite for local development
        self._use_sqlite = False
        self._sqlite_conn = None
        self._fallback_storage: dict[str, MemoryItem] = {}

    async def initialize(self) -> bool:
        """
        Initialize database connection and schema.

        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True

        # Try PostgreSQL first
        if await self._init_postgres():
            self._initialized = True
            return True

        # Fall back to SQLite
        if await self._init_sqlite():
            self._use_sqlite = True
            self._initialized = True
            return True

        # Use in-memory fallback
        self.logger.warning("Using in-memory storage (no persistence)")
        self._initialized = True
        return True

    async def _init_postgres(self) -> bool:
        """Initialize PostgreSQL connection."""
        try:
            import asyncpg
            from pgvector.asyncpg import register_vector

            settings = get_settings()
            url = self.database_url or getattr(settings, 'database_url', None)

            if not url:
                return False

            self._pool = await asyncpg.create_pool(url, min_size=2, max_size=10)

            # Register pgvector type
            async with self._pool.acquire() as conn:
                await register_vector(conn)

                # Create extension and tables
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                await self._create_tables(conn)

            self.logger.info("Connected to PostgreSQL with pgvector")
            return True

        except ImportError:
            self.logger.debug("asyncpg or pgvector not installed")
            return False
        except Exception as e:
            self.logger.warning(f"PostgreSQL connection failed: {e}")
            return False

    async def _init_sqlite(self) -> bool:
        """Initialize SQLite connection (without vector search)."""
        try:
            import aiosqlite

            db_path = "jarvis_memory.db"
            self._sqlite_conn = await aiosqlite.connect(db_path)

            # Create tables
            await self._sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT,
                    project_id TEXT,
                    file_path TEXT,
                    language TEXT,
                    tags TEXT,
                    metadata TEXT,
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT
                )
            """)
            await self._sqlite_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(type)"
            )
            await self._sqlite_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_items(project_id)"
            )
            await self._sqlite_conn.commit()

            self.logger.info(f"Using SQLite for memory storage: {db_path}")
            return True

        except ImportError:
            self.logger.debug("aiosqlite not installed")
            return False
        except Exception as e:
            self.logger.warning(f"SQLite initialization failed: {e}")
            return False

    async def _create_tables(self, conn) -> None:
        """Create PostgreSQL tables with pgvector."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                type VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                embedding vector(384),
                project_id VARCHAR(255),
                file_path VARCHAR(500),
                language VARCHAR(50),
                tags TEXT[],
                metadata JSONB DEFAULT '{}',
                importance FLOAT DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ,
                deleted_at TIMESTAMPTZ
            )
        """)

        # Create vector index for similarity search
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_embedding
            ON memory_items USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(type)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_items(project_id)"
        )

    async def store(
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
        Store a new memory item.

        Args:
            content: Text content to store
            memory_type: Type of memory
            project_id: Associated project
            file_path: Associated file path
            metadata: Additional metadata
            importance: Importance score (0-1)
            tags: Tags for categorization

        Returns:
            Created MemoryItem
        """
        await self.initialize()

        # Generate embedding
        try:
            embedding = await self.embedder.embed(content)
        except Exception as e:
            self.logger.warning(f"Embedding failed, storing without vector: {e}")
            embedding = None

        item = MemoryItem(
            id=str(uuid4()),
            type=memory_type,
            content=content,
            embedding=embedding,
            project_id=project_id,
            file_path=file_path,
            metadata=metadata or {},
            importance=importance,
            tags=tags or [],
        )

        # Store in database
        if self._pool:
            await self._store_postgres(item)
        elif self._sqlite_conn:
            await self._store_sqlite(item)
        else:
            self._fallback_storage[item.id] = item

        self.logger.debug(f"Stored memory: {item.id} ({memory_type.value})")
        return item

    async def _store_postgres(self, item: MemoryItem) -> None:
        """Store item in PostgreSQL."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO memory_items
                (id, type, content, embedding, project_id, file_path, language, tags, metadata, importance, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
                item.id,
                item.type.value,
                item.content,
                item.embedding,
                item.project_id,
                item.file_path,
                item.language,
                item.tags,
                json.dumps(item.metadata),
                item.importance,
                item.created_at,
                item.updated_at,
            )

    async def _store_sqlite(self, item: MemoryItem) -> None:
        """Store item in SQLite."""
        await self._sqlite_conn.execute("""
            INSERT INTO memory_items
            (id, type, content, embedding, project_id, file_path, language, tags, metadata, importance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.id,
            item.type.value,
            item.content,
            json.dumps(item.embedding) if item.embedding else None,
            item.project_id,
            item.file_path,
            item.language,
            json.dumps(item.tags),
            json.dumps(item.metadata),
            item.importance,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
        ))
        await self._sqlite_conn.commit()

    async def search(
        self,
        query: str,
        limit: int = 10,
        type_filter: list[MemoryType] | None = None,
        project_id: str | None = None,
        min_similarity: float = 0.5,
    ) -> list[SearchResult]:
        """
        Search memories by semantic similarity.

        Args:
            query: Search query text
            limit: Maximum results to return
            type_filter: Filter by memory types
            project_id: Filter by project
            min_similarity: Minimum similarity threshold

        Returns:
            List of SearchResults sorted by similarity
        """
        await self.initialize()

        # Generate query embedding
        try:
            query_embedding = await self.embedder.embed(query)
        except Exception as e:
            self.logger.warning(f"Query embedding failed: {e}")
            return []

        if self._pool:
            return await self._search_postgres(
                query_embedding, limit, type_filter, project_id, min_similarity
            )
        elif self._sqlite_conn:
            return await self._search_sqlite(
                query_embedding, limit, type_filter, project_id, min_similarity
            )
        else:
            return self._search_fallback(
                query_embedding, limit, type_filter, project_id, min_similarity
            )

    async def _search_postgres(
        self,
        embedding: list[float],
        limit: int,
        type_filter: list[MemoryType] | None,
        project_id: str | None,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Search in PostgreSQL using pgvector."""
        async with self._pool.acquire() as conn:
            # Build query
            conditions = ["deleted_at IS NULL", "embedding IS NOT NULL"]
            params = [embedding, limit]
            param_idx = 3

            if type_filter:
                types = [t.value for t in type_filter]
                conditions.append(f"type = ANY(${param_idx})")
                params.append(types)
                param_idx += 1

            if project_id:
                conditions.append(f"project_id = ${param_idx}")
                params.append(project_id)
                param_idx += 1

            query = f"""
                SELECT
                    id, type, content, embedding, project_id, file_path, language,
                    tags, metadata, importance, access_count, last_accessed,
                    created_at, updated_at, expires_at,
                    1 - (embedding <=> $1) AS similarity
                FROM memory_items
                WHERE {' AND '.join(conditions)}
                ORDER BY embedding <=> $1
                LIMIT $2
            """

            rows = await conn.fetch(query, *params)

            results = []
            for row in rows:
                similarity = float(row["similarity"])
                if similarity < min_similarity:
                    continue

                item = MemoryItem(
                    id=str(row["id"]),
                    type=MemoryType(row["type"]),
                    content=row["content"],
                    embedding=list(row["embedding"]) if row["embedding"] else None,
                    project_id=row["project_id"],
                    file_path=row["file_path"],
                    language=row["language"],
                    tags=row["tags"] or [],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    importance=row["importance"],
                    access_count=row["access_count"],
                    last_accessed=row["last_accessed"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    expires_at=row["expires_at"],
                )
                results.append(SearchResult(item=item, similarity=similarity))

            return results

    async def _search_sqlite(
        self,
        embedding: list[float],
        limit: int,
        type_filter: list[MemoryType] | None,
        project_id: str | None,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Search in SQLite (brute-force similarity calculation)."""
        # Build query
        conditions = ["embedding IS NOT NULL"]
        params = []

        if type_filter:
            placeholders = ",".join("?" * len(type_filter))
            conditions.append(f"type IN ({placeholders})")
            params.extend([t.value for t in type_filter])

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        query = f"""
            SELECT * FROM memory_items
            WHERE {' AND '.join(conditions)}
        """

        async with self._sqlite_conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        # Calculate similarities
        results = []
        for row in rows:
            row_embedding = json.loads(row[3]) if row[3] else None
            if not row_embedding:
                continue

            similarity = self.embedder.cosine_similarity(embedding, row_embedding)
            if similarity < min_similarity:
                continue

            item = MemoryItem(
                id=row[0],
                type=MemoryType(row[1]),
                content=row[2],
                embedding=row_embedding,
                project_id=row[4],
                file_path=row[5],
                language=row[6],
                tags=json.loads(row[7]) if row[7] else [],
                metadata=json.loads(row[8]) if row[8] else {},
                importance=row[9],
                access_count=row[10],
                last_accessed=datetime.fromisoformat(row[11]) if row[11] else None,
                created_at=datetime.fromisoformat(row[12]),
                updated_at=datetime.fromisoformat(row[13]),
                expires_at=datetime.fromisoformat(row[14]) if row[14] else None,
            )
            results.append(SearchResult(item=item, similarity=similarity))

        # Sort by similarity and limit
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]

    def _search_fallback(
        self,
        embedding: list[float],
        limit: int,
        type_filter: list[MemoryType] | None,
        project_id: str | None,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Search in fallback storage."""
        results = []

        for item in self._fallback_storage.values():
            # Apply filters
            if type_filter and item.type not in type_filter:
                continue
            if project_id and item.project_id != project_id:
                continue
            if not item.embedding:
                continue

            similarity = self.embedder.cosine_similarity(embedding, item.embedding)
            if similarity >= min_similarity:
                results.append(SearchResult(item=item, similarity=similarity))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]

    async def get(self, memory_id: str) -> MemoryItem | None:
        """Get a memory item by ID."""
        await self.initialize()

        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM memory_items WHERE id = $1 AND deleted_at IS NULL",
                    memory_id,
                )
                if row:
                    return self._row_to_item(row)
        elif self._sqlite_conn:
            async with self._sqlite_conn.execute(
                "SELECT * FROM memory_items WHERE id = ?", (memory_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._sqlite_row_to_item(row)
        else:
            return self._fallback_storage.get(memory_id)

        return None

    async def delete(self, memory_id: str) -> bool:
        """Soft-delete a memory item."""
        await self.initialize()

        if self._pool:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE memory_items SET deleted_at = NOW() WHERE id = $1",
                    memory_id,
                )
                return "UPDATE 1" in result
        elif self._sqlite_conn:
            await self._sqlite_conn.execute(
                "DELETE FROM memory_items WHERE id = ?", (memory_id,)
            )
            await self._sqlite_conn.commit()
            return True
        else:
            if memory_id in self._fallback_storage:
                del self._fallback_storage[memory_id]
                return True

        return False

    async def get_stats(self) -> MemoryStats:
        """Get memory system statistics."""
        await self.initialize()

        stats = MemoryStats()

        if self._pool:
            async with self._pool.acquire() as conn:
                # Total count
                stats.total_items = await conn.fetchval(
                    "SELECT COUNT(*) FROM memory_items WHERE deleted_at IS NULL"
                )

                # By type
                rows = await conn.fetch("""
                    SELECT type, COUNT(*) as count
                    FROM memory_items
                    WHERE deleted_at IS NULL
                    GROUP BY type
                """)
                stats.items_by_type = {row["type"]: row["count"] for row in rows}

        elif self._sqlite_conn:
            async with self._sqlite_conn.execute(
                "SELECT COUNT(*) FROM memory_items"
            ) as cursor:
                row = await cursor.fetchone()
                stats.total_items = row[0] if row else 0

        else:
            stats.total_items = len(self._fallback_storage)
            for item in self._fallback_storage.values():
                type_name = item.type.value
                stats.items_by_type[type_name] = stats.items_by_type.get(type_name, 0) + 1

        return stats

    def _row_to_item(self, row) -> MemoryItem:
        """Convert PostgreSQL row to MemoryItem."""
        return MemoryItem(
            id=str(row["id"]),
            type=MemoryType(row["type"]),
            content=row["content"],
            embedding=list(row["embedding"]) if row["embedding"] else None,
            project_id=row["project_id"],
            file_path=row["file_path"],
            language=row["language"],
            tags=row["tags"] or [],
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
            importance=row["importance"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )

    def _sqlite_row_to_item(self, row) -> MemoryItem:
        """Convert SQLite row to MemoryItem."""
        return MemoryItem(
            id=row[0],
            type=MemoryType(row[1]),
            content=row[2],
            embedding=json.loads(row[3]) if row[3] else None,
            project_id=row[4],
            file_path=row[5],
            language=row[6],
            tags=json.loads(row[7]) if row[7] else [],
            metadata=json.loads(row[8]) if row[8] else {},
            importance=row[9],
            access_count=row[10],
            last_accessed=datetime.fromisoformat(row[11]) if row[11] else None,
            created_at=datetime.fromisoformat(row[12]),
            updated_at=datetime.fromisoformat(row[13]),
            expires_at=datetime.fromisoformat(row[14]) if row[14] else None,
        )

    async def close(self) -> None:
        """Close database connections."""
        if self._pool:
            await self._pool.close()
        if self._sqlite_conn:
            await self._sqlite_conn.close()


# Global instance
_long_term_memory: LongTermMemory | None = None


def get_long_term_memory() -> LongTermMemory:
    """Get global long-term memory instance."""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory


__all__ = ["LongTermMemory", "get_long_term_memory"]
