# Mapeamento de brownfield

**Acionador:** "Mapear base de código", "Analisar código existente", "Documentar arquitetura atual"

**Objetivo:** compreender a estrutura existente do projeto antes de adicionar recursos.

**Idioma:** gere todos os documentos em pt-BR. Traduza headings, labels, placeholders e instruções dos templates. Preserve apenas paths, nomes de ferramentas, comandos, versões, APIs e termos técnicos consagrados quando necessário.

## Processo

Antes de começar, verifique se a habilidade `codenavi` está disponível para exploração de código (consulte Integrações de habilidades em SKILL.md). Se disponível, prefira-o para todas as tarefas de descoberta e navegação abaixo.

**Abordagem de alto nível:**

1. Explore a estrutura de diretórios sistematicamente
2. Identifique a pilha de tecnologia a partir de manifestos de dependência
3. Extraia padrões de amostras de código representativas
4. Documente convenções e arquiteturas observadas
5. Catalogue integrações externas
6. Identifique preocupações: dívida tecnológica, bugs conhecidos, riscos de segurança, gargalos de desempenho, áreas frágeis

**Profundidade da análise:**

- Amostra de 5 a 10 arquivos representativos por categoria
- Concentre-se na consistência e nos padrões, não na cobertura exaustiva
- Extraia exemplos reais, não suposições

## Saída: 7 arquivos em .specs/codebase/

---

### 1. STACK.md

**Objetivo:** Documentar pilha de tecnologia e dependências.

**Limite de tamanho:** 2.000 tokens (aproximadamente 1.200 palavras)

** Extraído de: **

- Arquivos de manifesto de dependência
- Configuração de compilação
- Configuração de tempo de execução

**Documento:**

```markdown
# Tech Stack

**Analyzed:** [date]

## Core

- Framework: [detected name + version]
- Language: [detected name + version]
- Runtime: [detected name + version]
- Package manager: [detected manager]

## Frontend (if applicable)

- UI Framework: [name + version]
- Styling: [approach + tools]
- State Management: [library/pattern]
- Form Handling: [library if present]

## Backend (if applicable)

- API Style: [REST/GraphQL/gRPC + framework]
- Database: [ORM/query builder + database system]
- Authentication: [library/approach]

## Testing

- Unit: [framework]
- Integration: [framework]
- E2E: [framework if present]

## External Services

- [Category]: [Service name]
- [Category]: [Service name]

## Development Tools

- [Tool category]: [Tool name]
```

**Instruções:**

- Extrair de arquivos de dependência reais
- Incluir versões para dependências principais
- Categorizar por propósito
- Observe explicitamente as estruturas de teste

---

### 2. ARQUITETURA.md

**Objetivo:** Documentar padrões de arquitetura e fluxo de dados.

**Limite de tamanho:** 4.000 tokens (aproximadamente 2.400 palavras)

** Extraído de: **

- Organização de diretório
- Análise da estrutura do código
- Padrões repetidos em arquivos

**Documento:**

```markdown
# Architecture

**Pattern:** [Identified pattern - monolith/microservices/modular/etc]

## High-Level Structure

[Create diagram/description based on actual organization]

## Identified Patterns

### [Pattern Name]

**Location:** [where this pattern lives]
**Purpose:** [what this achieves]
**Implementation:** [how it's structured]
**Example:** [reference to actual file/function]

### [Pattern Name]

[Same structure]

## Data Flow

### [Key Flow - e.g., Authentication/Payment/etc]

[Map actual flow from code analysis]

### [Key Flow]

[Map actual flow]

## Code Organization

**Approach:** [feature-based/layer-based/domain-driven/etc]

**Structure:**
[Document actual directory organization]

**Module boundaries:**
[How code is divided into modules/packages]
```

**Instruções:**

- Identifique padrões de código real, não de suposições
- Documentar decisões arquitetônicas observadas
- Criar diagramas de fluxo para caminhos críticos
- Referência de exemplos concretos da base de código

---

### 3. CONVENÇÕES.md

**Objetivo:** Estilo de código do documento e convenções de nomenclatura.

**Limite de tamanho:** 3.000 tokens (aproximadamente 1.800 palavras)

** Extraído de: **

- Análise de 5 a 10 arquivos representativos
- Identificação de padrões consistentes
- Observando convenções reais em uso

**Documento:**

```markdown
# Code Conventions

## Naming Conventions

**Files:**
[Observed pattern - document actual approach]
Examples: [actual filenames from codebase]

**Functions/Methods:**
[Observed pattern]
Examples: [actual function names]

**Variables:**
[Observed pattern]
Examples: [actual variable names]

**Constants:**
[Observed pattern]
Examples: [actual constant names]

## Code Organization

**Import/Dependency Declaration:**
[Observed ordering pattern]
[Example from actual file]

**File Structure:**
[Observed organization within files]
[Example from actual file]

## Type Safety/Documentation

**Approach:** [Type system/documentation approach used]
[Example from actual code]

## Error Handling

**Pattern:** [Observed error handling approach]
[Example from actual code]

## Comments/Documentation

**Style:** [When/how comments are used]
[Example from actual code]
```

**Instruções:**

- Extraia padrões de amostras de código reais
- Documente convenções observadas, não convenções ideais
- Incluir exemplos concretos da base de código
- Observe exceções ou variações quando encontradas

---

### 4. ESTRUTURA.md

**Objetivo:** Layout do diretório de documentos e organização de arquivos.

**Limite de tamanho:** 2.000 tokens (aproximadamente 1.200 palavras)

**Documento:**

```markdown
# Project Structure

**Root:** [project root path]

## Directory Tree

[Visual tree representation - max 3 levels deep]

## Module Organization

### [Module/Area Name]

**Purpose:** [what this area handles]
**Location:** [where files live]
**Key files:** [important files in this area]

### [Module/Area Name]

[Same structure]

## Where Things Live

**[Capability/Feature]:**

- UI/Interface: [location]
- Business Logic: [location]
- Data Access: [location]
- Configuration: [location]

**[Capability/Feature]:**
[Same structure]

## Special Directories

**[Directory name]:**
**Purpose:** [what belongs here]
**Examples:** [key files in this directory]
```

**Instruções:**

- Crie uma visualização em árvore da estrutura de diretórios real
- Limite a profundidade para manter a legibilidade
- Documentar a finalidade dos principais diretórios
- Mapear capacidades para locais físicos

---

### 5. TESTE.md

**Objetivo:** Documentar a infraestrutura e os padrões de teste.

**Limite de tamanho:** 4.000 tokens (aproximadamente 2.400 palavras)

**Documento:**

```markdown
# Testing Infrastructure

## Test Frameworks

**Unit/Integration:** [framework name + version]
**E2E:** [framework name + version]
**Coverage:** [tool if used]

## Test Organization

**Location:** [where tests live]
**Naming:** [test file naming pattern]
**Structure:** [how tests are organized]

## Testing Patterns

### Unit Tests

**Approach:** [observed pattern]
**Location:** [where unit tests live]
[Description of actual pattern used]

### Integration Tests

**Approach:** [observed pattern]
**Location:** [where integration tests live]
[Description of actual pattern used]

### E2E Tests

**Approach:** [observed pattern if present]
**Location:** [where E2E tests live]
[Description of actual pattern used]

## Test Execution

**Commands:** [how to run tests]
**Configuration:** [test configuration approach]

## Coverage Targets

**Current:** [if measurable]
**Goals:** [if documented]
**Enforcement:** [if automated]

## Test Coverage Matrix

Analyze the codebase to determine which code layers require which test types.
For each layer, document the required test type, file location pattern, and run command.

| Code Layer | Required Test Type          | Location Pattern       | Run Command |
| ---------- | --------------------------- | ---------------------- | ----------- |
| [layer]    | [unit/integration/e2e/none] | [glob or path pattern] | [command]   |

## Parallelism Assessment

| Test Type | Parallel-Safe? | Isolation Model | Evidence                      |
| --------- | -------------- | --------------- | ----------------------------- |
| [type]    | [Yes/No]       | [description]   | [file/pattern that proves it] |

## Gate Check Commands

| Gate Level | When to Use                            | Command                     |
| ---------- | -------------------------------------- | --------------------------- |
| Quick      | After tasks with unit tests only       | [unit test command]         |
| Full       | After tasks with e2e/integration tests | [unit + e2e commands]       |
| Build      | After phase completion                 | [build + lint + unit + e2e] |
```

**Instruções:**

- Identificar estruturas de teste a partir de dependências e código
- Documentar padrões de teste reais observados
- Observe a abordagem da organização do teste
- Incluir instruções de execução
- **Matriz de cobertura de teste:** Amostra de 5 a 10 arquivos de teste existentes para identificar quais camadas são testadas e como. Observe os locais dos arquivos de teste em relação à origem para determinar padrões. Extraia comandos de execução de `package.json`, `project.json`, `Makefile`, configuração CI. Marque camadas sem testes existentes como "nenhum" com uma nota em CONCERNS.md.
- **Avaliação de paralelismo:** Sinais NÃO seguros para paralelo: conexão de banco de dados compartilhada (mesma URL da configuração), limpeza em nível de tabela em `beforeEach`/`afterAll` (`.del()`, `DELETE FROM`, `TRUNCATE`), redefinição de estado simulado compartilhada em globais. Sinais de segurança paralela: criação de banco de dados por teste (Testcontainers, esquema dinâmico, SQLite na memória), namespace de dados (todos os dados codificados por ID de teste exclusivo), nenhum estado mutável compartilhado entre arquivos de teste, todos os deps simulados (`jest.fn()`, `vi.fn()`).
- **Comandos de verificação de portão:** Extraia dos comandos reais do projeto - não invente comandos.

---

### 6. INTEGRAÇÕES.md

**Objetivo:** Documentar integrações de serviços externos.

**Limite de tamanho:** 5.000 tokens (aproximadamente 3.000 palavras)

**Documento:**

```markdown
# External Integrations

## [Service Category]

**Service:** [service name]
**Purpose:** [what this integration provides]
**Implementation:** [where integration lives in code]
**Configuration:** [how service is configured]
**Authentication:** [auth approach if applicable]

## [Service Category]

[Same structure]

## API Integrations

### [API Name]

**Purpose:** [what this API provides]
**Location:** [where API client/code lives]
**Authentication:** [auth method]
**Key endpoints:** [major endpoints used]

## Webhooks

### [Webhook Source]

**Purpose:** [what events are handled]
**Location:** [webhook handler location]
**Events:** [event types processed]

## Background Jobs

**Queue system:** [system if used]
**Location:** [where job definitions live]
**Jobs:** [key background jobs]
```

**Instruções:**

- Identificar integrações a partir de código e configuração
- Abordagens de autenticação de documentos
- Observe os manipuladores de webhook, se presentes
- Incluir infraestrutura de trabalho em segundo plano

---

### 7. PREOCUPAÇÕES.md
**Objetivo:** Apresentar avisos acionáveis ​​sobre a base de código: dívida tecnológica, bugs conhecidos, falhas de segurança, gargalos de desempenho, áreas frágeis, limites de escalabilidade, dependências arriscadas, recursos ausentes e lacunas na cobertura de testes.

**Limite de tamanho:** 5.000 tokens (aproximadamente 3.000 palavras)

Consulte [concerns.md](concerns.md) para obter o modelo completo, diretrizes e exemplos.

**Instruções:**

- Documente apenas questões respaldadas por evidências (caminhos de arquivos, medições, etapas de reprodução)
- Incluir abordagens de correção, não apenas problemas
- Omitir seções sem descobertas
- Priorizar por risco/impacto
- Use um tom profissional e orientado para a solução

---

## Orçamento de contexto total

**Combinado:** aproximadamente 19.000 tokens (10% da janela de contexto)
**Aceitável para:** Projetos brownfield que exigem compreensão da base de código
**Estratégia de carregamento:** carregue documentos relevantes sob demanda com base na tarefa
