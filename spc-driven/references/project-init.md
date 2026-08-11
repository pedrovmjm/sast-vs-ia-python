# Inicialização do Projeto

**Acionador:** "Inicializar projeto", "Configurar projeto", "Iniciar novo projeto"

**Idioma:** gere `PROJECT.md` em pt-BR. Traduza headings, labels, placeholders e descrições; preserve apenas nomes técnicos, paths e comandos quando existirem.

## Processo

Extraia a visão do projeto por meio de perguntas e respostas iterativas (máximo de 3 a 5 perguntas por mensagem):

**Perguntas essenciais:**

1. O que você está construindo?
2. A quem se destina e que problema resolve?
3. Qual pilha de tecnologia você está usando? (se conhecido)
4. O que está no escopo da v1? O que está explicitamente excluído?
5. Restrições críticas? (cronograma, técnico, recursos)

**Parar quando:** Compreensão clara da visão, das metas e dos limites.

## Saída: .specs/project/PROJECT.md

**Estrutura:**

```markdown
# [Nome do projeto]

**Visão:** [descrição em 1-2 frases]
**Para:** [usuários-alvo]
**Resolve:** [problema central abordado]

## Metas

- [Meta principal com métrica de sucesso mensurável]
- [Meta secundária com métrica de sucesso mensurável]

## Stack técnica

**Base:**

- Framework: [nome + versão]
- Linguagem: [nome + versão]
- Banco de dados: [nome]

**Dependências-chave:** [3-5 bibliotecas/frameworks críticos]

## Escopo

**v1 inclui:**

- [Capacidade central 1]
- [Capacidade central 2]
- [Capacidade central 3]

**Explicitamente fora de escopo:**

- [O que NÃO será construído]
- [O que NÃO será construído]

## Restrições

- Prazo: [se aplicável]
- Técnicas: [se aplicável]
- Recursos: [se aplicável]
```

**Limite de tamanho:** 2.000 tokens (aproximadamente 1.200 palavras)

**Validação:**

- Visão clara em 1-2 frases?
- As metas têm resultados mensuráveis?
- Os limites do escopo são explícitos?
