# Tasks: corpus, fila e coleta C1/C2

**Design:** `.specs/features/corpus-fila-coleta-c1-c2/design.md`
**Status:** APROVADAS — EM ANDAMENTO
**Ferramentas:** filesystem/apply_patch, Git, PowerShell, Docker e rede apenas para fontes oficiais fixadas. Execuções Docker e coleta são seriais.

## Plano

```text
M2-T01 → M2-T02 → M2-T03 → M2-T04 → M2-T05 → M2-T06 → M2-T07 → M2-T08
```

O corpus, o estado da fila e a coleta compartilham artefatos mutáveis ignorados; por isso, as tarefas não são paralelizáveis. M2-T06 é um gate humano/técnico: sem reavaliação válida do risco do host, M2-T07 não inicia.

## Tarefas

### M2-T01: Congelar locks, política e planejamento — CONCLUÍDA

**O que:** validar o manifesto RealVuln v1.0, gerar lock autoral de 26 alvos/52 execuções, política de sanitização e documentos do M2.
**Onde:** `.specs/features/corpus-fila-coleta-c1-c2/`, `config/politica-sanitizacao-v1.json`, `config/corpus-realvuln-v1.lock.json`, `config/fila-c1-c2.lock.json`, `runner/corpus.py`, `tests/test_corpus.py`.
**Depende de:** M1 concluído.
**Requisitos:** M2-01, M2-03, M2-05, M2-09.

**Concluída quando:** 26 fontes e IDs, 52 execuções e permutação SHA-256 são estritamente validados; política é fechada; ao menos 20 testes cobrem duplicatas, URLs/commits, conjuntos incompletos, política e ordem; gate quick verde.
**Commit:** `feat(corpus): congelar manifesto RealVuln v1`.

**Evidência:** 29 testes específicos e 161 testes no gate quick, todos aprovados em 2026-08-11.

### M2-T02: Implementar sanitização e inventário do corpus — CONCLUÍDA

**O que:** estender a preparação para aplicar a política v1, relatar exclusões e provar regeneração sem executar arquivos.
**Onde:** `runner/preparacao.py`, `runner/corpus.py`, `tests/test_preparacao.py`, `tests/test_corpus.py`.
**Depende de:** M2-T01.
**Requisitos:** M2-03, M2-04.

**Concluída quando:** somente arquivos regulares permitidos são copiados; exclusões são determinísticas; duas preparações produzem inventários idênticos; sobreposição e especiais são recusados; links não são seguidos e somente o caminho Git explicitamente publicado na política pode ser omitido; gate quick verde.
**Commit:** `feat(corpus): sanitizar alvos por política congelada`.

**Evidência:** 29 testes de preparação e 171 testes no gate quick, todos aprovados em 2026-08-11.

### M2-T03: Adquirir e validar o corpus completo — CONCLUÍDA

**O que:** adquirir RealVuln/26 commits, executar o validador oficial isolado, preparar/regenerar 26 alvos e publicar evidência do corpus.
**Onde:** `scripts/adquirir-corpus.ps1`, `oracle/`, `benchmark/`, `alvos/corpus-v1/`, `evidencias/corpus-realvuln-v1/`, testes PowerShell/Docker.
**Depende de:** M2-T02.
**Requisitos:** M2-01, M2-02, M2-03, M2-04, M2-09.

**Concluída quando:** 26 commits conferem; validador informa 26 arquivos/817 entradas sem erro; contagens 697/120 conferem e a divergência do README é registrada; 26 regenerações são idênticas; nenhum alvo contém caminho proibido; resumo/hashes são auditáveis; gate build verde.
**Commit:** `feat(corpus): adquirir e validar censo RealVuln v1`.

**Evidência:** 26 alvos e suas regenerações idênticos; validador oficial `ALL PASSED` para 817 entradas; 697 vulnerabilidades/120 armadilhas; três espelhos e três links omitidos registrados; 193 testes Python, 15 testes de aquisição, 18 do wrapper, oito integrações Docker e fumaça aprovados no gate build de 2026-08-11.

### M2-T04: Implementar fila retomável — CONCLUÍDA

**O que:** criar modelo/CLI da fila com transições atômicas, revisão, claim exclusivo e retomada de órfã.
**Onde:** `runner/fila.py`, `tests/test_fila.py`, `runner/schemas/fila-c1-c2-v1.schema.json`.
**Depende de:** M2-T03.
**Requisitos:** M2-05, M2-08.

**Concluída quando:** 52 itens exatos; somente uma execução ativa; interrupção incrementa tentativa sem sobrescrever; terminais são imutáveis; corrupção/deriva é recusada; ao menos 20 testes passam; gate quick verde.
**Commit:** `feat(fila): orquestrar coleta C1 C2 retomável`.

**Evidência:** 30 testes específicos e 223 testes no gate quick, todos aprovados em 2026-08-11; o estado runtime valida hashes dos locks/configuração, revisão derivada do histórico, ordem temporal, claim exclusivo e caminhos de manifesto por tentativa.

### M2-T05: Implementar orquestrador e auditoria da coleta — CONCLUÍDA

**O que:** integrar fila, cópia nova por tarefa, wrapper SAST, validação terminal, cleanup próprio e resumo final.
**Onde:** `scripts/executar-coleta-c1-c2.ps1`, `runner/coleta.py`, `tests/test_coleta.py`, `scripts/test-coleta-c1-c2.ps1`, `scripts/gate.ps1`.
**Depende de:** M2-T04.
**Requisitos:** M2-04, M2-05, M2-06, M2-07, M2-08, M2-09.

**Concluída quando:** dry-run cobre 52; fixture reduzida comprova sucesso/falha/interrupção; configuração é revalidada a cada claim; áreas são novas e removidas; brutos/tentativas permanecem; gate full verde.
**Commit:** `feat(coleta): integrar fila serial C1 C2`.

**Evidência:** plano seco com 52 tarefas (26 C1/26 C2), 19 testes específicos de preparação/auditoria/orquestração, 242 testes Python, 18 testes do wrapper, 8 testes Docker, fumaça C1/C2, 15 testes de aquisição e teste PowerShell da coleta aprovados no gate full em 2026-08-11. Nenhuma fila ou saída de coleta foi criada.

### M2-T06: Reavaliar risco e congelar ambiente

**O que:** observar versões atuais, comparar a fontes oficiais, obter decisão explícita se necessário e gerar configuração imutável do bloco depois do gate build.
**Onde:** `config/host-risk-waiver-m2.json` se aprovado, `evidencias/coleta-c1-c2/configuracao.json`, `STATE.md`.
**Depende de:** M2-T05.
**Requisitos:** M2-06, M2-10.

**Concluída quando:** ausência/versões e riscos estão documentados; decisão tem data, escopo M2 e commit de aprovação; worktree está limpo; gate build verde; imagem/regras/locks/comandos/limites possuem hashes; nenhuma saída de coleta existe antes do freeze.
**Commit:** `chore(coleta): congelar ambiente C1 C2`.

**Registro de conclusao M2-T06 (2026-08-11):** configuracao `ebe3418e8465bbaf1644845431337c40af3873e3689d7ebbfc1904bc1e8b4435`, imagem `sha256:3aab47b08e5defe0a01b869d710d3b8fdfe315673c73560bcb7b4c9b95a8cd51`; gate build verde (250 testes Python, wrapper 18, Docker 8, aquisicao 15, coleta seca), worktree limpo e nenhuma fila/saida de coleta criada antes do freeze.

### M2-T07: Executar as 52 tarefas C1/C2

**O que:** executar a fila completa serialmente e preservar todas as tentativas/terminais.
**Onde:** `execucoes/`, `resultados/`, `evidencias/coleta-c1-c2/manifestos/`.
**Depende de:** M2-T06.
**Requisitos:** M2-04, M2-05, M2-06, M2-07, M2-08.

**Concluída quando:** 52 itens são terminais; C1/C2 compartilham hash/commit por alvo; manifestos/artefatos conferem; falhas estão explícitas; nenhum resultado de fumaça entrou; não há contêiner/área/parte residual.
**Commit:** `data(coleta): registrar manifestos C1 C2`.

**Registro de conclusao M2-T07 (2026-08-11):** 52 itens terminais (52 concluidas, 0 falhas); as nove falhas iniciais de formato Bandit foram corrigidas e reexecutadas na tentativa 3, com manifestos anteriores preservados. Permanecem 26 pares C1/C2, sem areas ou arquivos `.part` residuais.

### M2-T08: Auditar e documentar o M2

**O que:** produzir resumo final, validar requisito por requisito e transpor somente fatos comprovados para documentação/capítulos.
**Onde:** `evidencias/coleta-c1-c2/resumo.json`, `README.md`, `docs/EXECUCAO.md`, `06-metodologia.tex`, `07-desenvolvimento.tex`, spec/tasks/STATE/ROADMAP.
**Depende de:** M2-T07.
**Requisitos:** M2-01--M2-10.

**Concluída quando:** auditoria prova 26×2, hashes e estados; gate build final passa; LaTeX não ganha erro; M2 fica verificado; M3 permanece separado e nenhuma métrica de detecção é antecipada.
**Registro de conclusao M2-T08 (2026-08-11):** auditoria publicada em `evidencias/coleta-c1-c2/auditoria-m2-t08.json`; fila, manifestos, pares C1/C2 e limpeza verificados; nenhuma metrica de deteccao foi calculada.
**Commit:** `docs(tcc): registrar corpus e coleta C1 C2`.

## Gates

| Tarefa | Gate |
|---|---|
| M2-T01, T02, T04 | quick |
| M2-T03, T06, T08 | build |
| M2-T05 | full |
| M2-T07 | auditoria específica da coleta + nenhum resíduo |

## Rastreabilidade tarefa–requisito

| Requisito | Tarefas |
|---|---|
| M2-01 | T01, T03, T08 |
| M2-02 | T03, T08 |
| M2-03 | T01, T02, T03, T08 |
| M2-04 | T02, T03, T05, T07, T08 |
| M2-05 | T01, T04, T05, T07, T08 |
| M2-06 | T05, T06, T07, T08 |
| M2-07 | T05, T07, T08 |
| M2-08 | T04, T05, T07, T08 |
| M2-09 | T01, T03, T05, T08 |
| M2-10 | T06, T08 |
