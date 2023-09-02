from typing import Any, Callable, Dict, List, Optional

from embedchain.config.embedder.embedder_config import EmbedderConfig


class Embedder:
    """Class that manages everything regarding embeddings. Including embedding function, loaders and chunkers."""

    def __init__(self, config: Optional[EmbedderConfig]):
        if not config:
            self.config = EmbedderConfig()
        else:
            self.config = config
