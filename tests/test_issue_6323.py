import shutil
import sys
import types
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest


def test_issue_6323():
    posthog = types.ModuleType("posthog")
    posthog.Posthog = type(
        "Posthog",
        (),
        {"__init__": lambda self, *args, **kwargs: None, "shutdown": lambda self: None},
    )
    qdrant_client = types.ModuleType("qdrant_client")
    qdrant_client.QdrantClient = type("QdrantClient", (), {})

    with patch.dict(sys.modules, {"posthog": posthog, "qdrant_client": qdrant_client}):
        with patch("importlib.metadata.version", return_value="0.0.0"):
            from mem0 import Memory

    assert Memory is not None

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to reproduce the TypeScript Object.prototype cache collision")

    memory_source = Path("mem0-ts/src/oss/src/memory/index.ts").read_text()
    if (
        "existingEmbeddings[data] || (await this.embedder.embed(data, \"add\"))" not in memory_source
        and "existingEmbeddings[newData] ||" not in memory_source
    ):
        return

    script = textwrap.dedent(
        """
        const keys = ["toString", "constructor", "__proto__"];

        class VectorStore {
          insert(vectors) {
            const vector = vectors[0];
            const length = Array.isArray(vector) ? vector.length : 0;
            if (!Array.isArray(vector) || length !== 1536) {
              throw new Error(`Vector dimension mismatch. Expected 1536, got ${length}`);
            }
          }

          get() {
            return { payload: { data: "__proto__" } };
          }

          update(_memoryId, vector) {
            const length = Array.isArray(vector) ? vector.length : 0;
            if (!Array.isArray(vector) || length !== 1536) {
              throw new Error(`Vector dimension mismatch. Expected 1536, got ${length}`);
            }
          }
        }

        const embedder = {
          calls: [],
          async embed(text, action) {
            this.calls.push([text, action]);
            return new Array(1536).fill(0.1);
          },
        };
        const vectorStore = new VectorStore();

        async function createMemory(data, existingEmbeddings) {
          const embedding = existingEmbeddings[data] || (await embedder.embed(data, "add"));
          vectorStore.insert([embedding]);
        }

        async function updateMemory(data, existingEmbeddings) {
          const existingMemory = vectorStore.get();
          const newData = data ?? existingMemory.payload.data;
          const embedding = existingEmbeddings[newData] || (await embedder.embed(newData, "update"));
          vectorStore.update("memory-id", embedding);
        }

        (async () => {
          for (const key of keys) {
            await createMemory(key, {});
          }
          await updateMemory(undefined, {});
        })().catch((error) => {
          console.error(error.message);
          process.exit(1);
        });
        """
    )

    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
