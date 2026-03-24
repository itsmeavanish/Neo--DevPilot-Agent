"""
Memory item models for JARVIS.

Defines the structure of items stored in the RAG memory system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from jarvis.core.constants import MemoryType


@dataclass
class MemoryItem:
    """
    A single item stored in the memory system.

    Can represent:
    - Project context (file structure, dependencies)
    - Error occurrences and their fixes
    - Execution patterns (successful command sequences)
    - User preferences
    - Command history
    """

    # Identity
    id: str = field(default_factory=lambda: str(uuid4()))
    type: MemoryType = MemoryType.CONTEXT

    # Content
    content: str = ""
    embedding: list[float] | None = None

    # Metadata
    project_id: str | None = None
    file_path: str | None = None
    language: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Importance and access tracking
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: datetime | None = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None  # None = never expires

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "embedding": self.embedding,
            "project_id": self.project_id,
            "file_path": self.file_path,
            "language": self.language,
            "tags": self.tags,
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            type=MemoryType(data.get("type", "context")),
            content=data.get("content", ""),
            embedding=data.get("embedding"),
            project_id=data.get("project_id"),
            file_path=data.get("file_path"),
            language=data.get("language"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )

    def update_access(self) -> None:
        """Update access tracking."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()

    @property
    def is_expired(self) -> bool:
        """Check if the memory item has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class SearchResult:
    """Result from a memory search."""
    item: MemoryItem
    similarity: float  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "item": self.item.to_dict(),
            "similarity": self.similarity,
        }


@dataclass
class MemoryStats:
    """Statistics about the memory system."""
    total_items: int = 0
    items_by_type: dict[str, int] = field(default_factory=dict)
    total_size_bytes: int = 0
    oldest_item: datetime | None = None
    newest_item: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "total_items": self.total_items,
            "items_by_type": self.items_by_type,
            "total_size_bytes": self.total_size_bytes,
            "oldest_item": self.oldest_item.isoformat() if self.oldest_item else None,
            "newest_item": self.newest_item.isoformat() if self.newest_item else None,
        }


__all__ = ["MemoryItem", "SearchResult", "MemoryStats"]
