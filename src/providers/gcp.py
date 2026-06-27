"""GCP provider: Gemini LLM + embeddings via the google-genai SDK.

Uses the Generative Language API with an AI Studio API key (GOOGLE_API_KEY).
This replaces the deprecated vertexai.generative_models SDK (removal June 2026).

Heavy SDK imports and client init are done lazily (on first use) so that
importing this module — which the factory always does — costs nothing and never
fails on machines without GCP set up. Offline/local runs and the test suite use
CLOUD_PROVIDER=local and never construct these classes.

Auth: set GOOGLE_API_KEY in .env (get one at https://aistudio.google.com/apikey).

Cost note: defaults to gemini-2.5-flash (cheap) and gemini-embedding-2 (3072-dim).
Test answer quality first; only move to a stronger model if needed.
"""

from typing import Generator, List

from src.config import settings
from src.providers.base import BaseLLM, BaseEmbeddings, BaseStorage

_CLIENT = None


def _get_client():
    """Returns a lazily-initialized google-genai Client."""
    global _CLIENT
    if _CLIENT is None:
        from google import genai

        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Get one at "
                "https://aistudio.google.com/apikey and add it to .env."
            )
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


class VertexAILLM(BaseLLM):
    """Gemini text generation via google-genai SDK.

    Class name kept as VertexAILLM for backward compatibility with the
    ProviderFactory — the underlying SDK has been migrated.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.GCP_LLM_MODEL
        self._config = None

    def _generation_config(self, **kwargs):
        from google.genai import types

        return types.GenerateContentConfig(
            temperature=kwargs.get("temperature", 0.2),
            max_output_tokens=kwargs.get("max_tokens", 1024),
            top_p=kwargs.get("top_p", 0.95),
        )

    def generate(self, prompt: str, **kwargs) -> str:
        try:
            response = _get_client().models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self._generation_config(**kwargs),
            )
            return response.text
        except Exception as exc:  # noqa: BLE001 — surface a clear, actionable error
            raise RuntimeError(
                f"Gemini generation failed for model '{self.model_name}': {exc}. "
                "Check GOOGLE_API_KEY in .env and that the model name is valid."
            ) from exc

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        try:
            stream = _get_client().models.generate_content_stream(
                model=self.model_name,
                contents=prompt,
                config=self._generation_config(**kwargs),
            )
            for chunk in stream:
                text = getattr(chunk, "text", "")
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Gemini streaming failed for model '{self.model_name}': {exc}."
            ) from exc


class VertexAIEmbeddings(BaseEmbeddings):
    """Dense text embeddings via google-genai SDK (gemini-embedding-2, 3072-dim).

    Class name kept as VertexAIEmbeddings for backward compatibility with the
    ProviderFactory — the underlying SDK has been migrated.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.GCP_EMBED_MODEL

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        try:
            result = _get_client().models.embed_content(
                model=self.model_name,
                contents=documents,
            )
            return [e.values for e in result.embeddings]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Gemini embedding failed for model '{self.model_name}': {exc}."
            ) from exc


class GCSStorage(BaseStorage):
    """Google Cloud Storage object storage (the document drop zone on GCP)."""

    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self._client = None

    def _get_bucket(self):
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client(project=settings.GCP_PROJECT_ID)
        return self._client.bucket(self.bucket_name)

    def upload_file(self, local_path: str, remote_path: str) -> str:
        try:
            self._get_bucket().blob(remote_path).upload_from_filename(local_path)
            return f"gs://{self.bucket_name}/{remote_path}"
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"GCS upload failed: {exc}.") from exc

    def download_file(self, remote_path: str, local_path: str) -> None:
        try:
            self._get_bucket().blob(remote_path).download_to_filename(local_path)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"GCS download failed: {exc}.") from exc
