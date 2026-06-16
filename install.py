#!/usr/bin/env python3
"""Instalador rápido LOCAL-FIRST da Memória Central Compartilhada (multiplataforma).

Roda em Linux, macOS e Windows (só precisa de Python 3.8+ e Docker). Equivalente
multiplataforma ao ``openmemory/install-local-first.sh``: sobe API/MCP + Qdrant em
container e usa um Ollama LOCAL para LLM/embeddings — operação 100% local, sem
dependência de serviços fora da rede (privacidade).

Faz, ponta a ponta:
  1. Verifica pré-requisitos (Docker + Docker Compose v2).
  2. Garante os arquivos .env (compose + api).
  3. Detecta os modelos do Ollama (GET /api/tags) e deixa você escolher o LLM e o
     embedder — sem download automático (task_09); fallback para entrada manual.
  4. Persiste a seleção no .env do compose (interpolado no docker-compose.yml).
  5. Sobe o conjunto (docker compose up -d) — o schema é criado no startup.
  6. Valida a auto-descoberta (GET /discovery) e imprime os dados de conexão.

Uso:
  python install.py                                   # interativo
  python install.py --ollama-url http://192.168.0.10:11434
  python install.py --llm llama3.1:latest --embedder nomic-embed-text --yes
  python install.py --skip-models                     # mantém modelos do .env atual
  python install.py --with-ui                         # também sobe a UI (porta 3000)
"""

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOSE_DIR = ROOT / "openmemory"


# --------------------------------------------------------------------------- #
# Saída (texto simples para compatibilidade com qualquer terminal)
# --------------------------------------------------------------------------- #
def log(msg):  print("\n==> " + msg)
def ok(msg):   print("  [ok] " + msg)
def warn(msg): print("  [!] " + msg)
def die(msg):  print("  [x] " + msg, file=sys.stderr); sys.exit(1)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def run(args, **kwargs):
    """Run a subprocess, raising a friendly error on non-zero exit."""
    try:
        return subprocess.run(args, **kwargs)
    except FileNotFoundError:
        die(f"Comando não encontrado: {args[0]}")


def have_docker_compose():
    r = run(["docker", "compose", "version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def set_env(file_path, key, value):
    """Idempotently set KEY=VALUE in a .env file (replace or append)."""
    lines = []
    if file_path.exists():
        lines = file_path.read_text(encoding="utf-8").splitlines()
    prefix = key + "="
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.lstrip("# ").rstrip()
        if stripped.startswith(prefix) or line.startswith(prefix):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_ollama_models(ollama_url):
    """Query Ollama GET /api/tags and return the installed model names (or [])."""
    try:
        data = _get_json(ollama_url.rstrip("/") + "/api/tags")
    except Exception:
        return []
    names = []
    for m in data.get("models", []):
        name = m.get("name") or m.get("model")
        if name:
            names.append(name)
    return names


def detect_llamacpp_models(llamacpp_url):
    """Query the llama.cpp OpenAI-compatible GET /v1/models (or [] if down)."""
    base = llamacpp_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    try:
        data = _get_json(base + "/models")
    except Exception:
        return []
    names = []
    for m in (data.get("data") or data.get("models") or []):
        name = m.get("id") or m.get("name") or m.get("model")
        if name:
            names.append(name)
    return names


def select_backend(backends):
    """Prompt to choose between multiple detected backends; return the name."""
    labels = {"ollama": "Ollama", "llamacpp": "llama.cpp"}
    print("  Múltiplos backends locais detectados:")
    for i, name in enumerate(backends, start=1):
        print(f"    {i}. {labels.get(name, name)}")
    choice = input("  Selecione o backend (número ou nome): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(backends):
            return backends[idx]
    if choice in backends:
        return choice
    return backends[0]


def select_model(models, role):
    """Prompt for a model by number or name; return the chosen name."""
    choice = input(f"  Selecione o modelo de {role} (número ou nome): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            return models[idx]
    return choice


def wait_for_discovery(api_port, timeout):
    """Poll GET /discovery until it returns the expected JSON, or time out."""
    url = f"http://localhost:{api_port}/discovery"
    deadline = time.time() + timeout
    required = ("transport", "base_url", "route_template", "fields")
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if all(k in body for k in required):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Instalador rápido local-first (multiplataforma).")
    p.add_argument("--backend", choices=("auto", "ollama", "llamacpp"), default="auto",
                   help="Backend local: auto (default, detecta os dois), ollama ou llamacpp.")
    p.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
                   help="Endpoint do Ollama para detecção (default http://localhost:11434).")
    p.add_argument("--llamacpp-url", default=os.environ.get("LLAMACPP_URL", "http://localhost:8080"),
                   help="Endpoint do servidor llama.cpp para detecção (default http://localhost:8080).")
    p.add_argument("--llm", help="Nome do modelo LLM (não-interativo; exige --embedder e --yes).")
    p.add_argument("--embedder", help="Nome do modelo embedder (idem).")
    p.add_argument("--yes", "-y", action="store_true", help="Não-interativo (usa --llm/--embedder).")
    p.add_argument("--skip-models", action="store_true", help="Não mexe nos modelos do .env.")
    p.add_argument("--with-ui", action="store_true", help="Também sobe a UI (porta 3000).")
    p.add_argument("--api-port", default=os.environ.get("API_PORT", "8765"))
    p.add_argument("--timeout", type=int, default=int(os.environ.get("TIMEOUT", "180")))
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    raw_argv = argv if argv is not None else sys.argv
    # URLs foram dadas explicitamente (≠ default)?
    ollama_explicit = ("--ollama-url" in raw_argv) or bool(os.environ.get("OLLAMA_URL"))
    llamacpp_explicit = ("--llamacpp-url" in raw_argv) or bool(os.environ.get("LLAMACPP_URL"))
    # URL que o container usa p/ alcançar o backend no host (localhost não serve
    # de dentro do container): usa a informada ou o host.docker.internal.
    llamacpp_container_url = args.llamacpp_url if llamacpp_explicit else "http://host.docker.internal:8080"

    # 1. Pré-requisitos -------------------------------------------------------
    log("Verificando pré-requisitos")
    if not shutil.which("docker"):
        die("Docker não encontrado. Instale o Docker.")
    if not have_docker_compose():
        die("Docker Compose v2 não encontrado (use 'docker compose').")
    if not COMPOSE_DIR.is_dir() or not (COMPOSE_DIR / "docker-compose.yml").is_file():
        die(f"docker-compose.yml não encontrado em {COMPOSE_DIR}.")
    ok("Docker e Docker Compose v2 disponíveis.")

    # 2. Arquivos .env --------------------------------------------------------
    log("Preparando arquivos de ambiente")
    api_env = COMPOSE_DIR / "api" / ".env"
    api_env_example = COMPOSE_DIR / "api" / ".env.example"
    compose_env = COMPOSE_DIR / ".env"
    if not api_env_example.is_file():
        die("openmemory/api/.env.example não encontrado.")
    if not api_env.exists():
        shutil.copy(api_env_example, api_env)
        ok(f"Criado {api_env.relative_to(ROOT)} a partir do exemplo.")
    else:
        ok(f"{api_env.relative_to(ROOT)} já existe (preservado).")
    compose_env.touch()

    # 3 + 4. Detecção/seleção de modelos (Ollama + llama.cpp) ----------------
    if args.skip_models:
        log("Detecção de modelos pulada (--skip-models): mantendo o .env atual.")
    else:
        log("Detectando modelos locais (Ollama + llama.cpp)")
        available = {}
        if args.backend in ("auto", "ollama"):
            m = detect_ollama_models(args.ollama_url)
            if m:
                available["ollama"] = m
        if args.backend in ("auto", "llamacpp"):
            m = detect_llamacpp_models(args.llamacpp_url)
            if m:
                available["llamacpp"] = m

        labels = {"ollama": "Ollama", "llamacpp": "llama.cpp"}
        llm, embedder, backend = args.llm, args.embedder, None

        if llm and embedder:
            backend = "llamacpp" if args.backend == "llamacpp" else "ollama"
            ok(f"Usando modelos informados por flag (backend {labels[backend]}).")
        elif args.yes:
            die("--yes exige --llm e --embedder.")
        elif available:
            backend = next(iter(available)) if len(available) == 1 \
                else select_backend(list(available))
            models = available[backend]
            ok(f"Backend {labels[backend]} — modelos detectados:")
            for i, name in enumerate(models, start=1):
                print(f"    {i}. {name}")
            llm = select_model(models, "LLM")
            embedder = select_model(models, "embedder")
        else:
            warn("Nenhum backend local detectou modelos — entrada manual.")
            backend = args.backend if args.backend in ("ollama", "llamacpp") else "ollama"
            llm = input("  Nome do modelo LLM: ").strip()
            embedder = input("  Nome do modelo embedder: ").strip()

        if not llm:
            die("Modelo LLM não definido.")
        if not embedder:
            die("Modelo embedder não definido.")

        log(f"Gravando a seleção em {compose_env.relative_to(ROOT)}")
        set_env(compose_env, "LLM_MODEL", llm)
        set_env(compose_env, "EMBEDDER_MODEL", embedder)
        if backend == "llamacpp":
            # llama.cpp via provider openai apontando para o servidor local.
            v1 = llamacpp_container_url.rstrip("/")
            if not v1.endswith("/v1"):
                v1 += "/v1"
            set_env(compose_env, "LLM_PROVIDER", "openai")
            set_env(compose_env, "EMBEDDER_PROVIDER", "openai")
            set_env(compose_env, "LLM_BASE_URL", v1)
            set_env(compose_env, "EMBEDDER_BASE_URL", v1)
            set_env(compose_env, "LLM_API_KEY", "llama.cpp")
            set_env(compose_env, "EMBEDDER_API_KEY", "llama.cpp")
        else:
            set_env(compose_env, "LLM_PROVIDER", "ollama")
            set_env(compose_env, "EMBEDDER_PROVIDER", "ollama")
            if ollama_explicit:
                set_env(compose_env, "OLLAMA_BASE_URL", args.ollama_url)
        ok(f"Backend={labels[backend]} | LLM={llm} | embedder={embedder}")

    # USER / NEXT_PUBLIC_API_URL: ajudam a UI e silenciam avisos do compose.
    try:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or getpass.getuser()
    except Exception:
        user = "openmemory"
    set_env(compose_env, "USER", user)
    set_env(compose_env, "NEXT_PUBLIC_API_URL", f"http://localhost:{args.api_port}")

    # 5. Subir o conjunto -----------------------------------------------------
    services = ["mem0_store", "openmemory-mcp"]
    if args.with_ui:
        services.append("openmemory-ui")
    log("Subindo containers: " + " ".join(services))
    r = run(["docker", "compose", "up", "-d", "--build", *services], cwd=str(COMPOSE_DIR))
    if r.returncode != 0:
        die("Falha ao subir os containers (docker compose up).")

    # 6. Validar a auto-descoberta -------------------------------------------
    log(f"Aguardando GET /discovery (até {args.timeout}s)")
    if not wait_for_discovery(args.api_port, args.timeout):
        run(["docker", "compose", "logs", "--tail", "40", "openmemory-mcp"],
            cwd=str(COMPOSE_DIR))
        die("/discovery não respondeu a tempo.")
    ok("/discovery respondeu 200 com os campos esperados.")

    # Pronto ------------------------------------------------------------------
    log("Instalação local-first concluída 🎉")
    print(f"""
  API/MCP:    http://localhost:{args.api_port}
  Descoberta: http://localhost:{args.api_port}/discovery
  Qdrant:     http://localhost:6333""")
    if args.with_ui:
        print("  UI:         http://localhost:3000")
    print("""
  Rota MCP (preencha hostname e project):
    /mcp/{client_name}/sse/{hostname}      (SSE)
    /mcp/{client_name}/http/{hostname}     (Streamable HTTP)

  Os agentes na rede local podem se autoconfigurar via GET /discovery.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
