# PRD — Prontidão para produção do OpenMemory (mem0-shared)

## Visão Geral

O OpenMemory (mem0-shared) é a camada de memória de longo prazo usada por cerca de 200 desenvolvedores e dezenas de agentes MCP dentro da rede corporativa. As Fases 0–3 da arquitetura self-hosted já foram entregues e testadas, mas a auditoria de 2026-06-18 (seção 15 de `self-hosted-scale-architecture.md`) revelou pontos fracos que impedem chamar o sistema de "pronto para produção" com confiança.

Este esforço fecha esses pontos fracos para o cenário-alvo de **equipe interna em rede (LAN) confiável**, equilibrando três garantias: **não regredir/não perder dados**, **qualidade da memória em escala** e **operabilidade/diagnóstico**. Não persegue alta disponibilidade multi-nó nem exposição externa — esses ficam reservados a um esforço futuro, caso o uso ultrapasse a LAN.

- **Problema que resolve**: o sistema funciona, mas opera sem rede de segurança automatizada (testes fora do CI), sem backup/restauração validados, com governança de memória incompleta e diagnóstico limitado em produção.
- **Para quem**: os ~200 devs e agentes que dependem da memória, e a equipe que opera o serviço.
- **Por que é valioso**: transforma um sistema "funcional em demo" num serviço operável com confiança no dia a dia — sem perda de dados, sem degradação silenciosa de qualidade e com capacidade de diagnóstico quando algo falha.

## Objetivos

- **Eliminar regressões silenciosas**: toda alteração no `openmemory/api` é validada automaticamente antes de chegar à branch principal.
- **Garantir recuperação de dados**: backup periódico de memórias (vetores + metadados) com restauração testada e RTO/RPO conhecidos.
- **Sustentar a qualidade da memória em escala**: impedir crescimento ilimitado por project e remover/arquivar memórias inativas sem intervenção manual.
- **Habilitar diagnóstico em produção**: rastrear uma requisição ponta a ponta e ser alertado antes que o usuário perceba o problema.
- **Endurecer o acesso de forma proporcional ao risco LAN**: identificar a equipe de origem, proteger segredos e limitar abuso por project.

Marco-alvo: três fases incrementais, cada uma entregando valor operável de forma independente.

## Histórias de Usuário

**Persona: Operador/mantenedor do serviço**
- Como operador, quero que os testes do `openmemory/api` rodem automaticamente em cada PR, para que regressões sejam barradas antes do merge.
- Como operador, quero restaurar as memórias a partir de um backup recente, para que uma falha de disco/nó não signifique perda permanente.
- Como operador, quero acompanhar uma requisição lenta do MCP até o Qdrant/LLM, para que eu identifique o gargalo sem adivinhação.
- Como operador, quero ser alertado quando a fila de escrita, a latência ou a taxa de erro saírem do normal, para agir antes do impacto ao usuário.

**Persona: Administrador de governança de memória**
- Como administrador, quero definir um teto de memórias por project, para que um project descontrolado não degrade a busca dos demais.
- Como administrador, quero que projects inativos sejam arquivados/expurgados automaticamente, para manter o acervo enxuto e relevante.

**Persona: Desenvolvedor/agente consumidor (~200 devs)**
- Como dev, quero que minhas buscas e escritas continuem rápidas e corretas mesmo com o acervo crescendo, para confiar na memória no fluxo diário.
- Como dev, quero que minha equipe seja identificada nas operações, para atribuição e auditoria corretas.

**Persona: Responsável por segurança/conformidade interna**
- Como responsável de segurança, quero que segredos não fiquem em texto plano e que cada equipe se identifique, para reduzir risco mesmo dentro da LAN.

## Funcionalidades Principais

Agrupadas por fase (prioridade decrescente).

### Fase 1 — Rede de segurança

- **Gate de CI para o `openmemory/api`**: a suíte de testes existente (39 módulos) passa a ser executada automaticamente e bloqueia merges em caso de falha. Inclui acionamento por mudanças no caminho `openmemory/**`.
- **Backup e restauração de memórias**: rotina periódica de backup de Qdrant (vetores/coleções) e PostgreSQL (metadados, fila, auditoria), com procedimento de restauração executável e um drill documentado que comprova RTO/RPO.

### Fase 2 — Qualidade da memória + operabilidade

- **Teto de memórias por project (`max_memories`)**: política configurável (global + override por project) que limita o volume e dispara ação de governança ao ser excedida.
- **Cold tier de projects inativos**: arquivamento de projects sem atividade por janela definida (snapshot frio + remoção do acervo quente), reversível por restauração.
- **Tracing distribuído**: rastreamento de uma requisição através de MCP → embedding → Qdrant → (escrita) LLM, correlacionado por identificador de requisição/job.
- **Alertas e runbooks**: alertas acionáveis sobre as métricas já expostas (latência, profundidade de fila, taxa de erro, tamanho por project) e runbooks de incidente para os cenários mais prováveis.

### Fase 3 — Endurecimento leve

- **Identificação/autenticação por equipe**: substituir o "trust-on-LAN" por uma credencial por equipe (token/API key) validada na borda, mantendo a atribuição já existente.
- **Gestão de segredos fora do `.env`**: segredos deixam de viver em texto plano no compose/.env.
- **Rate limit por project+hostname**: limites de busca/escrita por origem (em vez do limite global atual), protegendo contra rajadas de um único consumidor.
- **Resiliência single-node**: healthchecks e políticas de reinício que recuperam serviços automaticamente após falha transitória.

## Experiência do Usuário

- **Operador (jornada principal)**: abre um PR → o CI executa testes do `openmemory/api` e reporta status → merge só com verde. Em incidente, consulta dashboards/alertas, abre o trace da requisição problemática, segue o runbook; se houver perda de dados, executa a restauração a partir do backup mais recente.
- **Administrador de governança**: define políticas (teto por project, janela de inatividade) via endpoints de governança já existentes; o sistema aplica automaticamente nos jobs agendados.
- **Dev/agente (~200)**: experiência **inalterada** no contrato MCP — buscas e escritas continuam idênticas; o benefício é indireto (mais rápido, mais confiável, sem degradação). A única mudança visível é passar a apresentar a credencial da equipe na configuração do cliente MCP (Fase 3).
- **Acessibilidade/descoberta**: as capacidades novas são de operação/administração e expostas por endpoints e dashboards; não alteram a interface do consumidor final.

## Restrições Técnicas de Alto Nível

- **Contrato MCP inalterado**: nenhuma mudança neste esforço pode quebrar o contrato MCP atual nem o compat_v3 usado pelos plugins.
- **Alvo LAN**: as soluções devem assumir rede confiável; segurança é proporcional a esse risco (sem mTLS obrigatório).
- **Single-node**: as garantias de dados (backup/restauração, resiliência) operam sobre infraestrutura de nó único; não se assume cluster.
- **Privacidade self-hosted**: dados de memória não saem da infraestrutura corporativa; backups/cold tier permanecem em armazenamento interno.
- **Compatibilidade de governança**: novas políticas estendem o resolver de política existente (global + override por project).

## Fora de Escopo (Non-Goals)

- **Alta disponibilidade multi-nó** (clusters Qdrant/PostgreSQL/Redis) — gaps D4–D6.
- **Autoscaling/HPA e migração para Kubernetes** — a operação permanece em Docker Compose/Swarm.
- **Coleção-por-project / `collection_registry`** (gap D1) — o isolamento por shard_key atual cobre o alvo LAN; revisitar só se o crescimento exigir multi-coleção.
- **mTLS service-to-service** — desproporcional para LAN confiável.
- **Embedding/LLM em vLLM/TGI com GPU autoscale** (gap D5) — Ollama permanece como backend.
- **Exposição pública/multi-tenant com isolamento forte** — alvo de um esforço futuro caso o uso ultrapasse a LAN.

## Plano de Entrega por Fases

### MVP (Fase 1) — Rede de segurança
- Gate de CI executando os testes do `openmemory/api`.
- Backup periódico + restauração testada de Qdrant e PostgreSQL.
- **Critério para avançar**: PRs barrados em falha de teste de forma confiável; um drill de restauração concluído com RTO/RPO medidos e documentados.

### Fase 2 — Qualidade + operabilidade
- `max_memories` por project aplicado pelos jobs de governança.
- Cold tier de projects inativos (arquivar + restaurar).
- Tracing distribuído ponta a ponta + alertas acionáveis + runbooks dos cenários principais.
- **Critério para avançar**: política de teto e cold tier funcionando em um project de teste; um incidente simulado diagnosticado via trace e resolvido seguindo o runbook.

### Fase 3 — Endurecimento leve
- Credencial por equipe validada na borda.
- Segredos fora do `.env`.
- Rate limit por project+hostname.
- Healthchecks + restart automático.
- **Critério de sucesso de longo prazo**: nenhuma operação aceita sem credencial de equipe; nenhum segredo em texto plano no repositório/compose; serviços se recuperam sozinhos de falhas transitórias.

## Métricas de Sucesso

- **Cobertura de gate**: 100% dos PRs que tocam `openmemory/**` executam a suíte de testes; 0 regressões mergeadas sem teste verde.
- **Recuperabilidade**: RPO ≤ 24h e RTO ≤ 1h comprovados em drill; restauração bem-sucedida em 100% dos drills.
- **Qualidade da memória**: nenhum project ultrapassa o teto configurado; índice de qualidade de retrieval e proporção de duplicatas no top-K estáveis ou em melhora ao longo do tempo.
- **Operabilidade**: 100% das requisições MCP rastreáveis ponta a ponta; alertas disparam antes do impacto percebido em incidentes simulados; tempo médio de diagnóstico reduzido.
- **Segurança proporcional**: 0 segredos em texto plano; 100% das operações com equipe identificada.

## Riscos e Mitigações

- **Risco de adoção (Fase 3 — credencial por equipe)**: devs podem resistir a configurar credenciais. Mitigação: distribuição simples (um passo no setup do cliente MCP), comunicação antecipada e período de transição com aviso antes de tornar obrigatório.
- **Risco de cronograma**: as três fases competem com o trabalho de produto. Mitigação: fases independentes e ordenadas por valor — a Fase 1 sozinha já eleva muito a confiança e pode ser entregue isolada.
- **Risco de dependência externa**: o upstream OpenMemory está oficialmente em descontinuação; o projeto é uma continuação interna. Mitigação: este esforço reduz a dependência ao consolidar testes próprios no CI e documentar operação/runbooks internos.
- **Risco de falsa sensação de segurança (single-node)**: backup/restauração não é HA; uma falha causa indisponibilidade temporária. Mitigação: comunicar claramente a postura de disponibilidade e manter HA como esforço futuro documentado.
- **Risco de escopo crescente**: pressão para incluir HA/coleção-por-project. Mitigação: ADR-001 delimita o que está adiado e por quê.

## Registros de Decisão de Arquitetura

- [ADR-001: Prontidão para produção orientada ao alvo LAN interna](adrs/adr-001.md) — Adota a Abordagem A (plano faseado pragmático para LAN), adiando HA multi-nó, autoscaling/K8s e coleção-por-project.

## Perguntas em Aberto

- **Destino dos backups e do cold tier**: armazenamento interno disponível (NFS, volume dedicado, MinIO/S3 on-prem)? Define o mecanismo na TechSpec.
- **Janela de inatividade para cold tier**: qual período sem atividade qualifica um project como inativo (ex.: 90/180 dias)?
- **Valor padrão de `max_memories`**: teto global default e ação ao exceder (bloquear escrita, acelerar TTL, ou apenas alertar)?
- **Frequência de backup e RPO aceitável**: diário é suficiente, ou há projects que exigem janela menor?
- **Formato da credencial por equipe**: token estático por equipe é suficiente para a LAN, ou deseja-se algo com expiração?
