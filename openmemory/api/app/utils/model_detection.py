"""Install-time Ollama model detection for OpenMemory setup.

This module powers the setup step that queries a local Ollama instance for the
models that are already installed (via the Ollama client ``list()`` which maps to
``GET /api/tags``) and lists them so the admin can pick which model to use as the
LLM and which to use as the embedder.

Design notes (see ADR-006):
- Detection is *read only*: we only call ``Client.list()``.  We never call
  ``Client.pull()`` - there is no automatic download in the MVP.
- There is no auto-selection: the admin chooses from the detected list.
- If Ollama is unavailable (any error talking to the client) detection raises
  :class:`OllamaUnavailableError` so the caller can fall back to manual model
  name entry instead of crashing.
- The chosen models are turned into a runtime config dict shaped for
  ``mem0.Memory.from_config`` with both ``llm`` and ``embedder`` providers set to
  ``"ollama"``.
"""

import os

try:
    from ollama import Client
except ImportError:  # pragma: no cover - exercised only when ollama is absent
    Client = None


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaUnavailableError(Exception):
    """Raised when the local Ollama instance cannot be reached / queried.

    The setup flow should catch this and fall back to manual model-name entry.
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


def setup_models_interactive(ollama_base_url=None, input_func=input, client=None):
    """Drive the install-time model selection flow.

    Detects models via Ollama and asks the admin to choose an LLM and an
    embedder from the detected list.  If detection fails (Ollama unavailable)
    it falls back to asking the admin to type the model names manually.

    This never triggers a model download (``pull``).

    Args:
        ollama_base_url: Base URL for the Ollama server.
        input_func: Callable used to read the admin's input (injectable for
            testing).  Defaults to the builtin ``input``.
        client: Optional pre-built Ollama client (for testing).

    Returns:
        dict: A runtime config consumable by ``Memory.from_config``.
    """
    try:
        models = detect_ollama_models(ollama_base_url=ollama_base_url, client=client)
    except OllamaUnavailableError as exc:
        print(f"Ollama unavailable ({exc}). Falling back to manual model entry.")
        models = []

    if models:
        print("Detected locally available Ollama models:")
        for index, name in enumerate(models, start=1):
            print(f"  {index}. {name}")
        llm_model = _select_from_list(models, "LLM", input_func)
        embedder_model = _select_from_list(models, "embedder", input_func)
    else:
        # Manual fallback: no auto-selection, admin types the names.
        llm_model = input_func("Enter the LLM model name: ").strip()
        embedder_model = input_func("Enter the embedder model name: ").strip()

    return build_ollama_runtime_config(
        llm_model=llm_model,
        embedder_model=embedder_model,
        ollama_base_url=ollama_base_url,
    )


def _select_from_list(models, role, input_func):
    """Prompt the admin to pick a model by number or name for the given role."""
    choice = input_func(f"Select the {role} model (number or name): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            return models[idx]
    # Accept a directly typed name too (no auto-selection beyond what was typed).
    return choice
