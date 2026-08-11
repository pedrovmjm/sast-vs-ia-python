# Tarefas

**Objetivo**: Dividir em tarefas GRANULARES e ATÔMICAS. Dependências claras. Ferramentas certas. Plano de execução paralela.

**Idioma:** gere `tasks.md` em pt-BR. Traduza títulos, labels, critérios, checklists, placeholders e descrições. Preserve IDs de tarefas, IDs de requisito, paths, comandos de gate e termos `quick/full/build` quando usados como níveis técnicos.

**Pule esta fase quando:**Existem ≤3 etapas óbvias. Nesse caso, as tarefas estão implícitas – vá direto para Executar e liste-as em seu plano de implementação.

## Por que tarefas granulares?

| Tarefa Vaga (RUIM) | Tarefas granulares (BOM) |
| ---------------- | --------------------------------- |
| "Criar formulário" | T1: Criar componente de entrada de e-mail |
|                  | T2: Adicionar função de validação de e-mail |
|                  | T3: Criar botão de envio |
|                  | T4: Adicionar gerenciamento de estado de formulário |
|                  | T5: Conectar formulário à API |
| "Implementar autenticação" | T1: Criar formulário de login |
|                  | T2: Criar formulário de cadastro |
|                  | T3: Adicionar utilitário de armazenamento de token |
|                  | T4: Criar serviço API de autenticação |
|                  | T5: Adicionar proteção de rota |

**Benefícios do granulado:**

- **Agentes não erram** - Foco único, sem ambiguidade
- **Fácil de testar** - Cada tarefa = um resultado verificável
- **Paralelizável** - Tarefas independentes são executadas simultaneamente
- **Erros isolados** - Uma falha não bloqueia tudo

**Regra**: Uma tarefa = UMA destas:

- Um componente
- Uma função
- Um terminal de API
- Uma alteração de arquivo

---

## Processo

### 1. Revisão do projeto

Leia `.specs/[feature]/design.md` antes de criar tarefas.

### 1.5. Matriz de Cobertura de Teste de Carga

Leia `.specs/codebase/TESTING.md` (se existir) antes de criar tarefas. A Matriz de Cobertura de Teste
e a Avaliação de Paralelismo conduzem a duas decisões críticas:

**Testes colocalizados:** toda tarefa que cria ou modifica uma camada de código com um tipo de teste obrigatório
DEVE incluir a escrita/atualização desses testes na mesma tarefa. Os testes NÃO são tarefas separadas.

| A tarefa cria... | Concluído Quando deve incluir... |
| ----------------------------------------- | ------------------------------------------- |
| Camada de código com requisito de "unidade" | Teste de unidade escrito + passagens rápidas |
| Camada de código com requisito "e2e" | Teste E2E escrito + aprovação completa |
| Camada de código com requisito de “integração” | Teste de integração escrito + aprovação completa |
| Camada de código com requisito "nenhum" | Verificação da porta ao nível adequado |

**Sinalizadores de paralelismo:** Faça referência cruzada da Avaliação de Paralelismo ao marcar tarefas `[P]`:

- Se o tipo de teste necessário de uma tarefa estiver marcado como "Parallel-Safe: No" → retirar o sinalizador `[P]`
- Se o tipo de teste necessário de uma tarefa estiver marcado como "Parallel-Safe: Yes" → `[P]` é permitido
- Se uma tarefa não possui testes → `[P]` depende apenas de dependências de código

Se TESTING.md não existir (projeto greenfield), pergunte ao usuário quais tipos de teste e comandos
o projeto usará antes de criar tarefas.

### 2. Divida as tarefas atômicas

**Tarefa = UMA entrega**. Exemplos:

- ✅ "Criar interface UserService" (um arquivo, um conceito)
- ❌ "Implementar gerenciamento de usuários" (muito vago, vários arquivos)

### 3. Definir dependências

O que DEVE ser feito antes que esta tarefa possa começar?

### 4. Crie um plano de execução

Agrupe as tarefas em fases. Identifique o que pode funcionar em paralelo.

### 5. Validar antes de apresentar (OBRIGATÓRIO)

Antes de mostrar as tarefas ao usuário, execute TODAS as três verificações de pré-aprovação. Estes NÃO são opcionais – são portões. Se alguma verificação falhar, reestruture as tarefas e execute-as novamente até que todas sejam aprovadas.

**Verificação 1: granularidade da tarefa** — verifique se cada tarefa é atômica (consulte a seção Verificação de granularidade).

**Verificação 2: Verificação cruzada de definição de diagrama** — verifique se o diagrama de execução corresponde ao campo `Depends on` de cada tarefa (consulte a seção Verificação cruzada de definição de diagrama). Construa a tabela de verificação cruzada e inclua-a na saída.

**Verificação 3: Testar validação de colocalização** — verifique se o campo `Tests` de cada tarefa corresponde à matriz de cobertura TESTING.md (consulte a seção Testar validação de colocalização). Construa a tabela de validação e inclua-a na saída.

**Produza ambas as tabelas com as tarefas** para que o usuário possa ver os resultados da validação. Qualquer ❌ significa que você DEVE reestruturar antes de apresentar - não mostre as tarefas com falha ao usuário e peça-lhe que aprove.

### 6. PERGUNTE sobre MCPs e habilidades

**CRÍTICO**: Antes da execução, pergunte ao usuário:
> "Para cada tarefa, quais ferramentas devo usar?"
>
> **MCPs disponíveis**: [lista do projeto ou usuário]
> **Habilidades disponíveis**: [lista do projeto ou usuário]

---

## Modelo: `.specs/[feature]/tasks.md`

```markdown
# [Feature] Tasks

**Design**: `.specs/[feature]/design.md`
**Status**: Draft | Approved | In Progress | Done

---

## Execution Plan

### Phase 1: Foundation (Sequential)

Tasks that must be done first, in order.
```

T1 → T2 → T3

```

### Phase 2: Core Implementation (Parallel OK)
After foundation, these can run in parallel.

```

     ┌→ T4 ─┐

T3 ──┼→ T5 ─┼──→ T8
└→ T6 ─┘
T7 ──────→

```

### Phase 3: Integration (Sequential)
Bringing it all together.

```

T8 → T9

---

## Divisão de tarefas

### T1: [Criar interface X]

**O que**: [Uma frase: entrega exata]
**Onde**: `src/path/to/file.ts`
**Depende de**: Nenhum
**Reutilizações**: `src/existing/BaseInterface.ts`
**Requisito**: [FEAT]-01

**Ferramentas**:

-MCP: `filesystem` (ou NENHUM)
- Habilidade: NENHUMA

**Concluído quando**:

- [] Interface definida com todos os métodos desde o design
- [] Tipos exportados corretamente
- [] Sem erros de TypeScript

**Testes**: [unidade/e2e/integração/nenhum — da matriz de cobertura]
**Gate**: [rápido/completo/compilação — a partir de comandos de verificação de portão]

---

### T2: [Implementar Serviço Y] [P]

**O que**: [entrega exata]
**Onde**: `src/services/YService.ts`
**Depende de**: T1
**Reutilizações**: padrões `src/services/BaseService.ts`

**Ferramentas**:

-MCP: `filesystem`, `context7`
- Habilidade: NENHUMA

**Concluído quando**:

- [ ] Implementa interface do T1
- [] Lida com casos de erro desde o design
- [] Aprovações na verificação do portão: `[quick gate command from TESTING.md]`
- [] Contagem de testes: [N] testes aprovados (sem exclusões silenciosas)

**Testes**: unidade
**Portão**: rápido

---

### T3: [Criar componente Z] [P]

**O que**: [entrega exata]
**Onde**: `src/components/ZComponent.tsx`
**Depende de**: T1
**Reutilizações**: `src/components/BaseComponent.tsx`

**Ferramentas**:

-MCP: `filesystem`
- Habilidade: NENHUMA

**Concluído quando**:

- [] O componente é renderizado corretamente
- [] Lida com adereços da interface
- [] Segue padrões de componentes existentes
- [] Aprovações na verificação do portão: `[quick gate command from TESTING.md]`
- [] Contagem de testes: [N] testes aprovados (sem exclusões silenciosas)

**Testes**: unidade
**Portão**: rápido

---

### T4: [Adicionar um recurso a Y]

**O que**: [entrega exata]
**Onde**: `src/services/YService.ts` (modificar)
**Depende de**: T2, T3
**Reutilizações**: padrões de serviço existentes

**Ferramentas**:

-MCP: `filesystem`, `github`
- Habilidade: `api-design`

**Concluído quando**:

- [] O recurso funciona de acordo com os critérios de aceitação
- [] Aprovações na verificação do portão: `[full gate command from TESTING.md]`
- [] Contagem de testes: [N] testes aprovados (sem exclusões silenciosas)

**Testes**: integração
**Portão**: cheio

**Confirmar**: `feat([scope]): [description]`

---

## Mapa de execução paralela

Representação visual do que pode ser executado simultaneamente:

```

Phase 1 (Sequential):
  T1 ──→ T2 ──→ T3

Phase 2 (Parallel):
  T3 complete, then:
    ├── T4 [P]
    ├── T5 [P]  } Can run simultaneously
    └── T6 [P]

Phase 3 (Sequential):
  T4, T5, T6 complete, then:
    T7 ──→ T8

```

**Restrição de paralelismo:** Uma tarefa marcada como `[P]` deve ter TODOS estes:

- Sem dependências inacabadas
- O tipo de teste necessário é seguro para paralelo (de acordo com a avaliação de paralelismo TESTING.md)
- Nenhum estado mutável compartilhado com outras tarefas `[P]` na mesma fase

Se os testes de uma tarefa NÃO forem seguros em paralelo, ela DEVE ser executada sequencialmente, mesmo que seja
o código de implementação não tem dependências. A execução do teste é o gargalo.

**Como funciona a execução paralela:**

As tarefas marcadas como `[P]` são executadas por meio de subagentes – um subagente por tarefa, iniciado simultaneamente.
Cada subagente recebe apenas sua definição de tarefa e contexto de projeto relevante (ver Subagente
Delegação em SKILL.md). O agente orquestrador espera que todos os subagentes em uma fase sejam concluídos
antes de avançar para a próxima fase.

Tarefas sequenciais (sem `[P]`) também são delegadas aos subagentes, mas um de cada vez. Isso mantém
artefatos de implementação (leituras de arquivos, saída de teste, logs de verificação de porta) fora do contexto principal.

**A função do agente orquestrador durante a execução:**
1. Escolha a(s) próxima(s) tarefa(s) a ser executada(s)
2. Forneça a cada subagente sua definição de tarefa + contexto
3. Monitore a conclusão do subagente
4. Atualize tarefas.md com resultados
5. Decida se deseja prosseguir, corrigir ou escalar

---

## Verificação de granularidade da tarefa

Antes de aprovar tarefas, verifique se elas são suficientemente granulares:

| Tarefa | Escopo | Estado |
| ------------------------------- | ------------- | ------------ |
| T1: Criar entrada de e-mail | 1 componente | ✅ Granulado |
| T2: Adicionar função de validação | 1 função | ✅ Granulado |
| T3: Criar formulário com todos os campos | Mais de 5 componentes | ❌ Divida! |
| T4: Conecte-se à API | 1 função | ✅ Granulado |

**Verificação de granularidade**:

- ✅ 1 componente / 1 função / 1 endpoint = Bom
- ⚠️ 2-3 coisas relacionadas no mesmo arquivo = OK se coeso
- ❌ Vários componentes ou arquivos = DEVE dividir

---

## Verificação cruzada de definição de diagrama

Antes de aprovar tarefas, verifique se o diagrama de execução está consistente com as definições da tarefa. Esses são artefatos independentes que podem variar — o diagrama é desenhado para maior clareza visual, enquanto os corpos das tarefas são escritos para maior precisão. Ambos devem concordar.
Para cada tarefa, verifique:

| Tarefa | Depende de (corpo da tarefa) | Programas de diagramas | Estado |
| ---- | ---------------------- | ------------- | ------ |
| T[N] | [departamentos do corpo] | [deps das setas do diagrama] | ✅ Correspondência ou ❌ Incompatibilidade |

**Regras:**

- Cada `Depends on` em um corpo de tarefa deve ter uma seta correspondente no diagrama.
- Cada seta no diagrama deve corresponder a um `Depends on` no corpo da tarefa alvo.
- As tarefas mostradas como paralelas (`[P]`) no diagrama não devem depender umas das outras.
- Se uma tarefa depende de outra tarefa na mesma fase paralela, elas NÃO são paralelas — corrija o diagrama ou remova o sinalizador `[P]`.

---

## Teste de validação de colocalização

Antes de aprovar tarefas, verifique se o campo `Tests` de CADA tarefa é consistente com a Matriz de Cobertura de Teste TESTING.md. Este é um portão difícil – as tarefas que falham nesta verificação DEVEM ser corrigidas.

Para cada tarefa, verifique: a tarefa cria ou modifica uma camada de código que possui um tipo de teste obrigatório na matriz de cobertura? Se sim, o campo `Tests` da tarefa DEVE corresponder.

| Tarefa | Camada de código criada/modificada | Matriz requer | A tarefa diz | Estado |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T[N]: [nome] | [camada da matriz de cobertura] | [tipo de teste] | [campo Testes da tarefa] | ✅ OK ou ❌ VIOLAÇÃO |

**Regras:**

- “Testado em outra tarefa” NÃO é uma justificativa válida para `Tests: none`. Isso é o adiamento do teste – o antipadrão exato que essa validação evita.
- `Tests: none` só é válido quando a matriz de cobertura diz "nenhum" para essa camada de código.
- Se uma tarefa criar MÚLTIPLAS camadas de código (por exemplo, serviço + controlador), use o tipo de teste MAIS ALTO exigido por qualquer uma delas.
- Qualquer ❌ VIOLAÇÃO → reestruture a tarefa para incluir os testes necessários antes de prosseguir.

**Resolvendo dependências de compilação:**

Quando uma tarefa cria código que não pode ser testado até que uma tarefa posterior seja concluída (por exemplo, um controlador que precisa de fiação de módulo antes que seus testes e2e possam ser executados), NÃO adie os testes para uma tarefa separada. Em vez disso, reestruture:

1. **Mesclar para frente:** Mova os testes da tarefa não testável para a tarefa mais antiga onde eles se tornam executáveis (por exemplo, a tarefa de fiação inclui testes de fiação + e2e para o controlador que ela habilita).
2. **Mesclar para trás:** Absorva a dependência de bloqueio na tarefa atual para que ela se torne autotestável (por exemplo, a tarefa do controlador inclui seu próprio registro de módulo).

Escolha qualquer opção que mantenha as tarefas atômicas e coesas. O objetivo: nenhuma tarefa produz código não verificado. Se o código não puder ser testado na tarefa que o cria, os limites da tarefa estão errados.

---

## Dicas

- **[P] = Paralelo OK** — Marcar tarefas que podem ser executadas simultaneamente
- **Reutilizações = Economia de token** — Sempre faça referência ao código existente
- **Ferramentas por tarefa** — MCPs e habilidades evitam abordagens erradas
- **Dependências são portas** — Limpe o que bloqueia o quê
- **Concluído quando = Testável** — Se você não puder verificar, reescreva
- **ID do requisito = rastreável** — Cada tarefa remonta a um requisito de especificação
- **Um commit por tarefa** — Planeje o formato da mensagem de commit com antecedência

---

## Padrões de verificação de tarefas

Cada tarefa DEVE incluir:

**Concluído quando lista de verificação:**

- Resultados específicos e testáveis
- Critérios de aprovação/reprovação
- O comando de teste específico da tabela Gate Check Commands
- Contagem de aprovação esperada (evita a exclusão silenciosa do teste)

**Verificar seção:**

- Comandos para comprovar funcionalidade
- Resultados esperados
- Indicadores de sucesso

**Estrutura:**

```markdown
### T1: [Task name]

**What:** [Deliverable]
**Where:** [File path]
**Tests**: [unit/e2e/integration/none]
**Gate**: [quick/full/build]

**Done when:**

- [ ] [Specific outcome]
- [ ] [Specific outcome]
- [ ] Gate check passes: `[command from Gate Check Commands]`
- [ ] Test count: [N] tests pass (no silent deletions)

**Verify:**
[Command to prove it works]
[Expected output/behavior]
```

**Verificação de qualidade:**

- A tarefa pode ser verificada sem julgamento humano?
- Os critérios de sucesso são binários (aprovado/reprovado)?
- A verificação pode ser automatizada?
