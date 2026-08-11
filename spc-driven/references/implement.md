# Executar

**Objetivo**: implementar UMA tarefa por vez. Alterações cirúrgicas. Verificar. Comprometer-se. Repita.

É aqui que o código é escrito. Cada tarefa segue o mesmo ciclo: planejar → implementar → verificar → confirmar. A verificação está integrada em cada tarefa, não em uma fase separada.

---

## OBRIGATÓRIO: Antes de iniciar qualquer implementação

**Leia [coding-principles.md](coding-principles.md) e declare:**

1. **Suposições** - O que estou assumindo? Alguma incerteza?
2. **Arquivos para tocar** - Liste APENAS os arquivos que esta tarefa requer
3. **Critérios de sucesso** - Como verificarei se isso funciona?

⚠️ **Não prossiga sem declará-los explicitamente.**

---

## Processo

**Contexto do subagente:** Quando esta tarefa é executada por um subagente, o subagente recebe
a definição da tarefa, princípios de codificação, TESTING.md e contexto de especificação/design relevante.
Todas as etapas abaixo se aplicam de forma idêntica, seja em execução no contexto principal ou em um subagente.
A única diferença: os subagentes reportam os resultados ao orquestrador em vez de
continuando para a próxima tarefa.

### 0. Listar etapas atômicas (OBRIGATÓRIO quando a fase de tarefas foi ignorada)

Se não houver `tasks.md` para este recurso, você DEVE listar as etapas atômicas antes de escrever qualquer código. Isso não é negociável — evita que o agente perca o foco e faça muitas coisas ao mesmo tempo.

```
## Execution Plan

1. [Step] → files: [list] → verify: [how] → commit: [message]
2. [Step] → files: [list] → verify: [how] → commit: [message]
3. [Step] → files: [list] → verify: [how] → commit: [message]
```

**Cada etapa deve ser:**

- UMA entrega (um componente, uma função, um endpoint, uma alteração de arquivo)
- Verificável de forma independente (pode provar que funciona antes de prosseguir)
- Comprometível de forma independente (obtém seu próprio commit atômico do git)

Se a listagem de etapas revelar >5 etapas ou dependências complexas, PARE e crie um `tasks.md` formal. A fase de Tarefas foi ignorada indevidamente.

### 1. Escolha a tarefa

De tarefas.md (se existir) ou do plano de execução acima. O usuário especifica ("implementar T3") ou sugere o próximo disponível.

### 2. Verifique as dependências

Se tarefas.md existir, verifique as dependências. Se estiver usando o plano inline, siga a ordem listada.

❌ Se bloqueado: "T3 depende de T2 o que não foi feito. Devo fazer T2 primeiro?"

### 3. Plano Estadual de Implementação

Antes de escrever o código:

```
Files: [list]
Approach: [brief description]
Success: [how to verify]
```

### 4. Escreva os testes primeiro (RED)

Se a tarefa incluir testes (de acordo com o campo Testes na matriz de cobertura tasks.md ou TESTING.md):

1. Escreva o(s) arquivo(s) de teste ANTES de escrever qualquer implementação
2. Os testes devem codificar o comportamento esperado dos critérios "Concluído quando" da tarefa
3. Execute o comando de teste - confirme os testes FAIL (estado VERMELHO)
4. Se os testes forem aprovados antes que a implementação exista, os testes são muito fracos – reescreva-os

**Restrições:**

- Os testes definem o comportamento correto independentemente da implementação
- Cada critério de aceitação de "Concluído quando" é mapeado para pelo menos uma afirmação de teste
- Casos extremos de spec.md que se aplicam a esta tarefa também obtêm casos de teste

Se a tarefa NÃO incluir testes (por exemplo, somente entidade, somente configuração), pule para a Etapa 4b.

###4b. Implementar (VERDE)

Escreva a implementação mínima necessária para satisfazer os critérios de sucesso da tarefa: passar em todos os testes relevantes (quando presentes) e atender às verificações de verificação/gate definidas quando não houver testes diretos.

**RESTRIÇÕES RÍGIDAS:**

- NÃO modifique os testes escritos na Etapa 4. Os testes são as especificações - a implementação está em conformidade com eles.
- NÃO enfraqueça as afirmações (tornando-as menos específicas para serem transmitidas com mais facilidade)
- NÃO exclua ou pule casos de teste
- NÃO use o mecanismo de ignorar/desativar/pendente da estrutura de teste para ignorar testes com falha
- Código mínimo a ser aprovado — salve melhorias estruturais para uma tarefa de refatoração

Se um teste estiver genuinamente errado (testa o comportamento errado de acordo com as especificações), PARE e pergunte ao usuário
antes de modificá-lo. Nunca altere um teste silenciosamente.

Siga [coding-principles.md](coding-principles.md):

- Código mais simples que funciona
- Toque SOMENTE nos arquivos listados
- Sem aumento de escopo

### 5. Verificação do portão (VERIFICAR)

Execute o comando gate check a partir da definição de tarefa. Isto é OBRIGATÓRIO - não "se aplicável".

1. Procure o comando para o nível Gate da tarefa (rápido/completo/build) na seção Gate Check Commands do TESTING.md e execute-o
2. Código de saída diferente de zero = STOP. Corrija a falha. Execute novamente. Não prossiga até ficar verde.
3. Confirme se a contagem de testes corresponde às expectativas (nenhum teste foi excluído ou ignorado silenciosamente)

**Portões em camadas (dos comandos de verificação de portão TESTING.md):**
| A tarefa inclui | Nível do portão | O que funciona |
| -------------------------------- | ---------- | ------------------------ |
| Apenas testes unitários | Rápido | Comando de teste de unidade |
| E2E ou testes de integração | Completo | Comandos Unidade + E2E |
| Última tarefa de uma fase | Construir | Build + lint + todos os testes |
| Sem testes (configuração, entidades, etc) | Construir | Construir + apenas lint |

A verificação do portão é determinística. O executor de teste decide se o código está correto,
não a autoavaliação do agente.

### 6. Revisão pós-gate

Depois que a verificação do portão for aprovada:

1. Verifique a contagem de testes: Existem pelo menos tantos casos de teste quanto antes? (impede a exclusão silenciosa)
2. Verifique se não há SPEC_DEVIATION: Se a implementação divergir da especificação/design, adicione um marcador:

```
// SPEC_DEVIATION: [what diverged]
// Reason: [why the deviation was necessary]
```

3. Verificação rápida de complexidade: "O engenheiro sênior sinalizaria isso como complicado demais?"
   - Sim → Simplifique, execute novamente o portão
   - Não → Prossiga para confirmar

### 7. Confirmação atômica do Git

Cada tarefa recebe seu próprio commit imediatamente após a verificação. Nunca agrupe várias tarefas em um commit.

**Formato ([Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)):**

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Tipos:**

| Tipo | Quando usar |
| ---------- | ------------------------------------------------------- |
| `feat` | Novo recurso ou capacidade |
| `fix` | Correção de bug |
| `refactor` | Alteração de código que não corrige um bug nem adiciona um recurso |
| `docs` | Somente documentação |
| `test` | Adicionando ou corrigindo testes |
| `style` | Formatação, falta de ponto e vírgula, etc. (sem alteração de código) |
| `perf` | Melhoria de desempenho |
| `build` | Construir sistema ou dependências externas |
| `ci` | Arquivos e scripts de configuração de CI |
| `chore` | Tarefas de manutenção que não modificam arquivos src ou de teste |

**Escopo:** Nome do recurso ou área do módulo, em letras minúsculas, por exemplo, `auth`, `cart`, `api`

**Regras de descrição:**

- Modo imperativo ("adicionar", não "adicionar" ou "adicionar")
- Primeira letra minúscula
- Sem ponto final no final
- Complete a frase: "Se aplicado, este commit será _[sua descrição]_"

**Alterações importantes:** Anexe `!` após tipo/escopo E adicione rodapé `BREAKING CHANGE:`:

```
feat(api)!: change authentication endpoint response format

BREAKING CHANGE: login endpoint now returns JWT in body instead of cookie
```

**Exemplos:**

```
feat(auth): add email validation to login form
```

```
fix(cart): prevent negative quantity on item decrement
```

```
refactor(api): extract token refresh logic into service

Move token refresh from inline handler to dedicated AuthTokenService
for reuse across multiple endpoints.
```

**Regras:**

- Uma tarefa = um commit
- A descrição faz referência ao que foi FEITO, não ao que foi planejado
- Inclua apenas os arquivos listados na tarefa - nunca insira alterações "enquanto estou aqui"
- Se os testes fizerem parte da tarefa, inclua-os no mesmo commit

### 8. Guarda-corpo do escopo

Durante a implementação, você notará coisas que poderiam ser melhoradas, refatoradas ou adicionadas. **Não aja de acordo com eles.** Em vez disso:

- Se for um bug: anote-o em STATE.md como um bloqueador ou use o modo rápido
- Se for uma melhoria: anote em STATE.md em "Ideias Adiadas" ou "Lições Aprendidas"
- Se estiver relacionado à tarefa atual: inclua apenas se estiver no critério “Concluído quando”

**A heurística:** "Isso está na minha definição de tarefa?" Se não, não toque nele.

### 9. Atualizar status da tarefa

Marque a tarefa como concluída em tarefas.md. Atualize a rastreabilidade de requisitos em spec.md se IDs de requisitos forem usados.

---

## Modelo de Execução

```markdown
## Implementing T[X]: [Task Title]

**Reading**: task definition from tasks.md
**Dependencies**: [All done? ✅ | Blocked by: TY]
**Tests**: [unit/e2e/integration/none]
**Gate**: [quick/full/build]

### Pre-Implementation (MANDATORY)

- **Assumptions**: [state explicitly]
- **Files to touch**: [list ONLY these]
- **Success criteria**: [how to verify]

### RED: Write Tests

- Test file(s): [paths]
- Test count: [N test cases]
- Confirmed failing: [Yes — all N tests fail as expected]

### GREEN: Implement

[Write minimum code to pass tests]

- Tests modified: None
- Tests skipped/deleted: None

### VERIFY: Gate Check

- Command: [gate check command]
- Result: [X passed, 0 failed]
- Test count: [N — matches RED phase count]

### Post-Gate

- [x] No SPEC_DEVIATION (or markers added)
- [x] No unnecessary changes made
- [x] Matches existing patterns

**Status**: ✅ Complete | ❌ Blocked | ⚠️ Partial
```

---

## Dicas

- **Uma tarefa por vez** — O foco evita erros
- **Ferramentas são importantes** — MCP errado = abordagem errada
- **Reutiliza tokens salvos** — Copie padrões, não reinvente
- **Verificar antes de confirmar** — Verifique todos os critérios e depois confirme
- **Permaneça cirúrgico** — Toque apenas no que for necessário
- **Commit por tarefa** — Limpar o histórico do git permite dividir e reverter
- **Nunca "enquanto estiver aqui"** — O aumento do escopo durante a implementação é o principal assassino de qualidade
- **Aprenda com os erros** — Se algo der errado, adicione uma Lição aprendida ao STATE.md
