# Harness experimental do TCC

Este repositório implementa o protocolo comparativo descrito em `06-metodologia.tex` e `07-desenvolvimento.tex`. O primeiro marco está reproduzível: ambiente Docker fixado, adaptadores Bandit/Semgrep, executor isolado, fumaça sintética e uma primeira execução descartável sobre um alvo RealVuln v1.0.

O host usa somente Git, PowerShell e Docker Desktop. Python, Bandit e Semgrep são executados dentro da imagem `tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0`. Código dos alvos é tratado como dado: não é importado, testado nem executado.

## Verificação rápida

Com o Docker Desktop em execução:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 quick
```

O gate completo do marco é:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 build
```

Ele reconstrói a imagem, executa todos os testes, as integrações Docker e a fumaça sintética, verifica isolamento, dependências e versões. A execução validada em 11 de agosto de 2026 passou com 132 testes Python, 18 testes do wrapper e 8 testes de integração Docker, sem falhas ou testes ignorados.

## Primeira execução RealVuln

A evidência rastreada está em `evidencias/primeira-execucao/`. Ela registra `finalidade=fumaca` e `status=descartavel`; portanto, não integra a futura coleta principal. C1 e C2 receberam uma entrada de seis arquivos com o mesmo inventário `tree-sha256-v1`, SHA-256 `60913ac90d496cf087a5fe6e9a4dbb04882c862a93f7d094eebb692d41467206`.

Para uma reprodução local independente, depois de adquirir o bundle fixado de regras Semgrep conforme `docs/EXECUCAO.md`, use nomes novos para não sobrescrever a evidência publicada:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-fumaca-realvuln.ps1 `
  -AlvoId ALVO-REPRO-LOCAL `
  -EvidenciaNome reproducao-local
```

Consulte `docs/EXECUCAO.md` para preparação completa, artefatos e controles. A proveniência, licenças e riscos conhecidos estão em `docs/FONTES_E_INTEGRIDADE.md`.

## Documentação

Comece por [`docs/README.md`](docs/README.md), que é o índice e a visão geral do artefato:

- [`docs/ESTRUTURA.md`](docs/ESTRUTURA.md): o que é cada pasta, quem a gera e o que pode ser apagado;
- [`docs/ARTEFATOS_JSON.md`](docs/ARTEFATOS_JSON.md): o significado de cada arquivo `.json`, campo a campo;
- [`docs/EXECUCAO-IA.md`](docs/EXECUCAO-IA.md): configuração e execução separada dos cenários C3–C6 com Cursor e Codex;
- [`docs/FLUXO-C6-CODEX-SAST.md`](docs/FLUXO-C6-CODEX-SAST.md): como os alertas de C1/C2 são congelados, enviados ao Codex e auditados em C6;
- [`docs/AUDITORIA-CAPITULO-06.md`](docs/AUDITORIA-CAPITULO-06.md) e [`docs/AUDITORIA-CAPITULO-07.md`](docs/AUDITORIA-CAPITULO-07.md): onde os capítulos divergem do repositório atual.

## Estrutura essencial

- `config/`: lock de fontes e exceção auditável do host;
- `docker/`: imagem e dependências fixadas; regras Semgrep locais são ignoradas;
- `runner/`: modelos, adaptadores, preparação e executor;
- `scripts/`: gates, testes de integração e CLIs do host;
- `tests/`: unidades, fixtures próprias e verificações da evidência;
- `evidencias/`: manifestos e resumos pequenos, próprios para auditoria;
- `benchmark/`, `alvos/` e `resultados/`: terceiros ou artefatos gerados, ignorados pelo Git.

## Estado atual

O corpus dos 26 alvos foi adquirido e validado, e a coleta censitária de C1 e C2 foi concluída em 11 de agosto de 2026: 52 execuções terminais, 26 pares C1/C2, nenhuma falha na fila final e 11 tentativas malsucedidas preservadas em disco. A auditoria de fechamento está em `evidencias/coleta-c1-c2/auditoria-m2-t08.json`.

As condições de IA estão especificadas em `config/agentes/`. C4 e C6 possuem
78 unidades válidas e zero chamadas pendentes em cada condição; C3 e C5 ainda
não foram coletadas. C6 consumiu o conjunto congelado de 1.410 alertas C1/C2 e
preservou 92 tentativas: 78 concluídas e 14 falhas de formato anteriores. O
fechamento está em `evidencias/coleta-c6/auditoria-m3-c6.json`. A pontuação
contra o oracle e as métricas adjudicadas do Capítulo 8 pertencem ao marco
seguinte.
