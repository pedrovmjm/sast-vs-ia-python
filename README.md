# Harness experimental do TCC

Este repositório contém o texto do TCC e o harness usado para comparar seis
condições de análise de segurança sobre 26 aplicações Python do RealVuln v1.0.
As coletas C1–C6 estão concluídas. As saídas brutas permanecem locais e
imutáveis; o Git guarda código, contratos congelados e evidências compactas de
auditoria.

O host usa Git, PowerShell, Docker Desktop e as CLIs autenticadas de Cursor e
Codex. Python, Bandit e Semgrep são executados na imagem
`tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0`. O código dos alvos é tratado
como dado: não é importado, testado nem executado.

## Verificação

Com o Docker Desktop em execução, rode o gate rápido:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 quick
```

O gate completo também reconstrói a imagem, executa integrações Docker, a
fumaça sintética, `compileall`, `pip check` e as sondas de isolamento:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 build
```

Os executores de IA possuem testes próprios, sem chamadas externas:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-executores-ia.ps1
```

## Documentação mantida

- [`docs/EXECUCAO.md`](docs/EXECUCAO.md): ambiente, gates e fumaça RealVuln;
- [`docs/EXECUCAO-IA.md`](docs/EXECUCAO-IA.md): preparação, planejamento e
  execução de C3–C6;
- [`docs/ARTEFATOS_JSON.md`](docs/ARTEFATOS_JSON.md): contratos e artefatos
  produzidos pelo harness;
- [`docs/FONTES_E_INTEGRIDADE.md`](docs/FONTES_E_INTEGRIDADE.md): proveniência,
  licenças e controles de integridade.

## Estrutura essencial

- `config/`: fontes, filas, políticas e perfis congelados;
- `docker/`: imagem e dependências fixadas;
- `runner/`: modelos, adaptadores, preparação e executor SAST;
- `scripts/`: gates, testes de integração e executores C1–C6;
- `tests/`: testes unitários e fixtures próprias;
- `evidencias/`: inventários e auditorias pequenas, próprias para Git;
- `benchmark/`, `alvos/`, `oracle/`, `execucoes/` e `resultados/`: dados de
  terceiros ou saídas geradas, mantidos localmente e ignorados pelo Git.

## Estado das coletas

| Condição | Ferramenta | Entrada | Fechamento |
|---|---|---|---|
| C1 | Bandit 1.9.4 | código sanitizado | 26/26 |
| C2 | Semgrep CE 1.172.0 | código sanitizado | 26/26 |
| C3 | Cursor, GPT-5.6 Luna | código sanitizado | 78/78; 97 tentativas preservadas |
| C4 | Codex, GPT-5.6 Luna | código sanitizado | 78/78 |
| C5 | Cursor, GPT-5.6 Luna | código + alertas C1/C2 | 78/78; 91 tentativas preservadas |
| C6 | Codex, GPT-5.6 Luna | código + alertas C1/C2 | 78/78; 92 tentativas preservadas |

As auditorias publicadas estão em:

- `evidencias/coleta-c1-c2/auditoria-m2-t08.json`;
- `evidencias/coleta-c3/auditoria-m3-c3.json`;
- `evidencias/coleta-c5/auditoria-m3-c5.json`;
- `evidencias/coleta-c6/auditoria-m3-c6.json`.

C5 e C6 consumiram o mesmo conjunto congelado de 1.410 alertas C1/C2 por
repetição. As falhas anteriores permanecem preservadas e nunca são contadas
como relatórios sem achados. O oracle não foi consultado nessas auditorias;
TP, FP, FN, TN e métricas derivadas pertencem à etapa de avaliação.

## Política de versionamento

O repositório remoto recebe somente o necessário para reprodução e auditoria.
Saídas brutas, corpus, oracle, regras adquiridas e artefatos de build continuam
locais por volume, licença, cegamento ou possibilidade de regeneração. O
histórico de planejamento (`.specs/`), a skill usada para produzi-lo e auditorias
editoriais transitórias não fazem parte do artefato final.
