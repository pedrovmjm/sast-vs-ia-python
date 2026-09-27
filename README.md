# SAST tradicional vs. desenvolvimento assistido por IA

Infraestrutura experimental do TCC **“Análise Comparativa entre SAST
Tradicional e Ferramentas Empresariais de Desenvolvimento Assistido por IA para
Detecção de Vulnerabilidades em Aplicações Python”**.

O experimento compara seis condições de análise de segurança sobre 26
aplicações Python do RealVuln v1.0. As coletas C1–C6 estão concluídas. As saídas
brutas publicáveis, o oracle e os snapshots redistribuíveis do corpus fazem
parte do artefato auditável. Entradas sem licença identificada ou com material
sensível continuam reconstruíveis por URL, commit e SHA-256. Os fontes da
monografia ficam separados em `monografia/`.

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
  produzidos pela infraestrutura experimental;
- [`docs/FLUXO-E-RASTREABILIDADE.md`](docs/FLUXO-E-RASTREABILIDADE.md): fluxo
  C1–C6, arquivos de agente e implementação das restrições;
- [`docs/DADOS_AUDITAVEIS.md`](docs/DADOS_AUDITAVEIS.md): dados publicados,
  inventário SHA-256, licenças e reconstrução dos 26 alvos;
- [`docs/FONTES_E_INTEGRIDADE.md`](docs/FONTES_E_INTEGRIDADE.md): proveniência,
  licenças e controles de integridade.

## Estrutura essencial

- `config/`: fontes, filas, políticas e perfis congelados;
- `docker/`: imagem e dependências fixadas;
- `runner/`: modelos, adaptadores, preparação e executor SAST;
- `scripts/`: gates, testes de integração e executores C1–C6;
- `tests/`: testes unitários e fixtures próprias;
- `alvos/`: 16 snapshots sanitizados cuja licença permite redistribuição;
- `oracle/`: ground truth e validador oficiais do RealVuln v1.0;
- `execucoes/`: estado, alertas congelados e áreas de trabalho das coletas;
- `resultados/`: saídas primárias imutáveis, com exclusões documentadas;
- `evidencias/`: inventários e auditorias derivadas;
- `monografia/`: fontes LaTeX da monografia, separados do artefato experimental;
- `benchmark/`: cache local reconstruível, não versionado;
- `docker/regras-semgrep/`: regras locais não redistribuídas por licença.

## Estado das coletas

| Condição | Ferramenta | Entrada | Fechamento |
|---|---|---|---|
| C1 | Bandit 1.9.4 | código sanitizado | 26/26 |
| C2 | Semgrep CE 1.172.0 | código sanitizado | 26/26 |
| C3 | Cursor, GPT-5.6 Luna | código sanitizado | 78/78; 97 tentativas preservadas |
| C4 | Codex, GPT-5.6 Luna | código sanitizado | 78/78; 90 tentativas preservadas |
| C5 | Cursor, GPT-5.6 Luna | código + alertas C1/C2 | 78/78; 91 tentativas preservadas |
| C6 | Codex, GPT-5.6 Luna | código + alertas C1/C2 | 78/78; 92 tentativas preservadas |

As auditorias publicadas estão em:

- `evidencias/coleta-c1-c2/auditoria-m2-t08.json`;
- `evidencias/coleta-c3/auditoria-m3-c3.json`;
- `evidencias/coleta-c4/auditoria-m3-c4.json`;
- `evidencias/coleta-c5/auditoria-m3-c5.json`;
- `evidencias/coleta-c6/auditoria-m3-c6.json`.

C5 e C6 consumiram o mesmo conjunto congelado de 1.410 alertas C1/C2 por
repetição. As falhas anteriores permanecem preservadas e nunca são contadas
como relatórios sem achados. O oracle não foi consultado nessas auditorias;
TP, FP, FN, TN e métricas derivadas pertencem à etapa de avaliação.

## Política de versionamento

O repositório remoto recebe o máximo que pode ser redistribuído com segurança:
saídas brutas, oracle, estado, evidências e snapshots licenciados. Os dez alvos
sem publicação integral continuam auditáveis por origem, commit, inventário e
hashes. Regras Semgrep adquiridas, caches Git, entradas sem licença identificada
e uma chave privada de demonstração não são enviados. A decisão completa está
em [`docs/DADOS_AUDITAVEIS.md`](docs/DADOS_AUDITAVEIS.md).
