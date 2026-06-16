"""
Memory client utilities for OpenMemory.

This module provides functionality to initialize and manage the Mem0 memory client
with automatic configuration management and Docker environment support.

Docker Ollama Configuration:
When running inside a Docker container and using Ollama as the LLM or embedder provider,
the system automatically detects the Docker environment and adjusts localhost URLs
to properly reach the host machine where Ollama is running.

Supported Docker host resolution (in order of preference):
1. OLLAMA_HOST environment variable (if set)
2. host.docker.internal (Docker Desktop for Mac/Windows)
3. Docker bridge gateway IP (typically 172.17.0.1 on Linux)
4. Fallback to 172.17.0.1

Example configuration that will be automatically adjusted:
{
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "llama3.1:latest",
            "ollama_base_url": "http://localhost:11434"  # Auto-adjusted in Docker
        }
    }
}
"""

import hashlib
import ipaddress
import json
import os
import socket
from urllib.parse import urlsplit

from app.database import SessionLocal
from app.models import Config as ConfigModel
from app.utils.env import is_local_only

from mem0 import Memory

_memory_client = None
_config_hash = None
_client_is_local_only = None  # is_local_only() state when _memory_client was last built


def _get_config_hash(config_dict):
    """Generate a hash of the config to detect changes."""
    config_str = json.dumps(config_dict, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()


def _get_docker_host_url():
    """
    Determine the appropriate host URL to reach host machine from inside Docker container.
    Returns the best available option for reaching the host from inside a container.
    """
    # Check for custom environment variable first
    custom_host = os.environ.get('OLLAMA_HOST')
    if custom_host:
        print(f"Using custom Ollama host from OLLAMA_HOST: {custom_host}")
        return custom_host.replace('http://', '').replace('https://', '').split(':')[0]
    
    # Check if we're running inside Docker
    if not os.path.exists('/.dockerenv'):
        # Not in Docker, return localhost as-is
        return "localhost"
    
    print("Detected Docker environment, adjusting host URL for Ollama...")
    
    # Try different host resolution strategies
    host_candidates = []
    
    # 1. host.docker.internal (works on Docker Desktop for Mac/Windows)
    try:
        socket.gethostbyname('host.docker.internal')
        host_candidates.append('host.docker.internal')
        print("Found host.docker.internal")
    except socket.gaierror:
        pass
    
    # 2. Docker bridge gateway (typically 172.17.0.1 on Linux)
    try:
        with open('/proc/net/route', 'r') as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == '00000000':  # Default route
                    gateway_hex = fields[2]
                    gateway_ip = socket.inet_ntoa(bytes.fromhex(gateway_hex)[::-1])
                    host_candidates.append(gateway_ip)
                    print(f"Found Docker gateway: {gateway_ip}")
                    break
    except (FileNotFoundError, IndexError, ValueError):
        pass
    
    # 3. Fallback to common Docker bridge IP
    if not host_candidates:
        host_candidates.append('172.17.0.1')
        print("Using fallback Docker bridge IP: 172.17.0.1")
    
    # Return the first available candidate
    return host_candidates[0]


def _fix_ollama_urls(config_section):
    """
    Fix Ollama URLs for Docker environment.
    Replaces localhost URLs with appropriate Docker host URLs.
    Sets default ollama_base_url if not provided.
    """
    if not config_section or "config" not in config_section:
        return config_section
    
    ollama_config = config_section["config"]
    
    # Set default ollama_base_url if not provided
    if "ollama_base_url" not in ollama_config:
        ollama_config["ollama_base_url"] = "http://host.docker.internal:11434"
    else:
        # Check for ollama_base_url and fix if it's localhost
        url = ollama_config["ollama_base_url"]
        if "localhost" in url or "127.0.0.1" in url:
            docker_host = _get_docker_host_url()
            if docker_host != "localhost":
                new_url = url.replace("localhost", docker_host).replace("127.0.0.1", docker_host)
                ollama_config["ollama_base_url"] = new_url
                print(f"Adjusted Ollama URL from {url} to {new_url}")
    
    return config_section


def reset_memory_client():
    """Reset the global memory client to force reinitialization with new config."""
    global _memory_client, _config_hash
    _memory_client = None
    _config_hash = None


# --- Server-side fail-closed egress guard (MEM0_LOCAL_ONLY) ------------------
#
# This mirrors, on the server, the fail-closed guarantee that
# integrations/mem0-plugin/scripts/_endpoints.py provides for the plugin's HTTP
# calls. The plugin guard only governs plugin -> server traffic; it does NOT
# cover the pipeline where memory content is actually embedded and sent to the
# LLM/embedder. When MEM0_LOCAL_ONLY is active we refuse to initialize a memory
# client whose LLM or embedder would reach a non-local (cloud) host, so memory
# content can never leave the local network — even if the DB config or env was
# (mis)configured for OpenAI/Anthropic/etc.


def _host_of(url):
    """Extract the lowercase hostname from a URL (empty string on failure)."""
    if not url:
        return ""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_private_host(host: str) -> bool:
    """Whether ``host`` is a local/private destination (no public egress).

    Accepts loopback, ``host.docker.internal``, ``*.local``/``*.internal``,
    bare single-label hostnames (Docker service names like ``mem0_store``) and
    RFC1918 / loopback / link-local IPs. Everything else is treated as public.
    """
    if not host:
        return False
    host = host.lower()
    if host in ("localhost", "host.docker.internal"):
        return True
    if host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        pass
    # Bare single-label hostname (no dots) -> Docker/compose service name.
    # Explicitly block known cloud provider names that happen to have no dots
    # (e.g. a typo like "openai" would otherwise pass as a "service name").
    _CLOUD_BARE_NAMES = frozenset({
        "openai", "anthropic", "gemini", "groq", "together", "azure",
        "cohere", "mistral", "replicate", "huggingface",
    })
    if "." not in host:
        return host not in _CLOUD_BARE_NAMES
    return False


def _provider_block_is_local(block) -> bool:
    """Whether an ``llm``/``embedder`` config block points at a local backend.

    - ``ollama``: local unless its base URL resolves to a public host.
    - ``openai``: local ONLY if ``openai_base_url`` points at a private host
      (e.g. a local llama.cpp/LM Studio server). With no base URL it hits
      ``api.openai.com`` -> treated as non-local.
    - any other provider (anthropic, groq, gemini, azure, together, ...) is a
      cloud provider with a fixed external endpoint -> non-local.
    """
    if not isinstance(block, dict):
        return False
    provider = (block.get("provider") or "").lower()
    cfg = block.get("config") or {}
    if provider == "ollama":
        url = cfg.get("ollama_base_url")
        return _is_private_host(_host_of(url)) if url else True
    if provider == "openai":
        base = cfg.get("openai_base_url")
        return _is_private_host(_host_of(base)) if base else False
    return False


def _local_only_violations(config) -> list:
    """List the non-local provider sections in ``config`` (empty == all local)."""
    violations = []
    for section in ("llm", "embedder"):
        block = config.get(section)
        if not _provider_block_is_local(block):
            provider = (block or {}).get("provider", "?")
            violations.append(f"{section}={provider}")
    return violations


# --- Install-time Ollama model detection (see app.utils.model_detection / ADR-006) ---

def detect_ollama_models(ollama_base_url=None, client=None):
    """Detect locally installed Ollama models for the install-time setup step.

    Thin wrapper around :func:`app.utils.model_detection.detect_ollama_models`.
    Returns a list of model names; raises ``OllamaUnavailableError`` when Ollama
    is unavailable so the caller can fall back to manual entry.
    """
    from app.utils.model_detection import detect_ollama_models as _detect

    return _detect(ollama_base_url=ollama_base_url, client=client)


def build_ollama_runtime_config(llm_model, embedder_model, ollama_base_url=None):
    """Build a mem0 runtime config (providers ``ollama``) from chosen models.

    Thin wrapper around
    :func:`app.utils.model_detection.build_ollama_runtime_config`.  The result is
    consumable by ``Memory.from_config``.
    """
    from app.utils.model_detection import build_ollama_runtime_config as _build

    return _build(
        llm_model=llm_model,
        embedder_model=embedder_model,
        ollama_base_url=ollama_base_url,
    )


def detect_llamacpp_models(base_url=None, fetch=None):
    """Detect models served by a local llama.cpp server (``GET /v1/models``).

    Thin wrapper around :func:`app.utils.model_detection.detect_llamacpp_models`.
    Returns a list of model names; raises ``LlamaCppUnavailableError`` when the
    server is unavailable so the caller can fall back to another backend / manual
    entry.
    """
    from app.utils.model_detection import detect_llamacpp_models as _detect

    return _detect(base_url=base_url, fetch=fetch)


def build_llamacpp_runtime_config(llm_model, embedder_model, base_url=None):
    """Build a mem0 runtime config (``openai`` provider) for a llama.cpp server.

    Thin wrapper around
    :func:`app.utils.model_detection.build_llamacpp_runtime_config`.
    """
    from app.utils.model_detection import build_llamacpp_runtime_config as _build

    return _build(llm_model=llm_model, embedder_model=embedder_model, base_url=base_url)


def detect_local_models(ollama_base_url=None, llamacpp_base_url=None):
    """Probe every local backend (Ollama + llama.cpp) and return what each exposes.

    Thin wrapper around :func:`app.utils.model_detection.detect_local_models`.
    """
    from app.utils.model_detection import detect_local_models as _detect

    return _detect(ollama_base_url=ollama_base_url, llamacpp_base_url=llamacpp_base_url)


def persist_model_selection(runtime_config, session_factory=SessionLocal):
    """Persist the install-time model selection into the runtime config (task_09).

    Writes the chosen ``llm``/``embedder`` blocks (as produced by
    :func:`build_ollama_runtime_config`) into the ``main`` row of the ``configs``
    table under the ``mem0`` key — the same place :func:`get_memory_client` reads
    from — so the selection actually drives the runtime client, and resets the
    cached client so the next call picks it up. Idempotent: it merges into any
    existing config rather than clobbering unrelated settings (e.g. vector_store
    or custom_instructions).

    Returns the persisted ``mem0`` config dict.
    """
    if not runtime_config or "llm" not in runtime_config or "embedder" not in runtime_config:
        raise ValueError(
            "runtime_config must contain both 'llm' and 'embedder' blocks "
            "(use build_ollama_runtime_config)."
        )

    db = session_factory()
    try:
        row = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        value = dict(row.value) if row and isinstance(row.value, dict) else {}
        mem0_cfg = dict(value.get("mem0") or {})
        mem0_cfg["llm"] = runtime_config["llm"]
        mem0_cfg["embedder"] = runtime_config["embedder"]
        value["mem0"] = mem0_cfg

        if row is None:
            row = ConfigModel(key="main", value=value)
            db.add(row)
        else:
            row.value = value
        db.commit()
    finally:
        db.close()

    # Force the next get_memory_client() to rebuild with the new selection.
    reset_memory_client()
    return value["mem0"]


# --- LLM provider config factories ---

def _build_ollama_llm_config(model, api_key, base_url, ollama_base_url):
    config = {"model": model or "llama3.1:latest"}
    # OLLAMA_BASE_URL takes precedence, then LLM_BASE_URL, then default
    config["ollama_base_url"] = ollama_base_url or base_url or "http://localhost:11434"
    return config


def _build_openai_llm_config(model, api_key, base_url, ollama_base_url):
    config = {
        "model": model or "gpt-4o-mini",
        "api_key": api_key or "env:OPENAI_API_KEY",
    }
    if base_url:
        config["openai_base_url"] = base_url
    return config


_LLM_CONFIG_FACTORIES = {
    "ollama": _build_ollama_llm_config,
    "openai": _build_openai_llm_config,
}


def _create_llm_config(provider, model, api_key, base_url, ollama_base_url):
    """Build LLM config using registered provider factory or generic fallback."""
    base_config = {
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    factory = _LLM_CONFIG_FACTORIES.get(provider)
    if factory:
        base_config.update(factory(model, api_key, base_url, ollama_base_url))
    else:
        # Generic provider (anthropic, groq, together, deepseek, etc.)
        if not model:
            raise ValueError(
                f"LLM_MODEL environment variable is required when using LLM_PROVIDER='{provider}'. "
                f"Set LLM_MODEL to a valid model name for the '{provider}' provider."
            )
        base_config["model"] = model
        if api_key:
            base_config["api_key"] = api_key

    return base_config


# --- Embedder provider config factories ---

def _build_ollama_embedder_config(model, api_key, base_url, ollama_base_url, llm_base_url):
    config = {"model": model or "nomic-embed-text"}
    config["ollama_base_url"] = base_url or ollama_base_url or llm_base_url or "http://localhost:11434"
    return config


def _build_openai_embedder_config(model, api_key, base_url, ollama_base_url, llm_base_url):
    config = {
        "model": model or "text-embedding-3-small",
        "api_key": api_key or "env:OPENAI_API_KEY",
    }
    if base_url:
        config["openai_base_url"] = base_url
    return config


_EMBEDDER_CONFIG_FACTORIES = {
    "ollama": _build_ollama_embedder_config,
    "openai": _build_openai_embedder_config,
}


def _create_embedder_config(provider, model, api_key, base_url, ollama_base_url, llm_base_url):
    """Build embedder config using registered provider factory or generic fallback."""
    factory = _EMBEDDER_CONFIG_FACTORIES.get(provider)
    if factory:
        config = factory(model, api_key, base_url, ollama_base_url, llm_base_url)
    else:
        if not model:
            raise ValueError(
                f"EMBEDDER_MODEL environment variable is required when using EMBEDDER_PROVIDER='{provider}'. "
                f"Set EMBEDDER_MODEL to a valid model name for the '{provider}' provider."
            )
        config = {"model": model}
        if api_key:
            config["api_key"] = api_key

    return config


def get_default_memory_config():
    """Get default memory client configuration with sensible defaults."""
    # Detect vector store based on environment variables
    vector_store_config = {
        "collection_name": "openmemory",
        "host": "mem0_store",
    }
    
    # Check for different vector store configurations based on environment variables
    if os.environ.get('CHROMA_HOST') and os.environ.get('CHROMA_PORT'):
        vector_store_provider = "chroma"
        vector_store_config.update({
            "host": os.environ.get('CHROMA_HOST'),
            "port": int(os.environ.get('CHROMA_PORT'))
        })
    elif os.environ.get('QDRANT_HOST') and os.environ.get('QDRANT_PORT'):
        vector_store_provider = "qdrant"
        vector_store_config.update({
            "host": os.environ.get('QDRANT_HOST'),
            "port": int(os.environ.get('QDRANT_PORT')),
            "embedding_model_dims": 768,
        })
    elif os.environ.get('WEAVIATE_CLUSTER_URL') or (os.environ.get('WEAVIATE_HOST') and os.environ.get('WEAVIATE_PORT')):
        vector_store_provider = "weaviate"
        # Prefer an explicit cluster URL if provided; otherwise build from host/port
        cluster_url = os.environ.get('WEAVIATE_CLUSTER_URL')
        if not cluster_url:
            weaviate_host = os.environ.get('WEAVIATE_HOST')
            weaviate_port = int(os.environ.get('WEAVIATE_PORT'))
            cluster_url = f"http://{weaviate_host}:{weaviate_port}"
        vector_store_config = {
            "collection_name": "openmemory",
            "cluster_url": cluster_url
        }
    elif os.environ.get('REDIS_URL'):
        vector_store_provider = "redis"
        vector_store_config = {
            "collection_name": "openmemory",
            "redis_url": os.environ.get('REDIS_URL')
        }
    elif os.environ.get('PG_HOST') and os.environ.get('PG_PORT'):
        vector_store_provider = "pgvector"
        vector_store_config.update({
            "host": os.environ.get('PG_HOST'),
            "port": int(os.environ.get('PG_PORT')),
            "dbname": os.environ.get('PG_DB', 'mem0'),
            "user": os.environ.get('PG_USER', 'mem0'),
            "password": os.environ.get('PG_PASSWORD', 'mem0')
        })
    elif os.environ.get('MILVUS_HOST') and os.environ.get('MILVUS_PORT'):
        vector_store_provider = "milvus"
        # Construct the full URL as expected by MilvusDBConfig
        milvus_host = os.environ.get('MILVUS_HOST')
        milvus_port = int(os.environ.get('MILVUS_PORT'))
        milvus_url = f"http://{milvus_host}:{milvus_port}"
        
        vector_store_config = {
            "collection_name": "openmemory",
            "url": milvus_url,
            "token": os.environ.get('MILVUS_TOKEN', ''),  # Always include, empty string for local setup
            "db_name": os.environ.get('MILVUS_DB_NAME', ''),
            "embedding_model_dims": 1536,
            "metric_type": "COSINE"  # Using COSINE for better semantic similarity
        }
    elif os.environ.get('ELASTICSEARCH_HOST') and os.environ.get('ELASTICSEARCH_PORT'):
        vector_store_provider = "elasticsearch"
        # Construct the full URL with scheme since Elasticsearch client expects it
        elasticsearch_host = os.environ.get('ELASTICSEARCH_HOST')
        elasticsearch_port = int(os.environ.get('ELASTICSEARCH_PORT'))
        # Use http:// scheme since we're not using SSL
        full_host = f"http://{elasticsearch_host}"
        
        vector_store_config.update({
            "host": full_host,
            "port": elasticsearch_port,
            "user": os.environ.get('ELASTICSEARCH_USER', 'elastic'),
            "password": os.environ.get('ELASTICSEARCH_PASSWORD', 'changeme'),
            "verify_certs": False,
            "use_ssl": False,
            "embedding_model_dims": 1536
        })
    elif os.environ.get('OPENSEARCH_HOST') and os.environ.get('OPENSEARCH_PORT'):
        vector_store_provider = "opensearch"
        vector_store_config.update({
            "host": os.environ.get('OPENSEARCH_HOST'),
            "port": int(os.environ.get('OPENSEARCH_PORT'))
        })
    elif os.environ.get('FAISS_PATH'):
        vector_store_provider = "faiss"
        vector_store_config = {
            "collection_name": "openmemory",
            "path": os.environ.get('FAISS_PATH'),
            "embedding_model_dims": 1536,
            "distance_strategy": "cosine"
        }
    else:
        # Default fallback to Qdrant
        vector_store_provider = "qdrant"
        vector_store_config.update({
            "port": 6333,
            "embedding_model_dims": 768,
        })
    
    print(f"Auto-detected vector store: {vector_store_provider} with config: {vector_store_config}")

    # Detect LLM provider from environment variables
    llm_provider = os.environ.get('LLM_PROVIDER', 'openai').lower()
    llm_model = os.environ.get('LLM_MODEL')
    llm_api_key = os.environ.get('LLM_API_KEY')
    llm_base_url = os.environ.get('LLM_BASE_URL')
    ollama_base_url = os.environ.get('OLLAMA_BASE_URL')

    llm_config = _create_llm_config(
        provider=llm_provider,
        model=llm_model,
        api_key=llm_api_key,
        base_url=llm_base_url,
        ollama_base_url=ollama_base_url,
    )
    print(f"Auto-detected LLM provider: {llm_provider}")

    # Detect embedder provider from environment variables
    embedder_provider = os.environ.get('EMBEDDER_PROVIDER', llm_provider if llm_provider == 'ollama' else 'openai').lower()
    embedder_model = os.environ.get('EMBEDDER_MODEL')
    embedder_api_key = os.environ.get('EMBEDDER_API_KEY')
    embedder_base_url = os.environ.get('EMBEDDER_BASE_URL')

    embedder_config = _create_embedder_config(
        provider=embedder_provider,
        model=embedder_model,
        api_key=embedder_api_key,
        base_url=embedder_base_url,
        ollama_base_url=ollama_base_url,
        llm_base_url=llm_base_url,
    )
    print(f"Auto-detected embedder provider: {embedder_provider}")

    return {
        "vector_store": {
            "provider": vector_store_provider,
            "config": vector_store_config
        },
        "llm": {
            "provider": llm_provider,
            "config": llm_config
        },
        "embedder": {
            "provider": embedder_provider,
            "config": embedder_config
        },
        "version": "v1.1"
    }


def _parse_environment_variables(config_dict):
    """
    Parse environment variables in config values.
    Converts 'env:VARIABLE_NAME' to actual environment variable values.
    """
    if isinstance(config_dict, dict):
        parsed_config = {}
        for key, value in config_dict.items():
            if isinstance(value, str) and value.startswith("env:"):
                env_var = value.split(":", 1)[1]
                env_value = os.environ.get(env_var)
                if env_value:
                    parsed_config[key] = env_value
                    print(f"Loaded {env_var} from environment for {key}")
                else:
                    print(f"Warning: Environment variable {env_var} not found, keeping original value")
                    parsed_config[key] = value
            elif isinstance(value, dict):
                parsed_config[key] = _parse_environment_variables(value)
            else:
                parsed_config[key] = value
        return parsed_config
    return config_dict


def get_memory_client(custom_instructions: str = None):
    """
    Get or initialize the Mem0 client.

    Args:
        custom_instructions: Optional instructions for the memory project.

    Returns:
        Initialized Mem0 client instance or None if initialization fails.

    Raises:
        Exception: If required API keys are not set or critical configuration is missing.
    """
    global _memory_client, _config_hash, _client_is_local_only

    # Fast path: skip DB I/O when the client is cached and neither a
    # custom_instructions override nor a change to MEM0_LOCAL_ONLY requires a
    # re-evaluation. Comparing the local-only flag state at build time catches
    # the "flag set after startup" eviction case without re-reading the DB.
    if (
        custom_instructions is None
        and _memory_client is not None
        and _client_is_local_only is not None
        and is_local_only() == _client_is_local_only
    ):
        return _memory_client

    try:
        # Start with default configuration
        config = get_default_memory_config()
        
        # Variable to track custom instructions
        db_custom_instructions = None
        
        # Load configuration from database
        try:
            db = SessionLocal()
            db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
            
            if db_config:
                json_config = db_config.value
                
                # Extract custom instructions from openmemory settings
                if "openmemory" in json_config and "custom_instructions" in json_config["openmemory"]:
                    db_custom_instructions = json_config["openmemory"]["custom_instructions"]
                
                # Override defaults with configurations from the database
                if "mem0" in json_config:
                    mem0_config = json_config["mem0"]
                    
                    # Update LLM configuration if available
                    if "llm" in mem0_config and mem0_config["llm"] is not None:
                        config["llm"] = mem0_config["llm"]

                    # Update Embedder configuration if available
                    if "embedder" in mem0_config and mem0_config["embedder"] is not None:
                        config["embedder"] = mem0_config["embedder"]

                    if "vector_store" in mem0_config and mem0_config["vector_store"] is not None:
                        config["vector_store"] = mem0_config["vector_store"]
            else:
                print("No configuration found in database, using defaults")
                    
            db.close()
                            
        except Exception as e:
            print(f"Warning: Error loading configuration from database: {e}")
            print("Using default configuration")
            # Continue with default configuration if database config can't be loaded

        # Use custom_instructions parameter first, then fall back to database value
        instructions_to_use = custom_instructions or db_custom_instructions
        if instructions_to_use:
            config["custom_fact_extraction_prompt"] = instructions_to_use

        # Fix Ollama URLs for Docker environment (applies to both env-var defaults and DB overrides)
        if config.get("llm", {}).get("provider") == "ollama":
            config["llm"] = _fix_ollama_urls(config["llm"])
        if config.get("embedder", {}).get("provider") == "ollama":
            config["embedder"] = _fix_ollama_urls(config["embedder"])

        # ALWAYS parse environment variables in the final config
        # This ensures that even default config values like "env:OPENAI_API_KEY" get parsed
        print("Parsing environment variables in final config...")
        config = _parse_environment_variables(config)

        # Fail-closed: in team local-only mode, refuse to build a client whose
        # LLM/embedder would reach a non-local host. This is the in-code
        # guarantee that memory content never leaves the local network — it does
        # not rely on the DB/env being configured correctly.
        if is_local_only():
            violations = _local_only_violations(config)
            if violations:
                print(
                    "FAIL-CLOSED (MEM0_LOCAL_ONLY): refusing to initialize the memory "
                    f"client — non-local provider(s) detected: {', '.join(violations)}. "
                    "Configure a local backend (Ollama or llama.cpp) via the install "
                    "setup. NO data was sent externally."
                )
                _memory_client = None
                _config_hash = None
                return None

        # Check if config has changed by comparing hashes
        current_config_hash = _get_config_hash(config)
        
        # Only reinitialize if config changed or client doesn't exist
        if _memory_client is None or _config_hash != current_config_hash:
            print(f"Initializing memory client with config hash: {current_config_hash}")
            try:
                _memory_client = Memory.from_config(config_dict=config)
                _config_hash = current_config_hash
                _client_is_local_only = is_local_only()
                print("Memory client initialized successfully")
            except Exception as init_error:
                print(f"Warning: Failed to initialize memory client: {init_error}")
                print("Server will continue running with limited memory functionality")
                _memory_client = None
                _config_hash = None
                return None
        
        return _memory_client
        
    except Exception as e:
        print(f"Warning: Exception occurred while initializing memory client: {e}")
        print("Server will continue running with limited memory functionality")
        return None


def get_memory_client_safe(custom_instructions: str = None):
    """Wrapper around get_memory_client() that returns None instead of raising."""
    try:
        return get_memory_client(custom_instructions)
    except Exception as e:
        import logging
        logging.warning("Failed to get memory client: %s", e)
        return None


def get_default_user_id():
    return "default_user"
