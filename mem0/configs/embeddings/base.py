from abc import ABC
from typing import Optional


class BaseEmbedderConfig(ABC):
    """
    Config for Embeddings.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dims: Optional[int] = None,
        # Ollama specific
        ollama_base_url: Optional[str] = None,
        # Huggingface specific
        model_kwargs: Optional[dict] = None,
    ):
        """
        Initializes a configuration class instance for the Embeddings.

        :param model: Embedding model to use, defaults to None
        :type model: Optional[str], optional
        :param api_key: API key to be use, defaults to None
        :type api_key: Optional[str], optional
        :param embedding_dims: The number of dimensions in the embedding, defaults to None
        :type embedding_dims: Optional[int], optional
        :param ollama_base_url: Base URL for the Ollama API, defaults to None
        :type ollama_base_url: Optional[str], optional
        :param model_kwargs: key-value arguments for the huggingface embedding model, defaults a dict inside init
        :type model_kwargs: Optional[Dict[str, Any]], defaults a dict inside init

        """

        self.model = model
        self.api_key = api_key
        self.embedding_dims = embedding_dims

        # Ollama specific
        self.ollama_base_url = ollama_base_url

        # Huggingface specific
        self.model_kwargs = model_kwargs or {}
