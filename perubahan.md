# Perubahan di branch `feature/mem0-fix`

Tanggal: 2026-02-05

## Ringkasan singkat
- Menambah **opsi mematikan graph store** tanpa menghapus default bawaan.
- Menambah **opsi history disimpan di Postgres** (tetap mempertahankan SQLite sebagai default).
- **History Postgres otomatis aktif** jika `POSTGRES_*` sudah di‐set (tanpa perlu env history tambahan).
- Menambah **pilihan LLM provider** lewat env (anthropic, groq, together, litellm, gemini, aws_bedrock, deepseek, xai, sarvam, ollama, lmstudio, vllm, azure_openai).
- Perbaikan kecil agar **xAI base URL** bisa diambil dari env tanpa error.
- Menambah **pilihan embedder provider** lewat env (ollama, huggingface, vertexai, gemini, lmstudio, together, langchain, aws_bedrock, azure_openai).

## Daftar commit yang menambah fitur
- `f8d81225` Allow disabling graph store
- `64b2a086` Store history in Postgres
- `2f75a3a1` Restore graph defaults; keep disable option
- `47e778b5` Infer history DB from Postgres env
- `89919bd3` Add LLM provider selection + env
- `89919bd3` Fix xAI base URL access
- `TBD` Add embedder provider selection + env

---

## 1) Graph store bisa `None` (tanpa error)
### File: `mem0/graphs/configs.py`
**Sebelum**
```python
class GraphStoreConfig(BaseModel):
    provider: str = Field(default="neo4j")
    config: Union[Neo4jConfig, MemgraphConfig, NeptuneConfig, KuzuConfig] = Field(
        description="Configuration for the specific data store", default=None
    )

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if provider == "neo4j":
            return Neo4jConfig(**v.model_dump())
        ...
```

**Sesudah**
```python
class GraphStoreConfig(BaseModel):
    provider: str = Field(default="neo4j")
    config: Optional[Union[Neo4jConfig, MemgraphConfig, NeptuneConfig, KuzuConfig]] = Field(
        description="Configuration for the specific data store", default=None
    )

    @field_validator("config")
    def validate_config(cls, v, values):
        if v is None:
            provider = values.data.get("provider")
            if provider == "kuzu":
                return KuzuConfig()
            return None
        provider = values.data.get("provider")
        payload = v.model_dump() if hasattr(v, "model_dump") else v
        if provider == "neo4j":
            return Neo4jConfig(**payload)
        ...
```

**Penjelasan**
- Dulu `graph_store.config` harus selalu berisi `url/username/password`. Sekarang boleh `None`.
- Hasilnya: **graph store bisa dimatikan** tanpa error validasi.

---

## 2) Graph store bisa dimatikan via env (tetap jaga default)
### File: `server/main.py`
**Sebelum** (logikanya selalu pakai default Neo4j)
```python
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "mem0graph")

DEFAULT_CONFIG = {
  ...
  "graph_store": {
      "provider": "neo4j",
      "config": {"url": NEO4J_URI, "username": NEO4J_USERNAME, "password": NEO4J_PASSWORD},
  },
}
```

**Sesudah** (default masih sama, tapi bisa `none`)
```python
GRAPH_STORE_PROVIDER = os.environ.get("GRAPH_STORE_PROVIDER")

DEFAULT_CONFIG = {
  ...
  "graph_store": None,
}

def _build_graph_store_config():
    provider = _normalize_provider(GRAPH_STORE_PROVIDER)
    if provider == "none":
        return {"provider": "neo4j", "config": None}
    if provider is None:
        return {
            "provider": "neo4j",
            "config": {"url": NEO4J_URI, "username": NEO4J_USERNAME, "password": NEO4J_PASSWORD},
        }
    ...

DEFAULT_CONFIG["graph_store"] = _build_graph_store_config()
```

**Penjelasan**
- Default **tetap Neo4j** (bawaan tidak dihapus).
- Jika set `GRAPH_STORE_PROVIDER=none`, graph store **dimatikan**.

---

## 3) History bisa disimpan ke Postgres (opsional)
### File: `mem0/configs/base.py`
**Sebelum**
```python
class MemoryConfig(BaseModel):
    history_db_path: str = Field(default=os.path.join(mem0_dir, "history.db"))
```

**Sesudah**
```python
class MemoryConfig(BaseModel):
    history_db_path: str = Field(default=os.path.join(mem0_dir, "history.db"))
    history_db_provider: str = Field(default="sqlite")
    history_db_url: Optional[str] = Field(default=None)
    history_db_table: str = Field(default="history")
```

**Penjelasan**
- Tambah field konfigurasi **provider history** dan **URL Postgres**.
- Default tetap SQLite.

---

## 4) Implementasi history Postgres + factory
### File: `mem0/memory/storage.py`
**Sebelum**
```python
class SQLiteManager:
    ...
```

**Sesudah**
```python
class SQLiteManager:
    ...

class PostgresHistoryManager:
    ...

def create_history_manager(config):
    provider = getattr(config, "history_db_provider", "sqlite")
    if provider in {"postgres", "postgresql", "pg"}:
        return PostgresHistoryManager(dsn, table)
    return SQLiteManager(...)
```

**Penjelasan**
- SQLite **tetap ada**.
- Tambah Postgres sebagai opsi history.
- `create_history_manager` memilih provider berdasarkan config.

---

## 5) Memory pakai factory untuk history DB
### File: `mem0/memory/main.py`
**Sebelum**
```python
from mem0.memory.storage import SQLiteManager
...
self.db = SQLiteManager(self.config.history_db_path)
```

**Sesudah**
```python
from mem0.memory.storage import create_history_manager
...
self.db = create_history_manager(self.config)
```

**Penjelasan**
- Semua path history sekarang lewat **factory** supaya bisa pilih SQLite/PG.

---

## 6) History otomatis ikut Postgres jika POSTGRES_* di‐set
### File: `server/main.py`
**Sebelum**
```python
HISTORY_DB_PROVIDER = os.environ.get("HISTORY_DB_PROVIDER", "sqlite")
DEFAULT_CONFIG["history_db_provider"] = HISTORY_DB_PROVIDER
```

**Sesudah**
```python
HISTORY_DB_PROVIDER = os.environ.get("HISTORY_DB_PROVIDER")

def _resolve_history_provider():
    provider = _normalize_provider(HISTORY_DB_PROVIDER)
    if provider == "none":
        return "sqlite"
    if provider:
        return provider
    if HISTORY_DB_URL:
        return "postgres"
    if any([POSTGRES_HOST_ENV, POSTGRES_PORT_ENV, POSTGRES_DB_ENV, POSTGRES_USER_ENV, POSTGRES_PASSWORD_ENV]):
        return "postgres"
    return "sqlite"

_HISTORY_PROVIDER = _resolve_history_provider()
DEFAULT_CONFIG["history_db_provider"] = _HISTORY_PROVIDER
DEFAULT_CONFIG["history_db_url"] = _build_history_db_url() if _HISTORY_PROVIDER in {"postgres","postgresql","pg"} else None
```

**Penjelasan**
- Kalau `POSTGRES_*` sudah di‐set, history **otomatis** pakai Postgres (tanpa env history tambahan).
- Kalau tidak, default tetap SQLite.

---

## 7) .env example diperluas (tanpa menghapus bawaan)
### File: `server/.env.example`
**Ditambahkan**
```
# Graph store (optional)
GRAPH_STORE_PROVIDER=
MEMGRAPH_URI=
MEMGRAPH_USERNAME=
MEMGRAPH_PASSWORD=
KUZU_DB_PATH=

# History DB (SQLite by default)
HISTORY_DB_PROVIDER=
HISTORY_DB_PATH=
HISTORY_DB_URL=
HISTORY_DB_TABLE=
```

**Penjelasan**
- Hanya **menambah contoh env**, tidak menghapus yang lama.

---

## 8) Pilihan LLM provider lewat env
### File: `server/main.py`
**Sebelum**
```python
if LLM_AZURE_DEPLOYMENT and LLM_AZURE_ENDPOINT:
    DEFAULT_CONFIG["llm"] = _azure_llm_config()

if VLLM_BASE_URL:
    DEFAULT_CONFIG["llm"] = _vllm_llm_config()
```

**Sesudah**
```python
LLM_PROVIDER = os.environ.get("LLM_PROVIDER")
LLM_MODEL = os.environ.get("LLM_MODEL")
LLM_TEMPERATURE = os.environ.get("LLM_TEMPERATURE")
LLM_MAX_TOKENS = os.environ.get("LLM_MAX_TOKENS")
LLM_TOP_P = os.environ.get("LLM_TOP_P")

def _resolve_llm_provider() -> str:
    provider = _normalize_llm_provider(LLM_PROVIDER)
    if provider and provider != "none":
        return provider
    if LLM_AZURE_DEPLOYMENT and LLM_AZURE_ENDPOINT:
        return "azure_openai"
    if VLLM_BASE_URL:
        return "vllm"
    return "openai"

_LLM_PROVIDER = _resolve_llm_provider()
if _LLM_PROVIDER == "azure_openai":
    DEFAULT_CONFIG["llm"] = _azure_llm_config()
elif _LLM_PROVIDER == "vllm":
    DEFAULT_CONFIG["llm"] = _vllm_llm_config()
else:
    DEFAULT_CONFIG["llm"] = {"provider": _LLM_PROVIDER, "config": _build_llm_config(_LLM_PROVIDER)}
```

**Penjelasan**
- Sekarang bisa set `LLM_PROVIDER` langsung (anthropic, groq, together, litellm, gemini, aws_bedrock, deepseek, xai, sarvam, ollama, lmstudio, vllm, azure_openai).
- Kalau `LLM_PROVIDER` tidak di‐set, fallback tetap: **Azure → vLLM → OpenAI**.

---

## 9) Contoh env LLM diperluas
### File: `server/.env.example`
**Ditambahkan**
```
LLM_PROVIDER=
LLM_MODEL=
LLM_TEMPERATURE=
LLM_MAX_TOKENS=
LLM_TOP_P=

ANTHROPIC_API_KEY=
GROQ_API_KEY=
TOGETHER_API_KEY=
MISTRAL_API_KEY=
GOOGLE_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=
XAI_API_KEY=
XAI_API_BASE=
SARVAM_API_KEY=
SARVAM_API_BASE=
OLLAMA_BASE_URL=
LMSTUDIO_BASE_URL=
LMSTUDIO_RESPONSE_FORMAT=
```

**Penjelasan**
- Mempermudah setup provider LLM tanpa ubah kode.

---

## 10) xAI base URL aman bila tidak diset
### File: `mem0/llms/xai.py`
**Sebelum**
```python
base_url = self.config.xai_base_url or os.getenv("XAI_API_BASE") or "https://api.x.ai/v1"
```

**Sesudah**
```python
base_url = getattr(self.config, "xai_base_url", None) or os.getenv("XAI_API_BASE") or "https://api.x.ai/v1"
```

**Penjelasan**
- Mencegah `AttributeError` saat `xai_base_url` tidak ada di config.

---

## 11) Pilihan embedder provider lewat env
### File: `server/main.py`
**Sebelum**
```python
if EMBEDDING_AZURE_DEPLOYMENT and EMBEDDING_AZURE_ENDPOINT:
    DEFAULT_CONFIG["embedder"] = _azure_embedder_config()
```

**Sesudah**
```python
EMBEDDER_PROVIDER = os.environ.get("EMBEDDER_PROVIDER")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL")
EMBEDDING_DIMS = os.environ.get("EMBEDDING_DIMS")

def _resolve_embedder_provider() -> str:
    provider = _normalize_embedder_provider(EMBEDDER_PROVIDER)
    if provider and provider != "none":
        return provider
    if EMBEDDING_AZURE_DEPLOYMENT and EMBEDDING_AZURE_ENDPOINT:
        return "azure_openai"
    return "openai"

_EMBEDDER_PROVIDER = _resolve_embedder_provider()
if _EMBEDDER_PROVIDER == "azure_openai":
    DEFAULT_CONFIG["embedder"] = _azure_embedder_config()
else:
    DEFAULT_CONFIG["embedder"] = {
        "provider": _EMBEDDER_PROVIDER,
        "config": _build_embedder_config(_EMBEDDER_PROVIDER),
    }
```

**Penjelasan**
- Bisa set `EMBEDDER_PROVIDER` langsung (ollama, huggingface, vertexai, gemini, lmstudio, together, langchain, aws_bedrock, azure_openai).
- Jika tidak diset, fallback tetap: **Azure → OpenAI**.

---

## 12) Contoh env embedder diperluas
### File: `server/.env.example`
**Ditambahkan**
```
EMBEDDER_PROVIDER=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
EMBEDDING_DIMS=
HUGGINGFACE_BASE_URL=
HUGGINGFACE_MODEL_KWARGS=
VERTEX_CREDENTIALS_JSON=
VERTEX_PROJECT_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
GOOGLE_API_KEY=
GEMINI_OUTPUT_DIM=
EMBEDDING_OLLAMA_BASE_URL=
EMBEDDING_LMSTUDIO_BASE_URL=
EMBEDDING_AWS_REGION=
EMBEDDING_AWS_ACCESS_KEY_ID=
EMBEDDING_AWS_SECRET_ACCESS_KEY=
```

**Penjelasan**
- Mempermudah setup embedder tanpa ubah kode.

---

## Cara pakai cepat
- **Matikan graph store**:
```sh
export GRAPH_STORE_PROVIDER=none
```

- **History di Postgres** (otomatis jika `POSTGRES_*` sudah set):
```sh
# cukup set POSTGRES_* untuk pgvector (history akan ikut otomatis)
# atau paksa:
export HISTORY_DB_PROVIDER=postgres
```

- **Kembali ke SQLite**:
```sh
export HISTORY_DB_PROVIDER=sqlite
export HISTORY_DB_PATH=/tmp/mem0_history.db
```
