"""Agent-driven provisioning endpoint for the local-only mem0 plugin.

An agent (Claude Code / Cursor / Codex) reads ``GET /provision?host=<host>`` and
executes the returned, self-contained recipe to wire the official mem0 plugin to
THIS local server with zero cloud egress:

  1. write the MCP config block pointing at this server,
  2. set the env (``OPENMEMORY_API_BASE``, ``MEM0_LOCAL_ONLY=1``, ``MEM0_API_KEY``,
     ``MEM0_TELEMETRY=false``),
  3. present the 3 memory modes to the user and persist the choice to
     ``~/.mem0/settings.json``,
  4. verify (``GET /discovery`` + a test search).

The recipe is deterministic — exact file targets and exact JSON to merge — and
idempotent (replace mem0 entries, never append). ``GET /provision/protocol``
returns a plain-text behavioral protocol for clients without lifecycle hooks.
"""

import os

from fastapi import APIRouter, Request

router = APIRouter(prefix="/provision", tags=["provision"])

PROVISION_VERSION = "1"
SUPPORTED_HOSTS = ("claude-code", "cursor", "codex")

# Memory modes — preset over the existing ~/.mem0/settings.json flags.
MODES = [
    {
        "id": "read-write",
        "label": "Sempre ler e gravar",
        "description": "Busca e captura automáticas em todos os eventos.",
        "settings": {"auto_search": True, "auto_save": True},
    },
    {
        "id": "read-only",
        "label": "Sempre ler, gravar só se solicitado",
        "description": "Busca automática; escrita apenas manual (/mem0:remember).",
        "settings": {"auto_search": True, "auto_save": False},
        "default": True,
    },
    {
        "id": "manual",
        "label": "Nunca sem solicitação",
        "description": "Nada automático; tudo via comandos /mem0:* e MCP.",
        "settings": {"auto_search": False, "auto_save": False},
    },
]


def _base_url(request: Request) -> str:
    """Resolve this server's base URL (env override, else the request URL)."""
    override = os.getenv("OPENMEMORY_DISCOVERY_BASE_URL")
    if override:
        return override.rstrip("/")
    return str(request.base_url).rstrip("/")


def _mcp_config(host: str, base_url: str) -> dict:
    """Host-specific MCP config block pointing at this local server.

    ``{hostname}`` is a placeholder the recipe tells the agent to replace with
    the machine hostname (attribution only; reads are project-shared).
    """
    sse_url = f"{base_url}/mcp/{host}/sse/{{hostname}}"
    http_url = f"{base_url}/mcp/{host}/http/{{hostname}}"
    if host == "codex":
        # Codex reads MCP servers from ~/.codex/config.toml (TOML).
        return {
            "format": "toml",
            "target_file": "~/.codex/config.toml",
            "content": (
                "[mcp_servers.mem0]\n"
                f'url = "{http_url}"\n'
            ),
        }
    if host == "cursor":
        return {
            "format": "json",
            "target_file": ".cursor/mcp.json",
            "content": {"mcpServers": {"mem0": {"url": http_url}}},
        }
    # claude-code (and default)
    return {
        "format": "json",
        "target_file": ".mcp.json",
        "content": {"mcpServers": {"mem0": {"type": "http", "url": http_url}}},
        "sse_url": sse_url,
    }


def _recipe(host: str) -> list:
    settings_path = "~/.mem0/settings.json"
    env_target = {
        "claude-code": "~/.claude/settings.json (bloco \"env\")",
        "cursor": "ambiente do shell / config do Cursor",
        "codex": "~/.codex/config.toml ou ambiente do shell",
    }.get(host, "ambiente do host")
    return [
        {
            "step": "mcp",
            "action": f"Escrever/mesclar o bloco mcp_config no arquivo do host. "
                      f"Substituir o token {{hostname}} pelo hostname da máquina. "
                      f"Idempotente: substituir a entrada 'mem0' existente, nunca anexar.",
        },
        {
            "step": "env",
            "action": f"Definir no env do host ({env_target}): "
                      f"OPENMEMORY_API_BASE, MEM0_LOCAL_ONLY=1, MEM0_API_KEY=local, "
                      f"MEM0_TELEMETRY=false (ver campo 'env').",
        },
        {
            "step": "mode",
            "action": f"Apresentar as 3 opções de 'modes' ao usuário e gravar as "
                      f"'settings' do modo escolhido em {settings_path} "
                      f"(merge das chaves auto_search/auto_save). Default: o modo com default=true.",
        },
        {
            "step": "verify",
            "action": "Confirmar GET /discovery e um POST /v3/memories/search/ de teste. "
                      "Confirmar com o usuário ANTES de gravar arquivos (ação que muta o ambiente).",
        },
    ]


def _payload(request: Request, host: str) -> dict:
    base_url = _base_url(request)
    return {
        "version": PROVISION_VERSION,
        "host": host,
        "base_url": base_url,
        "local_only": True,
        "mcp_config": _mcp_config(host, base_url),
        "env": {
            "OPENMEMORY_API_BASE": base_url,
            "MEM0_LOCAL_ONLY": "1",
            "MEM0_API_KEY": "local",
            "MEM0_TELEMETRY": "false",
        },
        "modes": MODES,
        "settings_path": "~/.mem0/settings.json",
        "recipe": _recipe(host),
        "verify": {
            "discovery": f"{base_url}/discovery",
            "test_search": f"{base_url}/v3/memories/search/",
        },
    }


@router.get("")
@router.get("/")
async def get_provision(request: Request, host: str = "claude-code") -> dict:
    """Return the provisioning manifest for the given host."""
    if host not in SUPPORTED_HOSTS:
        host = "claude-code"
    return _payload(request, host)


_PROTOCOL_TEXT = """\
# mem0 — protocolo de memória (modo comportamental, sem hooks)

Você está conectado a um servidor de memória mem0 LOCAL (sem nuvem). Use as
ferramentas MCP do mem0 assim:

- No INÍCIO de uma tarefa não-trivial: chame `search_memories` com o contexto
  atual (escopo por `project`) e use o que voltar.
- Ao concluir algo durável (decisão, preferência, aprendizado): chame
  `add_memory` com 1 frase objetiva.
- Nunca envie dados para fora do servidor local. Todo acesso é via MCP.
"""


@router.get("/protocol")
async def get_protocol() -> dict:
    """Plain-text behavioral protocol for clients without lifecycle hooks."""
    return {"protocol": _PROTOCOL_TEXT}
