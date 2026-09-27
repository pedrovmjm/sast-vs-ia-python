# Estrutura do repositório

Documento de referência: o que cada diretório é, quem o cria, quem o consome,
se entra no Git e o que pode ser removido sem perder rastreabilidade.

O repositório tem **duas naturezas misturadas na mesma raiz**:

1. **Texto do TCC** — os arquivos `.tex` na raiz;
2. **Artefato experimental** — o repositório controlador (*harness*) descrito no
   Capítulo 7.

Isso é intencional (os capítulos servem como especificação aprovada, decisão
AD-001 em `.specs/project/STATE.md`), mas exige que o leitor saiba distinguir as
duas coisas. As tabelas abaixo fazem essa separação.

---

## 1. Visão em uma tela

```
tcc/
├── 01-fundamentacao-teorica.tex   ─┐
├── 02-estado-da-arte.tex           │  TEXTO DO TCC
├── 06-metodologia.tex              │  (especificação aprovada do protocolo)
├── 07-desenvolvimento.tex          │
├── 08-avaliacao-resultados.tex    ─┘
│
├── README.md                       Porta de entrada do artefato
├── compose.yaml                    Como o contêiner é executado
├── docker/                         Como o contêiner é construído
├── runner/                         Código Python do harness (roda no contêiner)
├── scripts/                        CLIs PowerShell do host + utilitários Python
├── tests/                          Testes unitários e fixtures próprias
├── config/                         Contratos congelados (locks, políticas, prompts)
├── docs/                           Esta documentação
├── .specs/                         Planejamento rastreável (spec, design, tasks)
├── spc-driven/                     Skill de planejamento (ferramenta, não artefato)
│
├── benchmark/    ─┐
├── alvos/         │  DADOS: adquiridos ou gerados. Ignorados pelo Git.
├── oracle/        │  Reconstruíveis a partir de config/ + scripts/.
├── execucoes/     │
├── resultados/    │
├── build/        ─┘
│
└── evidencias/                     Recortes pequenos e auditáveis, versionados
```

---

## 2. Domínios de acesso (o cegamento do Capítulo 7)

O Capítulo 7 define três domínios que não podem se contaminar. É a garantia
metodológica mais importante do projeto:

| Domínio | Diretórios | Regra |
|---|---|---|
| **Entrada** | `alvos/corpus-v1/ALVO-NNNN` | Único conteúdo montado na ferramenta analisada, sempre somente leitura. Sem `.git`, sem *walkthroughs*, sem oracle. |
| **Controle** | `config/`, `runner/`, `scripts/`, `execucoes/` | Configuração, fila, adaptadores e metadados. Nunca exposto à ferramenta analisada. |
| **Avaliação** | `oracle/` | *Ground truth* e avaliador oficial. Só acessível **depois** que a saída bruta da execução foi encerrada e hasheada. |

`oracle/` é irmão de `alvos/`, nunca ancestral nem descendente. Um contêiner
recebe `/entrada:ro`, `/saida:rw` e — apenas em C2 — `/opt/regras-semgrep:ro`.
Nada mais.

---

## 3. Diretórios do artefato (versionados)

### `runner/` — o harness

Código Python puro. **Roda dentro do contêiner**, nunca no host (o host não tem
Python instalado; decisão AD-002).

| Arquivo | Papel | Módulo do Capítulo 7 |
|---|---|---|
| `modelos.py` | Define `Achado v1` e `ManifestoExecucao v1` com validação fechada: campo desconhecido é recusado, campo indisponível fica `None`, nada é inferido. | base de todos |
| `aquisicao.py` | Valida proveniência (URL, commit, hash, licença) **antes** de qualquer download. Puro: não abre rede. | Aquisição |
| `corpus.py` | Contratos congelados do corpus e da fila; ranking SHA-256 que define a ordem; hash canônico de JSON. | Aquisição |
| `preparacao.py` | Sanitiza a árvore do alvo e gera o inventário canônico (`tree-sha256-v1`). Trata código de terceiros como dado: não importa, não executa. | Preparação |
| `configuracao.py` | Gera e valida a configuração imutável que arma a coleta (o *freeze*). | Orquestração |
| `fila.py` | Fila persistente, exclusiva (arquivo `.lock`) e retomável por tentativa. | Orquestração |
| `coleta.py` | Prepara cada tentativa, confere o inventário e valida a saída do wrapper. | Orquestração |
| `executor_sast.py` | Executa **dentro** do contêiner endurecido: dispara Bandit ou Semgrep, preserva artefatos, chama o adaptador. Nunca chama Docker. | Executores |
| `adaptadores/comum.py` | Primitivas puras: JSON estrito, hash do bruto, normalização sintática de caminho. | Adaptadores |
| `adaptadores/bandit.py` | Converte a saída nativa do Bandit 1.9.4 em `Achado v1`. | Adaptadores |
| `adaptadores/semgrep.py` | Converte a saída nativa do Semgrep CE 1.172.0 em `Achado v1`. | Adaptadores |
| `schemas/*.schema.json` | Contratos JSON Schema dos artefatos acima. | — |

> **Ausente hoje:** não existe módulo de **Pontuação** (invocar o avaliador
> oficial, calcular TP/FP/FN/TN e as métricas derivadas). O Capítulo 7 o prevê
> na Tabela 2. Pertence ao marco M4.

### `scripts/` — CLIs do host

PowerShell 5.1 (o host é Windows). São eles que falam com o Docker; o Python
nunca orquestra contêiner.

| Script | O que faz |
|---|---|
| `gate.ps1 quick/full/build` | Portão de qualidade. `quick` = testes Python; `full` = mais build da imagem, integrações Docker e fumaça sintética; `build` = mais `compileall`, sonda de runtime, `pip check`, versões e preflight embarcado. |
| `adquirir-corpus.ps1` | Adquire e verifica os 26 alvos nos commits fixados; sanitiza; gera inventários. |
| `executar-fumaca-realvuln.ps1` | Executa a fumaça descartável ponta a ponta sobre um alvo. |
| `executar-sast.ps1` | *Wrapper* de uma execução SAST isolada (um par condição–alvo). |
| `executar-coleta-c1-c2.ps1` | Orquestra a fila completa de 52 execuções C1/C2, serialmente. |
| `test-*.ps1` | Testes de integração dos scripts acima, executados pelo gate. |
| `gerar-graficos-sast.py` | Lê `resultados/` e produz `evidencias/graficos-sast/` (CSV e SVG descritivos). Não calcula TP/FP/FN. |
| `validar-repeticoes-ia.py` | Audita completude, estados e metadados das repetições C3–C6. `resultados/ia/` já contém as coletas C4 e C6; C3/C5 permanecem pendentes. |

### `config/` — contratos congelados

Tudo aqui é **entrada imutável** do experimento: se um arquivo muda, os
resultados anteriores deixam de ser comparáveis. O significado campo a campo
está em `ARTEFATOS_JSON.md`.

### `tests/` — verificação

`unittest` puro, executado no contêiner. `tests/fixtures/` contém saídas Bandit e
Semgrep **artificiais** (achado completo, vazio, duplicado, JSON inválido,
resultado parcial) e um `alvo-sintetico/` que nunca é importado nem executado:
serve apenas de entrada para a fumaça sintética.

### `docker/` — imagem reprodutível

| Item | Observação |
|---|---|
| `Dockerfile` | Base fixada por *digest*, usuário `10001`, `--require-hashes` na instalação. Não copia corpus, oracle nem regras. |
| `requirements.in` / `requirements.lock` | 69 pacotes, somente *wheels*, com hash por arquivo. |
| `regras-semgrep/` | **Ignorado pelo Git.** As regras do Semgrep CE têm licença própria que proíbe redistribuição (AD-004). Adquiridas localmente conforme `EXECUCAO.md`, verificadas por hash de árvore, montadas somente leitura apenas em C2. |

### `evidencias/` — o que vai para o TCC

Recortes pequenos, versionados, feitos para serem citados no texto. É a ponte
entre `resultados/` (grande, ignorado) e os capítulos.

| Subdiretório | Conteúdo |
|---|---|
| `corpus-realvuln-v1/` | Inventário e registro de sanitização por alvo, resumo do corpus, saída do validador oficial e auditoria do *ground truth*. |
| `primeira-execucao/` | Evidência da fumaça de 11/08 (M1): inventários, manifestos e resumo. `finalidade=fumaca`, `status=descartavel`. |
| `coleta-c1-c2/` | Configuração congelada, fila inicial, os 63 manifestos terminais e a auditoria de fechamento do M2. |
| `coleta-c6/` | Auditoria de fechamento da condição híbrida C6, com cobertura, retentativas, consumo e integridade, sem consultar o oracle. |
| `graficos-sast/` | CSV e SVG descritivos de C1/C2. |
| `host-observado-*.json`, `reavaliacao-risco-host-*.json` | Versões do host e a reavaliação de risco que autorizou a coleta. |

### `.specs/` — planejamento rastreável

`project/` (visão, roadmap, estado e decisões AD-001 a AD-016) e `features/`
(spec, design e tasks por incremento). É onde as decisões de projeto ficam
justificadas — material direto para o Capítulo 7 e para a defesa.

### `spc-driven/`

Uma *skill* de planejamento: a metodologia de trabalho do autor com o
assistente. **Não é artefato do TCC** e não é referenciada por nenhum código.
Ver `AUDITORIA-CAPITULO-07.md`, item D-1.

---

## 4. Diretórios de dados (ignorados pelo Git)

Nenhum deles entra no histórico. Todos são reconstruíveis a partir de `config/`
e `scripts/`. É isso que permite publicar o repositório sem redistribuir código
de terceiros, *ground truth* ou regras licenciadas.

| Diretório | Como é gerado | Reconstruível? |
|---|---|---|
| `benchmark/corpus-realvuln-v1/` | `adquirir-corpus.ps1` clona o RealVuln v1.0 e os 26 repositórios nos commits fixados. | Sim, com rede. |
| `alvos/corpus-v1/ALVO-NNNN/` | Exportação sanitizada de cada revisão, com identificador opaco. É o **único** conteúdo entregue às ferramentas. | Sim, deterministicamente: o inventário `tree-sha256-v1` prova a igualdade. |
| `alvos/execucoes/` | Áreas temporárias, uma por (condição, alvo, tentativa). Descartadas após persistir inventário e bruto. | Sim; é efêmero. Hoje está vazio, como esperado. |
| `oracle/realvuln-v1/` | *Ground truth* dos 26 repositórios e o `validate_gt.py` oficial. | Sim. Acesso restrito à etapa de pontuação. |
| `execucoes/fila-c1-c2.json` | Estado *runtime* da fila, com histórico por tentativa. | Não exatamente: é o registro do que aconteceu. O recorte auditável está em `evidencias/coleta-c1-c2/`. |
| `resultados/<execucao_id>/tentativa-NNN/` | Saída de cada tentativa. Ver `ARTEFATOS_JSON.md`, seção 5. | Não: é o dado primário do experimento. Sobrevive apenas via `evidencias/`. |
| `build/` | Logs de build Docker e PDFs de compilação do Capítulo 7. Recriado sob demanda; foi apagado na limpeza de 25/08. | Sim; descartável. |

### Nomenclatura das execuções

```
C1-ALVO-0002-R01 / tentativa-003
└┬┘ └────┬────┘ └┬┘  └────┬────┘
 │       │       │        └── tentativa: nova a cada retomada; nunca sobrescreve
 │       │       └─────────── repetição: R01 (C1/C2 são determinísticos)
 │       └─────────────────── alvo opaco: sem CWE, sem nome de aplicação
 └─────────────────────────── condição: C1 Bandit, C2 Semgrep, C3-C6 IA
```

Estados possíveis: `pendente`, `em_execucao`, `concluida`, `falha`. Uma execução
só vira `concluida` depois que saída e metadados foram gravados e hasheados.

---

## 5. Limpeza

Removidos em 25/08/2026, depois de confirmar que nada os referenciava e que a
evidência vigente em `evidencias/` corresponde à coleta real:

| Alvo | Era |
|---|---|
| `benchmark/corpus-realvuln-v1/superseded-*/` | Cópias substituídas na reaquisição do corpus (1.778 arquivos, ~50 MB) |
| `benchmark/.t09-inspecao-*/` | Clones rasos temporários de inspeção do M1 (~5 MB) |
| `build/` | Logs de build Docker e PDFs de compilação do capítulo, regeráveis |
| `resultados/C1-ALVO-TESTE-R01/` e o homônimo em `fumaca-pre-m2/` | Diretórios vazios deixados por `scripts/test-executar-sast.ps1` |

Resultado: 158 MB para 104 MB. `build/` é recriado pelo build do Docker e pela
compilação LaTeX; os demais não voltam.

Candidato restante: `spc-driven/` — ferramenta de planejamento, não artefato do
TCC. Ver `AUDITORIA-CAPITULO-07.md`, item D-1.

**Nunca apagar sem intenção explícita:** `evidencias/`, `config/`,
`execucoes/fila-c1-c2.json` e `resultados/*/tentativa-*/`. São o dado primário e
a cadeia de custódia do experimento.
