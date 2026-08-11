# Design: coleta IA e avaliação em três repetições

## Organização

`config/agentes/prompt-relatorio-ia-v1.txt` é compartilhado por C3--C6. `cursor-c3-v1.json` e `codex-c4-v1.json` são configurações espelhadas; diferenças de produto, sessão e metadados ficam no manifesto, não no prompt.

Cada execução terá uma área própria:

```text
execucoes/ia/<condicao>-<alvo>-R<repeticao>/
  entrada/                 # cópia sanitizada, somente leitura para o agente
  prompt.txt
  alertas-sast.json        # somente C5/C6
  resposta-bruta.txt
  resposta.json
  manifesto.json
```

As áreas e respostas são artefatos locais ignorados; a evidência pequena versionada contém apenas manifestos, hashes, configurações e resumos.

## Protocolo de uma tarefa

1. Validar configuração, prompt, schema, commit e inventário do alvo.
2. Criar sessão nova no produto correspondente.
3. Conceder somente leitura à raiz sanitizada; bloquear execução, testes, ferramentas SAST e diretórios externos.
4. Enviar o prompt comum; em C5/C6 montar o arquivo neutro de alertas sem oracle.
5. Capturar resposta bruta e metadados observáveis sem editar a resposta.
6. Validar JSON pelo schema; normalizar caminhos, linhas e campos sem completar dados ausentes.
7. Registrar manifesto terminal e calcular métricas somente na etapa de avaliação.

## Avaliação

O avaliador deve produzir uma linha por tarefa e uma linha agregada por `(condição, alvo)`. A agregação por condição usa mediana, intervalo interquartil, mínimo e máximo para duração/tokens, além de distribuição de achados e validade de JSON. A adjudicação oracle é um passo separado e recebe somente os achados normalizados após o fechamento da coleta.

## Piloto obrigatório

Antes das 312 tarefas (C3--C6), executar um alvo fixado em uma repetição por condição. O piloto verifica modelo efetivamente exibido, isolamento, resposta JSON, contadores de tokens e reprodutibilidade do prompt. Qualquer divergência congela o bloco até decisão documentada.
