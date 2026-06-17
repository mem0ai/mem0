# TechSpec — Memória Central Compartilhada Local-First

## Resumo Executivo

A solução evolui o **servidor MCP do OpenMemory** (FastMCP + FastAPI) e o **núcleo `mem0`** (Memory/AsyncMemory) para uma memória central compartilhada 100% local, reusando o stack existente: **Ollama** (LLM + embeddings, definidos na instalação), **Qdrant em container** como vector store e **SQLite/SQLAlchemy** para metadados/fila. O conceito de **projeto** é mapeado como um campo `project` no payload do Qdrant e nos `filters` do mem0 (coleção única), a **identidade** usa o hostname no slot `user_id` apenas para atribuição, e a **busca passa a filtrar por `project`** (ignorando `user_id`) para garantir leitura compartilhada. A escrita torna-se **não bloqueante** via uma **fila interna** com worker de background que executa a extração por LLM, protegendo o LLM local da concorrência de 200+ devs.

O sistema adota **caminhos assimétricos**: a **escrita** passa por fila (não bloqueante, consistência eventual), enquanto a **leitura/consulta é direta e síncrona** contra o Qdrant, **sem passar pela fila**, projetada para **alta concorrência e baixa latência**. Um **endpoint de auto-descoberta** serve um JSON de configuração MCP para os agentes se autoconfigurarem. Na **instalação**, o setup **detecta os modelos locais disponíveis no Ollama** (`/api/tags`) e os lista para o admin escolher LLM e embedder, eliminando a digitação manual de nomes.

**Trade-off técnico principal:** adotamos **consistência eventual** na escrita (a memória fica pesquisável com pequeno atraso após a fila) em troca de latência de escrita não bloqueante e proteção do LLM local — em vez de extração síncrona com consistência imediata.

## Arquitetura do Sistema

### Visão dos Componentes

- **Servidor MCP (FastMCP)** — `openmemory/api/app/mcp_server.py`. Expõe as ferramentas `add_memories`, `search_memory`, `list_memories`, `delete_memories`. Modificado para: extrair `project` do contexto, usar hostname como `user_id` (atribuição), enfileirar escritas e filtrar buscas por `project`.
- **Endpoint de Auto-descoberta (FastAPI)** — nova rota GET no app FastAPI do OpenMemory que retorna o JSON de configuração MCP.
- **Detecção de Modelos na Instalação** — passo de setup que consulta o Ollama (`GET /api/tags`) para listar os modelos locais (LLM/embedder) disponíveis e permitir a seleção pelo admin, com fallback para entrada manual.
- **Fila de Escrita + Worker** — novo componente: persiste requisições de escrita (SQLite) e um worker de background consome a fila, chamando o núcleo `mem0` para extração/persistência.
- **Núcleo de Memória (`mem0`)** — `mem0/memory/main.py` (`Memory`/`AsyncMemory`). Reusado para extração aditiva, embeddings em lote e persistência; recebe `project` via `metadata`/`filters`.
- **Vector Store (Qdrant)** — serviço em container (porta 6333), coleção única; payload carrega `project`, `data`, `hash`, timestamps e hostname.
- **Catálogo de Projetos** — registro interno (tabela SQLite) materializado automaticamente na primeira escrita de cada `project`.
- **Histórico/Auditoria** — `mem0/memory/storage.py` (SQLiteManager) + `MemoryAccessLog` do OpenMemory para registrar operações por hostname/projeto.

**Fluxo de dados (escrita):** Agente → ferramenta MCP `add_memories` → valida + enfileira (SQLite) → **ack imediato** → Worker consome → `mem0.add(project=…, metadata)` → extração por LLM (Ollama) → embeddings (Ollama) → Qdrant + history.

**Fluxo de dados (leitura):** Agente → `search_memory(query)` → `mem0.search(filters={project})` → Qdrant (ANN + dedupe + recência) → resultados compartilhados do projeto.

### Caminho de Leitura (consulta rápida e concorrente)

A consulta (`search_memory`/`list_memories`) **não toca a fila**: chama diretamente `AsyncMemory.search(filters={project})` contra o **Qdrant em container**, que atende múltiplas consultas ANN concorrentes. A leitura é **independente do worker de escrita** — picos de escrita não degradam a consulta. O cliente Qdrant é **singleton/reutilizado** (sem reconexão por chamada) e os handlers são **async** para suportar concorrência alta.

## Design de Implementação

### Interfaces Principais

Interface do enfileirador de escrita (núcleo do comportamento não bloqueante):

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class WriteJob:
    id: str                 # id de rastreio retornado no ack
    project: str            # espaço/projeto alvo (auto-catalogado)
    hostname: str           # identidade (atribuição/auditoria)
    client_name: str        # cliente/agente MCP de origem
    text: str               # conteúdo bruto para extração por LLM
    created_at: str

class WriteQueue(Protocol):
    def enqueue(self, job: WriteJob) -> str:        # persiste e retorna job.id
        ...
    def dequeue(self, limit: int = 1) -> list[WriteJob]:
        ...
    def mark_done(self, job_id: str) -> None: ...
    def mark_failed(self, job_id: str, error: str) -> None: ...
    def depth(self) -> int:                          # profundidade p/ métricas
        ...
```

Assinatura ajustada da ferramenta MCP de escrita (retorno imediato):

```python
@mcp.tool(description="Enfileira conteúdo para extração de memórias no projeto")
async def add_memories(text: str, project: str) -> str:
    hostname = user_id_var.get(None)          # hostname = atribuição
    client = client_name_var.get(None)
    job_id = write_queue.enqueue(WriteJob(..., project=project, hostname=hostname,
                                          client_name=client, text=text))
    return json.dumps({"status": "queued", "job_id": job_id})
```

### Decisões de leitura

- Busca via `AsyncMemory` (assíncrona) para suportar muitas consultas simultâneas sem bloquear o event loop.
- Filtro por `project` reduz o conjunto de candidatos, mantendo a latência baixa na coleção única.
- `top_k` limitado (padrão ~20) e **rerank desativado por padrão** (ativável por chamada) para priorizar latência.
- Cliente Qdrant compartilhado/singleton; conexões reusadas.

### Modelos de Dados

- **WriteJob (fila — tabela SQLite `write_queue`)**: `id` (PK), `project`, `hostname`, `client_name`, `text`, `status` [queued|processing|done|failed], `error`, `created_at`, `updated_at`.
- **ProjectCatalog (tabela SQLite `projects`)**: `name` (PK), `created_at`, `first_seen_hostname`, `memory_count` (opcional).
- **Payload no Qdrant (estendido)**: reusa o atual (`data`, `text_lemmatized`, `hash`, `created_at`, `updated_at`, `user_id`=hostname) **+** `project`.
- **Filtros de busca**: `filters = {"project": <nome>}` (sem `user_id`).

### Endpoints de API

Recurso **Descoberta**:
- `GET /discovery` (ou `/.well-known/mcp`) → 200; retorna JSON: `{ "transport": "sse|http", "base_url": "http://<host>:8765", "route_template": "/mcp/{client_name}/sse/{user_id}", "fields": { "user_id": "hostname", "project": "obrigatório" } }`.

Recurso **Setup/Modelos** (uso na instalação):
- `GET {OLLAMA_BASE_URL}/api/tags` (consulta ao Ollama) → lista de modelos instalados; o setup parseia e apresenta LLM/embedder para seleção. Fallback: entrada manual do nome do modelo se a consulta falhar.

Ferramentas **MCP** (sobre rota existente `/mcp/{client_name}/sse/{user_id}`):
- `add_memories(text, project)` → `{ status: "queued", job_id }`.
- `search_memory(query, project)` → lista de memórias do projeto (filtra por `project`).
- `list_memories(project)` → memórias do projeto.
- `delete_memories(memory_ids)` → confirmação.

## Pontos de Integração

- **Ollama (LLM + embeddings)** — na rede local; endpoint definido na instalação (`OLLAMA_BASE_URL`). Sem default de modelo (admin escolhe). Tratar indisponibilidade do LLM como falha de job (retentativa + log), sem afetar o ack.
- **Qdrant** — serviço em container na rede local (porta 6333); cliente `qdrant-client` já presente.

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|------------|-----------------|-------------------|-----------------|
| `mcp_server.py` (`add_memories`) | modificado | Passa a enfileirar em vez de extrair síncrono; muda contrato de retorno. Risco médio. | Implementar enfileiramento + ack; adicionar `project`. |
| `mcp_server.py` (`search_memory`/`list`) | modificado | Filtra por `project` e ignora `user_id`; leitura direta (fora da fila). Risco médio (muda escopo de leitura). | Ajustar filtros; testes de leitura compartilhada e concorrente. |
| Fila de escrita + worker | novo | Componente assíncrono com persistência. Risco médio (falhas/backpressure). | Criar tabela SQLite, worker, métricas. |
| Catálogo de projetos | novo | Auto-criação na 1ª escrita. Risco baixo. | Criar tabela + upsert no fluxo de escrita. |
| Endpoint `/discovery` | novo | Serve config MCP. Risco baixo. | Adicionar rota GET no FastAPI. |
| Detecção de modelos (setup) | novo | Consulta Ollama `/api/tags` e lista p/ seleção. Risco baixo. | Implementar passo de setup + fallback manual. |
| `mem0/memory/main.py` | modificado | Aceitar/propagar `project` em add/search. Risco baixo (reusa filtros). | Mapear `project` em metadata/filters. |
| `docker-compose.yml` | modificado | Garantir Qdrant container + Ollama acessível na rede. Risco baixo. | Revisar serviços/portas/env. |

## Abordagem de Testes

### Testes Unitários
- **WriteQueue**: enqueue/dequeue/mark_done/mark_failed; persistência sobrevive a reinício; `depth()`.
- **Scoping por projeto**: `add` grava `project` no payload; `search` filtra por `project` e **não** por `user_id`.
- **Catálogo**: upsert idempotente; auto-criação na primeira escrita.
- **Descoberta**: `/discovery` retorna JSON válido conforme host/transportes.
- **Detecção de modelos**: parse da resposta de `/api/tags`; seleção válida; fallback manual quando o Ollama está indisponível.
- Mocks: LLM (Ollama) e embeddings mockados; Qdrant via instância de teste/local.

### Testes de Integração
- **Fluxo escrita→leitura**: enfileira por máquina A, worker processa, máquina B busca e recupera (leitura compartilhada).
- **Concorrência de leitura**: N consultas simultâneas (ex.: 50–100) mantêm p95 < ~200 ms.
- **Isolamento escrita/leitura**: sob pico de escrita (fila cheia), a latência de busca permanece dentro da meta.
- **Concorrência de escrita**: múltiplas escritas simultâneas não saturam o LLM (fila serializa); medir profundidade da fila.
- **Resiliência**: queda do worker com itens na fila → retomada sem perda.
- Ambiente: docker-compose com Qdrant + Ollama local.

## Sequenciamento de Desenvolvimento

### Ordem de Construção
1. **Campo `project` no núcleo** (`mem0.add/search` propagando `project` em metadata/filters) — sem dependências.
2. **Catálogo de projetos** (tabela + upsert) — depende do passo 1.
3. **Ajuste de busca por `project`** no `search_memory`/`list_memories` (ignorar `user_id`; leitura direta/async) — depende dos passos 1–2.
4. **Identidade por hostname** no slot `user_id` da camada MCP — depende do passo 3.
5. **Fila de escrita + worker** (tabela SQLite, enqueue/worker, métricas) — depende do passo 1.
6. **`add_memories` enfileira + ack** — depende dos passos 4 e 5.
7. **Endpoint `/discovery`** (JSON de config MCP) — depende do passo 6 (contrato de rota/campos estável).
8. **Detecção de modelos na instalação** (consulta `/api/tags` do Ollama + seleção + fallback manual) — depende do passo 1 (config de runtime do mem0).
9. **Empacotamento docker-compose** (Qdrant container + Ollama + envs) — depende dos passos 6–8.

### Dependências Técnicas
- Qdrant em container disponível na rede local (porta 6333).
- Ollama acessível na rede com LLM + embedder instalados no setup.
- SQLite (já presente) para fila e catálogo.

## Monitoramento e Observabilidade

- **Métricas**: profundidade da fila, tempo de processamento por job, taxa de falha de extração, latência p95/p99 de busca, consultas concorrentes em andamento, saturação do Qdrant, nº de projetos no catálogo, nº de hostnames ativos.
- **Logs estruturados**: por job (`job_id`, `project`, `hostname`, `status`, `error`), por busca (`project`, `top_k`, latência), via `MemoryAccessLog`.
- **Alertas**: profundidade da fila acima de limite (backpressure); taxa de falha de extração elevada; p95 de busca acima da meta; indisponibilidade do Ollama/Qdrant.

## Considerações Técnicas

### Decisões-Chave
- **Coleção Qdrant única + filtro `project`** — Justificativa: mudança mínima, latência adequada na rede local. Trade-off: coleção grande exige índice/filtro eficientes. Alternativa rejeitada: coleção por projeto (complexidade operacional). *(ADR-003)*
- **Hostname como identidade (atribuição) + busca por `project`** — Justificativa: identidade leve sem login; leitura compartilhada. Trade-off: sem isolamento de acesso. Alternativa rejeitada: parâmetro de identidade separado (altera contrato MCP). *(ADR-003)*
- **Fila interna de escrita assíncrona** — Justificativa: escrita não bloqueante + proteção do LLM. Trade-off: consistência eventual. Alternativas rejeitadas: extração síncrona; `infer=false` literal. *(ADR-004)*
- **Leitura direta, síncrona e concorrente (fora da fila)** — Justificativa: consulta rápida e resiliente a picos de escrita. Trade-off: leitura pode não refletir escritas ainda na fila (consistência eventual já assumida). Reusa Qdrant server + `AsyncMemory`.
- **Auto-descoberta via JSON** — Justificativa: autoconfiguração programática reusando FastAPI. Trade-off: bootstrap do endereço inicial. Alternativas rejeitadas: script de setup; `.well-known` (apenas caminho). *(ADR-005)*
- **Qdrant em container** — Reusa o padrão do `docker-compose.yml`; suporta concorrência de 200+ devs (vs. embarcado on-disk).
- **Detecção de modelos na instalação** — o setup consulta o Ollama (`/api/tags`) e **lista os modelos locais para o admin escolher** LLM/embedder (sem digitação manual). Justificativa: menos atrito/erro reusando o Ollama. Trade-off: depende do Ollama acessível no setup. Alternativas rejeitadas: auto-seleção por heurística; download automático (pull) no MVP. *(ADR-006)*
- **"Manter ambas + recente vence"** — Reusa o modo **aditivo** atual do mem0 (só ADD, dedupe por hash, ranqueamento por relevância/recência); **não** será construída lógica de update-in-place.

### Riscos Conhecidos
- **Consistência eventual** confunde agentes que esperam leitura imediata pós-escrita — mitigar expondo `job_id`/status e documentando o comportamento.
- **Backpressure da fila** sob pico — mitigar com limites de concorrência e métricas de profundidade.
- **Latência sob volume** na coleção única — mitigar com filtro por `project`, `top_k` e validação de carga (protótipo de p95 sob concorrência).
- **Atribuição incorreta de `project`** — mitigar exigindo `project` explícito; revisar estratégia no piloto.
- **Bootstrap da descoberta** — endereço/porta padrão documentados; anúncio na rede como item futuro.

## Registros de Decisão de Arquitetura

- [ADR-001: Evoluir o OpenMemory (MCP-first) para Memória Central Compartilhada Multi-Espaço](adrs/adr-001.md) — Reusar servidor MCP e stack local existentes.
- [ADR-002: Espaços auto-criados e auto-gerenciados por projeto, com acesso aberto na rede local](adrs/adr-002.md) — Espaços = projetos, auto-catalogados, acessíveis a todos.
- [ADR-003: Escopo de projeto via campo `project` em coleção única, com identidade por hostname](adrs/adr-003.md) — Filtro por `project`, hostname para atribuição.
- [ADR-004: Fila interna de escrita com extração por LLM assíncrona](adrs/adr-004.md) — Ack imediato + worker de background.
- [ADR-005: Auto-descoberta de conexão MCP via endpoint JSON](adrs/adr-005.md) — Endpoint GET serve config MCP.
- [ADR-006: Detecção de LLMs/embedders locais na instalação via Ollama](adrs/adr-006.md) — Setup consulta `/api/tags` e lista modelos para o admin escolher.
