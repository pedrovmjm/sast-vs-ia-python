# Modo Rápido

**Objetivo:** Executar tarefas pequenas e ad hoc com os mesmos princípios de qualidade, mas sem cerimônia completa de pipeline.

**Acionador:** "Correção rápida", "Tarefa rápida", "Pequena alteração", "Correção de bug", "Basta fazer X"

## Quando usar

| Use o modo rápido | Usar pipeline completo |
| -------------------------- | ----------------------------------- |
| Correções de bugs com causa conhecida | Novos recursos com múltiplas histórias |
| Mudanças de configuração | Mudanças arquitetônicas |
| Pequenos ajustes na interface do usuário | Recursos que exigem decisões de design |
| Adicionando campo simples em entidade existente, sem novo endpoint ou contrato publico | Recursos multicomponentes |
| Roteiros únicos | Qualquer coisa com escopo pouco claro |
| Atualizações de dependências | Recursos que exigem histórias de usuários |

**Regra prática:** Se você puder descrevê-lo em uma frase E ele abrange ≤3 arquivos, é uma tarefa rápida.

**Nunca use modo rapido** para criar novo dominio, entidade, tabela/colecao, CRUD, endpoint, contrato publico, repository ou service. Esse tipo de trabalho e no minimo escopo medio e deve gerar `.specs/features/<slug>/spec.md` antes da implementacao.

## Processo

### 1. Descreva a tarefa

O usuário fornece uma descrição clara de uma frase. Se for vago, peça detalhes:

- ❌ "Consertar o login" → Pergunte: "O que está quebrado? O que deveria acontecer em vez disso?"
- ✅ "Correção: o botão de login retorna 401 porque a atualização do token ignora a verificação expirada"

### 2. Verificação pré-implementação

Antes de escrever o código, indique:

```
Quick Task: [description]
Files: [list ONLY files to touch]
Approach: [one sentence]
Verify: [how to prove it works]
```

Obtenha a aprovação do usuário antes de continuar. Se a verificação de pré-implementação revelar que a tarefa é maior do que o esperado (>3 arquivos, dependências pouco claras, decisões de design necessárias), recomende o pipeline completo.

### 3. Implementar

Siga [coding-principles.md](coding-principles.md):

- Código mais simples que funciona
- Toque SOMENTE nos arquivos listados
- Sem aumento de escopo - conserte a coisa, nada mais

### 4. Verifique

Execute a verificação a partir da etapa 2. Marque como concluído somente após a verificação ser aprovada.

### 5. Comprometa-se

Commit atômico seguindo [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>): <description>
```

Use modo imperativo, letras minúsculas, sem ponto final. Consulte [implement.md](implement.md) para obter a tabela completa de tipos.

Exemplos:

-`fix(auth): prevent 401 on token refresh`
-`feat(settings): add dark mode toggle`
-`chore(deps): update eslint to v9`

### 6. Rastrear

Atualize `.specs/project/STATE.md` com registro de tarefa rápida (consulte a seção Tarefas rápidas state-management.md).

---

## Estrutura

As tarefas rápidas são separadas dos recursos planejados:

```
.specs/
└── quick/
    └── NNN-slug/
        ├── TASK.md       # Description + verification
        └── SUMMARY.md    # O que foi feito + commit
```

**Modelo TAREFA.md:**

```markdown
# Tarefa rápida NNN: [Título]

**Data:** [data]
**Status:** Concluída | Em andamento | Bloqueada

## Descrição

[Uma frase: o quê e por quê]

## Arquivos alterados

- `src/path/to/file.ts` — [o que mudou]
- `src/path/to/other.ts` — [o que mudou]

## Verificação

- [ ] [Como verificar que funciona]
- [ ] [Comportamento esperado após a correção]

## Commit

`[hash]` — [mensagem do commit]
```

---

## Guarda-corpos

- **Máximo de 3 arquivos** — Se mais, use o pipeline completo
- **Máximo de 1 hora** — Se for mais longo, o escopo está errado
- **Sem decisões de design** — Se você estiver escolhendo entre abordagens, use o pipeline completo
- **Sem novas dependências** — A adição de pacotes requer uma revisão completa do pipeline
- **Acompanhe tudo** — Até mesmo tarefas rápidas recebem commits e entradas STATE.md

---

## Dicas

- **Rápido ≠ desleixado** — Os mesmos princípios de codificação se aplicam, apenas com menos cerimônia
- **Em caso de dúvida, vá em frente** — É melhor planejar demais do que enviar código quebrado
- **Composto de tarefas rápidas** — Se você estiver realizando mais de 5 tarefas rápidas para a mesma área, é um recurso que precisa de planejamento
- **Verifique antes de marcar como concluído** — O ponto principal é a qualidade, mesmo para pequenas tarefas
