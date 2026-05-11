# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-mcp"

WORKDIR /usr/src/openmemory

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m spacy download en_core_web_sm
RUN --mount=type=cache,target=/root/.cache/huggingface \
    python -c "from fastembed import SparseTextEmbedding; next(SparseTextEmbedding(model_name='Qdrant/bm25').embed(['warmup']))"
RUN --mount=type=cache,target=/root/.cache/huggingface \
    python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-reranker-v2-m3')"

COPY config.json .
COPY . .

EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
