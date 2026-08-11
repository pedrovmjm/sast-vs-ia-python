# Especifique

**Objetivo**: Capturar O QUE construir com requisitos testáveis e rastreáveis.

**Idioma:** gere `spec.md` em pt-BR. Traduza histórias de usuário, critérios de aceite, edge cases, headings, labels e placeholders. Preserve IDs de requisito, paths, nomes técnicos e expressões formais necessárias.

Se o recurso tiver áreas cinzentas ambíguas (múltiplas abordagens válidas para comportamento voltado ao usuário), o agente acionará automaticamente o processo [discutir áreas cinzentas](discuss.md) nesta fase. Para recursos claros e bem definidos, vai direto para a próxima fase.

## Processo

### 1. Esclareça os requisitos

Você é um parceiro pensante, não um entrevistador. Comece aberto – deixe o usuário descartar seu modelo mental. Siga a energia: seja o que for que eles enfatizem, mergulhe nisso.

Pergunte em conversação (não como uma lista de verificação):

- "Que problema você está resolvendo?"
- “Quem é o usuário e qual a sua dor?”
- "Como é o sucesso?"

Se necessário:

- "Quais são as restrições (tempo, tecnologia, recursos)?"
- "O que está explicitamente fora do escopo?"

**Desafie a imprecisão.** Nunca aceite respostas confusas. "Bom" significa o quê? "Usuários" significa quem? "Simples" significa como? Torne o abstrato concreto: "Mostre-me como usar isso." "Como é isso realmente?"

**Saiba quando parar.** Quando você entender o que eles estão construindo, por que, para quem se destina e o que parece ser feito, ofereça-se para prosseguir.

### 2. Capture histórias de usuários com prioridades

**P1 = MVP** (deve ser enviado), **P2** (deveria ter), **P3** (é bom ter)

Cada história DEVE ser **testável de forma independente** - você pode implementar e demonstrar apenas essa história.

### 3. Escreva os critérios de aceitação

Use o formato **WHEN/THEN/SHALL** - é preciso e testável:

- QUANDO [evento/ação] ENTÃO [sistema] DEVERÁ [resposta/comportamento]

---

## Modelo: `.specs/[feature]/spec.md`

```markdown
# [Feature Name] Specification

## Problem Statement

[Describe the problem in 2-3 sentences. What pain point are we solving? Why now?]

## Goals

- [ ] [Primary goal with measurable outcome]
- [ ] [Secondary goal with measurable outcome]

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature     | Reason         |
| ----------- | -------------- |
| [Feature X] | [Why excluded] |
| [Feature Y] | [Why excluded] |

---

## User Stories

### P1: [Story Title] ⭐ MVP

**User Story**: As a [role], I want [capability] so that [benefit].

**Why P1**: [Why this is critical for MVP]

**Acceptance Criteria**:

1. WHEN [user action/event] THEN system SHALL [expected behavior]
2. WHEN [user action/event] THEN system SHALL [expected behavior]
3. WHEN [edge case] THEN system SHALL [graceful handling]

**Independent Test**: [How to verify this story works alone - e.g., "Can demo by doing X and seeing Y"]

---

### P2: [Story Title]

**User Story**: As a [role], I want [capability] so that [benefit].

**Why P2**: [Why this isn't MVP but important]

**Acceptance Criteria**:

1. WHEN [event] THEN system SHALL [behavior]
2. WHEN [event] THEN system SHALL [behavior]

**Independent Test**: [How to verify]

---

### P3: [Story Title]

**User Story**: As a [role], I want [capability] so that [benefit].

**Why P3**: [Why this is nice-to-have]

**Acceptance Criteria**:

1. WHEN [event] THEN system SHALL [behavior]

---

## Edge Cases

- WHEN [boundary condition] THEN system SHALL [behavior]
- WHEN [error scenario] THEN system SHALL [graceful handling]
- WHEN [unexpected input] THEN system SHALL [validation response]

---

## Requirement Traceability

Each requirement gets a unique ID for tracking across design, tasks, and validation.

| Requirement ID | Story       | Phase  | Status  |
| -------------- | ----------- | ------ | ------- |
| [FEAT]-01      | P1: [Story] | Design | Pending |
| [FEAT]-02      | P1: [Story] | Design | Pending |
| [FEAT]-03      | P2: [Story] | -      | Pending |

**ID format:** `[CATEGORY]-[NUMBER]` (e.g., `AUTH-01`, `CART-03`, `NOTIF-02`)

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

**Coverage:** X total, Y mapped to tasks, Z unmapped ⚠️

---

## Success Criteria

How we know the feature is successful:

- [ ] [Measurable outcome - e.g., "User can complete X in < 2 minutes"]
- [ ] [Measurable outcome - e.g., "Zero errors in Y scenario"]
```

---

## Dicas

- **P1 = Vertical Slice** — Um recurso completo e demonstrável, não apenas backend ou frontend
- **WHEN/THEN é código** — Se você não pode escrevê-lo como um teste, reescreva-o
- **IDs de requisitos são obrigatórios** — Cada história é mapeada para IDs rastreáveis
- **Casos extremos são importantes** — O que quebra? O que está vazio? O que é enorme?
- **Fora do escopo evita fluência** — Se não estiver aqui, não será construído
- **Confirmar antes de discutir** — O usuário deve aprovar as especificações antes de passar para a fase de discussão
