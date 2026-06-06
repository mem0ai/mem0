#!/bin/sh
set -e

if [ "${EMBEDDER_PROVIDER:-}" = "ollama" ]; then
    echo "Warming up Ollama embedding model: ${EMBEDDING_MODEL:-nomic-embed-text-v2-moe}"
    python3 /usr/src/openmemory/warmup.py
fi

exec uvicorn main:app --host 0.0.0.0 --port 8765 --workers 1
