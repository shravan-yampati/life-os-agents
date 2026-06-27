from src.config import settings
from src.providers.base import BaseLLM, BaseEmbeddings, BaseStorage
from src.providers.aws import BedrockLLM, BedrockEmbeddings, S3Storage
from src.providers.gcp import VertexAILLM, VertexAIEmbeddings, GCSStorage
from src.providers.local import LocalLLM, LocalEmbeddings, LocalStorage

class ProviderFactory:
    """Factory class responsible for resolving concrete cloud client instances

    based on the current environment configuration.
    """

    @staticmethod
    def get_llm() -> BaseLLM:
        provider = settings.CLOUD_PROVIDER.lower()
        if provider == "gcp":
            return VertexAILLM()
        elif provider == "aws":
            return BedrockLLM()
        elif provider == "local":
            return LocalLLM()
        else:
            raise ValueError(f"Unsupported CLOUD_PROVIDER: {settings.CLOUD_PROVIDER}")

    @staticmethod
    def get_embeddings() -> BaseEmbeddings:
        provider = settings.CLOUD_PROVIDER.lower()
        if provider == "gcp":
            return VertexAIEmbeddings()
        elif provider == "aws":
            return BedrockEmbeddings()
        elif provider == "local":
            return LocalEmbeddings()
        else:
            raise ValueError(f"Unsupported CLOUD_PROVIDER: {settings.CLOUD_PROVIDER}")

    @staticmethod
    def get_storage() -> BaseStorage:
        provider = settings.CLOUD_PROVIDER.lower()
        if provider == "gcp":
            return GCSStorage()
        elif provider == "aws":
            return S3Storage()
        elif provider == "local":
            return LocalStorage()
        else:
            raise ValueError(f"Unsupported CLOUD_PROVIDER: {settings.CLOUD_PROVIDER}")
