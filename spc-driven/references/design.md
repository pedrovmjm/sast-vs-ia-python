# Projeto

**Objetivo**: Definir COMO construí-lo. Arquitetura, componentes, o que reutilizar.

**Idioma:** gere `design.md` em pt-BR. Traduza headings, labels, placeholders, notas de pesquisa e decisões. Preserve nomes de APIs, bibliotecas, classes, métodos, paths, comandos e diagramas Mermaid.

**Pule esta fase quando:** A mudança for direta — sem decisões arquitetônicas, sem novos padrões, sem interações de componentes a serem planejadas. Para recursos simples, o design acontece em linha durante a execução.

## Processo

### 1. Carregar contexto

Leia `.specs/features/[feature]/spec.md` antes de projetar. Se `.specs/features/[feature]/context.md` existir, carregue-o também — ele contém decisões de implementação que restringem o design (escolhas de layout, preferências de comportamento, padrões de interação). As decisões marcadas como "A critério do agente" são suas.

### 1.5. Pesquisa (opcional, mas recomendada)

Se o recurso envolver tecnologia, padrões ou integrações desconhecidas, pesquise antes de projetar. Documente as descobertas brevemente no documento de design ou como notas embutidas. Isso evita que suposições incorretas se propaguem nas tarefas.

Siga a **Cadeia de verificação de conhecimento** (consulte SKILL.md) em ordem estrita:

```
Codebase → Project docs → Context7 MCP → Web search → Flag as uncertain
```

**CRÍTICO: NUNCA presuma ou fabrique informações.** Se você não conseguir encontrar uma resposta na cadeia, diga explicitamente "Não sei" ou "Não consegui encontrar documentação para isso". Inventar uma API, um padrão ou um comportamento que não existe é muito pior do que admitir a incerteza. Suposições erradas se propagam através do design → tarefas → implementação e causam falhas em cascata.

Bons gatilhos para pesquisa: novas bibliotecas, APIs desconhecidas, recursos sensíveis ao desempenho, recursos sensíveis à segurança, padrões que você nunca usou nesta base de código antes.

### 2. Definir Arquitetura

Visão geral de como os componentes interagem. Use diagramas de sereia quando for útil. Antes de criar qualquer diagrama, verifique se a habilidade `mermaid-studio` está disponível (consulte Integrações de habilidades em SKILL.md).

### 3. Identifique a reutilização de código

**CRÍTICO**: Que código existente podemos aproveitar? Isso economiza tokens e reduz erros.

Se `.specs/codebase/CONCERNS.md` existir, verifique-o antes de projetar. Qualquer componente sinalizado como frágil, com dívidas tecnológicas ou com lacunas na cobertura de testes requer cuidado extra no design – documente como o design mitiga essas preocupações.

### 4. Definir componentes e interfaces

Cada componente: Finalidade, Localização, Interfaces, Dependências, O que reutiliza.

### 5. Definir modelos de dados

Se o recurso envolver dados, defina modelos antes da implementação.

---

## Modelo: `.specs/[feature]/design.md`

````markdown
# [Feature] Design

**Spec**: `.specs/[feature]/spec.md`
**Status**: Draft | Approved

---

## Architecture Overview

[Brief description of the architecture approach]

``` sereia
gráfico TD
    A[User Action] --> B[Component A]
    B --> C[Service Layer]
    C --> D[Data Store]
    B --> E[Component B]
```
````

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component            | Location            | How to Use                |
| -------------------- | ------------------- | ------------------------- |
| [Existing Component] | `src/caminho/para/arquivo`  | [Extend/Import/Reference] |
| [Existing Utility]   | `src/utils/arquivo`    | [How it helps]            |
| [Existing Pattern]   | `src/patterns/arquivo` | [Apply same pattern]      |

### Integration Points

| System         | Integration Method                      |
| -------------- | --------------------------------------- |
| [Existing API] | [How new feature connects]              |
| [Database]     | [How data connects to existing schemas] |

---

## Components

### [Component Name]

- **Purpose**: [What this component does - one sentence]
- **Location**: `src/caminho/para/componente/`
- **Interfaces**:
  - `methodName(param: Tipo): ReturnType` - [description]
  - `methodName(param: Tipo): ReturnType` - [description]
- **Dependencies**: [What it needs to function]
- **Reuses**: [Existing code this builds upon]

### [Component Name]

- **Purpose**: [What this component does]
- **Location**: `src/caminho/para/componente/`
- **Interfaces**:
  - `methodName (param: Tipo): ReturnType`
- **Dependências**: [Dependências]
- **Reutilizações**: [Código existente]

---

## Modelos de dados (se aplicável)

### [Nome do modelo]

```typescript
interface ModelName {
  id: string
  field1: string
  field2: number
  createdAt: Date
}
```

**Relacionamentos**: [Como isso se relaciona com outros modelos]

### [Nome do modelo]

```typescript
interface AnotherModel {
  id: string
  // ...
}
```

---

## Estratégia de tratamento de erros

| Cenário de erro | Manuseio | Impacto do usuário |
| -------------- | ------------- | ---------------- |
| [Cenário 1] | [Como é tratado] | [O que o usuário vê] |
| [Cenário 2] | [Como é tratado] | [O que o usuário vê] |

---

## Decisões técnicas (apenas as não óbvias)

| Decisão | Escolha | Justificativa |
| ----------------- | --------------- | ------------- |
| [O que decidimos] | [O que escolhemos] | [Por que - breve] |

---

## Dicas

- **Carregue o contexto primeiro** — Se context.md existir, as decisões serão bloqueadas
- **Pesquise quando tiver dúvidas** — 5 minutos de pesquisa evitam horas de retrabalho
- **Reutilizar é rei** — Cada componente deve fazer referência aos padrões existentes
- **Interfaces primeiro** — Defina contratos antes da implementação
- **Mantenha-o visual** — Os diagramas economizam 1.000 palavras (verifique a habilidade do sereia-studio em Integrações de habilidades)
- **Componentes pequenos** — Se o componente fizer mais de 3 coisas, divida-o
- **Verifique CONCERNS.md** — Se existir, sinalize as áreas frágeis que o projeto deve abordar
- **Confirmar antes das tarefas** — O usuário aprova o design antes de iniciar as tarefas
