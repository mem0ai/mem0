---
status: pending
title: Pipeline de consolidação semântica (candidatura + LLM)
type: backend
complexity: high
dependencies:
  - task_04
  - task_05
---

# Pipeline de consolidação semântica (candidatura + LLM)

## Visão Geral
Incremento 2 (maior valor de qualidade): o handler que gera candidatos por similaridade vetorial (mesmo `project`+`type`, acima do limiar) e usa o LLM Service para decidir **merge** de quase-duplicatas (produzindo o texto canônico) ou **resolução de contradição** (elegendo a canônica). As fontes vão para quarentena reversível.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A candidatura DEVE usar busca vetorial escopada por `project`+`type` acima de `similarity_threshold`, ignorando memórias não-`active` e pinadas.
- A adjudicação DEVE usar o LLM Service para classificar cada par/grupo em `merge`, `contradiction` ou `none`.
- Em `merge`, a canônica (texto consolidado) DEVE ser gravada e as fontes quarentenadas.
- Em `contradiction`, a canônica DEVE ser eleita por `contradiction_tiebreak` e a perdedora quarentenada.
- Falha de LLM DEVE resultar em `none` (falha segura, nada é alterado).
- Pinadas nunca DEVEM ser fonte a quarentenar; o job processa em lotes com teto e fora de pico.
- O job DEVE ser registrado como handler de `job_type=consolidate`.
</requirements>

## Subtarefas
- [ ] 10.1 Implementar a geração de candidatos via busca vetorial escopada e limiar.
- [ ] 10.2 Implementar a chamada ao LLM Service para adjudicação estruturada (merge/contradiction/none).
- [ ] 10.3 Aplicar `merge` (gravar canônica + quarentenar fontes) e `contradiction` (eleger canônica + quarentenar perdedora).
- [ ] 10.4 Tratar falha de LLM como `none` e respeitar pinadas/teto/lote.
- [ ] 10.5 Registrar o handler em `job_type=consolidate`.

## Detalhes de Implementação
Ver seção "Sequenciamento de Desenvolvimento" (passo 10) do TechSpec e o [ADR-004](adrs/adr-004.md). Candidatura via `search_batch` (`qdrant.py` ~461) escopada por `project`+`type`; cliente LLM reutilizado do padrão de `routers/config.py`/`mem0/memory/main.py` (`LlmFactory.create`). Gravação da canônica via `add(infer=False)`; fontes via `QuarantineEngine` (task_04).

### Arquivos Relevantes
- `openmemory/api/app/governance/consolidation.py` — **novo**: candidatura + adjudicação + aplicação.
- `mem0/vector_stores/qdrant.py` — `search`/`search_batch` para candidatura.
- `mem0/memory/main.py` — padrão de construção do cliente LLM (`LlmFactory.create`, ~449).
- `openmemory/api/app/utils/quarantine.py` — `QuarantineEngine` (task_04).
- `openmemory/api/app/workers/governance_worker.py` — registro do handler.

### Arquivos Dependentes
- `openmemory/api/app/utils/metrics.py` — `governance_merged_total`, `governance_contradictions_resolved_total`, `governance_revert_rate` (task_12).

### ADRs Relacionados
- [ADR-004: Consolidação semântica por candidatura via vetor + adjudicação por LLM](adrs/adr-004.md) — define o pipeline de duas etapas.
- [ADR-001: Governança automática com rede de segurança, faseada](adrs/adr-001.md) — Incremento 2, ativado após validação dos guarda-corpos.

## Entregáveis
- Handler de consolidação semântica registrado no worker.
- Candidatura vetorial + adjudicação LLM + aplicação de merge/contradição.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração de consolidação ponta a ponta (LLM mockado) **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Candidatura retorna apenas pares no mesmo `project`+`type` acima do limiar, excluindo não-`active` e pinadas.
  - [ ] Adjudicação `merge` grava canônica e quarentena as fontes.
  - [ ] Adjudicação `contradiction` elege canônica por `recency`/`confidence` e quarentena a perdedora.
  - [ ] Adjudicação `none` não altera nada.
  - [ ] Falha do LLM resulta em `none` (nada alterado).
  - [ ] Pinada candidata nunca é quarentenada.
- Testes de integração:
  - [ ] Com LLM mockado, job `consolidate` reduz quase-duplicatas e resolve contradição, refletindo na busca (task_03).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Merge/contradição reversíveis, sem tocar pinadas
- Custo de LLM contido pela pré-filtragem vetorial (lote/teto)
