---
status: pending
title: Job de dedup em lote
type: backend
complexity: medium
dependencies:
  - task_04
  - task_05
---

# Job de dedup em lote

## Visão Geral
Primeiro guarda-corpo de volume (baixo risco): um handler de job que consolida duplicatas **exatas** por hash dentro de um projeto, enviando as cópias redundantes para quarentena reversível. Reaproveita o hash MD5 já calculado no caminho de escrita do mem0.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O handler `dedup` DEVE identificar memórias com o mesmo `hash` no mesmo escopo (`project`) e manter uma como canônica.
- As duplicatas redundantes DEVEM ir para quarentena via `QuarantineEngine` (nunca exclusão direta).
- Memórias pinadas NÃO DEVEM ser quarentenadas nem escolhidas para remoção indevida.
- O job DEVE ser idempotente: reexecutar não quarentena além do necessário.
- O job DEVE ser registrado como handler de `job_type=dedup` no despacho do worker.
- O job DEVE processar em lotes com teto configurável e registrar contagem do que consolidou.
</requirements>

## Subtarefas
- [ ] 7.1 Implementar a varredura de duplicatas exatas por `hash` no escopo do projeto.
- [ ] 7.2 Escolher a canônica (ex.: mais antiga/estável) e marcar as demais para quarentena.
- [ ] 7.3 Quarentenar as redundantes via `QuarantineEngine`, respeitando pinadas.
- [ ] 7.4 Registrar o handler em `job_type=dedup` no `governance-worker`.
- [ ] 7.5 Garantir idempotência e processamento em lote com teto.

## Detalhes de Implementação
Ver seção "Sequenciamento de Desenvolvimento" (passo 7) do TechSpec e o [ADR-001](adrs/adr-001.md). O dedup exato espelha a lógica de hash de `mem0/memory/main.py` (~linhas 1065–1085). O handler é plugado no ponto de extensão da task_05 e usa o motor da task_04.

### Arquivos Relevantes
- `openmemory/api/app/governance/dedup.py` — **novo**: handler do job de dedup.
- `openmemory/api/app/workers/governance_worker.py` — registro do handler.
- `openmemory/api/app/utils/quarantine.py` — `QuarantineEngine` (task_04).
- `mem0/memory/main.py` — referência do hash MD5 (linhas ~1065–1085).
- `mem0/vector_stores/qdrant.py` — `list`/`scroll` para varrer por escopo.

### Arquivos Dependentes
- `openmemory/api/app/utils/metrics.py` — `governance_deduped_total` (task_12).

### ADRs Relacionados
- [ADR-001: Governança automática com rede de segurança, faseada](adrs/adr-001.md) — dedup é guarda-corpo de baixo risco do Incremento 1.

## Entregáveis
- Handler do job de dedup registrado no worker.
- Integração com `QuarantineEngine`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de dedup ponta a ponta **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Duas memórias com mesmo `hash` no projeto: uma permanece `active`, a outra é quarentenada.
  - [ ] Hashes distintos não são tocados.
  - [ ] Duplicata pinada não é quarentenada.
  - [ ] Reexecução não quarentena a canônica nem duplica ações.
  - [ ] Teto de lote limita o número de itens processados por execução.
- Testes de integração:
  - [ ] Job `dedup` enfileirado e processado pelo worker consolida duplicatas e some-as da busca (filtro da task_03).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Duplicatas exatas consolidadas de forma reversível, sem tocar pinadas
- Idempotência comprovada
