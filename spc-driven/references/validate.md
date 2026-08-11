# Executar: validar e verificar

**Objetivo**: verificar se a implementação atende às especificações E aos princípios de codificação. Esta NÃO é uma fase separada — a verificação faz parte da conclusão de cada tarefa no Execute.

**Idioma:** gere relatórios de validação em pt-BR. Traduza headings, labels, checklists, placeholders, achados e recomendações. Preserve comandos, paths, contagens, IDs e mensagens técnicas literais.

**Dois níveis de verificação:**

1. **Verificação por tarefa (sempre):** Após implementar cada tarefa, verifique seus critérios "Concluído quando" antes de confirmar. Isso é obrigatório e automático.

2. **Validação em nível de recurso (na conclusão ou sob demanda):** Depois que todas as tarefas de um recurso (ou grupo prioritário) forem concluídas, execute uma validação abrangente. Inclui verificação de critérios de aceitação, revisão de qualidade de código e UAT opcionalmente interativo.

**O UAT interativo é acionado quando:** O recurso tem um comportamento complexo voltado para o usuário, onde o julgamento humano é importante (fluxos de interface do usuário, padrões de interação, design visual). Para trabalhos apenas de back-end ou de infraestrutura, as verificações automatizadas são suficientes.

**Acionador para validação explícita:** "Validar", "verificar trabalho", "UAT", "testar comigo", "orientar-me sobre isso"

---

## Processo

### 1. Verifique as tarefas concluídas

Acesse tarefas.md:

- [] Todas as tarefas marcadas como concluídas?
- [ ] Algum bloqueado ou parcial?

### 2. Verifique os critérios de aceitação

Para cada história de usuário em spec.md:

```markdown
### P1: [Story Title]

**Acceptance Criteria**:

1. WHEN [X] THEN [Y] → [PASS/FAIL]
2. WHEN [X] THEN [Y] → [PASS/FAIL]
```

### 3. Verifique casos extremos

Em casos extremos spec.md:

- [] [Caso extremo 1] tratado corretamente
- [] [Caso extremo 2] tratado corretamente

### 4. Execute a verificação do portão no nível de construção (OBRIGATÓRIO)

Execute a verificação de portão no nível de construção em TESTING.md. Isso NÃO é opcional.

Se TESTING.md não existir (projeto greenfield), use o comando gate acordado com o usuário durante a fase de Tarefas.

1. Execute: `[build gate command from TESTING.md, or the command agreed during planning]`
2. Código de saída diferente de zero = STOP. Não prossiga para a verificação de qualidade do código.
3. Registre os resultados:
   - Contagem total de testes: [N]
   - Aprovado: [N]
   - Falhou: [lista]
   - Ignorados: [lista — cada salto deve ser justificado]

**Verificação de integridade do teste:**

- Compare a contagem de testes atual com a contagem antes da implementação deste recurso
- Se a contagem de testes DIMINUIR: investigue o porquê. Os testes só devem ser excluídos com justificativa explícita.
- Se as afirmações foram enfraquecidas (menos específicas do que antes): sinalizar como possível regressão

### 5. Verificação de qualidade do código (OBRIGATÓRIO)

Para cada arquivo alterado, verifique em [coding-principles.md](coding-principles.md):

| Verifique | Passar? |
| ------------------------------------ | ----- |
| Nenhum recurso além do que foi solicitado |       |
| Sem abstrações para código de uso único |       |
| Nenhuma "flexibilidade" desnecessária adicionada |       |
| Tocou apenas nos arquivos necessários para a tarefa |       |
| Não "melhorou" o código não relacionado |       |
| Corresponde aos padrões/estilos existentes |       |
| O engenheiro sênior aprovaria?       |       |

❌ Algum “Não”? → Corrija antes de concluir a marcação.

### 6. UAT interativo (se for recurso voltado para o usuário)

Para cada entrega testável, apresente um teste de cada vez:

```
Test [N]: [Test Name]

Expected: [What should happen — specific and observable]

→ Does this work? Describe what you see.
```

Aguarde a resposta do usuário:

| O usuário diz | Interprete como |
| ------------------------------ | ----------------------- |
| "sim", "passar", "funciona", "próximo" | ✅ Passe |
| "pular", "não é possível testar", "n/a" | ⏭️ Pular |
| Qualquer outra coisa | ❌ Problema — registre literalmente |

**Inferência de gravidade (nunca pergunte a gravidade ao usuário):**

| A descrição do usuário contém | Gravidade inferida |
| --------------------------------------- | ----------------- |
| acidente, erro, exceção, falha, quebrado | Bloqueador |
| não funciona, errado, falta, não consigo | Principal |
| lento, estranho, desligado, menor, pequeno | Menor |
| cor, fonte, espaçamento, alinhamento, visual | Cosméticos |
| (não claro) | Principal (padrão) |

### 7. Gere planos de correção (se forem encontrados problemas)

Para cada problema encontrado durante o UAT:

1. **Diagnosticar** — Analise a base de código para encontrar a causa raiz
2. **Criar tarefa de correção** — Escreva uma definição de tarefa com:
   - O quê: a correção específica
   - Onde: Caminhos de arquivo
   - Verificar: como provar que a correção funciona
   - Feito quando: Critérios de aceitação para a correção
3. **Apresentar plano de correção** — Mostre todas as tarefas de correção ao usuário para aprovação

As tarefas de correção seguem o mesmo formato das tarefas regulares e podem ser executadas com a fase de implementação.

**Guardrail:** Máximo de três iterações de diagnóstico por problema. Se a causa raiz não for encontrada após três tentativas, sinalize para investigação humana.

### 8. Relatório

---

## Modelo de relatório de validação
```markdown
# [Feature] Validation

**Date**: [YYYY-MM-DD]
**Spec**: `.specs/features/[feature]/spec.md`

---

## Task Completion

| Task | Status     | Notes   |
| ---- | ---------- | ------- |
| T1   | ✅ Done    | -       |
| T2   | ✅ Done    | -       |
| T3   | ⚠️ Partial | [Issue] |

---

## User Story Validation

### P1: [Story Title] ⭐ MVP

| Criterion     | Result  |
| ------------- | ------- |
| WHEN X THEN Y | ✅ PASS |
| WHEN A THEN B | ✅ PASS |

**Status**: ✅ P1 Complete

### P2: [Story Title]

| Criterion     | Result             |
| ------------- | ------------------ |
| WHEN X THEN Y | ❌ FAIL - [reason] |

**Status**: ⚠️ P2 Issues

---

## Interactive UAT Results (if performed)

| #   | Test        | Result   | Details                                         |
| --- | ----------- | -------- | ----------------------------------------------- |
| 1   | [Test name] | ✅ Pass  | -                                               |
| 2   | [Test name] | ❌ Issue | [Verbatim user response] — Severity: [inferred] |
| 3   | [Test name] | ⏭️ Skip  | [Reason]                                        |

---

## Code Quality

| Principle        | Status |
| ---------------- | ------ |
| Minimum code     | ✅     |
| Surgical changes | ✅     |
| No scope creep   | ✅     |
| Matches patterns | ✅     |

---

## Edge Cases

- [x] Edge case 1: Handled correctly
- [ ] Edge case 2: NOT handled - needs fix

---

## Tests

- **Gate command**: [full command]
- **Result**: [X] passed, [Y] failed, [Z] skipped
- **Test count before feature**: [N]
- **Test count after feature**: [M]
- **Delta**: [+(M - N) new tests]
- **Skipped tests**: [list with justification for each]
- **Failures**: [list with details]

---

## Fix Plans (if issues found)

### Fix 1: [Issue description]

- **Root cause**: [What's actually wrong]
- **Fix task**: [Task definition]
- **Priority**: [Blocker/Major/Minor/Cosmetic]

---

## Requirement Traceability Update

Update spec.md requirement statuses:

| Requirement | Previous Status | New Status   |
| ----------- | --------------- | ------------ |
| [FEAT]-01   | Implementing    | ✅ Verified  |
| [FEAT]-02   | Implementing    | ❌ Needs Fix |

---

## Summary

**Overall**: ✅ Ready | ⚠️ Issues | ❌ Not Ready

**What works**: [List]

**Issues found**: [Issue 1: How to fix]

**Next steps**: [Action]
```

---

## Dicas

- **P1 primeiro** — MVP deve funcionar antes de P2/P3
- **WHEN/THEN = Teste** — Cada critério é um caso de teste
- **Seja específico** — "Não funciona" não ajuda
- **Recomende correções** — Não apenas relate problemas, crie tarefas de correção
- **A verificação de qualidade é obrigatória** — Não opcional
- **Inferir gravidade** — Nunca pergunte ao usuário "quão ruim é isso?"
- **Máximo de 3 iterações de diagnóstico** — Evita loops de investigação infinitos
- **Rastreabilidade de atualização** — Cada requisito verificado atualiza o status spec.md
