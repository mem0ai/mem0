from abc import ABC
from typing import Optional

class BaseEmbedderConfig(ABC):
    """
    Config for Embeddings.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        embedding_dims: Optional[int] = None,
        api_key: Optional[str] = None,

        # Ollama specific
        ollama_base_url: Optional[str] = None,

        # LM Studio specific
        lmstudio_base_url: Optional[str] = None
    ):
        """
        Initializes a configuration class instance for the Embeddings.

        :param model: Embedding model to use, defaults to None
        :type model: Optional[str], optional
        :param embedding_dims: The number of dimensions in the embedding, defaults to None
        :type embedding_dims: Optional[int], optional
        :param api_key: API key to use, defaults to None
        :type api_key: Optional[str], optional
        :param ollama_base_url: Base URL for the Ollama API, defaults to None
        :type ollama_base_url: Optional[str], optional
        :param lmstudio_base_url: Base URL for the LM Studio, defaults to None
        :type lmstudio_base_url: Optional[str], optional
        """
        
        self.model = model
        self.embedding_dims = embedding_dims
        self.api_key = api_key

        # Ollama specific
        self.ollama_base_url = ollama_base_url

        # LM Studio specific
        self.lmstudio_base_url = lmstudio_base_url