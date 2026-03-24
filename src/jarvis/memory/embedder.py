"""
Embedding service for JARVIS.

Uses Ollama to generate vector embeddings for semantic search.
"""

import asyncio
from typing import Sequence

import httpx

from jarvis.core.logging import get_logger
from jarvis.core.exceptions import EmbeddingError
from jarvis.config import get_settings

logger = get_logger("jarvis.memory.embedder")


class Embedder:
    """
    Generate text embeddings using Ollama.

    Uses the nomic-embed-text model by default which produces
    384-dimensional embeddings suitable for semantic search.
    """

    # Embedding model (384 dimensions)
    DEFAULT_MODEL = "nomic-embed-text"
    EMBEDDING_DIM = 384

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: int = 30,
    ):
        """
        Initialize the embedder.

        Args:
            host: Ollama server URL (default from settings)
            model: Embedding model name (default: nomic-embed-text)
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        self.logger = get_logger("jarvis.memory.embedder")

        # Cache for embeddings (simple in-memory cache)
        self._cache: dict[str, list[float]] = {}
        self._cache_max_size = 1000

    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            EmbeddingError: If embedding fails
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text")

        # Check cache
        cache_key = hash(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        text = text.strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.host}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text,
                    },
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding", [])

                if not embedding:
                    raise EmbeddingError("Empty embedding returned from Ollama")

                # Cache the result
                self._add_to_cache(cache_key, embedding)

                return embedding

        except httpx.ConnectError:
            raise EmbeddingError(
                f"Cannot connect to Ollama at {self.host}. "
                f"Make sure Ollama is running with model '{self.model}' pulled."
            )
        except httpx.TimeoutException:
            raise EmbeddingError(f"Embedding request timed out after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            raise EmbeddingError(f"Ollama returned error: {e.response.status_code}")
        except Exception as e:
            raise EmbeddingError(f"Embedding failed: {e}")

    async def embed_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 10,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            batch_size: Number of concurrent requests

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        embeddings = []

        # Process in batches to avoid overwhelming the server
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            tasks = [self.embed(text) for text in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.warning(f"Batch embedding failed: {result}")
                    embeddings.append([0.0] * self.EMBEDDING_DIM)  # Zero vector for failures
                else:
                    embeddings.append(result)

        return embeddings

    async def is_available(self) -> bool:
        """Check if the embedding service is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.host}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "").split(":")[0] for m in models]
                    return self.model.split(":")[0] in model_names
            return False
        except Exception:
            return False

    async def ensure_model(self) -> bool:
        """
        Ensure the embedding model is available.

        Pulls the model if not already present.
        """
        if await self.is_available():
            return True

        self.logger.info(f"Pulling embedding model: {self.model}")

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream(
                    "POST",
                    f"{self.host}/api/pull",
                    json={"name": self.model},
                ) as response:
                    async for line in response.aiter_lines():
                        pass  # Wait for pull to complete
            return True
        except Exception as e:
            self.logger.error(f"Failed to pull model: {e}")
            return False

    def _add_to_cache(self, key: int, embedding: list[float]) -> None:
        """Add embedding to cache, evicting old entries if necessary."""
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = embedding

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score between 0 and 1
        """
        if len(a) != len(b):
            raise ValueError("Vectors must have same length")

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# Global embedder instance
_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Get the global embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


__all__ = ["Embedder", "get_embedder"]
