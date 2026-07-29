"""Regression coverage for TypeScript OSS embedding-cache prototype keys."""

import os
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

try:
    from mem0 import Memory as PythonMemory
except PackageNotFoundError:
    PythonMemory = None


@pytest.mark.parametrize("memory_text", ("toString", "constructor", "__proto__"))
def test_issue_6323(memory_text):
    """infer=False and metadata-only updates must embed Object.prototype-named text."""
    # Keep this test in the Python suite while exercising the affected TypeScript
    # SDK directly.  Its normal test dependencies are not installed in every
    # Python-only development environment.
    repo_root = Path(__file__).resolve().parents[1]
    typescript_sdk = repo_root / "mem0-ts"
    if PythonMemory is None:
        pytest.skip("the mem0ai package is not installed")
    if shutil.which("node") is None or not (typescript_sdk / "node_modules" / "ts-node").exists():
        pytest.skip("TypeScript SDK test dependencies are not installed")

    assert PythonMemory.__name__ == "Memory"

    script = r'''
const assert = require("node:assert/strict");
const { Memory } = require("./src/oss/src/memory");
const text = process.env.ISSUE_6323_MEMORY_TEXT;

(async () => {
  const memory = new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: { apiKey: "test-key", model: "text-embedding-3-small" },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: `issue-6323-${text}`,
        dimension: 1536,
        dbPath: ":memory:",
      },
    },
    llm: {
      provider: "openai",
      config: { apiKey: "test-key", model: "gpt-5-mini" },
    },
    disableHistory: true,
  });

  await memory._ensureInitialized();
  memory._captureEvent = async () => {};
  memory._displayFirstRunNotice = async () => {};

  let embedCalls = 0;
  memory.embedder = {
    embed: async (value, operation) => {
      assert.equal(value, text);
      assert.ok(["add", "update"].includes(operation));
      embedCalls += 1;
      return new Array(1536).fill(0.1);
    },
  };

  const added = await memory.add(text, { userId: "alice", infer: false });
  assert.equal(added.results[0].memory, text);

  await memory.update(added.results[0].id, {
    metadata: { source: "issue-6323" },
  });
  assert.equal(embedCalls, 2);
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
'''

    environment = os.environ | {
        "ISSUE_6323_MEMORY_TEXT": memory_text,
        "MEM0_TELEMETRY": "false",
        "TS_NODE_PROJECT": str(typescript_sdk / "tsconfig.test.json"),
    }
    result = subprocess.run(
        ["node", "-r", "ts-node/register/transpile-only", "-e", script],
        cwd=typescript_sdk,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
