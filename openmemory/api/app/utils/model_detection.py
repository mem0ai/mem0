"""Install-time local-LLM model detection for OpenMemory setup.

This module powers the setup step that detects which models are already installed
on the local machine and lists them so the admin can pick the LLM and embedder.
Two local backends are supported (ADR-006):

- **Ollama** — via the Ollama client ``list()`` (maps to ``GET /api/tags``).
- **llama.cpp** — via its OpenAI-compatible HTTP server (``GET /v1/models``).
  llama.cpp has no native mem0 provider, so it is wired through the ``openai``
  provider pointing at the local server (same approach as LM Studio).

Design notes (ADR-006):
- Detection is *read only* (Ollama ``list()`` / llama.cpp ``/v1/models``). We
  never trigger a download (no ``pull``) — no automatic download in the MVP.
- There is no auto-selection: the admin chooses from the detected list.
- If a backend is unavailable, detection raises the matching ``*UnavailableError``
  so the caller can probe the other backend or fall back to manual entry.
- The chosen models are turned into a runtime config dict shaped for
  ``mem0.Memory.from_config`` (Ollama → ``ollama`` providers; llama.cpp →
  ``openai`` providers pointing at the local server).
"""

import json
import os
import urllib.request

try:
    from ollama import Client
except ImportError:  # pragma: no cover - exercised only when ollama is absent
    Client = None


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_LLAMACPP_BASE_URL = "http://localhost:8080"


class OllamaUnavailableError(Exception):
    """Raised when the local Ollama instance cannot be reached / queried.

    The setup flow should catch this and fall back to manual model-name entry.
    """


class LlamaCppUnavailableError(Exception):
    """Raised when the local llama.cpp server cannot be reached / queried.

    The setup flow should catch this and probe another backend or fall back to
    manual model-name entry.
    """


def _resolve_ollama_base_url(ollama_base_url=None):
    """Resolve the Ollama base URL from an explicit arg, env, or the default."""
    return (
        ollama_base_url
        or os.environ.get("OLLAMA_BASE_URL")
        or DEFAULT_OLLAMA_BASE_URL
    )


def _extract_model_name(model):
    """Pull a usable model name out of a single ``/api/tags`` entry.

    Ollama responses have used both ``name`` and ``model`` keys across versions,
    and newer client versions may return objects instead of plain dicts.
    """
    if isinstance(model, dict):
        return model.get("name") or model.get("model")
    # Object-style response (e.g. ollama ListResponse.Model)
    return getattr(model, "name", None) or getattr(model, "model", None)


def detect_ollama_models(ollama_base_url=None, client=None):
    """Detect the models installed locally in Ollama.

    Calls the Ollama client ``list()`` (``GET /api/tags``) and parses the
    ``{"models": [{"name": ...}]}`` payload into a list of model names.

    Args:
        ollama_base_url: Base URL of the Ollama server.  Falls back to the
            ``OLLAMA_BASE_URL`` env var and then to ``http://localhost:11434``.
        client: Optional pre-built Ollama client (mainly for testing).

    Returns:
        list[str]: The names of the locally available models (may be empty).

    Raises:
        OllamaUnavailableError: If the ollama library is missing or the server
            cannot be reached / the listing fails.  Callers should fall back to
            manual entry.
    """
    base_url = _resolve_ollama_base_url(ollama_base_url)

    if client is None:
        if Client is None:
            raise OllamaUnavailableError(
                "The 'ollama' library is not installed; cannot detect models. "
                "Install it or enter model names manually."
            )
        try:
            client = Client(host=base_url)
        except Exception as exc:  # noqa: BLE001 - surface as fallback signal
            raise OllamaUnavailableError(
                f"Could not create Ollama client for {base_url}: {exc}"
            ) from exc

    try:
        response = client.list()
    except Exception as exc:  # noqa: BLE001 - any failure -> manual fallback
        raise OllamaUnavailableError(
            f"Could not query Ollama at {base_url}: {exc}"
        ) from exc

    if isinstance(response, dict):
        raw_models = response.get("models") or []
    else:
        raw_models = getattr(response, "models", None) or []

    names = []
    for model in raw_models:
        name = _extract_model_name(model)
        if name:
            names.append(name)
    return names


def build_ollama_runtime_config(
    llm_model,
    embedder_model,
    ollama_base_url=None,
):
    """Build a mem0 runtime config from the admin's chosen Ollama models.

    The returned dict is shaped for ``mem0.Memory.from_config`` with both the
    ``llm`` and ``embedder`` providers set to ``"ollama"`` using the selected
    model names.

    Args:
        llm_model: Model name chosen for the LLM.
        embedder_model: Model name chosen for the embedder.
        ollama_base_url: Base URL for the Ollama server (resolved from env /
            default when not provided).

    Returns:
        dict: Config consumable by ``Memory.from_config``.

    Raises:
        ValueError: If either model name is empty.
    """
    if not llm_model:
        raise ValueError("An LLM model name must be selected.")
    if not embedder_model:
        raise ValueError("An embedder model name must be selected.")

    base_url = _resolve_ollama_base_url(ollama_base_url)

    return {
        "llm": {
            "provider": "ollama",
            "config": {
                "model": llm_model,
                "temperature": 0.1,
                "max_tokens": 2000,
                "ollama_base_url": base_url,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": embedder_model,
                "ollama_base_url": base_url,
            },
        },
    }


# --------------------------------------------------------------------------- #
# llama.cpp backend (OpenAI-compatible HTTP server)
# --------------------------------------------------------------------------- #
def _resolve_llamacpp_base_url(llamacpp_base_url=None):
    """Resolve the llama.cpp base URL from an explicit arg, env, or default."""
    return (
        llamacpp_base_url
        or os.environ.get("LLAMACPP_BASE_URL")
        or DEFAULT_LLAMACPP_BASE_URL
    )


def _openai_v1(base_url):
    """Normalize a llama.cpp base URL to its OpenAI-compatible ``/v1`` endpoint."""
    base = base_url.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def _http_get_json(url, timeout=5):  # pragma: no cover - thin urllib wrapper
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_llamacpp_models(base_url=None, fetch=None):
    """Detect the models served by a local llama.cpp server.

    Queries the OpenAI-compatible ``GET /v1/models`` endpoint and parses the
    ``{"data": [{"id": ...}]}`` payload into a list of model names. llama.cpp
    usually serves a single loaded model, but newer multi-model servers may list
    several.

    Args:
        base_url: Base URL of the llama.cpp server. Falls back to the
            ``LLAMACPP_BASE_URL`` env var and then to ``http://localhost:8080``.
        fetch: Optional ``fetch(url) -> dict`` (injectable for testing).

    Returns:
        list[str]: The names of the served models (may be empty).

    Raises:
        LlamaCppUnavailableError: If the server cannot be reached / parsed.
    """
    base = _resolve_llamacpp_base_url(base_url)
    url = _openai_v1(base) + "/models"
    fetch = fetch or _http_get_json
    try:
        response = fetch(url)
    except Exception as exc:  # noqa: BLE001 - any failure -> fallback signal
        raise LlamaCppUnavailableError(
            f"Could not query llama.cpp at {base}: {exc}"
        ) from exc

    raw_models = []
    if isinstance(response, dict):
        raw_models = response.get("data") or response.get("models") or []

    names = []
    for model in raw_models:
        if isinstance(model, dict):
            name = model.get("id") or model.get("name") or model.get("model")
        else:  # object-style entry
            name = getattr(model, "id", None) or getattr(model, "name", None)
        if name:
            names.append(name)
    return names


def build_llamacpp_runtime_config(llm_model, embedder_model, base_url=None):
    """Build a mem0 runtime config from the chosen llama.cpp models.

    llama.cpp has no native mem0 provider, so it is wired through the ``openai``
    provider pointing at the local server's OpenAI-compatible ``/v1`` endpoint
    (a dummy API key is supplied because the OpenAI client requires one). The
    result is consumable by ``Memory.from_config``.

    Raises:
        ValueError: If either model name is empty.
    """
    if not llm_model:
        raise ValueError("An LLM model name must be selected.")
    if not embedder_model:
        raise ValueError("An embedder model name must be selected.")

    v1 = _openai_v1(_resolve_llamacpp_base_url(base_url))

    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "temperature": 0.1,
                "max_tokens": 2000,
                "openai_base_url": v1,
                "api_key": "llama.cpp",
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embedder_model,
                "openai_base_url": v1,
                "api_key": "llama.cpp",
            },
        },
    }


# --------------------------------------------------------------------------- #
# Unified local detection across backends
# --------------------------------------------------------------------------- #
def detect_local_models(
    ollama_base_url=None,
    llamacpp_base_url=None,
    ollama_client=None,
    llamacpp_fetch=None,
):
    """Probe every local backend and return the models each one exposes.

    Returns a dict mapping the backend name (``"ollama"`` / ``"llamacpp"``) to
    its non-empty list of detected models. Backends that are unavailable or that
    expose no models are simply omitted, so an empty dict means "nothing local
    detected" (fall back to manual entry).
    """
    found = {}
    try:
        models = detect_ollama_models(ollama_base_url=ollama_base_url, client=ollama_client)
        if models:
            found["ollama"] = models
    except OllamaUnavailableError:
        pass
    try:
        models = detect_llamacpp_models(base_url=llamacpp_base_url, fetch=llamacpp_fetch)
        if models:
            found["llamacpp"] = models
    except LlamaCppUnavailableError:
        pass
    return found


def _build_runtime_config(backend, llm_model, embedder_model,
                          ollama_base_url=None, llamacpp_base_url=None):
    """Build the runtime config for the chosen backend."""
    if backend == "llamacpp":
        return build_llamacpp_runtime_config(
            llm_model, embedder_model, base_url=llamacpp_base_url
        )
    return build_ollama_runtime_config(
        llm_model, embedder_model, ollama_base_url=ollama_base_url
    )


def setup_models_interactive(
    ollama_base_url=None,
    input_func=input,
    client=None,
    backend="auto",
    llamacpp_base_url=None,
    llamacpp_fetch=None,
    persist=False,
    persist_func=None,
):
    """Drive the install-time model selection flow across local backends.

    Detects models from the local backend(s) and asks the admin to choose an LLM
    and an embedder from the detected list. If detection fails it falls back to
    asking the admin to type the model names manually. Never triggers a download.

    Args:
        ollama_base_url: Base URL for the Ollama server.
        input_func: Callable used to read the admin's input (injectable for
            testing). Defaults to the builtin ``input``.
        client: Optional pre-built Ollama client (for testing).
        backend: ``"ollama"``, ``"llamacpp"`` or ``"auto"`` (probe both and pick;
            if both have models the admin is asked which one).
        llamacpp_base_url: Base URL for the llama.cpp server.
        llamacpp_fetch: Optional ``fetch(url) -> dict`` for llama.cpp (testing).
        persist: When True, persist the selection into the runtime config (the
            ``configs`` DB row read by ``get_memory_client``) so it actually
            drives the running mem0 client (task_09).
        persist_func: Callable ``(runtime_config) -> None`` used to persist
            (injectable for testing). Defaults to
            ``app.utils.memory.persist_model_selection``.

    Returns:
        dict: A runtime config consumable by ``Memory.from_config``.
    """
    # 1. Detect models from the requested backend(s).
    available = {}
    if backend in ("ollama", "auto"):
        try:
            models = detect_ollama_models(ollama_base_url=ollama_base_url, client=client)
            if models:
                available["ollama"] = models
        except OllamaUnavailableError as exc:
            if backend == "ollama":
                print(f"Ollama unavailable ({exc}). Falling back to manual entry.")
    if backend in ("llamacpp", "auto"):
        try:
            models = detect_llamacpp_models(base_url=llamacpp_base_url, fetch=llamacpp_fetch)
            if models:
                available["llamacpp"] = models
        except LlamaCppUnavailableError as exc:
            if backend == "llamacpp":
                print(f"llama.cpp unavailable ({exc}). Falling back to manual entry.")

    # 2. Pick the backend to configure.
    if backend in ("ollama", "llamacpp"):
        chosen = backend if backend in available else None
    elif len(available) == 1:
        chosen = next(iter(available))
    elif len(available) > 1:
        chosen = _select_backend(list(available), input_func)
    else:
        chosen = None

    # 3. Select the models (from the detected list, or manual fallback).
    if chosen:
        models = available[chosen]
        print(f"Detected locally available {_BACKEND_LABELS[chosen]} models:")
        for index, name in enumerate(models, start=1):
            print(f"  {index}. {name}")
        llm_model = _select_from_list(models, "LLM", input_func)
        embedder_model = _select_from_list(models, "embedder", input_func)
    else:
        # Manual fallback: no auto-selection, admin types the names. The backend
        # defaults to the one explicitly requested, else Ollama.
        chosen = backend if backend in ("ollama", "llamacpp") else "ollama"
        llm_model = input_func("Enter the LLM model name: ").strip()
        embedder_model = input_func("Enter the embedder model name: ").strip()

    runtime_config = _build_runtime_config(
        chosen,
        llm_model=llm_model,
        embedder_model=embedder_model,
        ollama_base_url=ollama_base_url,
        llamacpp_base_url=llamacpp_base_url,
    )

    if persist:
        if persist_func is None:
            # Imported lazily to avoid a circular import (memory.py imports models
            # which imports this module's siblings at app startup).
            from app.utils.memory import persist_model_selection as persist_func
        persist_func(runtime_config)
        print("Model selection persisted to the runtime configuration.")

    return runtime_config


_BACKEND_LABELS = {"ollama": "Ollama", "llamacpp": "llama.cpp"}


def _select_backend(backends, input_func):
    """Prompt the admin to choose between multiple detected backends."""
    print("Multiple local backends detected:")
    for index, name in enumerate(backends, start=1):
        print(f"  {index}. {_BACKEND_LABELS.get(name, name)}")
    choice = input_func("Select the backend (number or name): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(backends):
            return backends[idx]
    if choice in backends:
        return choice
    # Default to the first detected backend on an unrecognized answer.
    return backends[0]


def _select_from_list(models, role, input_func):
    """Prompt the admin to pick a model by number or name for the given role."""
    choice = input_func(f"Select the {role} model (number or name): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            return models[idx]
    # Accept a directly typed name too (no auto-selection beyond what was typed).
    return choice
