from typing import List, Generator
from src.providers.base import BaseLLM, BaseEmbeddings, BaseStorage
from src.config import settings

class BedrockLLM(BaseLLM):
    def __init__(self):
        self.region = settings.AWS_REGION
        # Boto3 client will be initialized here in Phase 1
        self.client = None

    def generate(self, prompt: str, **kwargs) -> str:
        # Mock for Phase 0.5 scaffolding test
        return f"[AWS Bedrock Mock Response] for prompt: {prompt}"

    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        # Mock stream for Phase 0.5
        yield f"[AWS Bedrock Mock Stream Token 1]"
        yield f" for prompt: {prompt}"


class BedrockEmbeddings(BaseEmbeddings):
    def __init__(self):
        self.region = settings.AWS_REGION
        self.client = None

    def embed_query(self, text: str) -> List[float]:
        # Return a mock 1536-dimensional embedding vector
        return [0.1] * 1536

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        # Return mock embeddings
        return [[0.1] * 1536 for _ in documents]


class S3Storage(BaseStorage):
    def __init__(self):
        self.bucket = settings.S3_BUCKET_NAME
        self.client = None

    def upload_file(self, local_path: str, remote_path: str) -> str:
        return f"s3://{self.bucket}/{remote_path}"

    def download_file(self, remote_path: str, local_path: str) -> None:
        pass
