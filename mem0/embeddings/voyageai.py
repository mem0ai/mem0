import os
from typing import Iterator, List, Literal, Optional

from voyageai import Client

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

# Total tokens allowed in a single request, per model (from the Voyage AI docs at
# https://docs.voyageai.com/docs/embeddings). Used to build token-aware batches.
VOYAGE_TOTAL_TOKEN_LIMITS = {
    "voyage-4-lite": 1_000_000,
    "voyage-3.5-lite": 1_000_000,
    "voyage-4": 320_000,
    "voyage-3.5": 320_000,
    "voyage-2": 320_000,
    "voyage-4-large": 120_000,
    "voyage-4-nano": 120_000,
    "voyage-code-4": 120_000,
    "voyage-3-large": 120_000,
    "voyage-code-3": 120_000,
    "voyage-large-2-instruct": 120_000,
    "voyage-finance-2": 120_000,
    "voyage-multilingual-2": 120_000,
    "voyage-law-2": 120_000,
    "voyage-context-4": 120_000,
    "voyage-context-3": 120_000,
}
DEFAULT_TOTAL_TOKEN_LIMIT = 120_000

# Voyage accepts at most 1000 inputs in a single request, regardless of model.
MAX_BATCH_SIZE = 1000

# Models that accept a Matryoshka `output_dimension` (256/512/1024/2048). Fixed-dim
# models reject the parameter, so it is only forwarded for these.
FLEXIBLE_DIMENSION_MODELS = {
    "voyage-4-large",
    "voyage-4",
    "voyage-4-lite",
    "voyage-code-4",
    "voyage-4-nano",
    "voyage-3-large",
    "voyage-3.5",
    "voyage-3.5-lite",
    "voyage-code-3",
    "voyage-context-4",
    "voyage-context-3",
}

# Chunk size (in tokens) for the document side of contextualized embeddings. It is
# set to the per-chunk maximum so that every input string resolves to exactly one
# chunk, and therefore exactly one embedding vector. See `_embed_contextualized`.
CONTEXT_CHUNK_SIZE = 32_000


class VoyageEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "voyage-3.5"
        self.config.embedding_dims = self.config.embedding_dims or 1024
        api_key = self.config.api_key or os.getenv("VOYAGE_API_KEY")
        self.client = Client(api_key=api_key)

    @property
    def _is_contextualized(self) -> bool:
        return self.config.model.startswith("voyage-context")

    def _input_type(self, memory_action: Optional[str]) -> str:
        """Map a Mem0 memory action to a Voyage ``input_type``.

        Searches are queries; everything else (add/update) is a document.
        """
        return "query" if memory_action == "search" else "document"

    def _output_dimension(self) -> Optional[int]:
        if self.config.model in FLEXIBLE_DIMENSION_MODELS:
            return self.config.embedding_dims
        return None

    def _num_tokens(self, text: str) -> int:
        """Estimate the token count of ``text`` for the active model."""
        return self.client.count_tokens([text], self.config.model)

    def _iter_batches(self, texts: List[str]) -> Iterator[List[str]]:
        """Yield batches that respect both the per-model token budget and the
        1000-input cap.

        A single text larger than the token budget is emitted on its own rather
        than dropped; Voyage truncates it server-side.
        """
        max_tokens = VOYAGE_TOTAL_TOKEN_LIMITS.get(self.config.model, DEFAULT_TOTAL_TOKEN_LIMIT)
        batch: List[str] = []
        batch_tokens = 0
        for text in texts:
            n_tokens = self._num_tokens(text)
            if batch and (len(batch) >= MAX_BATCH_SIZE or batch_tokens + n_tokens > max_tokens):
                yield batch
                batch, batch_tokens = [], 0
            batch.append(text)
            batch_tokens += n_tokens
        if batch:
            yield batch

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Voyage AI.

        Args:
            text (str): The text to embed.
            memory_action (optional): "add", "search", or "update". Selects the
                Voyage ``input_type`` (search -> query, otherwise document).
        Returns:
            list: The embedding vector.
        """
        # This is the hot path: mem0's memory layer only ever embeds one text at a
        # time. A single input is always one request, so skip token-aware batching
        # entirely — going through `_iter_batches` here would call
        # `client.count_tokens`, which loads a HuggingFace tokenizer on every call.
        input_type = self._input_type(memory_action or "add")
        return self._embed_request([text], input_type)[0]

    def embed_batch(self, texts, memory_action="add"):
        if not texts:
            return []

        input_type = self._input_type(memory_action)
        embeddings: List[List[float]] = []
        for batch in self._iter_batches(texts):
            embeddings.extend(self._embed_request(batch, input_type))

        if len(embeddings) != len(texts):
            raise ValueError(
                f"Voyage embed_batch() returned {len(embeddings)} embeddings for {len(texts)} texts"
                f" using model '{self.config.model}'"
            )
        return embeddings

    def _embed_request(self, batch: List[str], input_type: str) -> List[List[float]]:
        """Embed one already-formed batch in a single request (no token counting).

        Callers are responsible for keeping ``batch`` within Voyage's per-request
        limits; ``embed`` passes a single text and ``embed_batch`` uses
        ``_iter_batches``.
        """
        if self._is_contextualized:
            return self._embed_contextualized(batch, input_type)
        return self._embed_plain(batch, input_type)

    def _embed_plain(self, batch: List[str], input_type: str) -> List[List[float]]:
        output_dimension = self._output_dimension()
        kwargs = {"model": self.config.model, "input_type": input_type}
        if output_dimension is not None:
            kwargs["output_dimension"] = output_dimension
        response = self.client.embed(batch, **kwargs)
        return list(response.embeddings)

    def _embed_contextualized(self, batch: List[str], input_type: str) -> List[List[float]]:
        """Embed each input string as its OWN independent document.

        Every string is passed as a flat ``list[str]`` element with auto-chunking
        enabled and ``chunk_size`` set to the per-chunk maximum, so each input
        resolves to exactly one chunk and therefore exactly one embedding vector.
        Inputs are NOT contextualized against one another: generic ``embed_batch``
        callers pass unrelated texts, so cross-input contextualization would leak
        one text's context into another's vector. The API rejects auto-chunking
        for queries, so the retrieval path drops it.
        """
        output_dimension = self._output_dimension()
        kwargs = {"inputs": batch, "model": self.config.model, "input_type": input_type}
        if output_dimension is not None:
            kwargs["output_dimension"] = output_dimension
        if input_type != "query":
            kwargs["enable_auto_chunking"] = True
            kwargs["chunk_size"] = CONTEXT_CHUNK_SIZE
        response = self.client.contextualized_embed(**kwargs)
        embeddings: List[List[float]] = []
        for result in sorted(response.results, key=lambda r: r.index):
            # Each input is one document of one chunk -> take that single vector.
            embeddings.append(result.embeddings[0])
        return embeddings
