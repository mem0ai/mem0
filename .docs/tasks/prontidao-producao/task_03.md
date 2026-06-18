---
status: pending
title: Endpoints /admin/backup/* + restauração + drill documentado
type: backend
complexity: medium
dependencies:
  - task_02
---

# Tarefa 3: Endpoints /admin/backup/* + restauração + drill documentado

## Visão Geral
Backup sem restauração testada não é rede de segurança. Esta tarefa expõe endpoints administrativos para disparar backup, restaurar a partir de uma chave e consultar status/RPO, e entrega um drill de restauração documentado que comprova RTO/RPO.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- DEVE existir `POST /admin/backup/run` (dispara backup, retorna identificador/chave).
- DEVE existir `POST /admin/backup/restore` (inicia restauração a partir de uma chave; resposta assíncrona 202).
- DEVE existir `GET /admin/backup/status` (último backup, tamanho, timestamp, RPO corrente).
- A restauração DEVE recuperar snapshot do Qdrant e restaurar o dump do PostgreSQL, com ordem documentada.
- DEVE haver um drill de restauração documentado e, quando viável, automatizável, com RTO/RPO medidos.
</requirements>

## Subtarefas
- [ ] 3.1 Adicionar os endpoints de backup ao router admin existente.
- [ ] 3.2 Implementar a restauração (Qdrant snapshot + dump PostgreSQL) com ordem definida.
- [ ] 3.3 Expor status/RPO a partir das métricas/objetos do bucket.
- [ ] 3.4 Escrever o procedimento de drill (passos, pré-condições, medição de RTO/RPO).
- [ ] 3.5 Automatizar o drill quando viável (script/teste de integração).

## Detalhes de Implementação
Ver seção "Endpoints de API" do TechSpec e ADR-003. Reusar a rotina de backup da task_02. Os endpoints seguem o padrão do `app/routers/admin.py` (respostas 202 para operações longas, como já feito em migração/promoção).

### Arquivos Relevantes
- `openmemory/api/app/routers/admin.py` — adicionar rotas `/admin/backup/*`.
- `openmemory/scripts/backup.*` — rotina criada na task_02 (reuso para restore).
- `openmemory/api/app/utils/metrics.py` — leitura de métricas para status/RPO.

### Arquivos Dependentes
- `openmemory/docs/` — documento de drill de restauração.
- `openmemory/api/tests/test_backup_endpoints.py` (novo) — testes.

### ADRs Relacionados
- [ADR-003: Backup/restauração e cold tier sobre MinIO](adrs/adr-003.md) — restauração e ordem.

## Entregáveis
- Endpoints `/admin/backup/run|restore|status` funcionais.
- Procedimento de restauração documentado com RTO/RPO medidos em um drill.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Teste de integração backup→restore ponta a ponta **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `POST /admin/backup/run` enfileira/dispara e retorna chave válida.
  - [ ] `POST /admin/backup/restore` com chave inexistente retorna 404.
  - [ ] `GET /admin/backup/status` reporta timestamp e RPO corrente.
- Testes de integração:
  - [ ] Backup→restore reidrata Qdrant e PostgreSQL efêmeros e os dados conferem.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Drill concluído com RTO ≤ 1h e RPO ≤ 24h documentados
- Restauração bem-sucedida a partir do bucket
