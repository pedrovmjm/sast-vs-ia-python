# Transferência de sessão

## Pausar trabalho

**Acionador:** "Pausar trabalho", "Terminar sessão", "Criar transferência"

**Objetivo:** Verificar o estado atual para retomada.

**Saída:** `.specs/HANDOFF.md` (substitui o anterior)

**Tamanho alvo:** ~500 tokens

**Estrutura:**

```markdown
# Handoff

**Date:** [ISO timestamp]
**Feature:** [feature name]
**Task:** [task identifier] - [brief status]

## Completed ✓

- [Completed work item]
- [Completed work item]

## In Progress

- [Current work]([percentage or status])
- Specific location: [file:line if applicable]

## Pending

- [Next immediate step]
- [Following step]

## Blockers

- [Blocker description] - [impact]

## Context

- Branch: [git branch if applicable]
- Uncommitted: [files with changes]
- Related decisions: [STATE.md references if applicable]
```

**Instruções:**

- Foco em informações acionáveis para retomada
- Incluir referências de arquivo/linha específicas quando relevante
- Observe explicitamente as alterações não confirmadas
- Referência de entradas STATE.md relacionadas, se aplicável

## Retomar trabalho

**Acionador:** "Retomar trabalho", "Continuar", "Transferir carga"

**Processo:**

1. Carregue HANDOFF.md
2. Carregue STATE.md para contexto
3. Resuma a posição atual
4. Proponha a próxima ação

**Padrão de resposta:**

- "Retomando [recurso] em [tarefa]"
- "Concluído: [resumo]"
- "Próximo: [ação imediata]"
- "Continuar com [etapa específica]?"