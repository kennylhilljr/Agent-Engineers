"""Embedding provider for the Knowledge Base RAG pipeline (AI-253).

Supports two modes:
  - ``mock``  — deterministic hash-based 384-dim vectors (no API calls)
  - ``openai`` — calls OpenAI text-embedding-3-small (only when explicitly requested)
"""

from __future__ import annotations

import hashlib
import math
from typing import List, Optional


class EmbeddingProvider:
    """Generates dense vector embeddings for text chunks.

    Args:
        provider: ``'mock'`` (default) or ``'openai'``.
        api_key:  OpenAI API key (only required when provider='openai').
    """

    EMBEDDING_DIM = 384

    def __init__(self, provider: str = "mock", api_key: Optional[str] = None) -> None:
        if provider not in ("mock", "openai"):
            raise ValueError(f"Unknown provider {provider!r}. Use 'mock' or 'openai'.")
        self.provider = provider
        self.api_key = api_key

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def embed(self, text: str) -> List[float]:
        """Return a 384-dim embedding vector for *text*.

        Mock mode is deterministic: the same text always produces the same vector.

        Args:
            text: Text to embed.

        Returns:
            List of 384 floats (unit-normalised).
        """
        if self.provider == "openai":
            return self._embed_openai(text)
        return self._embed_mock(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts.

        Args:
            texts: Texts to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        return [self.embed(t) for t in texts]

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity in [-1, 1].  Returns 0.0 if either vector is zero.
        """
        if len(a) != len(b):
            raise ValueError("Vectors must have the same dimension.")
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _embed_mock(self, text: str) -> List[float]:
        """Deterministic hash-based mock embedding.

        Uses SHA-256 seeded with the text to produce reproducible 384-dim vectors.
        Different texts produce statistically distinct vectors.
        """
        # Generate enough hash bytes to fill 384 floats.
        # Each float needs 4 bytes → 384 * 4 = 1536 bytes.
        # SHA-256 produces 32 bytes per hash, so we need ~48 hashes.
        raw_bytes = bytearray()
        counter = 0
        while len(raw_bytes) < self.EMBEDDING_DIM * 4:
            seed = f"{text}:{counter}".encode("utf-8")
            raw_bytes.extend(hashlib.sha256(seed).digest())
            counter += 1

        # Convert byte groups → floats in [-1, 1]
        vector: List[float] = []
        for i in range(self.EMBEDDING_DIM):
            offset = i * 4
            # Interpret 4 bytes as a big-endian uint32, then map to [-1, 1]
            uint_val = int.from_bytes(raw_bytes[offset : offset + 4], "big")
            float_val = (uint_val / 0xFFFFFFFF) * 2.0 - 1.0
            vector.append(float_val)

        # L2-normalise
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def _embed_openai(self, text: str) -> List[float]:  # pragma: no cover
        """Call OpenAI text-embedding-3-small.

        Only used when provider='openai'.  Not exercised in tests (no API calls).
        """
        try:
            import openai  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "openai package is required for provider='openai'. "
                "Install it with: pip install openai"
            ) from exc

        client = openai.OpenAI(api_key=self.api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
