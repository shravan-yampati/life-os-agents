"""Naive RAG pipeline: chunk -> embed -> store -> retrieve -> generate.

This is the baseline strategy in the benchmark. Hybrid (BM25 + rerank)
and Agentic (LangGraph router) pipelines will build on the same
components.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from src.ingestion.chunker import chunk_text
from src.ingestion.loader import load_document
from src.providers.factory import ProviderFactory
from src.retrieval.vector_store import SearchResult, get_vector_store

PROMPT_TEMPLATE = """You are a helpful assistant. Answer the question using only the provided context. If the context does not contain the answer, say so.

CONTEXT:
{context}

QUESTION: {question}"""


@dataclass
class RAGResponse:
    answer: str
    sources: List[SearchResult] = field(default_factory=list)


class NaiveRAG:
    """Baseline dense-retrieval RAG pipeline."""

    def __init__(self, top_k: int = 4):
        self.top_k = top_k
        self.llm = ProviderFactory.get_llm()
        self.embeddings = ProviderFactory.get_embeddings()
        probe = self.embeddings.embed_query("dimension probe")
        self.store = get_vector_store(dim=len(probe))

    def ingest(self, path: str | Path) -> int:
        """Loads, chunks, embeds, and stores a document. Returns chunk count."""
        text = load_document(path)
        chunks = chunk_text(text)
        if not chunks:
            return 0
        vectors = self.embeddings.embed_documents(chunks)
        return self.store.add(chunks, vectors, source=str(path))

    def ask(self, question: str) -> RAGResponse:
        """Retrieves relevant chunks and generates a grounded answer."""
        query_vec = self.embeddings.embed_query(question)
        results = self.store.search(query_vec, top_k=self.top_k)
        if not results:
            return RAGResponse(
                answer="No documents have been ingested yet. Run ingest first."
            )
        context = "\n\n---\n\n".join(r.text for r in results)
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)
        answer = self.llm.generate(prompt)
        return RAGResponse(answer=answer, sources=results)
