import os
from typing import Optional

try:
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
except RuntimeError:
    from embedchain.utils.misc import use_pysqlite3

    use_pysqlite3()
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class JinaEmbeddingFunction(EmbeddingFunction):
    """
    Jina AI Embedding Function for ChromaDB.
    
    Supports both API and local modes:
    - API: jina-embeddings-v5-text-nano (768d), jina-embeddings-v5-text-small (1024d)
    - Local: jinaai/jina-embeddings-v5-text-nano, jinaai/jina-embeddings-v5-text-small
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "jina-embeddings-v5-text-nano",
        task: str = "retrieval.passage",
        use_local: bool = False,
        model_kwargs: Optional[dict] = None,
    ):
        self._model_name = model_name
        self._task = task
        self._use_local = use_local
        
        if use_local:
            # Local mode using HuggingFace transformers
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
            except ImportError:
                raise ValueError(
                    "The langchain-community package is not installed. Please install it with `pip install langchain-community`"
                )
            
            # Map short names to full HuggingFace model IDs
            if not model_name.startswith("jinaai/"):
                hf_model_map = {
                    "jina-embeddings-v5-text-nano": "jinaai/jina-embeddings-v5-text-nano",
                    "jina-embeddings-v5-text-small": "jinaai/jina-embeddings-v5-text-small",
                }
                hf_model_name = hf_model_map.get(model_name, model_name)
            else:
                hf_model_name = model_name
            
            self._embeddings = HuggingFaceEmbeddings(
                model_name=hf_model_name,
                model_kwargs=model_kwargs or {},
            )
        else:
            # API mode
            if api_key is None:
                raise ValueError("api_key is required for API mode")
            
            try:
                from openai import OpenAI
            except ImportError:
                raise ValueError(
                    "The openai python package is not installed. Please install it with `pip install openai`"
                )
            
            self._client = OpenAI(api_key=api_key, base_url="https://api.jina.ai/v1")

    def __call__(self, input: Documents) -> Embeddings:
        if self._use_local:
            return self._embeddings.embed_documents(input)
        else:
            response = self._client.embeddings.create(
                input=input,
                model=self._model_name,
                extra_body={"task": self._task},
            )
            return [item.embedding for item in response.data]


class JinaEmbedder(BaseEmbedder):
    """
    Jina AI Embedder for mem0.
    
    Supports both API and local deployment:
    
    API mode (default):
        from embedchain.config import BaseEmbedderConfig
        config = BaseEmbedderConfig(
            model="jina-embeddings-v5-text-nano",
            api_key="your-jina-api-key"
        )
        embedder = JinaEmbedder(config=config)
    
    Local mode (HuggingFace models):
        config = BaseEmbedderConfig(
            model="jinaai/jina-embeddings-v5-text-nano",
            model_kwargs={"use_local": True}
        )
        embedder = JinaEmbedder(config=config)
    """
    
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.model is None:
            self.config.model = "jina-embeddings-v5-text-nano"

        # Check if local mode is requested
        use_local = self.config.model_kwargs.get("use_local", False)
        
        if not use_local:
            # API mode - require API key
            api_key = self.config.api_key or os.environ.get("JINA_API_KEY")
            if api_key is None:
                raise ValueError("JINA_API_KEY environment variable not provided. For local mode, set model_kwargs={'use_local': True}")
        else:
            api_key = None

        # Default task to retrieval.passage, can be overridden via model_kwargs
        task = self.config.model_kwargs.get("task", "retrieval.passage")

        embedding_fn = JinaEmbeddingFunction(
            api_key=api_key,
            model_name=self.config.model,
            task=task,
            use_local=use_local,
            model_kwargs=self.config.model_kwargs,
        )
        self.set_embedding_fn(embedding_fn=embedding_fn)

        # Set vector dimension based on model
        if self.config.vector_dimension:
            vector_dimension = self.config.vector_dimension
        elif "nano" in self.config.model:
            vector_dimension = VectorDimensions.JINA_NANO.value
        elif "small" in self.config.model:
            vector_dimension = VectorDimensions.JINA_SMALL.value
        else:
            vector_dimension = VectorDimensions.JINA_NANO.value

        self.set_vector_dimension(vector_dimension=vector_dimension)
