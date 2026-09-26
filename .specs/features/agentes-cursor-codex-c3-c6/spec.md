# Especificação: agentes Cursor/Codex e condições C3--C6

**Status:** em execução; C4 coletada e C6 preparada para piloto
**Dependências:** M2 concluído; `config/agentes/` versionável; disponibilidade do Cursor ainda deve ser verificada no piloto. A coleta C4 possui 78 unidades válidas e zero chamadas pendentes. Os 26 arquivos de alertas de C6 foram gerados e congelados por hash.

## Objetivo

Executar Cursor e Codex sobre os mesmos 26 alvos sanitizados usados em C1/C2, com prompt comum, três repetições independentes e rastreabilidade suficiente para avaliar detecção, estabilidade, qualidade do relatório, tempo e tokens.

## Condições

| Condição | Produto | Perfil | Entrada adicional |
|---|---|---|---|
| C3 | Cursor | GPT-5.6 Luna | nenhuma |
| C4 | Codex | GPT-5.6 Luna | nenhuma |
| C5 | Cursor | GPT-5.6 Luna | `alertas-sast.json` |
| C6 | Codex | GPT-5.6 Luna | `alertas-sast.json` |

C3/C4 são IA isolada. C5/C6 são híbridas: recebem a união normalizada de C1/C2, sem rótulos do oracle ou indicação de verdadeiro/falso positivo.

## Repetições e avaliação

Cada condição terá 26 alvos × 3 repetições = 78 tarefas. A unidade de avaliação é `(condição, alvo, repetição)`, nunca uma média que esconda falhas.

Serão preservados, por tarefa, prompt, configuração, produto, modelo solicitado e exibido, sessão, timestamps, duração, tokens disponíveis, resposta bruta, hash da resposta, JSON normalizado, avisos e estado terminal. Falha de formato, sessão ou disponibilidade permanece no denominador e não é convertida em ausência de achados.

As análises serão feitas em duas camadas:

1. **Descritiva antes do oracle:** quantidade de achados, arquivos, CWEs, severidades, duração, tokens e taxa de respostas válidas por condição e repetição.
2. **Adjudicada depois do oracle:** TP, FP, FN, TN, precisão, recall, F1, F2, F3 e taxa de falsos positivos, usando somente o avaliador oficial e mantendo a saída bruta imutável.

Estabilidade será reportada por alvo e entrada vulnerável: detectada em zero, uma, duas ou três repetições. Não haverá voto majoritário silencioso.

## Critérios de aceite

- C3 e C4 usam exatamente o mesmo prompt, corpus, schema e restrições.
- Cada condição possui exatamente 78 itens previstos.
- Nenhuma sessão pode executar código, testes, Bandit, Semgrep ou acessar oracle.
- C5/C6 recebem o mesmo `alertas-sast.json` correspondente ao alvo.
- Modelo indisponível, modelo exibido divergente ou contador de tokens ausente é registrado, não estimado.
- O piloto de um alvo por condição aprova formato, permissões, captura de sessão e metadados antes da fila completa.
- Nenhum resultado é incorporado ao TCC antes de sua origem e estado terminal serem auditados.
