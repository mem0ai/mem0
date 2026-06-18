---
status: pending
title: MinIO + rotina de backup (snapshot Qdrant + pg_dump → bucket)
type: infra
complexity: high
dependencies:
  - task_01
---

# Tarefa 2: MinIO + rotina de backup (snapshot Qdrant + pg_dump → bucket)

## Visão Geral
Backup que sobrevive à falha do nó é o chão mínimo da rede de segurança. Esta tarefa provisiona o MinIO (object store S3-compatível na LAN) e uma rotina containerizada que gera snapshot nativo das coleções do Qdrant e `pg_dump` do PostgreSQL, enviando ambos a um bucket versionado.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir um serviço MinIO no compose, com destino configurável por env (`S3_ENDPOINT`, `S3_BUCKET`, credenciais).
- A rotina DEVE usar a API de snapshots nativa do Qdrant por coleção e `pg_dump` para o PostgreSQL.
- Os artefatos DEVEM ser enviados ao bucket com a convenção de chave definida no TechSpec (`backups/{data}/...`).
- A rotina DEVE ser acionável sob demanda e agendável (cron/container), com retry/backoff em uploads.
- Falha de uma etapa DEVE ser observável (log + métrica) sem corromper backups anteriores.
</requirements>

## Subtarefas
- [ ] 2.1 Adicionar serviço MinIO ao compose de infra e bucket inicial.
- [ ] 2.2 Implementar a rotina de backup do Qdrant via snapshot nativo.
- [ ] 2.3 Implementar o dump do PostgreSQL (`pg_dump`) e compressão.
- [ ] 2.4 Enviar artefatos ao bucket com a convenção de chave e retry/backoff.
- [ ] 2.5 Expor métricas de backup (timestamp/sucesso/duração) e logs estruturados.
- [ ] 2.6 Configurar retenção/rotação de objetos no bucket.

## Detalhes de Implementação
Ver seções "Pontos de Integração", "Modelos de Dados" (convenção de chave) e ADR-003 do TechSpec. Reusar o padrão de cliente S3 (boto3/mc). As métricas seguem o padrão de `app/utils/metrics.py`.

### Arquivos Relevantes
- `openmemory/compose/` — diretório de serviços compose (adicionar MinIO).
- `openmemory/docker-compose.scale.yml` — orquestração que inclui os serviços.
- `openmemory/scripts/bootstrap-scale.sh` — bootstrap; ponto para inicializar bucket.
- `openmemory/api/app/utils/metrics.py` — registrar métricas de backup.
- `mem0/vector_stores/qdrant.py` — referência do cliente Qdrant (snapshots).

### Arquivos Dependentes
- `openmemory/scripts/backup.*` (novo) — rotina de backup.
- `openmemory/compose/backup.yml` (novo) — serviço/cron de backup.

### ADRs Relacionados
- [ADR-003: Backup/restauração e cold tier sobre MinIO](adrs/adr-003.md) — define mecanismo e storage.

## Entregáveis
- MinIO operacional no compose com bucket de backups.
- Rotina de backup (Qdrant snapshot + pg_dump) enviando ao bucket.
- Métricas `backup_last_success_timestamp`, `backup_duration_seconds`, `backup_age_seconds`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de backup contra MinIO/Qdrant/Postgres efêmeros **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Orquestração chama snapshot do Qdrant para cada coleção (mock do cliente).
  - [ ] `pg_dump` é invocado com parâmetros corretos (mock de subprocess).
  - [ ] Upload usa a convenção de chave esperada; retry dispara em falha transitória.
  - [ ] Falha de upload incrementa métrica de erro e não apaga backup anterior.
- Testes de integração:
  - [ ] Backup end-to-end grava objetos no MinIO efêmero e métricas refletem sucesso.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Objetos de backup presentes no bucket após execução
- Métricas de backup expostas em `/metrics`
