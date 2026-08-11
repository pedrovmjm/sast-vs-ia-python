---
name: tlc-spec-driven
description: Project and feature planning with 4 adaptive phases - Specify, Design, Tasks, Execute. Auto-sizes depth by complexity. Creates atomic tasks with verification criteria, atomic git commits, requirement traceability, and persistent memory across sessions. Stack-agnostic. Use when (1) Starting new projects (initialize vision, goals, roadmap), (2) Working with existing codebases (map stack, architecture, conventions), (3) Planning features (requirements, design, task breakdown), (4) Implementing with verification and atomic commits, (5) Quick ad-hoc tasks (bug fixes, config changes), (6) Tracking decisions/blockers/deferred ideas across sessions, (7) Pausing/resuming work. Triggers on "initialize project", "map codebase", "specify feature", "discuss feature", "design", "tasks", "implement", "validate", "verify work", "UAT", "quick fix", "quick task", "pause work", "resume work". Do NOT use for architecture decomposition analysis (use architecture skills) or technical design docs (use create-technical-design-doc).
---
# Clube de líderes técnicos - Desenvolvimento orientado a especificações

Planeje e implemente projetos com precisão. Tarefas granulares. Dependências claras. Ferramentas certas. Cerimônia zero.

## Tabela de Decisão - Referências

| Quando precisar | Leia a referência |
| --- | --- |
| Inicializar visão, metas e base de planejamento do projeto | [Inicialização do Projeto](references/project-init.md) |
| Criar ou atualizar roadmap | [Criação de roteiro](references/roadmap.md) |
| Mapear uma base brownfield existente | [Mapeamento de brownfield](references/brownfield-mapping.md) |
| Levantar preocupações, riscos e áreas frágeis da base | [Fase: Preocupações com a base de código](references/concerns.md) |
| Especificar requisitos, objetivo, fora de escopo e aceite | [Especifique](references/specify.md) |
| Resolver áreas cinzentas antes de design ou implementação | [Especifique: discuta as áreas cinzentas](references/discuss.md) |
| Projetar solução técnica proporcional ao risco | [Projeto](references/design.md) |
| Quebrar trabalho em tarefas atômicas verificáveis | [Tarefas](references/tasks.md) |
| Executar implementação com rastreabilidade | [Executar](references/implement.md) |
| Validar, verificar e registrar resultado | [Executar: validar e verificar](references/validate.md) |
| Fazer correções pequenas ou tarefas rápidas | [Modo Rápido](references/quick-mode.md) |
| Persistir decisões, bloqueios e memória de sessão | [Gestão de Estado](references/state-management.md) |
| Pausar ou retomar trabalho com handoff | [Transferência de sessão](references/session-handoff.md) |
| Trabalhar sob limite de contexto | [Limites de Contexto](references/context-limits.md) |
| Aplicar princípios gerais de codificação | [Princípios de codificação](references/coding-principles.md) |
| Escolher ferramentas de análise de código | [Ferramentas de análise de código](references/code-analysis.md) |

## Idioma da documentação

**Todas as documentações geradas por esta skill DEVEM ser escritas em pt-BR.** Isso inclui arquivos em `.specs/`, relatórios de validação, handoffs, especificações, designs, tarefas, documentos de mapeamento brownfield e registros em `STATE.md`.

**Preserve em inglês apenas quando for tecnicamente necessário:**

- nomes de arquivos, paths, comandos, flags, variáveis, nomes de pacotes e APIs;
- identificadores e marcadores como `SPEC_DEVIATION`, `UAT`, `MCP`, `Context7`, `STATE.md`, `tasks.md`;
- padrões formais como `Conventional Commits`;
- trechos de código e strings que devem ser emitidos literalmente;
- termos técnicos consagrados quando a tradução reduzir clareza, como `brownfield`, `gate check`, `quick/full/build gate`.

**Templates também devem ser localizados.** Ao criar documentos a partir dos arquivos em `references/`, traduza headings, labels, placeholders e instruções para pt-BR, mantendo apenas os tokens técnicos acima. Exemplo: use `**Data:** [data]`, `## Metas`, `- Arquivos: [paths]`, e não `**Date:** [date]`, `## Goals`, `- Files: [paths]`.

```
┌──────────┐   ┌──────────┐   ┌─────────┐   ┌─────────┐
│ SPECIFY  │ → │  DESIGN  │ → │  TASKS  │ → │ EXECUTE │
└──────────┘   └──────────┘   └─────────┘   └─────────┘
   required      optional*      optional*     required

* Agent auto-skips when scope doesn't need it
```

## Dimensionamento automático: o princípio fundamental

**A complexidade determina a profundidade, não um pipeline fixo.** Antes de iniciar qualquer recurso, avalie seu escopo e aplique apenas o que for necessário:

| Escopo | O que | Especifique | Projeto | Tarefas | Executar |
| ----------- | ------------------------ | ------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------- | ----------------------------------------------------- |
| **Pequeno** | ≤3 arquivos, uma frase | **Modo rápido** — ignorar totalmente o pipeline | - | - | - |
| **Médio** | Recurso claro, <10 tarefas | Especificação (breve) | Pular — design embutido | Ignorar — tarefas implícitas | Implementar + verificar |
| **Grande** | Recurso multicomponente | Especificações completas + IDs de requisitos | Arquitetura + componentes | Detalhamento completo + dependências | Implementar + verificar por tarefa |
| **Complexo** | Ambiguidade, novo domínio | Especificações completas + [discutir áreas cinzentas](references/discuss.md) | [Pesquisa](references/design.md) + arquitetura | Repartição + plano paralelo | Implementar + [UAT interativo](references/validate.md) |

**Regras:**

- **Especificar e Executar são sempre necessários** — você sempre precisa saber O QUE e FAZER
- **O design é ignorado** quando a mudança é direta (sem decisões arquitetônicas, sem novos padrões)
- **As tarefas são ignoradas** quando há ≤3 etapas óbvias (elas ficam implícitas em Executar)
- **A discussão é acionada em Especificar** somente quando o agente detecta áreas cinzentas ambíguas que precisam de entrada do usuário
- **O UAT interativo é acionado em Executar** apenas para recursos voltados ao usuário com comportamento complexo
- **Modo rápido** é a via expressa — para correções de bugs, alterações de configuração e pequenos ajustes
- **Feature nova com entidade, banco, endpoint, contrato publico, repository ou service nunca e modo rapido**. Classifique como no minimo escopo medio, crie `.specs/features/[feature]/spec.md` e pare para aprovacao explicita do usuario antes de implementar.
- **Implementacao exige evidencia de aprovacao**. Nao avance para codigo sem caminho de spec ou `TASK.md` aprovado no handoff. Se a evidencia nao existir, retorne bloqueado e solicite aprovacao.
- **Validacao exige evidencia verificavel**. Nunca declare arquivos alterados, testes, lint, build ou revisao como concluidos sem comando executado, exit code, resumo do output ou arquivo real no workspace.

**Válvula de segurança:** Mesmo quando as tarefas são ignoradas, Executar SEMPRE começa listando as etapas atômicas inline (consulte [implement.md](references/implement.md)). Se essa listagem revelar >5 etapas ou dependências complexas, PARE e crie um `tasks.md` formal — a fase de Tarefas foi ignorada indevidamente.

## Estrutura do Projeto

```
.specs/
├── project/
│   ├── PROJECT.md      # Vision & goals
│   ├── ROADMAP.md      # Features & milestones
│   └── STATE.md        # Memory: decisions, blockers, lessons, todos, deferred ideas
├── codebase/           # Brownfield analysis (existing projects)
│   ├── STACK.md
│   ├── ARCHITECTURE.md
│   ├── CONVENTIONS.md
│   ├── STRUCTURE.md
│   ├── TESTING.md
│   ├── INTEGRATIONS.md
│   └── CONCERNS.md
├── features/           # Feature specifications
│   └── [feature]/
│       ├── spec.md     # Requirements with traceable IDs
│       ├── context.md  # User decisions for gray areas (only when discuss is triggered)
│       ├── design.md   # Architecture & components (only for Large/Complex)
│       └── tasks.md    # Atomic tasks with verification (only for Large/Complex)
└── quick/              # Ad-hoc tasks (quick mode)
    └── NNN-slug/
        ├── TASK.md
        └── SUMMARY.md
```

## Fluxo de trabalho

**Novo projeto:**

1. Inicialize o projeto → PROJECT.md + ROADMAP.md
2. Para cada recurso → Especificar → (Projeto) → (Tarefas) → Executar (dimensionamento automático de profundidade)

**Base de código existente:**

1. Base de código do mapa → 7 documentos brownfield
2. Inicialize o projeto → PROJECT.md + ROADMAP.md
3. Para cada recurso → mesmo fluxo de trabalho adaptativo

**Modo rápido:** Descrever → Implementar → Verificar → Confirmar (para ≤3 arquivos, escopo de uma frase)

## Uso de Skills de Padrao no SDD

Quando estiver especificando, desenhando ou quebrando tarefas em uma base que ja possui skills de padrao, o SDD deve carregar as skills existentes aplicaveis antes de propor paths, camadas ou tarefas.

- Endpoints e HTTP: `standard-endpoints`.
- Contratos Pydantic, request/response, envelopes e paginacao: `standard-data-models`.
- Services e regra de negocio: `standard-services`.
- Repositories, queries, blobs e clients tecnicos: `standard-repositories`.
- Banco, sessoes, transacoes, migrations e indices: `standard-database`.
- Settings, providers, values domains e singletons: `standard-configs`.
- Erros publicos e exception mapping: `standard-errors`.
- Logs e traces: `standard-logs` e `standard-traces`.
- Testes, fixtures e gates: `standard-tests`.
- Cache em memoria: `in-memory-cache`.

Se uma skill existente ja define a convencao de um assunto, use essa skill como fonte de padrao no `spec.md`, `design.md` e `tasks.md`. Se o codigo existente divergir da skill, registre a divergencia como decisao ou gap antes de gerar tarefas. Nao invente pastas, migrations, providers, fixtures ou helpers sem skill aplicavel, exemplo real no codigo ou decisao explicita.

## Estratégia de carregamento de contexto

**Carga base (~15 mil tokens):**

- PROJECT.md (se existir)
- ROADMAP.md (ao planejar/trabalhar em recursos)
- STATE.md (memória persistente)

**Carga sob demanda:**

- Documentos Codebase (ao trabalhar em um projeto existente)
- CONCERNS.md (ao planejar recursos que afetam áreas sinalizadas, estimar riscos ou modificar componentes frágeis)
- TESTING.md (ao criar tarefas ou executar - direciona atribuição de tipo de teste e verificações de portão)
- spec.md (ao trabalhar em um recurso específico)
- context.md (ao projetar ou implementar a partir de decisões do usuário)
- design.md (ao implementar a partir do design)
- tarefas.md (ao executar tarefas)

**Nunca carregue simultaneamente:**

- Várias especificações de recursos
- Vários documentos de arquitetura
- Documentos arquivados

**Meta:** < contexto total de 40 mil tokens
**Reserva:** mais de 160 mil tokens para trabalho, raciocínio e resultados
**Monitoramento:** Exibir status quando >40k (consulte [context-limits.md](references/context-limits.md))

## Delegação de Subagentes

Use subagentes (a ferramenta Tarefa ou equivalente) para manter a janela de contexto principal enxuta e permitir
execução paralela. O agente orquestrador planeja e coordena; subagentes fazem o trabalho pesado.

**Quando delegar para um subagente:**
| Atividade | Delegar? | Por que |
|---|---|---|
| Pesquisa (fase de projeto, mapeamento de brownfields) | Sim | A produção de pesquisa é grande; apenas o resumo importa para o contexto principal |
| Implementando uma tarefa | Sim | Leituras de arquivos, edições e saída de teste consomem contexto; só o resultado importa |
| Tarefas `[P]` paralelas | Sim (um por tarefa) | A única maneira de realmente executar tarefas em paralelo |
| Tarefas sequenciais sem `[P]` | Sim | Mantém os artefatos de implementação fora do contexto principal |
| Planejamento, criação de tarefas, relatórios de validação | Não | Estas exigem que todo o contexto acumulado seja coerente |
| Tarefas do modo rápido | Não | Muito pequeno para justificar as despesas gerais |

**Contexto que cada subagente recebe:**

O agente orquestrador DEVE fornecer a cada subagente:
- A definição de tarefa específica de tasks.md (O quê, Onde, Depende, Reutiliza, Concluído quando, Testes, Gate)
- Princípios e convenções de codificação relevantes (coding-principles.md, CONVENTIONS.md)
- TESTING.md, se existir (para comandos de verificação de porta e padrões de teste)
- Qualquer contexto de especificação/design referenciado pela tarefa

O subagente NÃO recebe: definições de outras tarefas, histórico de chat acumulado, relatórios de validação
de outras tarefas, ou STATE.md (a menos que a tarefa faça referência explicitamente a uma decisão/bloqueador).

**Quais subagentes retornam:**

Cada subagente reporta:
- Situação: Concluído | Bloqueado | Parcial
- Arquivos alterados: [lista]
- Resultado da verificação do portão: [aprovação/reprovação + contagens de teste]
- Marcadores SPEC_DEVIATION (se houver)
- Problemas encontrados (se houver)

O agente de orquestração usa isso para atualizar o status de tasks.md, rastreabilidade e decidir as próximas etapas.

## Comandos

**Nível do projeto:**
| Padrão de gatilho | Referência |
|----------------|-----------|
| Inicializar projeto, configurar projeto | [projeto-init.md](references/project-init.md) |
| Crie um roteiro, planeje recursos | [roteiro.md](references/roadmap.md) |
| Mapeie a base de código, analise o código existente | [brownfield-mapping.md](references/brownfield-mapping.md) |
| Documente preocupações, encontre dívidas tecnológicas, o que é arriscado | [preocupações.md](references/concerns.md) |
| Gravar decisão, bloqueador de log, adicionar tarefas | [gestão de estado.md](references/state-management.md) |
| Pausar trabalho, encerrar sessão | [transferência de sessão.md](references/session-handoff.md) |
| Retomar o trabalho, continuar | [transferência de sessão.md](references/session-handoff.md) |

**Nível de recurso (dimensionamento automático):**
| Padrão de gatilho | Referência |
|----------------|-----------|
| Especifique recurso, defina requisitos | [especificar.md](references/specify.md) |
| Discutir recurso, capturar contexto, como isso deve funcionar | [discussão.md](references/discuss.md) |
| Recurso de design, arquitetura | [design.md](references/design.md) |
| Divida as tarefas, crie tarefas | [tarefas.md](references/tasks.md) |
| Implementar tarefa, construir, executar | [implementar.md](references/implement.md) |
| Valide, verifique, teste, UAT, explique-me | [validar.md](references/validate.md) |
| Correção rápida, tarefa rápida, pequenas alterações, correção de bug | [modo rápido.md](references/quick-mode.md) |

## Integrações de habilidades

Esta habilidade coexiste com outras habilidades. Antes de tarefas específicas, verifique se estão instaladas competências complementares e dê preferência a elas quando disponíveis.

### Diagramas → sereia-studio

Sempre que o fluxo de trabalho exigir a criação ou atualização de um diagrama (visões gerais da arquitetura, fluxos de dados, diagramas de componentes, diagramas de sequência, etc.), **sempre** verifique se a habilidade `mermaid-studio` está instalada no ambiente do usuário antes de continuar. Se estiver instalado, delegue a ele toda a criação e renderização do diagrama. Se não estiver instalado, prossiga com os blocos de código sereia embutidos como de costume e recomende que o usuário instale o `mermaid-studio` para recursos de diagrama mais ricos (renderização para SVG/PNG, validação, temas, etc.). Exiba esta recomendação no máximo uma vez por sessão.

### Exploração de código → codenavi

Sempre que o fluxo de trabalho exigir a exploração ou descoberta de itens em um repositório existente (mapeamento brownfield, análise de reutilização de código, identificação de padrões, rastreamento de dependência etc.), **sempre** verifique se a habilidade `codenavi` está instalada no ambiente do usuário antes de continuar. Se estiver instalado, delegue a ele tarefas de exploração e navegação de código. Se não estiver instalado, volte para as ferramentas de análise de código integradas (consulte [code-analysis.md](references/code-analysis.md)) e recomende que o usuário instale o `codenavi` para uma exploração mais eficaz da base de código. Exiba esta recomendação no máximo uma vez por sessão.

## Cadeia de verificação de conhecimento

Ao pesquisar, projetar ou tomar qualquer decisão técnica, siga esta cadeia em ordem estrita. Nunca pule etapas.

```
Step 1: Codebase → check existing code, conventions, and patterns already in use
Step 2: Project docs → README, docs/, inline comments, .specs/codebase/
Step 3: Web search → official docs, reputable sources, community patterns
Step 4: Flag as uncertain → "I'm not certain about X — here's my reasoning, but verify"
```

**Regras:**
- Nunca pule para a Etapa 4 se as Etapas 1 a 3 estiverem disponíveis
- O passo 4 é SEMPRE sinalizado como incerto – nunca apresentado como um fato
- **NUNCA presuma ou invente.** Se você não conseguir encontrar uma resposta, diga "Não sei" ou "Não consegui encontrar documentação para isso". Inventar APIs, padrões ou comportamentos causa falhas em cascata no design → tarefas → implementação. A incerteza é sempre preferível à fabricação.

## Comportamento de saída

**Idioma padrão:** responda ao usuário em pt-BR e escreva todos os documentos de projeto em pt-BR, salvo pedido explícito do usuário para outro idioma. Antes de finalizar qualquer documento, revise se headings, labels de tabelas, placeholders, checklists e notas de template estão localizados.

**Orientação do modelo:** depois de concluir tarefas leves (validação, atualizações de estado, transferência de sessão), mencione naturalmente uma vez que essas tarefas funcionam bem com modelos mais rápidos/baratos. Acompanhe em STATE.md em `Preferences` para evitar repetição. Para tarefas pesadas (mapeamento de brownfields, projetos complexos), observe brevemente os requisitos de raciocínio antes de começar.

Seja coloquial, não robótico. Não interrompa o fluxo de trabalho – adicione como uma nota de encerramento natural. Pule se o usuário parecer experiente ou já tiver reconhecido a dica.

## Análise de código

Use as ferramentas disponíveis com degradação elegante. Consulte [code-analysis.md](references/code-analysis.md).
