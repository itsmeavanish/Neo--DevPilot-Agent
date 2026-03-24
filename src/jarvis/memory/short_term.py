"""
Short-term memory for JARVIS.

Uses Redis for fast, session-scoped memory with automatic expiration.
"""

import json
from datetime import timedelta
from typing import Any

from jarvis.core.logging import get_logger
from jarvis.core.exceptions import MemoryError as JarvisMemoryError
from jarvis.config import get_settings

logger = get_logger("jarvis.memory.short_term")


class ShortTermMemory:
    """
    Fast, session-scoped memory using Redis.

    Stores:
    - Current task context
    - Recent command outputs
    - Temporary data during execution
    - Session state

    All data automatically expires after a configurable TTL.
    """

    DEFAULT_TTL = 3600  # 1 hour
    KEY_PREFIX = "jarvis:stm:"

    def __init__(
        self,
        redis_url: str | None = None,
        default_ttl: int = DEFAULT_TTL,
    ):
        """
        Initialize short-term memory.

        Args:
            redis_url: Redis connection URL (default from settings)
            default_ttl: Default TTL in seconds for stored items
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.logger = get_logger("jarvis.memory.short_term")
        self._client = None
        self._fallback: dict[str, Any] = {}  # In-memory fallback when Redis unavailable

    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is not None:
            return self._client

        try:
            import redis.asyncio as redis
            settings = get_settings()
            url = self.redis_url or getattr(settings, 'redis_url', None) or "redis://localhost:6379/0"
            self._client = redis.from_url(url, decode_responses=True)
            # Test connection
            await self._client.ping()
            self.logger.info("Connected to Redis")
            return self._client
        except ImportError:
            self.logger.warning("redis package not installed, using in-memory fallback")
            return None
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}, using in-memory fallback")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        session_id: str | None = None,
    ) -> bool:
        """
        Store a value in short-term memory.

        Args:
            key: Storage key
            value: Value to store (will be JSON serialized)
            ttl: Time-to-live in seconds (None = use default)
            session_id: Optional session ID for namespacing

        Returns:
            True if stored successfully
        """
        full_key = self._make_key(key, session_id)
        ttl = ttl or self.default_ttl

        try:
            serialized = json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            self.logger.warning(f"Failed to serialize value: {e}")
            return False

        client = await self._get_client()

        if client:
            try:
                await client.setex(full_key, ttl, serialized)
                return True
            except Exception as e:
                self.logger.warning(f"Redis set failed: {e}")

        # Fallback to in-memory
        self._fallback[full_key] = {
            "value": serialized,
            "expires_at": None,  # No expiration tracking in fallback
        }
        return True

    async def get(
        self,
        key: str,
        session_id: str | None = None,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a value from short-term memory.

        Args:
            key: Storage key
            session_id: Optional session ID for namespacing
            default: Default value if not found

        Returns:
            Stored value or default
        """
        full_key = self._make_key(key, session_id)
        client = await self._get_client()

        value = None

        if client:
            try:
                value = await client.get(full_key)
            except Exception as e:
                self.logger.warning(f"Redis get failed: {e}")

        # Check fallback
        if value is None and full_key in self._fallback:
            value = self._fallback[full_key]["value"]

        if value is None:
            return default

        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    async def delete(
        self,
        key: str,
        session_id: str | None = None,
    ) -> bool:
        """
        Delete a value from short-term memory.

        Args:
            key: Storage key
            session_id: Optional session ID

        Returns:
            True if deleted
        """
        full_key = self._make_key(key, session_id)
        client = await self._get_client()

        deleted = False

        if client:
            try:
                result = await client.delete(full_key)
                deleted = result > 0
            except Exception as e:
                self.logger.warning(f"Redis delete failed: {e}")

        if full_key in self._fallback:
            del self._fallback[full_key]
            deleted = True

        return deleted

    async def exists(
        self,
        key: str,
        session_id: str | None = None,
    ) -> bool:
        """Check if a key exists."""
        full_key = self._make_key(key, session_id)
        client = await self._get_client()

        if client:
            try:
                return await client.exists(full_key) > 0
            except Exception:
                pass

        return full_key in self._fallback

    async def extend_ttl(
        self,
        key: str,
        ttl: int,
        session_id: str | None = None,
    ) -> bool:
        """Extend the TTL of a key."""
        full_key = self._make_key(key, session_id)
        client = await self._get_client()

        if client:
            try:
                return await client.expire(full_key, ttl)
            except Exception as e:
                self.logger.warning(f"Redis expire failed: {e}")

        return False

    async def get_many(
        self,
        keys: list[str],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Get multiple values at once."""
        if not keys:
            return {}

        full_keys = [self._make_key(k, session_id) for k in keys]
        result = {}

        client = await self._get_client()

        if client:
            try:
                values = await client.mget(full_keys)
                for key, value in zip(keys, values):
                    if value is not None:
                        try:
                            result[key] = json.loads(value)
                        except (TypeError, ValueError):
                            result[key] = value
            except Exception as e:
                self.logger.warning(f"Redis mget failed: {e}")

        # Check fallback for missing keys
        for key in keys:
            if key not in result:
                full_key = self._make_key(key, session_id)
                if full_key in self._fallback:
                    try:
                        result[key] = json.loads(self._fallback[full_key]["value"])
                    except (TypeError, ValueError):
                        result[key] = self._fallback[full_key]["value"]

        return result

    async def clear_session(self, session_id: str) -> int:
        """
        Clear all keys for a session.

        Args:
            session_id: Session ID to clear

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.KEY_PREFIX}session:{session_id}:*"
        client = await self._get_client()
        count = 0

        if client:
            try:
                cursor = 0
                while True:
                    cursor, keys = await client.scan(cursor, match=pattern, count=100)
                    if keys:
                        count += await client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                self.logger.warning(f"Redis scan/delete failed: {e}")

        # Clear from fallback
        prefix = f"{self.KEY_PREFIX}session:{session_id}:"
        to_delete = [k for k in self._fallback if k.startswith(prefix)]
        for k in to_delete:
            del self._fallback[k]
            count += 1

        return count

    async def push_list(
        self,
        key: str,
        value: Any,
        max_length: int = 100,
        session_id: str | None = None,
    ) -> int:
        """
        Push value to a list (FIFO queue).

        Args:
            key: List key
            value: Value to push
            max_length: Maximum list length (oldest items trimmed)
            session_id: Optional session ID

        Returns:
            Current list length
        """
        full_key = self._make_key(key, session_id)
        serialized = json.dumps(value, default=str)

        client = await self._get_client()

        if client:
            try:
                pipe = client.pipeline()
                pipe.rpush(full_key, serialized)
                pipe.ltrim(full_key, -max_length, -1)
                pipe.llen(full_key)
                results = await pipe.execute()
                return results[-1]
            except Exception as e:
                self.logger.warning(f"Redis list push failed: {e}")

        # Fallback
        if full_key not in self._fallback:
            self._fallback[full_key] = {"value": "[]"}

        try:
            lst = json.loads(self._fallback[full_key]["value"])
            lst.append(value)
            if len(lst) > max_length:
                lst = lst[-max_length:]
            self._fallback[full_key]["value"] = json.dumps(lst, default=str)
            return len(lst)
        except Exception:
            return 0

    async def get_list(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        session_id: str | None = None,
    ) -> list[Any]:
        """
        Get items from a list.

        Args:
            key: List key
            start: Start index
            end: End index (-1 = end)
            session_id: Optional session ID

        Returns:
            List of items
        """
        full_key = self._make_key(key, session_id)
        client = await self._get_client()

        if client:
            try:
                items = await client.lrange(full_key, start, end)
                return [json.loads(item) for item in items]
            except Exception as e:
                self.logger.warning(f"Redis list get failed: {e}")

        # Fallback
        if full_key in self._fallback:
            try:
                lst = json.loads(self._fallback[full_key]["value"])
                if end == -1:
                    return lst[start:]
                return lst[start:end + 1]
            except Exception:
                pass

        return []

    async def is_available(self) -> bool:
        """Check if Redis is available."""
        client = await self._get_client()
        if client:
            try:
                await client.ping()
                return True
            except Exception:
                pass
        return False

    def _make_key(self, key: str, session_id: str | None = None) -> str:
        """Create full key with prefix and optional session."""
        if session_id:
            return f"{self.KEY_PREFIX}session:{session_id}:{key}"
        return f"{self.KEY_PREFIX}{key}"

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Global instance
_short_term_memory: ShortTermMemory | None = None


def get_short_term_memory() -> ShortTermMemory:
    """Get global short-term memory instance."""
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    return _short_term_memory


__all__ = ["ShortTermMemory", "get_short_term_memory"]
