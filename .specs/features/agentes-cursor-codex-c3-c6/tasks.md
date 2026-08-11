# Tasks: agentes Cursor/Codex C3--C6

## M3-T01 — Congelar protocolo e configurações

- [ ] Revisar `prompt-relatorio-ia-v1.txt` e schema.
- [ ] Registrar hashes de prompt, schema e configurações.
- [ ] Confirmar modelo principal GPT-5.6 Luna nos dois produtos.

## M3-T02 — Executar piloto

- [ ] Executar um alvo em C3, C4, C5 e C6.
- [ ] Verificar leitura somente, ausência de execução e ausência de oracle.
- [ ] Verificar resposta JSON, metadados, sessão e tokens.
- [ ] Registrar decisão de liberar ou bloquear a fila completa.

## M3-T03 — Executar C3/C4

- [ ] Criar 78 tarefas C3 e 78 tarefas C4.
- [ ] Executar três repetições por alvo, preservando falhas e tentativas.
- [ ] Não misturar Cursor e Codex na mesma sessão ou manifesto.

## M3-T04 — Preparar C5/C6

- [ ] Gerar `alertas-sast.json` por alvo a partir de C1/C2, sem oracle.
- [ ] Validar deduplicação e preservar origem Bandit/Semgrep.
- [ ] Confirmar que C5/C6 recebem bytes idênticos para cada alvo.

## M3-T05 — Executar C5/C6

- [ ] Criar 78 tarefas C5 e 78 tarefas C6.
- [ ] Executar três repetições e preservar respostas brutas.

## M3-T06 — Avaliar e preparar gráficos

- [ ] Validar 312 manifestos e estados terminais.
- [ ] Gerar resumo descritivo por condição, alvo e repetição.
- [ ] Calcular estabilidade em zero/uma/duas/três repetições.
- [ ] Após autorização, executar o avaliador oracle para TP/FP/FN/TN.
- [ ] Gerar dados CSV/SVG para os gráficos do Capítulo 8.
