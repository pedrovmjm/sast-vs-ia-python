# Especifique: discuta as áreas cinzentas

**Objetivo:** capturar COMO o usuário visualiza o recurso quando a especificação tem áreas ambíguas. Esta NÃO é uma fase separada — ela é acionada em Especificar quando o agente detecta áreas cinzentas que precisam de entrada do usuário.

**Acionador:** automaticamente quando áreas cinzentas são detectadas durante a criação de especificações ou explicitamente por meio de "discutir recurso", "como isso deve funcionar?", "capturar contexto"

**Quando acionar (detecção automática):** A especificação contém um comportamento voltado para o usuário que pode ocorrer de várias maneiras E o usuário não expressou uma preferência. Se a especificação for clara e inequívoca, ignore isso completamente.

**Quando NÃO acionar:** Trabalho de infraestrutura, operações CRUD, contratos de API bem definidos, qualquer coisa onde o "como" é óbvio a partir do "o quê".

## Por que esta fase existe

As especificações capturam O QUE construir. O design captura a arquitetura. Mas nenhum deles captura a visão do usuário para áreas ambíguas – preferências de layout, padrões de interação, estilo de tratamento de erros, tom do conteúdo. Sem isso, o agente adivinha. Com isso, o agente constrói o que o usuário realmente imaginou.

A saída — `context.md` — alimenta diretamente o Design e as Tarefas:

- **O design lê** para saber quais decisões são bloqueadas ou flexíveis
- **Tarefas lêem** para incluir comportamentos específicos nas definições de tarefas

## Processo

### 1. Analise o recurso

Leia `.specs/features/[feature]/spec.md` e identifique o domínio:

| Domínio | Áreas cinzentas para explorar |
| ------------------------------ | ---------------------------------------------------------------------------- |
| Algo que os usuários **VERÃO** | Layout, densidade, interações, estados vazios, hierarquia visual |
| Usuários de algo **CALL** (API) | Formato de resposta, erros, autenticação, controle de versão, limitação de taxa |
| Usuários de algo **RUN** (CLI) | Formato de saída, sinalizadores, modos, tratamento de erros, verbosidade |
| Algo que os usuários **LEIAM** | Estrutura, tom, profundidade, fluxo, navegação |
| Algo sendo **ORGANIZADO** | Critérios de agrupamento, nomenclatura, duplicatas, exceções |

Gere de 3 a 4 áreas cinzentas **específicas de recursos**. Não categorias genéricas, mas decisões concretas para ESTE recurso.

### 2. Apresentar áreas cinzentas

Apresente o limite do recurso (de spec.md) e as áreas cinzas ao usuário. Deixe-os escolher o que discutir. NÃO inclua a opção “pular tudo” — o usuário invocou esta fase para discutir.

### 3. Aprofunde-se em cada área

Para cada área selecionada:

1. Faça de 3 a 4 perguntas concretas com opções específicas (não categorias vagas)
2. Após as perguntas, marque: "Mais sobre [área] ou seguir em frente?"
3. Se mais → pergunte mais 3-4, verifique novamente
4. Depois de todas as áreas → "Pronto para criar contexto?"

**Elaboração da pergunta:**

- As opções devem ser concretas ("Layout do cartão" e não "Opção A")
- Cada resposta deve informar a próxima pergunta
- Incluir "Você decide" como uma opção quando razoável - captura a discrição do agente

### 4. Proteção do escopo (CRÍTICO)

O limite do recurso de spec.md é **fixo**. A discussão esclarece COMO implementar, nunca SE adicionar novos recursos.

**Permitido:** "Como as postagens devem ser exibidas?" (esclarecendo a ambiguidade)
**Não permitido:** "Devemos também adicionar comentários?" (nova capacidade)

Quando o usuário sugere aumento de escopo: "Parece um recurso separado. Vou anotá-lo em Ideias Adiadas. Voltar para [área atual]."

### 5. Escreva context.md

---

## Modelo: `.specs/features/[feature]/context.md`

```markdown
# [Feature] Context

**Gathered:** [date]
**Spec:** `.specs/features/[feature]/spec.md`
**Status:** Ready for design

---

## Feature Boundary

[Clear statement of what this feature delivers — the scope anchor from spec.md]

---

## Implementation Decisions

### [Area 1 that was discussed]

- [Specific decision made]
- [Another decision if applicable]

### [Area 2 that was discussed]

- [Specific decision made]

### [Area 3 that was discussed]

- [Specific decision made]

### Agent's Discretion

[Areas where user explicitly said "you decide" — agent has flexibility here during design/implementation]

---

## Specific References

[Any "I want it like X" moments, product references, specific behaviors, interaction patterns mentioned during discussion]

[If none: "No specific requirements — open to standard approaches"]

---

## Deferred Ideas

[Ideas that came up during discussion but belong in other features/phases. Captured here so they're not lost, but explicitly out of scope]

[If none: "None — discussion stayed within feature scope"]
```

---

## Dicas

- **Decisões, não visão** — "Layout baseado em cartão com sombras sutis" é uma decisão. "Deve parecer moderno" não é.
- **O escopo é sagrado** — Ideias diferidas capturam o aumento do escopo sem perder ideias
- **Usuário = visionário, Agente = construtor** — Pergunte sobre como eles imaginam isso, não sobre implementação técnica
- **Não pergunte sobre:** Arquitetura técnica, desempenho, detalhes de implementação — esse é o trabalho do Design
- **Confirmar antes do design** — O usuário aprova context.md antes de passar para a fase de design