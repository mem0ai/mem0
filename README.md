# mem0-shared — Memória Central Compartilhada (local-first)

Fork do [mem0](https://github.com/mem0ai/mem0) adaptado para servir como **memória
central compartilhada de time**, rodando **100% na rede local**. Uma instalação
única sobe o servidor MCP/API, o vector store e usa um LLM local — nenhum
conteúdo de memória sai da rede.

> Este repositório **não** é o mem0 de origem com seus padrões de nuvem. As
> seções abaixo descrevem o que de fato existe e está ativo aqui. O SDK mem0
> original continua disponível como base (veja [Base: SDK mem0](#base-sdk-mem0)).

## O que isto entrega

- **Memória compartilhada entre máquinas** — as memórias são escopadas por
  `project` (não por máquina). Qualquer agente em qualquer host lê e escreve no
  mesmo acervo; o hostname serve apenas para **atribuição/auditoria**.
- **Local-first e fail-closed** — o servidor **recusa inicializar** se o
  LLM/embedder configurado apontar para um host não-local (OpenAI, Anthropic
  etc.). A garantia é em código, não só em convenção (`MEM0_LOCAL_ONLY=1`).
- **Telemetria desligada** — `MEM0_TELEMETRY=false` e, com `MEM0_LOCAL_ONLY=1`,
  os eventos de uso (PostHog) do core são forçados a off antes do import do mem0.
- **Escrita assíncrona durável** — `add_memories` **enfileira** e devolve ack
  imediato (`{status: queued, job_id}`); um worker em background extrai via LLM e
  persiste. Falhas são re-enfileiradas até o teto de tentativas — nenhum job é
  perdido.
- **Auto-descoberta MCP** — agentes se autoconfiguram via `GET /discovery`
  (transporte, `base_url`, template de rota e campos esperados).
- **Detecção de modelos locais** — o instalador detecta **Ollama** (`/api/tags`)
  e **llama.cpp** (`/v1/models`) e deixa você escolher backend e modelos.

## Arquitetura

```
Agentes (Claude Code, Cursor, …)
        │  MCP  /mcp/{client_name}/sse/{hostname}
        ▼
┌─────────────────────────────┐
│ openmemory-mcp  (API/MCP)   │  :8765   FastAPI + MCP + worker de escrita
│  ├─ fila de escrita (SQLite)│          catálogo de projetos + auditoria
│  └─ guard fail-closed       │          (MEM0_LOCAL_ONLY)
└──────────┬──────────────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
Qdrant          LLM local
(:6333)         Ollama (:11434) ou llama.cpp (OpenAI-compat)
coleção única   extração + embeddings
```

Fluxo ponta a ponta:

1. Um agente conecta na rota MCP `/mcp/{client_name}/sse/{hostname}`.
2. `add_memories(text, project)` **enfileira** e retorna ack imediato — sem bloquear.
3. O **worker** consome a fila, extrai via LLM e persiste no projeto; falhas são
   retentadas até o teto e só então marcadas `failed`.
4. `search_memory(query, project)` recupera a memória **compartilhada** entre
   todas as máquinas (filtra por `project`, ignora hostname).
5. Cada escrita gera um registro de **auditoria** durável (`write_audit_logs`)
   com hostname/projeto/cliente.

## Instalação rápida (1 comando)

Pré-requisitos: **Docker + Docker Compose v2** e um backend de LLM local
acessível na rede (**Ollama** e/ou **llama.cpp**).

Multiplataforma (Linux/macOS/Windows), na raiz do projeto — só precisa de
Python 3.8+ e Docker:

```bash
python install.py
```

Linux (bash), a partir de `openmemory/`:

```bash
cd openmemory
./install-local-first.sh
```

O instalador confere pré-requisitos, prepara os `.env`, detecta os modelos
locais, deixa você escolher backend/modelos, sobe o conjunto e valida a
auto-descoberta. Variações úteis:

```bash
# Ollama em outra máquina da LAN:
python install.py --ollama-url http://192.168.0.10:11434

# Forçar llama.cpp (servidor OpenAI-compatível):
python install.py --backend llamacpp --llamacpp-url http://192.168.0.10:8080

# Token/API key do backend local (opcional — Ollama dispensa):
python install.py --api-key SEU_TOKEN

# Escolher onde as memórias ficam no host (Qdrant + SQLite):
python install.py --data-dir /srv/mem0-data

# Não-interativo (CI / provisionamento):
python install.py --llm llama3.1:latest --embedder nomic-embed-text --yes

# Manter modelos do .env / também subir a UI:
python install.py --skip-models --with-ui
```

No modo interativo o instalador também pergunta o **token do backend local**
(Enter quando não houver) e o **local de salvamento** das memórias (Enter mantém
os volumes Docker gerenciados; ou informe um caminho para relocar Qdrant +
SQLite). Detalhes em
[`openmemory/INSTALL-memoria-compartilhada.md`](openmemory/INSTALL-memoria-compartilhada.md).

Sobem três serviços: `mem0_store` (Qdrant, `:6333`), `openmemory-mcp`
(API/MCP, `:8765`) e `openmemory-ui` (`:3000`).

> ⚠️ O `openmemory/run.sh` é o instalador **do upstream mem0** e **não é
> local-first** (exige `OPENAI_API_KEY`). Para o fluxo deste projeto use
> **`install.py`** / **`install-local-first.sh`**.

Guia completo de instalação, passos manuais e variáveis de ambiente:
[`openmemory/INSTALL-memoria-compartilhada.md`](openmemory/INSTALL-memoria-compartilhada.md).

## Validação (smoke test)

Sobe o conjunto, espera a API/MCP, valida o `/discovery` e confere o Qdrant —
tudo local:

```bash
cd openmemory
./scripts/smoke-memoria-compartilhada.sh            # sobe, valida e derruba
KEEP_UP=1 ./scripts/smoke-memoria-compartilhada.sh  # mantém no ar após validar
```

## Conectar agentes via auto-descoberta

Com o servidor no ar (`:8765`), qualquer agente se autoconfigura consultando o
**endpoint de descoberta** — sem precisar conhecer URLs com antecedência.

### 1. Consultar o endpoint de descoberta

```bash
curl http://SEU-SERVIDOR:8765/discovery
```

Resposta (o `base_url` reflete o endereço pelo qual o agente chegou ao servidor):

```json
{
  "transport": "sse",
  "base_url": "http://SEU-SERVIDOR:8765",
  "route_template": "/mcp/{client_name}/sse/{user_id}",
  "transports": {
    "sse": "/mcp/{client_name}/sse/{user_id}",
    "http": "/mcp/{client_name}/http/{user_id}"
  },
  "fields": {
    "client_name": "nome do agente/cliente MCP",
    "user_id": "hostname da máquina",
    "project": "obrigatório"
  }
}
```

O mesmo payload está disponível no caminho convencional `GET /.well-known/mcp`.

### 2. Montar a URL MCP

Substitua `{client_name}` pelo nome do agente (ex.: `claude-code`) e `{user_id}`
pelo **hostname da máquina** onde o agente roda. O hostname é atribuição/auditoria
— não restringe o acesso.

| Transporte | URL |
|------------|-----|
| SSE (padrão, amplo suporte) | `http://SERVIDOR:8765/mcp/claude-code/sse/HOSTNAME` |
| Streamable HTTP (MCP spec 2025-03-26+) | `http://SERVIDOR:8765/mcp/claude-code/http/HOSTNAME` |

### 3. Configurar o agente

**Claude Code** — adicione em `~/.claude/claude_desktop_config.json` ou nas
configurações de MCP do projeto:

```json
{
  "mcpServers": {
    "openmemory": {
      "type": "sse",
      "url": "http://SEU-SERVIDOR:8765/mcp/claude-code/sse/HOSTNAME"
    }
  }
}
```

**Cursor / outros clientes MCP com SSE:**

```json
{
  "mcpServers": {
    "openmemory": {
      "url": "http://SEU-SERVIDOR:8765/mcp/AGENTE/sse/HOSTNAME"
    }
  }
}
```

**Streamable HTTP** (para clientes que suportam o transporte mais recente):

```json
{
  "mcpServers": {
    "openmemory": {
      "type": "http",
      "url": "http://SEU-SERVIDOR:8765/mcp/AGENTE/http/HOSTNAME"
    }
  }
}
```

> **Claude Code com o plugin instalado** (`integrations/mem0-plugin`) conecta
> automaticamente via hooks de sessão — não é necessário configurar o MCP
> manualmente. O plugin resolve o endereço via `OPENMEMORY_API_BASE`.

### 4. Ferramentas MCP disponíveis

| Ferramenta | Descrição |
|------------|-----------|
| `add_memories(text, project)` | Enfileira escrita assíncrona. Retorna `{"status":"queued","job_id":"..."}` imediatamente — não bloqueia. |
| `get_job_status(job_id)` | Consulta status de um job (`queued / processing / done / failed`) e o erro, se houver. |
| `search_memory(query, project)` | Busca semântica por similaridade. Retorna memórias de **todos os agentes** que escreveram no `project`. |
| `list_memories(project)` | Lista todas as memórias do projeto. |
| `delete_memories(memory_ids)` | Remove memórias específicas por ID. |
| `delete_all_memories()` | Remove todas as memórias acessíveis ao agente atual. |

> `project` é **obrigatório** em todas as ferramentas de leitura e escrita. Define
> o espaço compartilhado: memórias gravadas por qualquer agente em `project="X"` são
> visíveis a todos que buscam em `project="X"`, independente de hostname.

---

## Configuração essencial (`openmemory/api/.env`)

| Variável | Função |
|----------|--------|
| `MEM0_LOCAL_ONLY=1` | Guard fail-closed: recusa subir se LLM/embedder não for local. |
| `MEM0_TELEMETRY=false` | Desliga telemetria do core (forçado quando local-only). |
| `LLM_PROVIDER` / `LLM_MODEL` | Provedor/modelo do LLM (Ollama por padrão). |
| `EMBEDDER_PROVIDER` / `EMBEDDER_MODEL` | Provedor/modelo de embeddings. |
| `OLLAMA_BASE_URL` | Endpoint do Ollama na rede local. |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant (no compose, aponta para `mem0_store`). |
| `DATABASE_URL` | SQLite (catálogo + fila de escrita + auditoria + histórico). |
| `QDRANT_STORAGE` / `SQLITE_STORAGE` | Origem dos volumes de dados (definidos pelo instalador via `--data-dir`). Padrão: volumes Docker gerenciados. |
| `OPENMEMORY_DISCOVERY_BASE_URL` | (Opcional) URL base anunciada em `/discovery`. |

Backends locais suportados: **Ollama** (provider `ollama`) e **llama.cpp** (via
provider `openai` apontando para o servidor OpenAI-compatível). Veja
`openmemory/api/.env.example` para exemplos.

## Modo de memória dos agentes

A automação dos hooks de memória do plugin tem 3 modos, gravados em
`~/.mem0/settings.json` (o MCP e os comandos manuais funcionam nos três):

| Modo | Efeito |
|------|--------|
| **1. Ler + gravar** | Busca memórias e captura aprendizados automaticamente. |
| **2. Ler; gravar manual** | Injeta contexto automático; só grava quando solicitado (default recomendado). |
| **3. Manual** | Nada automático; tudo via comandos `/mem0:*` e MCP. |

Detalhes em [`integrations/mem0-plugin/skills/mode/SKILL.md`](integrations/mem0-plugin/skills/mode/SKILL.md).

## Principais mudanças em relação ao upstream

| Área | Mudança |
|------|---------|
| `mem0/memory/main.py` | Campo `project` em `add`/`search` (escopo compartilhado). |
| `openmemory/api/app/workers/` | Worker de background + fila de escrita persistente. |
| `openmemory/api/app/utils/write_queue.py` | `WriteQueue` durável com retentativas. |
| `openmemory/api/app/utils/projects.py` | Catálogo de projetos auto-gerenciado. |
| `openmemory/api/app/utils/identity.py` | Identidade/atribuição por hostname. |
| `openmemory/api/app/utils/model_detection.py` | Detecção de modelos Ollama / llama.cpp. |
| `openmemory/api/app/routers/discovery.py` | `GET /discovery` para auto-config MCP. |
| `openmemory/api/app/routers/compat_v3.py` | Endpoints de compatibilidade v3. |
| `openmemory/api/app/routers/provision.py` | Provisionamento local-first. |
| `install.py` / `openmemory/install-local-first.sh` | Instaladores local-first. |

Cobertura de testes do servidor em `openmemory/api/tests/` (guard local-only,
fila/worker de escrita, descoberta, projetos, detecção de modelos, compat v3) e
escopo de projeto em `tests/memory/test_project_scope.py`.

## Base: SDK mem0

Por baixo, este projeto continua sendo o monorepo mem0 (SDK Python `mem0`, SDK
TypeScript `mem0-ts`, CLIs, servidor e integrações). Para detalhes de
desenvolvimento do SDK, estrutura do monorepo, comandos de build/lint/test e
padrões de código, veja [`AGENTS.md`](AGENTS.md).

- Documentação do mem0 de origem: https://docs.mem0.ai
- Repositório de origem: https://github.com/mem0ai/mem0

## Licença

Apache 2.0 — veja [LICENSE](LICENSE).
</content>
</invoke>
