"""Local, dependency-free provider for offline development and testing.

LocalEmbeddings uses deterministic feature hashing (hashed bag-of-words),
so cosine similarity reflects lexical overlap between texts. LocalLLM is
an extractive answerer: it returns the sentences from the supplied context
that best match the question. Neither requires credentials or a network,
which makes the full pipeline runnable on any machine.
"""

import hashlib
import math
import re
import shutil
from pathlib import Path
from typing import Generator, List

from src.providers.base import BaseEmbeddings, BaseLLM, BaseStorage

_WORD_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "it", "its", "this", "that", "with", "as", "by",
    "at", "be", "from", "what", "which", "who", "how", "when", "where",
    "does", "do", "did", "has", "have", "had",
}


def _tokenize(text: str) -> List[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


class LocalEmbeddings(BaseEmbeddings):
    """Hashed bag-of-words embeddings. Deterministic and offline."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        return [self._embed(doc) for doc in documents]


class LocalLLM(BaseLLM):
    """Extractive question answerer.

    Expects prompts produced by the RAG pipeline containing CONTEXT and
    QUESTION sections; returns the context sentences with the highest
    lexical overlap with the question.
    """

    def __init__(self, max_sentences: int = 3):
        self.max_sentences = max_sentences

    def generate(self, prompt: str, **kwargs) -> str:
        context, question = self._parse_prompt(prompt)
        if not context:
            return "I could not find any relevant context to answer the question."

        q_tokens = set(_tokenize(question))
        sentences = re.split(r"(?<=[.!?])\s+", context)
        scored = []
        for order, sentence in enumerate(sentences):
            s_tokens = set(_tokenize(sentence))
            if not s_tokens:
                continue
            overlap = len(q_tokens & s_tokens)
            if overlap > 0:
                scored.append((overlap / math.sqrt(len(s_tokens)), order, sentence))

        if not scored:
            return "The retrieved context does not appear to answer the question."

        top = sorted(scored, key=lambda item: -item[0])[: self.max_sentences]
        # Restore original document order so the answer reads naturally
        top.sort(key=lambda item: item[1])
        return " ".join(sentence.strip() for _, _, sentence in top)

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        for word in self.generate(prompt, **kwargs).split(" "):
            yield word + " "

    @staticmethod
    def _parse_prompt(prompt: str) -> tuple[str, str]:
        context_match = re.search(
            r"CONTEXT:\s*(.*?)\s*QUESTION:", prompt, flags=re.DOTALL
        )
        question_match = re.search(r"QUESTION:\s*(.*)", prompt, flags=re.DOTALL)
        context = context_match.group(1) if context_match else ""
        question = question_match.group(1) if question_match else prompt
        return context, question


class LocalStorage(BaseStorage):
    """Filesystem-backed stand-in for cloud object storage."""

    def __init__(self, root: str = ".raglab/storage"):
        self.root = Path(root)

    def upload_file(self, local_path: str, remote_path: str) -> str:
        target = self.root / remote_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, target)
        return str(target.resolve())

    def download_file(self, remote_path: str, local_path: str) -> None:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.root / remote_path, local_path)
