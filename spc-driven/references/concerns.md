# Fase: Preocupações com a base de código

**Acionador:** Parte do mapeamento brownfield ou explicitamente "documentar preocupações", "encontrar dívida tecnológica", "o que é arriscado nesta base de código"

**Objetivo:** Apresentar avisos acionáveis sobre a base de código. Focado em "o que observar ao fazer alterações". Esta é uma documentação viva, não uma lista de reclamações.

## Quando gerar

CONCERNS.md é gerado como parte do fluxo de mapeamento brownfield (juntamente com STACK.md, ARCHITECTURE.md, etc.). Também pode ser criado ou atualizado de forma independente quando:

- Explorar uma nova área da base de código revela riscos
- Uma investigação de bug revela problemas sistêmicos
- A implementação de um recurso atinge uma fragilidade inesperada
- Uma auditoria de dependência revela riscos

## Processo

### 1. Reúna evidências

Durante a exploração da base de código, procure sinais concretos – não opiniões. Fontes de evidências:

- Padrões de código que indicam atalhos (comentários TODO/FIXME/HACK, lógica duplicada, falta de tratamento de erros)
- Lacunas de cobertura de teste (caminhos críticos não testados, casos extremos ausentes)
- Manifestos de dependência (pacotes desatualizados, bibliotecas obsoletas, avisos de segurança)
- Indicadores de desempenho (consultas N+1, índices ausentes, bloqueio síncrono de chamadas)
- Padrões de segurança (verificações de autenticação somente do lado do cliente, entradas não validadas, segredos expostos)

### 2. Classificar e documentar

Cada preocupação deve ter: **qual** é o problema, **onde** ele reside (caminhos de arquivo), **por que** é importante (impacto) e **como** corrigi-lo (abordagem).

### 3. Priorizar por risco

Concentre-se nas preocupações que podem causar danos reais – perda de dados, violações de segurança, falhas enfrentadas pelo usuário, escalada de muros. Problemas menores de estilo e TODOs normais não pertencem aqui.

---

## Modelo: `.specs/codebase/CONCERNS.md`

**Limite de tamanho:** 5.000 tokens (aproximadamente 3.000 palavras)

```markdown
# Preocupações da base de código

**Data da análise:** [YYYY-MM-DD]

## Dívida técnica

**[Área/Componente]:**

- Problema: [qual é o atalho/contorno]
- Arquivos: [paths específicos de arquivos com crases]
- Por quê: [por que foi feito desse jeito]
- Impacto: [o que quebra ou degrada por causa disso]
- Abordagem de correção: [como resolver adequadamente]

## Bugs conhecidos

**[Descrição do bug]:**

- Sintomas: [o que acontece]
- Gatilho: [como reproduzir]
- Arquivos: [onde o bug está]
- Contorno: [mitigação temporária, se houver]
- Causa raiz: [se conhecida]
- Bloqueado por: [se estiver aguardando algo]

## Considerações de segurança

**[Área que exige cuidado de segurança]:**

- Risco: [o que pode dar errado]
- Arquivos: [onde o risco está]
- Mitigação atual: [o que já existe]
- Recomendações: [o que deve ser adicionado]

## Gargalos de desempenho

**[Operação/endpoint lento]:**

- Problema: [o que está lento]
- Arquivos: [onde o gargalo está]
- Medição: [números reais: "500ms p95", "2s de carregamento"]
- Causa: [por que está lento]
- Caminho de melhoria: [como acelerar]

## Áreas frágeis

**[Componente/Módulo]:**

- Arquivos: [onde a fragilidade está]
- Por que é frágil: [o que faz quebrar facilmente]
- Falhas comuns: [o que normalmente dá errado]
- Modificação segura: [como alterar sem quebrar]
- Cobertura de testes: [é testado? lacunas?]

## Limites de escala

**[Recurso/Sistema]:**

- Capacidade atual: [números: "100 req/s", "10k usuários"]
- Limite: [onde quebra]
- Sintomas no limite: [o que acontece]
- Caminho de escala: [como aumentar a capacidade]

## Dependências em risco

**[Pacote/Serviço]:**

- Risco: [ex.: "obsoleto", "sem manutenção", "breaking changes a caminho"]
- Impacto: [o que quebra se falhar]
- Plano de migração: [alternativa ou caminho de upgrade]

## Recursos críticos ausentes

**[Lacuna de recurso]:**

- Problema: [o que está faltando]
- Contorno atual: [como os usuários lidam com isso]
- Bloqueia: [o que não pode ser feito sem isso]
- Complexidade de implementação: [estimativa aproximada de esforço]

## Lacunas de cobertura de testes

**[Área não testada]:**

- O que não é testado: [funcionalidade específica]
- Risco: [o que pode quebrar sem ser percebido]
- Prioridade: [Alta/Média/Baixa]
- Dificuldade para testar: [por que ainda não foi testado]

---

_Auditoria de preocupações: [data]_
_Atualize conforme problemas forem corrigidos ou novos problemas forem descobertos_
```

**Inclua apenas seções que contenham descobertas.** Seções vazias devem ser totalmente omitidas.

---

## O que pertence versus o que não pertence

**Incluir:**

- Dívida tecnológica com impacto claro e abordagem de correção
- Bugs conhecidos com etapas de reprodução
- Lacunas de segurança e recomendações de mitigação
- Gargalos de desempenho com medições
- Código frágil que quebra facilmente
- Limites de escala com números
- Dependências que precisam de atenção
- Recursos ausentes que bloqueiam fluxos de trabalho
- Lacunas de cobertura de teste

**Excluir:**

- Opiniões sem evidências (“o código é confuso”)
- Reclamações sem soluções ("auth é uma merda")
- Ideias de recursos futuros (para planejamento de produtos)
- TODOs normais (aqueles que vivem em comentários de código)
- Decisões arquitetônicas que estão funcionando bem
- Pequenos problemas de estilo de código

---

## Diretrizes para redação

- **Sempre inclua caminhos de arquivo** — Preocupações sem locais não são acionáveis. Use crases: `src/file.ts`
- Seja específico com medições ("500ms p95" não "lento")
- Inclui etapas de reprodução de bugs
- Sugira abordagens de correção, não apenas problemas
- Concentre-se em itens acionáveis
- Priorizar por risco/impacto

**Tom:** Profissional, não emocional. Orientado para soluções. Focado no risco. Fato.

- ✅ "Padrão de consulta N+1 em `app/api/courses/route.ts` — 1,2s p95 com mais de 50 cursos"
- ❌ "Consultas terríveis, tudo lento"
- ✅ "Correção: adicionar índice em `user_id` na tabela `subscriptions`"
- ❌ "Precisa de conserto"

---

## Como CONCERNS.md é usado

- **Planejamento de recursos:** Verifique CONCERNS.md antes de projetar recursos que afetem áreas sinalizadas
- **Estimativa de risco:** use áreas frágeis e limites de escala para estimar o risco de mudança
- **Integração de novas sessões:** Carregue CONCERNS.md para fornecer contexto sobre o que observar
- **Priorização de refatoração:** Use dívidas tecnológicas e teste lacunas de cobertura para planejar sprints de melhoria
- **Fase de implementação:** Consulte antes de modificar qualquer componente sinalizado

Esta é uma documentação viva. Atualize à medida que os problemas são corrigidos ou novos são descobertos durante qualquer fase do fluxo de trabalho.
