# Gestão de Estado

**Objetivo:** Memória persistente entre sessões – decisões, bloqueadores, aprendizados.

## Estrutura

**Saída:** `.specs/project/STATE.md`

```markdown
# State

**Last Updated:** [ISO timestamp]
**Current Work:** [Feature name] - [Task identifier]

---

## Recent Decisions (Last 60 days)

### AD-[NNN]: [Decision title]([date])

**Decision:** [What was decided]
**Reason:** [Why this choice]
**Trade-off:** [What was sacrificed]
**Impact:** [How this affects implementation]

### AD-[NNN]: [Decision title]([date])

[Same structure]

---

## Active Blockers

### B-[NNN]: [Blocker description]

**Discovered:** [Date]
**Impact:** [Severity and scope]
**Workaround:** [Temporary solution if available]
**Resolution:** [Path to permanent fix]

---

## Lessons Learned

### L-[NNN]: [Learning description]

**Context:** [Situation that occurred]
**Problem:** [What went wrong]
**Solution:** [How it was resolved]
**Prevents:** [What this knowledge prevents in future]

---

## Quick Tasks Completed

| #   | Description              | Date   | Commit | Status  |
| --- | ------------------------ | ------ | ------ | ------- |
| 001 | [Quick task description] | [date] | [hash] | ✅ Done |

---

## Deferred Ideas

Ideas captured during work that belong in future features or phases. Prevents scope creep while preserving good ideas.

- [ ] [Idea description] — Captured during: [feature/phase]
- [ ] [Idea description] — Captured during: [feature/phase]

---

## Todos

Capture in-progress thoughts and action items that don't fit in active tasks.

- [ ] [TODO: action item]
- [ ] [TODO: action item]
```

## Quando atualizar

| Evento | Ação |
| -------------------------------- | -------------------------------------- |
| Escolha arquitetônica significativa | Adicionar AD-[NNN] |
| Implementação bloqueada | Adicionar B-[NNN] |
| Descoberta/aprendizagem importante | Adicionar L-[NNN] |
| Tarefa rápida concluída | Adicionar linha à tabela de Tarefas Rápidas |
| Aumento do escopo capturado | Adicionar às ideias diferidas |
| Pensamento em andamento | Adicionar a Todos |
| Fim da sessão | Atualizar "Última atualização" + "Trabalho atual" |

## Gerenciamento de tamanho (estratégia híbrida)

**Zonas:**

- 🟢 <7k tokens: Sem ação
- 🟡 7-10k tokens: Nota de rodapé "STATE.md em [X]k. Limpeza recomendada."
- 🔴 >10k tokens: Prompt ativo "STATE.md crítico ([X]k). Limpar agora?"

**Processo de limpeza:**

- Mover decisões >60 dias para STATE-ARCHIVE.md
- Mantenha apenas bloqueadores ativos
- Preservar aprendizados recentes (<60 dias)

**Validação:**

- As decisões têm uma fundamentação clara?
- Os bloqueadores incluem caminho de resolução?
- Os aprendizados são acionáveis?

---

## Preferências

Rastreie o estado comportamental do usuário em STATE.md:

```markdown
## Preferences

**Model Guidance Shown:** [ISO date or "never"]
```

**Atualizar quando:**

| Evento | Ação |
| --------------------------- | ------------------------ |
| Primeira dica de modelo dada | Definir data |
| O usuário reconhece/dispensa | Mantenha a data (não repita) |

Isso evita sugestões repetitivas, ao mesmo tempo que mantém um comportamento natural e útil.