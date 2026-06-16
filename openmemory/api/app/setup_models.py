"""Install-time model-selection entrypoint (task_09 / ADR-006).

Thin CLI around :func:`app.utils.model_detection.setup_models_interactive` so the
Ollama detection + selection flow is actually runnable (it was only a library
function before). Detects the models installed in the local Ollama, lets the
admin pick an LLM and an embedder, and — by default — persists the selection
into the runtime config (the ``configs`` row read by ``get_memory_client``) so
it drives the running mem0 client.

Run inside the API container (or any environment with the app deps):

    python -m app.setup_models                  # interactive, persists to DB
    python -m app.setup_models --ollama-url URL  # explicit Ollama endpoint
    python -m app.setup_models --no-persist      # only print the chosen config
    python -m app.setup_models --llm M --embedder N --yes   # non-interactive

This never downloads a model (no ``pull``); if Ollama is unavailable it falls
back to asking for the model names.
"""

import argparse
import json
import os
import sys


def _build_parser():
    p = argparse.ArgumentParser(
        prog="python -m app.setup_models",
        description="Detect local LLM models (Ollama / llama.cpp) and select the "
                    "LLM and embedder.",
    )
    p.add_argument(
        "--backend",
        choices=("auto", "ollama", "llamacpp"),
        default="auto",
        help="Local backend to use (default: auto — probe both and pick).",
    )
    p.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_BASE_URL"),
        help="Ollama base URL (default: $OLLAMA_BASE_URL or http://localhost:11434).",
    )
    p.add_argument(
        "--llamacpp-url",
        default=os.environ.get("LLAMACPP_BASE_URL"),
        help="llama.cpp server URL (default: $LLAMACPP_BASE_URL or http://localhost:8080).",
    )
    p.add_argument(
        "--llm",
        help="LLM model name (non-interactive; requires --embedder and --yes).",
    )
    p.add_argument(
        "--embedder",
        help="Embedder model name (non-interactive; requires --llm and --yes).",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive: use --llm/--embedder without prompting.",
    )
    p.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not persist the selection; just print the resulting config.",
    )
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    from app.utils import model_detection as md

    if args.yes:
        if not args.llm or not args.embedder:
            print("--yes requires both --llm and --embedder.", file=sys.stderr)
            return 2
        # Non-interactive: build the config directly for the chosen backend
        # (auto defaults to ollama since model names were given explicitly).
        backend = "llamacpp" if args.backend == "llamacpp" else "ollama"
        config = md._build_runtime_config(
            backend,
            llm_model=args.llm,
            embedder_model=args.embedder,
            ollama_base_url=args.ollama_url,
            llamacpp_base_url=args.llamacpp_url,
        )
        if not args.no_persist:
            from app.utils.memory import persist_model_selection
            persist_model_selection(config)
            print("Model selection persisted to the runtime configuration.")
    else:
        config = md.setup_models_interactive(
            backend=args.backend,
            ollama_base_url=args.ollama_url,
            llamacpp_base_url=args.llamacpp_url,
            persist=not args.no_persist,
        )

    print(json.dumps(config, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
