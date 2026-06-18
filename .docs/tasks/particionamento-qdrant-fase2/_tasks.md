# Particionamento Qdrant (Fase 2) — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Modelo de estado de particionamento (`migration_state` + colunas em `projects`) | completed | medium | — |
| 02 | Extensão do provider Qdrant: índice de inquilino + índices de payload + criação com shard/replicação | completed | high | — |
| 03 | `PartitionResolver` — resolução da coleção ativa e shard_key por projeto | completed | medium | task_01 |
| 04 | Integrar leitura/escrita ao resolver (contrato MCP inalterado) | completed | medium | task_02, task_03 |
| 05 | Dual-write condicional no write-worker | completed | medium | task_04 |
| 06 | Worker de migração: cópia blue→green com checkpoint | completed | high | task_01, task_02 |
| 07 | Validação, flip atômico e rollback (endpoints de migração) | completed | high | task_05, task_06 |
| 08 | Promoção de projeto gigante a shard_key dedicado | completed | high | task_02, task_06, task_07 |
| 09 | Visibilidade operacional: tamanhos por projeto + métricas/alertas | completed | medium | task_01 |
