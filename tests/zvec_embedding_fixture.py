import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FIXTURE_EMBEDDINGS_PATH = Path(__file__).resolve().parent / "fixtures" / "zvec_embeddings.json"


def load_fixture_embeddings() -> dict[str, Any]:
    return json.loads(FIXTURE_EMBEDDINGS_PATH.read_text())


class FixtureEmbedding:
    def __init__(self, payload: dict[str, Any]):
        self._vectors: dict[str, list[float]] = payload["texts"]
        self._embedding_dims: int = int(payload["embedding_dims"])
        self.config = SimpleNamespace(embedding_dims=self._embedding_dims)

    def _fallback_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [(digest[idx % len(digest)] / 127.5) - 1.0 for idx in range(self._embedding_dims)]
        norm = math.sqrt(sum(value * value for value in raw))
        if norm == 0:
            return [0.0 for _ in range(self._embedding_dims)]
        return [value / norm for value in raw]

    def embed(self, text: str, memory_action: str = "search") -> list[float]:  # noqa: ARG002
        key = str(text)
        return self._vectors.get(key, self._fallback_vector(key))
