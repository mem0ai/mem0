from typing import Optional

from mem0.configs.rerankers.base import BaseRerankerConfig


class CohereRerankerConfig(BaseRerankerConfig):
    """
    Configuration class for Cohere reranker-specific parameters.
    Inherits from BaseRerankerConfig and adds Cohere-specific settings.
    """

    def __init__(
        self,
        # Base parameters
        model: Optional[str] = "rerank-english-v3.0",
        api_key: Optional[str] = None,
        top_k: Optional[int] = None,
        # Cohere-specific parameters
        return_documents: bool = False,
        max_chunks_per_doc: Optional[int] = None,
    ):
        """
        Initialize Cohere reranker configuration.

        Args:
            model (str): The Cohere rerank model to use.
            api_key (str, optional): The Cohere API key.
            top_k (int, optional): Maximum number of documents to return after reranking.
            return_documents (bool): Whether to return the document texts in the response.
            max_chunks_per_doc (int, optional): Maximum number of chunks per document.
        """
        super().__init__(model=model, api_key=api_key, top_k=top_k)
        self.return_documents = return_documents
        self.max_chunks_per_doc = max_chunks_per_doc