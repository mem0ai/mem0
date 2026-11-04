"""Keep the vector store embedding dimension in sync with the configured embedder.

Vector store configurations default their dimension field to ``1536``, which is the
dimension of OpenAI's ``text-embedding-3-small``. Every other embedder produces vectors
of a different size, so the default silently creates a collection/table with the wrong
vector size and the database rejects every write with a dimension mismatch.

The helpers below let the memory layer resolve the dimension from the embedder that was
actually configured, and fail fast with an actionable message when the user configured
two conflicting values.
"""

from typing import Any, Optional

# The dimension field of a vector store configuration. Most stores call it
# ``embedding_model_dims``; Databricks calls it ``embedding_dimension``.
EMBEDDING_DIMS_FIELDS = ("embedding_model_dims", "embedding_dimension")


def _get_embedder_dims(embedder: Any) -> Optional[int]:
    """Return the dimension the embedder reports, or ``None`` when it is unknown."""
    config = getattr(embedder, "config", None)
    dims = getattr(config, "embedding_dims", None)
    if isinstance(dims, bool) or not isinstance(dims, int) or dims <= 0:
        return None
    return dims


def _dims_field(vector_store_config: Any) -> Optional[str]:
    """Return the name of the dimension field of the configuration, or ``None``.

    ``None`` means the store does not use a fixed embedding dimension (e.g. chroma,
    upstash_vector), so there is nothing to keep in sync.
    """
    for field in EMBEDDING_DIMS_FIELDS:
        if isinstance(vector_store_config, dict):
            if field in vector_store_config:
                return field
        elif hasattr(vector_store_config, field):
            return field
    if isinstance(vector_store_config, dict):
        # A raw dict declares no field name, so the common one is used.
        return EMBEDDING_DIMS_FIELDS[0]
    return None


def _is_explicitly_set(vector_store_config: Any, field: str) -> bool:
    """Return whether the user explicitly configured the embedding dimension."""
    if isinstance(vector_store_config, dict):
        return field in vector_store_config
    return field in getattr(vector_store_config, "model_fields_set", set())


def _get_configured_dims(vector_store_config: Any, field: str) -> Optional[int]:
    if isinstance(vector_store_config, dict):
        return vector_store_config.get(field)
    return getattr(vector_store_config, field, None)


def _set_configured_dims(vector_store_config: Any, field: str, dims: int) -> None:
    if isinstance(vector_store_config, dict):
        vector_store_config[field] = dims
        return
    setattr(vector_store_config, field, dims)
    # The value was inferred, not configured by the user. Marking it as "set" would make
    # a later instance treat it as an explicit choice and fail on a mismatch, so it is
    # removed from the set of explicitly provided fields again.
    fields_set = getattr(vector_store_config, "model_fields_set", None)
    if isinstance(fields_set, set):
        fields_set.discard(field)


def resolve_embedding_dims(embedder: Any, vector_store_config: Any, provider: str = "") -> Optional[int]:
    """Align the vector store's embedding dimension with the configured embedder.

    - When the user did not configure the dimension on the vector store, it is inferred
      from the embedder so the collection is created with the right vector size.
    - When both the embedder and the vector store declare a dimension and they
      disagree, a ``ValueError`` is raised instead of letting the database silently
      reject every write.

    Args:
        embedder: The embedder instance created for this memory.
        vector_store_config: The vector store configuration object (or dict).
        provider: Name of the vector store provider, used in error messages.

    Returns:
        The resolved dimension, or ``None`` when it cannot be determined.
    """
    if vector_store_config is None:
        return None

    field = _dims_field(vector_store_config)
    if field is None:
        # This store does not use a fixed embedding dimension (e.g. chroma, upstash).
        return None

    embedder_dims = _get_embedder_dims(embedder)
    if embedder_dims is None:
        # The embedder does not know its dimension, so the configured value is kept.
        return None

    configured_dims = _get_configured_dims(vector_store_config, field)

    if _is_explicitly_set(vector_store_config, field) and configured_dims is not None and configured_dims != embedder_dims:
        raise ValueError(
            f"Embedding dimension mismatch: the configured embedder produces {embedder_dims}-dimension "
            f"vectors, but the '{provider}' vector store is configured with "
            f"{field}={configured_dims}. Set the vector store's "
            f"{field} to {embedder_dims}, or use an embedder that produces "
            f"{configured_dims}-dimension vectors."
        )

    if configured_dims == embedder_dims:
        return embedder_dims

    _set_configured_dims(vector_store_config, field, embedder_dims)
    return embedder_dims
