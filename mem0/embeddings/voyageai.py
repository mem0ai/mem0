import os
from typing import Generator, List, Literal, Optional, Tuple, Union

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

# Token limits per batch for each VoyageAI model
VOYAGE_TOTAL_TOKEN_LIMITS = {
    # Voyage 4 models (upcoming)
    "voyage-4-large": 120_000,
    "voyage-4": 320_000,
    "voyage-4-lite": 1_000_000,
    # Voyage 3.x models
    "voyage-context-3": 32_000,
    "voyage-3.5-lite": 1_000_000,
    "voyage-3.5": 320_000,
    "voyage-2": 320_000,
    "voyage-3-large": 120_000,
    "voyage-code-3": 120_000,
    "voyage-large-2-instruct": 120_000,
    "voyage-finance-2": 120_000,
    "voyage-multilingual-2": 120_000,
    "voyage-law-2": 120_000,
    "voyage-large-2": 120_000,
    "voyage-3": 120_000,
    "voyage-3-lite": 120_000,
    "voyage-code-2": 120_000,
    "voyage-3-m-exp": 120_000,
}


class VoyageAIEmbedding(EmbeddingBase):
    """
    VoyageAI embedding provider with support for text, multimodal, and contextualized embeddings.

    Supports:
    - Text embeddings with flexible dimensions and quantization
    - Multimodal embeddings (text + images)
    - Contextualized chunk embeddings for document-aware retrieval
    - Asymmetric embeddings via input_type (query vs document)
    - Token-aware batching for efficient batch processing
    """

    # Default batch size (max texts per API call)
    DEFAULT_BATCH_SIZE = 1000

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        try:
            import voyageai
        except ImportError:
            raise ImportError("The 'voyageai' library is required. Please install it using 'pip install voyageai'.")

        # Text embedding defaults - using latest models
        self.config.model = self.config.model or "voyage-3.5"
        self.config.embedding_dims = self.config.embedding_dims or 1024

        # Get API key from config or environment
        api_key = self.config.api_key or os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise ValueError(
                "VoyageAI API key is required. Please provide an API key via config "
                "or set the 'VOYAGE_API_KEY' environment variable."
            )

        self.client = voyageai.Client(api_key=api_key)

        # Map memory_action to VoyageAI input_type
        # "document" for storage/indexing, "query" for retrieval
        self.input_type_mapping = {
            "add": self.config.memory_add_embedding_type or "document",
            "update": self.config.memory_update_embedding_type or "document",
            "search": self.config.memory_search_embedding_type or "query",
        }

    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None) -> list:
        """
        Get the embedding for the given text using VoyageAI.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update".
                Maps to VoyageAI's input_type: "add"/"update" -> "document", "search" -> "query".
                Defaults to None (no input_type specified).

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        input_type = self.input_type_mapping.get(memory_action) if memory_action else None

        # Build kwargs with all supported VoyageAI parameters
        embed_kwargs = {
            "texts": [text],
            "model": self.config.model,
            "truncation": self.config.voyageai_truncation,
        }

        if input_type:
            embed_kwargs["input_type"] = input_type

        if self.config.embedding_dims:
            embed_kwargs["output_dimension"] = self.config.embedding_dims

        if self.config.voyageai_output_dtype:
            embed_kwargs["output_dtype"] = self.config.voyageai_output_dtype

        result = self.client.embed(**embed_kwargs)
        return result.embeddings[0]

    def _build_batches(
        self, texts: List[str]
    ) -> Generator[Tuple[List[str], int], None, None]:
        """
        Generate batches of texts based on token limits.

        Uses VoyageAI's tokenize API to count tokens and respects both
        batch_size (max texts) and model-specific token limits.

        Args:
            texts: List of texts to batch.

        Yields:
            Tuple of (batch of texts, batch size).
        """
        max_tokens_per_batch = VOYAGE_TOTAL_TOKEN_LIMITS.get(self.config.model, 120_000)
        batch_size = self.config.voyageai_batch_size or self.DEFAULT_BATCH_SIZE
        index = 0

        while index < len(texts):
            batch: List[str] = []
            batch_tokens = 0

            while (
                index < len(texts)
                and len(batch) < batch_size
                and batch_tokens < max_tokens_per_batch
            ):
                # Count tokens for this text
                n_tokens = len(
                    self.client.tokenize([texts[index]], model=self.config.model)[0]
                )

                # Check if adding this text would exceed token limit
                if batch_tokens + n_tokens > max_tokens_per_batch and len(batch) > 0:
                    break

                batch_tokens += n_tokens
                batch.append(texts[index])
                index += 1

            yield batch, len(batch)

    def embed_batch(
        self,
        texts: List[str],
        memory_action: Optional[Literal["add", "search", "update"]] = None,
    ) -> List[list]:
        """
        Embed multiple texts with token-aware batching.

        Automatically batches texts to respect VoyageAI's token limits per request.
        This is more efficient than calling embed() for each text individually.

        Args:
            texts: List of texts to embed.
            memory_action: The type of embedding to use. Maps to VoyageAI's input_type.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        # Preprocess texts
        processed_texts = [text.replace("\n", " ") for text in texts]
        input_type = self.input_type_mapping.get(memory_action) if memory_action else None

        embeddings: List[list] = []

        for batch, _ in self._build_batches(processed_texts):
            embed_kwargs = {
                "texts": batch,
                "model": self.config.model,
                "truncation": self.config.voyageai_truncation,
            }

            if input_type:
                embed_kwargs["input_type"] = input_type

            if self.config.embedding_dims:
                embed_kwargs["output_dimension"] = self.config.embedding_dims

            if self.config.voyageai_output_dtype:
                embed_kwargs["output_dtype"] = self.config.voyageai_output_dtype

            result = self.client.embed(**embed_kwargs)
            embeddings.extend(result.embeddings)

        return embeddings

    def embed_multimodal(
        self,
        inputs: List[Union[str, "PIL.Image.Image"]],
        memory_action: Optional[Literal["add", "search", "update"]] = None,
    ) -> list:
        """
        Embed multimodal inputs (text and/or images) using VoyageAI.

        Uses voyage-multimodal-3 or voyage-multimodal-3.5 model for direct image+text embedding.
        Note: Multimodal models currently support fixed 1024 dimensions only.

        Args:
            inputs (list): List of strings or PIL Image objects to embed together.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update".
                Maps to VoyageAI's input_type. Defaults to None.

        Returns:
            list: The embedding vector (1024 dimensions).
        """
        input_type = self.input_type_mapping.get(memory_action) if memory_action else None

        multimodal_model = self.config.voyageai_multimodal_model or "voyage-multimodal-3.5"

        embed_kwargs = {
            "inputs": [inputs],  # VoyageAI expects list of input sequences
            "model": multimodal_model,
            "truncation": self.config.voyageai_truncation,
        }

        if input_type:
            embed_kwargs["input_type"] = input_type

        result = self.client.multimodal_embed(**embed_kwargs)
        return result.embeddings[0]

    def embed_contextualized(
        self,
        chunks: List[List[str]],
        memory_action: Optional[Literal["add", "search", "update"]] = None,
    ) -> List[list]:
        """
        Embed document chunks with context awareness using VoyageAI.

        Uses voyage-context-3 model which encodes each chunk in context with others
        from the same document, resulting in more context-aware embeddings.

        Args:
            chunks (List[List[str]]): List of lists, where each inner list contains
                chunks from a single document, ordered by position.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update".
                Maps to VoyageAI's input_type. Defaults to None.

        Returns:
            List[list]: List of embedding vectors (one per chunk across all documents).
        """
        input_type = self.input_type_mapping.get(memory_action) if memory_action else None

        context_model = self.config.voyageai_context_model or "voyage-context-3"

        embed_kwargs = {
            "inputs": chunks,
            "model": context_model,
        }

        if input_type:
            embed_kwargs["input_type"] = input_type

        if self.config.embedding_dims:
            embed_kwargs["output_dimension"] = self.config.embedding_dims

        if self.config.voyageai_output_dtype:
            embed_kwargs["output_dtype"] = self.config.voyageai_output_dtype

        # Note: contextualized_embed doesn't support truncation parameter
        result = self.client.contextualized_embed(**embed_kwargs)
        # Flatten embeddings from all results (one result per document, multiple embeddings per result)
        return [emb for r in result.results for emb in r.embeddings]
