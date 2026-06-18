# PRD — Fase 2: Particionamento e escala de armazenamento da memória

> **Idioma:** PT-BR. **Status:** rascunho para revisão. **Data:** 2026-06-17.
> **Predecessor:** [PRD da Fase 0+1](../self-hosted-scale-architecture/_prd.md) (MVP de leitura rápida + fundação durável já definido).

## Visão Geral

A Fase 1 entregou busca de memória em tempo sub-segundo para os ~200 devs ao remover os gargalos de embedding inline e escrita acoplada. Restou, porém, um limite estrutural: **todas as memórias vivem em um único repositório vetorial compartilhado, sem isolamento real por projeto e sem o índice que torna o filtro de projeto rápido em escala**. Enquanto o volume é moderado isso não dói; mas o volume agregado cresce rápido e, sem ação, o tamanho voltará a ser fator de lentidão — desfazendo o ganho da Fase 1.

Esta fase entrega o **particionamento da memória por projeto**, de forma **proativa**, para que a busca continue rápida e previsível mesmo quando o volume total e os maiores projetos crescerem várias vezes. O particionamento é **lógico** dentro de um repositório compartilhado (ver [ADR-001](adrs/adr-001.md)): cada projeto passa a ser uma "chave de inquilino" que agrupa fisicamente suas memórias, preservando a busca **cross-project** (caso de uso comum) barata e a transição **sem downtime**.

- **Qual problema resolve:** o crescimento do volume de memórias ameaça reintroduzir lentidão na busca; hoje não há isolamento nem indexação por projeto que sustente a escala.
- **Para quem é:** desenvolvedores que consomem a memória via agentes MCP (consumidores) e a equipe de plataforma que opera o serviço (operadores).
- **Por que é valioso:** garante que a experiência rápida da Fase 1 **não regrida com o crescimento**, mantendo a memória compartilhada confiável e escalável sem abrir mão da privacidade self-hosted.

## Objetivos

- **Latência plana com o crescimento (objetivo principal):** a busca mantém as metas de latência da Fase 1 mesmo quando o volume total e o maior projeto crescem várias vezes — o tamanho deixa de ser fator de lentidão.
- **Preservar a busca cross-project barata:** consultar memórias atravessando vários projetos continua simples e rápido após o particionamento.
- **Transição sem downtime:** repartir as memórias existentes sem janela de indisponibilidade nem perda de frescor para os devs.
- **Visibilidade e ação por projeto:** o operador enxerga o tamanho/saúde de cada projeto e é alertado antes que um projeto grande ameace a latência.
- **Marco-alvo:** particionamento aplicado a toda a base existente e ativo por padrão para novos projetos, com a latência validada sob carga representativa após a migração.

## Histórias de Usuário

### Persona principal — Desenvolvedor (consumidor via agente MCP)

- Como **dev**, quero que a busca continue em sub-segundo mesmo quando a memória da empresa cresce muito, para que a ferramenta não fique lenta de novo com o tempo.
- Como **dev**, quero continuar buscando conhecimento que atravessa vários projetos sem perda de desempenho, para que a memória compartilhada siga útil entre times.
- Como **dev**, quero não perceber a migração acontecendo, para que meu trabalho não seja interrompido por uma "obra" na infraestrutura.

### Persona secundária — Equipe de plataforma (operador)

- Como **operador**, quero que nenhum projeto individual consiga degradar a busca dos demais por seu volume, para ter previsibilidade conforme a adoção cresce.
- Como **operador**, quero ver o tamanho e a saúde de cada projeto e receber alerta quando um projeto se aproxima do limite saudável, para agir antes da degradação.
- Como **operador**, quero conduzir a repartição em background, fora de pico e de forma reversível, para migrar com segurança sem afetar os devs.

### Casos de borda

- Um projeto isolado cresce muito mais rápido que os demais (projeto "gigante").
- Migração de um projeto grande interrompida no meio (queda/reinício) e retomada sem recomeçar do zero.
- Busca cross-project disparada durante a janela em que parte dos projetos já migrou e parte não.
- Escrita de novas memórias chegando enquanto a base correspondente ainda está sendo repartida.

## Funcionalidades Principais

Agrupadas por prioridade dentro da Fase 2.

### P0 — Particionamento lógico por projeto

- **Projeto como chave de inquilino indexada:** cada memória passa a ser agrupada e filtrada por projeto de forma eficiente, com as memórias de um mesmo projeto fisicamente próximas. _Por quê:_ é o que torna o filtro de projeto rápido em escala e mantém a latência plana.
- **Busca cross-project preservada:** consultar vários projetos ao mesmo tempo continua sendo uma operação barata sobre o mesmo repositório. _Por quê:_ é caso de uso comum e não pode regredir.

### P0 — Migração sem downtime da base existente

- **Repartição em background com retomada:** as memórias atuais são reorganizadas para o novo modelo de forma incremental, em segundo plano, com checkpoint para retomar após falhas, mantendo busca e escrita disponíveis durante todo o processo. _Por quê:_ a transição precisa ser transparente para os devs (requisito confirmado).
- **Reversibilidade da transição:** é possível validar o novo arranjo antes de torná-lo o padrão e voltar atrás em caso de problema. _Por quê:_ reduz o risco de uma migração de grande volume.

### P0 — Capacidade e resiliência de armazenamento

- **Repositório de memória distribuído (cluster):** o armazenamento vetorial passa a operar com múltiplos nós, dando capacidade e tolerância a falhas para o volume-alvo. _Por quê:_ sustenta centenas de milhões de memórias com replicação.

### P1 — Visibilidade e governança de tamanho por projeto

- **Painel de tamanho/saúde por projeto:** o operador vê quantas memórias cada projeto tem e recebe alerta quando um projeto se aproxima do limite saudável. _Por quê:_ permite agir (promover o projeto a partição dedicada) antes da degradação — é parte do critério de sucesso operacional.
- **Promoção de projeto gigante:** projetos que ultrapassam o limite saudável podem ser movidos para uma partição dedicada, sem mudar a forma como os agentes buscam. _Por quê:_ rota de escala para os poucos projetos que mais pesam, sem criar uma segunda arquitetura.

### Interação entre funcionalidades

O particionamento lógico entrega a latência plana; a migração sem downtime garante que chegar lá não custe indisponibilidade; o cluster dá a capacidade física; a visibilidade por projeto fecha o ciclo, permitindo ao operador antecipar e promover projetos gigantes. O contrato dos agentes MCP (`search_memory`, `add_memories`) **permanece inalterado** — o particionamento é transparente para o dev.

## Experiência do Usuário

### Dev (consumidor)

1. Continua usando as mesmas ferramentas MCP no IDE, sem qualquer mudança de configuração.
2. Durante a migração, busca e escrita seguem funcionando normalmente; não há janela de indisponibilidade nem aviso de "manutenção".
3. Após a Fase 2, a busca permanece rápida mesmo com a base muito maior, e a busca cross-project continua respondendo bem.

> A experiência do dev **não muda visualmente**. O ganho é a **ausência de regressão** de latência ao longo do tempo.

### Operador (plataforma)

1. Inicia a repartição em background, fora do horário de pico, acompanhando o progresso.
2. Valida o novo arranjo (latência, isolamento) antes de promovê-lo a padrão; pode reverter se necessário.
3. Passa a acompanhar um painel de tamanho/saúde por projeto, com alertas de limite.
4. Quando um projeto se aproxima do limite, promove-o a partição dedicada de forma controlada.

### Acessibilidade

Produto de infraestrutura, sem mudança de interface para o dev. As metas de acessibilidade da UI existente permanecem inalteradas. Eventuais elementos novos de painel para o operador seguem os padrões da UI atual.

## Restrições Técnicas de Alto Nível

- **Self-hosted obrigatório:** todas as memórias permanecem na infraestrutura da empresa; nenhum dado sai para serviços externos.
- **Ambiente de deploy:** Docker Swarm / VMs dedicadas (sem Kubernetes). Cluster do repositório e migração em background são operados/escalados **manualmente**; sem autoscaling (consistente com a Fase 1).
- **Compatibilidade de contrato:** os agentes MCP (`search_memory`, `add_memories`) continuam funcionando sem alteração; o particionamento é transparente.
- **Continuidade de serviço:** a transição deve ocorrer sem downtime e sem perda de frescor das escritas; deve ser retomável após falha e reversível.
- **Metas de desempenho na perspectiva do usuário:** manter as metas da Fase 1 sob a base ampliada — busca p99 < 100 ms (cache quente) / < 300 ms (cache frio); confirmação de escrita < 50 ms; processamento de escrita p95 < 60 s. A meta-chave da Fase 2 é que esses números **não se degradem** com o crescimento.
- **Privacidade/segurança:** mantém o modelo de confiança da Fase 1; isolamento entre projetos é **lógico**, não físico total (ver Riscos).

## Fora de Escopo (Non-Goals)

- **Governança de qualidade de memória** — consolidação/dream, TTL/pruning, dedup avançado — permanece na **Fase 3**.
- **Cold tier / arquivamento de projetos inativos** (snapshot externo + descarte) — Fase 3; aqui o foco é desempenho/isolamento, não ciclo de vida de arquivamento.
- **Autoscaling automático** do cluster ou dos serviços — depende de orquestrador elástico, fora do ambiente escolhido.
- **Isolamento físico total por projeto / multi-tenant enterprise** (coleção física por projeto, RBAC, mTLS) — explicitamente descartado em favor do particionamento lógico ([ADR-001](adrs/adr-001.md)).
- **Busca híbrida (semântica + keyword + entidade) no caminho crítico do MCP** — opcional e fora desta fase; a capacidade técnica existe, mas sua ativação não é objetivo aqui.
- **Mudança de modelo de embedding ou re-embedding em massa** — não é objetivo da Fase 2.

## Plano de Entrega por Fases

> Escopo desta fase no contexto do roadmap geral (Fases 0–3 da proposta técnica). Aqui, "MVP" = entrega central da Fase 2.

### MVP (núcleo da Fase 2)

- Particionamento lógico por projeto (chave de inquilino indexada) ativo por padrão para novos projetos.
- Migração sem downtime, retomável e reversível, da base existente.
- Repositório em cluster (múltiplos nós) com replicação.

**Critérios de sucesso para avançar:**
- Latência de busca dentro das metas da Fase 1 com a base migrada e sob carga representativa, **sem degradação** atribuível ao volume.
- Busca cross-project mantém desempenho aceitável após o particionamento.
- Migração concluída sem downtime e sem perda de memórias.

### Incremento — Visibilidade e promoção (ainda na Fase 2)

- Painel de tamanho/saúde por projeto + alertas de limite.
- Promoção controlada de projeto gigante a partição dedicada.

**Critério para avançar:** operador consegue identificar e promover um projeto que se aproxima do limite **antes** de a busca degradar.

### Fase 3 (posterior)

- Governança (dream/TTL/pruning), cold tier para projetos inativos, e elasticidade contínua se houver migração para orquestrador elástico.
- Critério de longo prazo: qualidade de memória estável e custo de operação sob controle com centenas de milhões de memórias.

## Métricas de Sucesso

- **Estabilidade de latência sob crescimento (principal):** a busca p99 permanece dentro das metas da Fase 1 mesmo após o volume total e o maior projeto crescerem várias vezes (latência plana).
- **Desempenho cross-project:** consultas que atravessam projetos mantêm latência aceitável após o particionamento.
- **Transição limpa:** migração da base existente concluída com **zero downtime** e **zero memórias perdidas**; capacidade de retomar após falha demonstrada.
- **Antecipação operacional:** projetos que se aproximam do limite saudável são identificados e tratados (promovidos) **antes** de impactar a latência percebida.
- **Transparência ao dev:** nenhuma alteração de configuração nos agentes MCP e nenhuma reclamação de indisponibilidade durante a migração.

## Riscos e Mitigações

- **Risco de adoção — regressão silenciosa de latência pós-migração:** se a repartição não entregar a latência plana esperada, a confiança conquistada na Fase 1 se perde. _Mitigação:_ validar latência sob carga representativa antes de promover o novo arranjo a padrão; manter a transição reversível.
- **Risco operacional — migração de grande volume:** repartir uma base grande é demorado e sensível a falhas. _Mitigação:_ executar em background, fora de pico, com checkpoint/retomada e janela de validação antes do corte.
- **Risco de isolamento lógico (não físico):** um incidente de infraestrutura no repositório compartilhado pode afetar mais de um projeto ao mesmo tempo. _Mitigação:_ cluster com replicação; promoção de projetos críticos/gigantes a partições dedicadas; aceito conscientemente em troca da busca cross-project barata ([ADR-001](adrs/adr-001.md)).
- **Risco de cronograma — fase longa (6–12 semanas):** a duração estimada amplia a exposição a mudanças concorrentes. _Mitigação:_ entregar o núcleo (particionamento + migração) antes do incremento de visibilidade/promoção.
- **Risco de dependência externa — capacidade de hardware do cluster:** o cluster distribuído exige RAM/armazenamento adequados ao volume-alvo. _Mitigação:_ confirmar o provisionamento (memória/armazenamento por nó) antes da migração; registrado em Perguntas em Aberto.
- **Risco competitivo:** soluções gerenciadas (Mem0 Platform) e concorrentes (Zep, Letta) oferecem escala "pronta". _Mitigação:_ o diferencial é a privacidade self-hosted total — manter esse valor central.

## Registros de Decisão de Arquitetura

- [ADR-001: Particionamento lógico por projeto na coleção compartilhada (multitenancy por payload)](adrs/adr-001.md) — Particionar por projeto **dentro de um repositório compartilhado** (projeto como chave de inquilino indexada + sharding para projetos gigantes), em vez de uma coleção física por projeto, para preservar busca cross-project barata e latência plana.

## Perguntas em Aberto

- **Limiar de "projeto gigante":** qual o tamanho (nº de memórias) a partir do qual um projeto deve ser promovido a partição dedicada? (a proposta sugere ordens de grandeza; o limiar real precisa ser definido/observado)
- **Capacidade de hardware do cluster:** há RAM/armazenamento suficientes provisionados para manter a parcela quente do índice em memória no volume-alvo? (impacta a meta de latência plana)
- **Carga representativa de validação:** quais números de volume e de QPS cross-project devem ser usados como alvo do teste de carga pós-migração?
- **Ordem de migração:** migrar primeiro os projetos maiores (maior risco) ou os menores (validação de baixo risco)? (a proposta sugere "maiores primeiro" via background job)
- **Exclusão/limpeza por projeto:** com isolamento lógico, qual o comportamento esperado e o tempo aceitável para remover/expurgar todas as memórias de um projeto quando necessário? (fronteira com a Fase 3)
- **Responsável pela operação da migração:** qual equipe conduz e monitora a repartição em background e responde a alertas de tamanho por projeto?
