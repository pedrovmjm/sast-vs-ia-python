# Tasks: ambiente e primeira execução SAST

**Design:** `.specs/features/ambiente-e-primeira-execucao-sast/design.md`
**Status:** APROVADAS — EM ANDAMENTO
**Ferramentas autorizadas pela solicitação:** `apply_patch`/filesystem para arquivos autorais, PowerShell/Git/Docker para verificação local e web somente em fontes oficiais/primárias. Skill: `spc-driven`. Nenhum MCP adicional é necessário neste marco.

## Plano de execução

```text
T00 → T01 → T02 → T03 → T04 ─┬→ T05 [P] ─┐
                              └→ T06 [P] ─┴→ T07 → T08 → T09 → T10
```

T05 e T06 podem ser implementadas em paralelo depois do esquema comum. Os gates Docker e as execuções de fumaça permanecem seriais.

## Divisão de tarefas

### T00: Inicializar o Git local — ✅ CONCLUÍDA

**O que:** criar branch `main`, proteção de artefatos e primeiro commit local.
**Onde:** `.gitignore`, `.git/`.
**Depende de:** nenhum.
**Requisito:** AMB-01.
**Ferramentas:** PowerShell e Git.

**Concluída quando:** repositório limpo, `Zone.Identifier` ignorado e commit `5bdadd3` existente.
**Testes:** nenhum.
**Gate:** `git status --short --branch && git log -1 --oneline`.
**Commit:** `chore(repo): inicializar repositório local`.

### T01: Registrar planejamento e fontes oficiais — ✅ CONCLUÍDA

**O que:** criar os documentos SPC e o registro auditável das fontes/licenças.
**Onde:** `.specs/`, `docs/FONTES_E_INTEGRIDADE.md`.
**Depende de:** T00.
**Requisitos:** AMB-02, AMB-03.
**Ferramentas:** filesystem e web oficial.

**Concluída quando:**

- [x] projeto, roadmap, estado, spec, design e tasks estão em pt-BR;
- [x] URLs, versões, commits/digest, licenças e riscos estão documentados;
- [x] divergências RealVuln/licença das regras Semgrep estão explícitas;
- [x] gate passa: `git diff --check`;
- [x] contagem de testes: 0 (documentação, conforme matriz).

**Testes:** nenhum.
**Gate:** provisório documental.
**Verificar:** `git diff --check` e leitura dos arquivos.
**Commit:** `docs(spec): estruturar primeiro incremento experimental`.

### T02: Implementar manifesto e verificação de fontes — ✅ CONCLUÍDA

**O que:** validar o lock de fontes e rejeitar revisão, domínio ou hash divergente.
**Onde:** `.gitattributes`, `.gitignore`, `config/fontes.lock.json`, `config/host-risk-waiver.json`, `runner/__init__.py`, `runner/aquisicao.py`, `tests/__init__.py`, `tests/test_aquisicao.py`.
**Depende de:** T01.
**Requisitos:** AMB-02, AMB-03, AMB-13.
**Reutiliza:** Git, Docker CLI e manifesto oficial do RealVuln.
**Ferramentas:** filesystem, PowerShell/Git/Docker.

**Concluída quando:**

- [x] 25 casos de unidade cobrem manifesto, URLs exatas, revisões, hashes, JSON estrito, árvore canônica e exceção do host;
- [x] nenhum script baixado é executado pela validação;
- [x] gate quick passa;
- [x] contagem observada: 25 testes, 0 falhas, 0 ignorados.

**Testes:** unidade.
**Gate:** quick; até T03, usar diretamente a imagem-base Python fixada por digest.
**Verificar:** `python -m unittest tests.test_aquisicao` no contêiner.
**Commit:** `feat(fontes): validar manifesto de proveniência`.

### T03: Construir a imagem SAST reproduzível — ✅ CONCLUÍDA

**O que:** criar imagem única com Python, Bandit e Semgrep fixados por digest/lock com hashes.
**Onde:** `.dockerignore`, `docker/Dockerfile`, `docker/requirements.in`, `docker/requirements.lock`, `compose.yaml`, `scripts/gate.ps1`, `tests/test_ambiente.py`, `tests/runtime_probe.py`.
**Depende de:** T02.
**Requisitos:** AMB-03, AMB-04.
**Reutiliza:** imagem oficial Python e distribuições PyPI verificadas.
**Ferramentas:** Docker e PowerShell.

**Concluída quando:**

- [x] build usa a imagem-base por digest;
- [x] `pip` usa `--require-hashes` e somente wheels;
- [x] versões observadas são Python 3.12.13, Bandit 1.9.4 e Semgrep 1.172.0;
- [x] a imagem não contém `benchmark/`, `oracle/` ou alvos;
- [x] gate build passa, incluindo sonda dos controles em runtime;
- [x] contagem acumulada observada: 37 testes, 0 falhas, 0 ignorados.

**Testes:** integração.
**Gate:** build.
**Verificar:** comandos `--version`, `docker image inspect` e gates de TESTING.md.
**Commit:** `build(docker): fixar ambiente SAST reproduzível`.

### T04: Definir esquema comum e manifesto de execução — ✅ CONCLUÍDA

**O que:** implementar modelos versionados, serialização determinística e validação de nulos/linhas.
**Onde:** `runner/modelos.py`, `runner/schemas/achado-v1.schema.json`, `runner/schemas/execucao-v1.schema.json`, `tests/test_modelos.py`.
**Depende de:** T03.
**Requisitos:** AMB-06, AMB-07.
**Ferramentas:** filesystem e Docker.

**Concluída quando:**

- [x] serialização preserva `null`, valores brutos/normalizados e referências ao bruto;
- [x] caminhos absolutos, travessia, linhas não positivas e intervalos invertidos são rejeitados;
- [x] conclusão exige artefato preservado e `timeout` é registrado como tipo de falha;
- [x] 24 testes do T04 e 61 testes acumulados passam, sem falhas ou ignorados;
- [x] gate quick passa.

**Testes:** unidade.
**Gate:** quick.
**Verificar:** `python -m unittest tests.test_modelos`.
**Commit:** `feat(esquema): definir achado e execução versionados`.

### T05: Implementar adaptador Bandit [P] — ✅ CONCLUÍDA

**O que:** converter JSON Bandit para o esquema comum sem inferência externa.
**Onde:** `runner/adaptadores/bandit.py`, `tests/fixtures/bandit/`, `tests/test_bandit.py`.
**Depende de:** T04.
**Requisito:** AMB-08.
**Reutiliza:** contrato JSON do Bandit 1.9.4.
**Ferramentas:** filesystem e Docker.

**Concluída quando:** achado, lista vazia, CWE ausente, erros parciais, duplicatas, caminhos sintáticos, hash/proveniência e documento inválido estão cobertos; 16 testes próprios passam; gate quick verde (87 testes acumulados após integração paralela).
**Testes:** unidade.
**Gate:** quick.
**Commit:** `feat(adaptadores): normalizar saída do Bandit`.

### T06: Implementar adaptador Semgrep [P] — ✅ CONCLUÍDA

**O que:** converter JSON Semgrep, preservando erros e campos ausentes, sem registro remoto durante análise.
**Onde:** `runner/adaptadores/semgrep.py`, `tests/fixtures/semgrep/`, `tests/test_semgrep.py`.
**Depende de:** T04.
**Requisito:** AMB-09.
**Reutiliza:** contrato JSON do Semgrep 1.172.0.
**Ferramentas:** filesystem e Docker.

**Concluída quando:** achado, lista vazia, erro parcial tipado, caminhos sintáticos, hash/proveniência e documento inválido estão cobertos; 10 testes próprios passam; gate quick verde com 87 testes acumulados.
**Testes:** unidade.
**Gate:** quick.
**Commit:** `feat(adaptadores): normalizar saída do Semgrep`.

### T07: Implementar executor SAST endurecido — ✅ CONCLUÍDA

**O que:** executar uma ferramenta por contêiner, serialmente, com entrada `ro`, saída `rw` e controles do design.
**Onde:** `docker/Dockerfile`, `runner/executor_sast.py`, `scripts/executar-sast.ps1`, `scripts/test-executar-sast.ps1`, `scripts/test-executor-integracao.ps1`, `tests/test_executor_sast.py`, `scripts/gate.ps1`.
**Depende de:** T05, T06.
**Requisitos:** AMB-05, AMB-06.
**Ferramentas:** filesystem, Docker e PowerShell.

**Concluída quando:**

- [x] testes inspecionam rede, usuário, capabilities, `no-new-privileges`, mounts, recursos e timeout;
- [x] bruto e metadados são escritos antes da normalização;
- [x] falha/timeout preservam tentativa;
- [x] 8 testes de integração Docker passam, além de 18 testes do wrapper e 23 testes próprios do executor;
- [x] gate full verde com 110 testes Python.

**Testes:** integração, não segura em paralelo.
**Gate:** full.
**Commit:** `feat(execucao): isolar condições SAST em Docker`.

### T08: Validar adaptadores em fixture externa — ✅ CONCLUÍDA

**O que:** criar fixture Python própria e comando de fumaça para C1/C2 fora do corpus.
**Onde:** `tests/fixtures/alvo-sintetico/`, `scripts/test-fumaca-sintetica.ps1`, `tests/test_fumaca_sintetica.py`, `scripts/gate.ps1`.
**Reutiliza:** `scripts/executar-sast.ps1`, a única CLI pública do host.
**Depende de:** T07.
**Requisitos:** AMB-05, AMB-08, AMB-09, AMB-10.
**Ferramentas:** filesystem, Docker e PowerShell.

**Concluída quando:**

- [x] C1/C2 reais e seriais geram bruto e três achados normalizados esperados por ferramenta;
- [x] modelos, hashes, proveniência, versões, regras, linhas, CWEs, mapeamentos e comandos conferem;
- [x] adaptadores reexecutados sobre os brutos reproduzem os normalizados persistidos;
- [x] a entrada mantém SHA-256 `1dbbff2e447b9ea0596f38b414c0d1e1ce4f5789e30f964b8dc568f39fd474ef` antes/depois;
- [x] não há rede, execução da fixture, avisos, watchdog, partes nem contêiner residual;
- [x] gate full verde com 113 testes Python, 18 testes do wrapper, 8 integrações Docker e o e2e PowerShell C1/C2.
**Testes:** e2e serial.
**Gate:** full.
**Commit:** `test(fumaca): validar SAST fora do corpus`.

### T09: Executar fumaça descartável no RealVuln — ✅ CONCLUÍDA

**O que:** adquirir um alvo pelo commit do manifesto, sanitizar, executar C1/C2 e registrar evidência descartável.
**Onde:** `runner/preparacao.py`, `tests/test_preparacao.py`, `evidencias/primeira-execucao/`.
**Depende de:** T08.
**Requisitos:** AMB-02, AMB-03, AMB-11, AMB-13.
**Ferramentas:** Git, Docker e filesystem.

**Concluída quando:** commits conferem, inventários de C1/C2 são iguais, o alvo é regenerável, a evidência tem hashes/versões/comandos/tempos/status `descartavel`, pelo menos 5 testes e gate build verdes.

- [x] RealVuln v1.0 e DSVW foram adquiridos somente pelos commits fixados;
- [x] C1/C2 usaram inventários idênticos com SHA-256 `60913ac90d496cf087a5fe6e9a4dbb04882c862a93f7d094eebb692d41467206`;
- [x] uma segunda preparação reproduziu integralmente o inventário e foi descartada;
- [x] resumo, dois inventários e dois manifestos preservam versões, imagem, comandos, tempos, hashes e status `descartavel`;
- [x] 19 testes próprios (12 de preparação e 7 da evidência) e 132 testes Python acumulados passaram;
- [x] gate build passou, incluindo 18 testes do wrapper, 8 integrações Docker e o e2e sintético C1/C2.
**Testes:** integração e e2e, não seguros em paralelo.
**Gate:** build.
**Commit:** `feat(fumaca): registrar primeira execução RealVuln`.

### T10: Atualizar documentação operacional e Capítulo 7

**O que:** documentar reprodução e transpor somente valores comprovados para o capítulo de desenvolvimento.
**Onde:** `README.md`, `docs/EXECUCAO.md`, `07-desenvolvimento.tex`, spec/tasks/STATE.
**Depende de:** T09.
**Requisito:** AMB-12.
**Ferramentas:** filesystem, Git e LaTeX disponível.

**Concluída quando:** comandos são copiáveis, valores correspondem às evidências, tarefas/requisitos estão verificados, LaTeX não ganha erro novo e gate build permanece verde.
**Testes:** nenhum código novo; validação documental/build.
**Gate:** build.
**Commit:** `docs(tcc): registrar ambiente e primeira execução SAST`.

## Verificação de granularidade

| Tarefa | Entrega | Estado |
|---|---|---|
| T00 | inicialização do repositório | ✅ Atômica |
| T01 | pacote coerente de planejamento | ✅ Atômica |
| T02 | validação de fontes | ✅ Atômica |
| T03 | imagem SAST | ✅ Atômica |
| T04 | esquema comum | ✅ Atômica |
| T05 | adaptador Bandit | ✅ Atômica |
| T06 | adaptador Semgrep | ✅ Atômica |
| T07 | executor Docker | ✅ Atômica |
| T08 | fumaça sintética | ✅ Atômica |
| T09 | fumaça RealVuln | ✅ Atômica |
| T10 | documentação da evidência | ✅ Atômica |

## Verificação cruzada do plano

| Tarefa | Depende de no corpo | Setas no plano | Estado |
|---|---|---|---|
| T00 | nenhum | início | ✅ |
| T01 | T00 | T00 → T01 | ✅ |
| T02 | T01 | T01 → T02 | ✅ |
| T03 | T02 | T02 → T03 | ✅ |
| T04 | T03 | T03 → T04 | ✅ |
| T05 | T04 | T04 → T05 | ✅ |
| T06 | T04 | T04 → T06 | ✅ |
| T07 | T05, T06 | T05/T06 → T07 | ✅ |
| T08 | T07 | T07 → T08 | ✅ |
| T09 | T08 | T08 → T09 | ✅ |
| T10 | T09 | T09 → T10 | ✅ |

## Validação de colocalização de testes

| Tarefa | Camada | Matriz exige | Tarefa declara | Estado |
|---|---|---|---|---|
| T01 | documentação | nenhum | nenhum | ✅ |
| T02 | validação pura | unidade | unidade | ✅ |
| T03 | ambiente Docker | integração | integração | ✅ |
| T04 | modelos | unidade | unidade | ✅ |
| T05 | adaptador | unidade | unidade | ✅ |
| T06 | adaptador | unidade | unidade | ✅ |
| T07 | executor | integração | integração | ✅ |
| T08 | fluxo sintético | e2e | e2e | ✅ |
| T09 | preparação + fumaça | e2e | integração + e2e | ✅ |
| T10 | documentação | nenhum | nenhum | ✅ |
