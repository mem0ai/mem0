# Memória Central Compartilhada Local-First — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Campo `project` no núcleo mem0 (add/search) | completed | medium | — |
| 02 | Tabela e catálogo de projetos (modelo + upsert idempotente) | completed | low | — |
| 03 | Busca por `project` e leitura direta/assíncrona (search/list) | completed | medium | task_01 |
| 04 | Identidade por hostname no slot `user_id` (atribuição) | completed | low | task_03 |
| 05 | Fila de escrita persistente (tabela SQLite + WriteQueue) | completed | medium | — |
| 06 | Worker de background (consome fila → extração + catálogo) | completed | high | task_01, task_02, task_05 |
| 07 | `add_memories` enfileira + ack imediato | completed | medium | task_04, task_05 |
| 08 | Endpoint `GET /discovery` (JSON de config MCP) | completed | low | task_07 |
| 09 | Detecção de modelos na instalação (Ollama `/api/tags`) | completed | medium | task_01 |
| 10 | Empacotamento docker-compose (Qdrant + Ollama + envs) | completed | medium | task_06, task_07, task_08, task_09 |
