import requests
import json
import time
from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "nomic-embed-text"
        self.config.embedding_dims = self.config.embedding_dims or 512
        self.base_url = (self.config.ollama_base_url or "http://localhost:11434").rstrip('/')

    def _normalize_text(self, text):
        """Convert various input formats to string"""
        if isinstance(text, str):
            return text
        elif isinstance(text, list):
            # Handle nested list like [['Daniel', 'works', 'at', 'Li Auto']]
            if len(text) > 0 and isinstance(text[0], list):
                # Flatten nested list
                flat = []
                for item in text:
                    if isinstance(item, list):
                        flat.extend(item)
                    else:
                        flat.append(item)
                return " ".join(str(x) for x in flat)
            else:
                # Simple list ['word1', 'word2']
                return " ".join(str(x) for x in text)
        else:
            return str(text)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """Get embedding with automatic text normalization"""
        max_retries = 3
        retry_delay = 1
        
        # Normalize text to string
        normalized_text = self._normalize_text(text)
        
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.config.model, "input": normalized_text},
                    timeout=30
                )
                resp.raise_for_status()
                data = resp.json()
                
                embeddings = data.get("embeddings", [])
                if embeddings and isinstance(embeddings[0], list):
                    return embeddings[0]
                return embeddings
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
