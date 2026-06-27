"""Factory resolution tests.

These verify CLOUD_PROVIDER selects the right concrete classes WITHOUT making
network calls — the gcp/aws providers are now real cloud clients and require
credentials, so we never invoke .generate() on them here. The offline `local`
provider is exercised end-to-end. Cloud providers are smoke-tested separately
via scripts/smoke_gcp.py once authenticated.
"""

from src.config import settings
from src.providers import ProviderFactory, BaseLLM, BaseEmbeddings, BaseStorage


def test_gcp_resolution(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "gcp")
    assert ProviderFactory.get_llm().__class__.__name__ == "VertexAILLM"
    assert ProviderFactory.get_embeddings().__class__.__name__ == "VertexAIEmbeddings"
    assert ProviderFactory.get_storage().__class__.__name__ == "GCSStorage"


def test_aws_resolution(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "aws")
    assert ProviderFactory.get_llm().__class__.__name__ == "BedrockLLM"
    assert ProviderFactory.get_embeddings().__class__.__name__ == "BedrockEmbeddings"
    assert ProviderFactory.get_storage().__class__.__name__ == "S3Storage"


def test_local_resolution_and_generation(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    llm = ProviderFactory.get_llm()
    embeddings = ProviderFactory.get_embeddings()
    storage = ProviderFactory.get_storage()

    assert isinstance(llm, BaseLLM)
    assert isinstance(embeddings, BaseEmbeddings)
    assert isinstance(storage, BaseStorage)
    # Local provider runs offline — safe to actually invoke.
    answer = llm.generate(
        "CONTEXT:\nParis is the capital of France.\n\nQUESTION: capital of France?"
    )
    assert isinstance(answer, str) and answer
    assert len(embeddings.embed_query("hello")) > 0


def test_unsupported_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "azure")
    import pytest

    with pytest.raises(ValueError):
        ProviderFactory.get_llm()
