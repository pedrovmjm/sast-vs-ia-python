# Criação de roteiro

**Acionador:** "Criar roteiro", "Planejar recursos", "Mapear fases do projeto"

**Idioma:** gere `ROADMAP.md` em pt-BR. Traduza headings, labels, placeholders e descrições; preserve nomes técnicos e status canônicos apenas quando forem exigidos por integração externa.

## Processo

Com base em PROJECT.md, decomponha a visão em:

- Marcos (incrementos entregáveis)
- Recursos (capacidades voltadas para o usuário)
- Acompanhamento de status (planejado/em andamento/concluído)

## Saída: .specs/project/ROADMAP.md

**Estrutura:**

```markdown
# Roadmap

**Marco atual:** [nome do marco]
**Status:** Planejado | Em andamento | Concluído

---

## [Nome do marco 1]

**Meta:** [o que torna este marco entregável]
**Alvo:** [data ou critérios de conclusão]

### Recursos

**[Nome do recurso]** - STATUS

- [Capacidade 1]
- [Capacidade 2]
- [Capacidade 3]

**[Nome do recurso]** - STATUS

- [Capacidade 1]
- [Capacidade 2]

---

## [Nome do marco 2]

**Meta:** [o que este marco adiciona]

### Recursos

**[Nome do recurso]** - PLANEJADO
**[Nome do recurso]** - PLANEJADO

---

## Considerações futuras

- [Possível capacidade futura]
- [Possível capacidade futura]
```

**Valores de status:**

- PLANEJADO: Não iniciado
- EM ANDAMENTO: Atualmente em implementação
- COMPLETO: Enviado e verificado

**Limite de tamanho:** 3.000 tokens (aproximadamente 1.800 palavras)

**Estratégia de atualização:**

- Marcar recursos PLANEJADOS → EM ANDAMENTO ao iniciar
- Marque EM ANDAMENTO → CONCLUÍDO quando verificado
- Adicione novos marcos à medida que o projeto evolui

**Validação:**

- Cada marco tem um resultado claro e entregável?
- Os recursos são recursos voltados para o usuário?
- O status reflete a realidade atual?
