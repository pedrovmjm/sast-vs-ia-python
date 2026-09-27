# Tasks: agentes Cursor/Codex C3--C6

## M3-T01 — Congelar protocolo e configurações

- [ ] Revisar `prompt-relatorio-ia-v1.txt` e schema.
- [x] Registrar hashes de prompt, schema e configurações.
- [ ] Confirmar modelo principal GPT-5.6 Luna nos dois produtos.

## M3-T02 — Executar piloto

- [ ] Executar um alvo em C3, C4, C5 e C6.
- [ ] Verificar leitura somente, ausência de execução e ausência de oracle.
- [ ] Verificar resposta JSON, metadados, sessão e tokens.
- [ ] Registrar decisão de liberar ou bloquear a fila completa.

**Estado em 2026-09-26:** o piloto C6 foi aprovado com resposta válida, sessão e tokens presentes, zero violações e hash de alertas correspondente ao lock. O item permanece aberto porque os pilotos C3 e C5 ainda não foram executados.

## M3-T03 — Executar C3/C4

- [ ] Criar 78 tarefas C3 e 78 tarefas C4.
- [ ] Executar três repetições por alvo, preservando falhas e tentativas.
- [ ] Não misturar Cursor e Codex na mesma sessão ou manifesto.

**Estado em 2026-09-26:** C4 possui 78 unidades válidas e zero chamadas pendentes após as novas tentativas. C3 ainda não foi executada. Setenta manifestos C4 preservam o formato anterior do harness; a compatibilidade desses metadados deve ser descrita na auditoria, sem reescrever os originais.

## M3-T04 — Preparar C5/C6

- [x] Gerar `alertas-sast.json` por alvo a partir de C1/C2, sem oracle.
- [x] Validar deduplicação e preservar origem Bandit/Semgrep.
- [x] Confirmar que C5/C6 recebem bytes idênticos para cada alvo.

**Estado em 2026-09-26:** 26 arquivos, 1.410 alertas após deduplicação e hashes congelados em `config/agentes/alertas-sast-c6-v1.lock.json`.

## M3-T05 — Executar C5/C6

- [x] Criar e concluir as 78 unidades C6, preservando todas as tentativas.
- [ ] Criar e executar as 78 unidades C5.

**Estado em 2026-09-26:** C6 foi encerrada com 78 unidades válidas, 92 tentativas físicas e 14 falhas de formato preservadas em sete unidades posteriormente concluídas. O plano final indica zero chamadas pendentes. Evidência em `evidencias/coleta-c6/auditoria-m3-c6.json`.

## M3-T06 — Avaliar e preparar gráficos

- [ ] Validar 312 manifestos e estados terminais.
- [ ] Gerar resumo descritivo por condição, alvo e repetição.
- [ ] Calcular estabilidade em zero/uma/duas/três repetições.
- [ ] Após autorização, executar o avaliador oracle para TP/FP/FN/TN.
- [ ] Gerar dados CSV/SVG para os gráficos do Capítulo 8.

**Parcial C6:** resumo descritivo sem oracle publicado; 700 achados nas 78 respostas válidas, 3.901.020 tokens em todas as tentativas e zero violações. A avaliação adjudicada continua pendente.
