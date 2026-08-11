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

## Estrutura essencial

- `config/`: lock de fontes e exceção auditável do host;
- `docker/`: imagem e dependências fixadas; regras Semgrep locais são ignoradas;
- `runner/`: modelos, adaptadores, preparação e executor;
- `scripts/`: gates, testes de integração e CLIs do host;
- `tests/`: unidades, fixtures próprias e verificações da evidência;
- `evidencias/`: manifestos e resumos pequenos, próprios para auditoria;
- `benchmark/`, `alvos/` e `resultados/`: terceiros ou artefatos gerados, ignorados pelo Git.

O corpus completo, o oracle e a coleta principal ainda pertencem aos marcos seguintes.
