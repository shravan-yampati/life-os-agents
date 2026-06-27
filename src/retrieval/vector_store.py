"""Swappable vector store backends.

Mirrors the cloud ProviderFactory pattern: the pipeline talks to
BaseVectorStore, and VECTOR_BACKEND in .env selects the implementation.

- LocalVectorStore: numpy cosine search persisted to a JSON file. Zero
  infrastructure; intended for development and offline runs.
- PgVectorStore: Postgres + pgvector (see docker-compose.yml), the
  production-shaped backend used for benchmarking.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

from src.config import settings


@dataclass
class SearchResult:
    text: str
    source: str
    score: float


class BaseVectorStore(ABC):
    """Abstract interface for vector storage and similarity search."""

    @abstractmethod
    def add(
        self, texts: List[str], embeddings: List[List[float]], source: str
    ) -> int:
        """Stores chunks and their embeddings. Returns number stored."""

    @abstractmethod
    def search(self, embedding: List[float], top_k: int = 4) -> List[SearchResult]:
        """Returns the top_k most similar chunks by cosine similarity."""

    @abstractmethod
    def clear(self) -> None:
        """Removes all stored chunks."""

    @abstractmethod
    def count(self) -> int:
        """Returns the number of stored chunks."""


class LocalVectorStore(BaseVectorStore):
    """In-memory cosine search with JSON persistence."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or settings.LOCAL_VECTOR_PATH)
        self._records: List[dict] = []
        if self.path.exists():
            self._records = json.loads(self.path.read_text(encoding="utf-8"))

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._records), encoding="utf-8")

    def add(
        self, texts: List[str], embeddings: List[List[float]], source: str
    ) -> int:
        for text, emb in zip(texts, embeddings, strict=True):
            self._records.append({"text": text, "source": source, "embedding": emb})
        self._persist()
        return len(texts)

    def search(self, embedding: List[float], top_k: int = 4) -> List[SearchResult]:
        if not self._records:
            return []
        matrix = np.array([r["embedding"] for r in self._records], dtype=np.float64)
        query = np.array(embedding, dtype=np.float64)
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
        norms[norms == 0] = 1e-12
        scores = (matrix @ query) / norms
        order = np.argsort(-scores)[:top_k]
        return [
            SearchResult(
                text=self._records[i]["text"],
                source=self._records[i]["source"],
                score=float(scores[i]),
            )
            for i in order
        ]

    def clear(self) -> None:
        self._records = []
        if self.path.exists():
            self.path.unlink()

    def count(self) -> int:
        return len(self._records)


class PgVectorStore(BaseVectorStore):
    """Postgres + pgvector backend (requires docker-compose up)."""

    def __init__(self, dim: int, table: str = "chunks"):
        import psycopg2

        self.table = table
        self.dim = dim
        self.conn = psycopg2.connect(settings.DATABASE_URL)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    embedding vector({dim}) NOT NULL
                )
                """
            )

    def add(
        self, texts: List[str], embeddings: List[List[float]], source: str
    ) -> int:
        with self.conn.cursor() as cur:
            for text, emb in zip(texts, embeddings, strict=True):
                cur.execute(
                    f"INSERT INTO {self.table} (text, source, embedding) "
                    f"VALUES (%s, %s, %s)",
                    (text, source, json.dumps(emb)),
                )
        return len(texts)

    def search(self, embedding: List[float], top_k: int = 4) -> List[SearchResult]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT text, source, 1 - (embedding <=> %s::vector) AS score
                FROM {self.table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (json.dumps(embedding), json.dumps(embedding), top_k),
            )
            return [
                SearchResult(text=row[0], source=row[1], score=float(row[2]))
                for row in cur.fetchall()
            ]

    def clear(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"TRUNCATE {self.table}")

    def count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self.table}")
            return cur.fetchone()[0]


def get_vector_store(dim: int) -> BaseVectorStore:
    """Resolves the vector store backend from settings.VECTOR_BACKEND."""
    backend = settings.VECTOR_BACKEND.lower()
    if backend == "local":
        return LocalVectorStore()
    elif backend == "pgvector":
        return PgVectorStore(dim=dim)
    else:
        raise ValueError(f"Unsupported VECTOR_BACKEND: {settings.VECTOR_BACKEND}")
