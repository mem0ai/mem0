from typing import Any, Callable, Dict, List, Optional


class EmbedderConfig:
    def __init__(self, embedding_fn: Callable[[list[str]], list[str]] = None):
        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")
        self.embedding_fn = embedding_fn
