from abc import ABC, abstractmethod
from typing import List, Generator

class BaseLLM(ABC):
    """Abstract Base Class defining the interface for Language Models."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generates a complete response for a given text prompt.

        Args:
            prompt: The input prompt to send to the model.
            **kwargs: Configuration flags (temperature, max_tokens, etc.)

        Returns:
            The generated string response from the model.
        """
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Streams response tokens from the model as they are generated.

        Args:
            prompt: The input prompt to send to the model.
            **kwargs: Configuration flags (temperature, max_tokens, etc.)

        Yields:
            Token strings generated sequentially.
        """
        pass


class BaseEmbeddings(ABC):
    """Abstract Base Class defining the interface for text embeddings."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embeds a single query string into a dense vector.

        Args:
            text: Query string.

        Returns:
            A list of floats representing the dense vector.
        """
        pass

    @abstractmethod
    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """Embeds a list of document strings into a list of dense vectors.

        Args:
            documents: A list of text strings.

        Returns:
            A list of lists of floats representing document vectors.
        """
        pass


class BaseStorage(ABC):
    """Abstract Base Class defining the interface for document storage."""

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> str:
        """Uploads a file from local storage to the remote bucket.

        Args:
            local_path: Local system path to the file.
            remote_path: Target path in the bucket.

        Returns:
            The public or direct access URL of the uploaded asset.
        """
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> None:
        """Downloads a file from the remote bucket to local storage.

        Args:
            remote_path: Source path in the bucket.
            local_path: Target path on the local filesystem.
        """
        pass
