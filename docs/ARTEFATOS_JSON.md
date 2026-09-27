# Dicionário dos artefatos JSON

Todo arquivo `.json` do projeto pertence a **uma** de cinco famílias. Saber a
família já responde as três perguntas que importam: quem escreve, quem lê e se
pode ser editado à mão.

| Família | Onde | Quem escreve | Pode editar à mão? |
|---|---|---|---|
| **A. Contratos congelados** | `config/` | O autor, uma única vez, antes da coleta | **Não** depois do *freeze*. Editar invalida os resultados. |
| **B. Esquemas de validação** | `runner/schemas/` | O autor, ao definir o formato | Sim, mas cria uma nova versão do esquema |
| **C. Estado de execução** | `execucoes/` | O controlador, durante a coleta | **Nunca** |
| **D. Saída bruta e derivada** | `resultados/` | O controlador, por tentativa | **Nunca**. É o dado primário |
| **E. Evidência publicada** | `evidencias/` | Scripts de auditoria, ao fechar uma etapa | **Nunca**. É o que o TCC cita |

Fora dessas cinco há o `oracle/`, que é material de terceiros e nunca é
modificado, e `tests/fixtures/`, que é entrada artificial dos testes.

---

## 1. Família A — contratos congelados (`config/`)

São a **entrada imutável** do experimento. Juntos definem exatamente o que foi
analisado, com qual versão, em que ordem e sob qual autorização. Cada um é
hasheado e o hash entra na configuração da coleta; por isso alterar qualquer um
deles depois do *freeze* quebra a cadeia de rastreabilidade.

### `fontes.lock.json`

A **procedência de tudo que vem de fora**. Uma linha por fonte externa, com
URL oficial, versão/commit, *digest* e licença observada:

| Chave | Significado |
|---|---|
| `host_policy` | Versões recomendadas de Git, WSL, Docker Desktop e Engine. Comparadas com o host no *preflight*; a divergência não bloqueia, mas exige um *waiver*. |
| `sources.realvuln` | RealVuln v1.0: tag anotada, objeto da tag e commit desembrulhado. É o que impede clonar a `main` (hoje já em v2.0.0 com 66 repositórios). |
| `sources.python_image` | Imagem base `python:3.12.13-slim-bookworm` fixada pelo *manifest digest* amd64. |
| `sources.bandit`, `sources.semgrep` | Versão, SHA-256 do *wheel* e commit da tag. |
| `sources.*.license_observed` | Licenças efetivamente vistas no artefato, incluindo divergências (o RealVuln v1.0 declara MIT em `LICENSE` e Apache-2.0 em `pyproject.toml`). |

### `corpus-realvuln-v1.lock.json`

**A tabela de correspondência opaca.** Traduz `ALVO-0001 … ALVO-0026` no
`realvuln_id`, na URL e no commit reais. É deliberadamente o único lugar onde
essa tradução existe, e ele nunca é montado em contêiner analisado — é isso que
torna o identificador `ALVO-NNNN` cego para a ferramenta.

Contém ainda `quantidade_alvos: 26`, `politica_sanitizacao: sanitizacao-v1` e os
hashes do manifesto e do *ground truth* do benchmark.

### `espelhos-corpus-realvuln-v1.lock.json`

Três alvos (0015, 0021, 0023) cujas URLs oficiais do manifesto saíram do ar. O
arquivo autoriza um espelho público **apenas como transporte**: o objeto
adquirido tem que ter o SHA-1 completo oficial, senão a aquisição falha
(decisão AD-011). Registra `url_oficial`, `url_espelho`, `commit` e `motivo`.

### `politica-sanitizacao-v1.json`

A lista **fechada** do que é removido ao exportar cada revisão. Foi congelada
antes do estudo; mudar qualquer entrada obriga a regenerar as cópias de todas as
condições.

| Chave | Exemplos | Por quê |
|---|---|---|
| `segmentos_excluidos` | `.git`, `__pycache__`, `.venv`, `node_modules` | Metadados, caches e dependências instaladas não são o código sob análise |
| | `ground-truth`, `oracle`, `solution(s)`, `walkthrough(s)`, `writeup(s)` | **Evita vazar a resposta para dentro da entrada** |
| `arquivos_excluidos` | `.ds_store`, `thumbs.db`, `zone.identifier` | Ruído de sistema operacional e de download |
| `caminhos_excluidos` | 3 caminhos exatos | Os *symlinks* Git `120000` conhecidos, omitidos sem serem seguidos (decisão AD-012) |
| `modos_git_permitidos` | `100644`, `100755` | Só blob regular entra. Qualquer outro modo bloqueia a aquisição |

### `fila-c1-c2.lock.json`

**A ordem das 52 execuções, congelada antes de qualquer resultado.** Isso é o
que impede escolher a ordem depois de ver os achados.

| Chave | Significado |
|---|---|
| `algoritmo_ordem` | `sha256-ranking-v1` |
| `semente` | `m2-c1-c2-2026-08-11-v1`, publicada para reprodução |
| `corpus_lock_sha256` | Amarra a ordem ao corpus exato (hash canônico — ver seção 7) |
| `quantidade_execucoes` | 52 = 26 alvos x 2 condições |
| `ordem` | A lista literal de `execucao_id`, na sequência de execução |

### `host-risk-waiver.json` e `host-risk-waiver-m2.json`

Aceites de risco **assinados e com escopo**. O host roda versões de Git, WSL e
Docker anteriores a correções de segurança conhecidas (incluindo a CVE-2025-9074
do Docker Desktop). Em vez de esconder isso, o projeto registra a decisão:

| Chave | Significado |
|---|---|
| `versions` | Versões efetivamente observadas no host |
| `allowed_actions` | **O escopo.** O waiver do M1 vale para `sast-smoke`; o do M2 vale para `M2-T06/T07/T08` e nada mais |
| `required_controls` | Os controles compensatórios que continuam obrigatórios: sem rede, alvo somente leitura, usuário não root, capabilities removidas, `no-new-privileges`, sem `docker.sock` |
| `approval` | Identificador, referência histórica e, quando aplicável, commit da aprovação. As referências para `.specs/` permanecem como valores congelados; o conteúdo decisório está no próprio waiver e nas evidências de risco |

São **dois** arquivos de propósito: a decisão AD-009 estabelece que a exceção do
M1 não se estende implicitamente ao M2.

### `agentes/cursor-c3-v1.json`, `agentes/codex-c4-v1.json` e `agentes/codex-c6-v1.json`

Perfis das condições de IA. Eles compartilham prompt, schema e restrições. Os
campos específicos de cada cliente registram o identificador aceito pela CLI e
as limitações de observabilidade do produto.

| Chave | Significado |
|---|---|
| `perfil` | `principal`. O perfil complementar (Auto no Cursor, GPT-5.6 Terra no Codex) só é habilitado se aprovado no piloto |
| `modelo_solicitado` | `GPT-5.6 Luna` nos dois produtos |
| `modelo_cli_solicitado` | Identificador exato usado pela CLI do Cursor: `gpt-5.6-luna-medium` |
| `repeticoes` / `alvos` | 3 e 26, ou seja, 78 execuções por condição |
| `prompt_sha256` / `schema_saida_sha256` | Amarram o perfil ao texto exato da instrução e ao contrato de saída |
| `restricoes` | Somente leitura, sem executar código ou testes, sem Bandit/Semgrep, sem oracle, sem `docker.sock`, **sessão nova por repetição**, mesma instrução |
| `metadados_obrigatorios` | O que a sessão precisa registrar: versão do cliente, modelo solicitado/exibido, forma de verificação, id da sessão, tempos, tokens e hash da resposta bruta |
| `metadados_nulos_permitidos` | Exceções explícitas de observabilidade. No Codex, `modelo_exibido` pode ser `null` quando o JSONL não expõe o modelo; `modelo_verificacao` explica a ausência |
| `estado` | Estado no momento do freeze. Pode ser histórico: C6 permanece `aguarda-piloto` no contrato imutável, embora a coleta já esteja concluída |

O perfil C6 acrescenta `entrada_adicional`, `alertas_sast_lock` e o hash desse
lock. `agentes/alertas-sast-c6-v1.lock.json` contém uma entrada por alvo com o
SHA-256 do `alertas-sast.json`, contagens antes/depois da deduplicação e as
tentativas C1/C2 usadas como fonte. O lote recusa conteúdo divergente.

O perfil não deve ser atualizado retrospectivamente para refletir o andamento:
seu SHA-256 está registrado nos manifestos. O estado operacional atual fica nas
auditorias de fechamento em `evidencias/coleta-c3/`, `coleta-c4/`,
`coleta-c5/` e `coleta-c6/`.

### `agentes/schema-relatorio-ia-v1.json`

O **contrato de saída** que a IA precisa cumprir: um *array* JSON em que cada
item tem `arquivo`, `linha_inicial`, `linha_final`, `cwe` (no formato
`CWE-<número>`), `severidade` (`baixa`/`media`/`alta`/`critica`), `descricao` e
`recomendacao`. `additionalProperties: false` — nada além disso é aceito. Sem
achados, a resposta correta é `[]`.

O texto da instrução em si está em `agentes/prompt-relatorio-ia-v1.txt`
(versionado como arquivo justamente para não haver diferença por cópia manual).

---

## 2. Família B — esquemas de validação (`runner/schemas/`)

JSON Schema 2020-12. Não descrevem dados: **validam** os dados das famílias C, D
e E. São a definição executável das tabelas do Capítulo 7.

| Arquivo | Valida |
|---|---|
| `achado-v1.schema.json` | Um achado normalizado. Materializa a Tabela 3 (Esquema comum dos achados) |
| `execucao-v1.schema.json` | Um manifesto de execução. Estados, tempos, códigos de saída, hashes de artefato |
| `fila-c1-c2-v1.schema.json` | O estado da fila e o histórico por tentativa |
| `configuracao-coleta-c1-c2-v1.schema.json` | A configuração congelada da coleta |

---

## 3. Família C — estado de execução (`execucoes/`)

| Arquivo | Significado |
|---|---|
| `fila-c1-c2.json` | O estado vivo da fila. Cada item tem `execucao_id`, `estado`, `tentativa` e um `historico[]` que registra **toda** transição, inclusive as falhas e as interrupções. É aqui que se prova que nada foi sobrescrito |
| `.fila-c1-c2.json.lock` | Lock de exclusão mútua. Impede duas coletas simultâneas. Arquivo vazio por natureza |

Exemplo real de `historico` (C1-ALVO-0025-R01), lido de cima para baixo:

```
tentativa 1 → falha (formato)      manifesto preservado em tentativa-001/
tentativa 2 → interrompida          sem manifesto: o processo foi cortado
tentativa 3 → concluida             manifesto em tentativa-003/
```

A tentativa 1 **não foi apagada**. Ela continua em disco como tentativa
malsucedida, exatamente como o Capítulo 7 exige.

> **A fila é a fonte autoritativa da contagem.** Varrer `resultados/` procurando
> `estado: concluida` devolve **53**; a fila tem **52**. A diferença é um
> manifesto órfão em `C2-ALVO-0001-R01/tentativa-001`: o contêiner terminou e
> gravou o manifesto, mas o controlador foi interrompido antes de registrar o
> desfecho, então a tentativa foi refeita. Sempre conte pela fila ou pela maior
> tentativa de cada `execucao_id`.

---

## 4. Família D — saída por tentativa (`resultados/`)

Layout real:

```
resultados/C1-ALVO-0002-R01/tentativa-003/
```

Os arquivos aparecem nesta ordem cronológica, e a ordem é o próprio protocolo:

| # | Arquivo | O que é | Quando é escrito |
|---|---|---|---|
| 1 | `manifesto.pendente.json` | A execução declarada antes de começar: condição, alvo, comando, imagem, hash da entrada. Tempos e resultados ainda `null` | Antes de subir o contêiner |
| 2 | `manifesto.em_execucao.json` | O mesmo, com `inicio_utc` preenchido | Ao iniciar |
| 3 | `stdout.bin` / `stderr.bin` | Bytes crus dos fluxos, sem decodificação nem edição | Durante |
| 4 | `bruto.json` | **A saída nativa da ferramenta, intocada.** É a fonte de verdade de tudo o mais | Ao terminar. Renomeado de `.part` só depois do fim |
| 5 | `processo.json` | Comando, código de saída, códigos aceitáveis, início/término, duração monotônica, `timeout` (bool) e limite | Ao terminar |
| 6 | `versoes.json` | Versões observadas **dentro** do contêiner: `{"bandit":"1.9.4","python":"3.12.13","semgrep":"1.172.0"}` | Ao terminar |
| 7 | `avisos.json` | Só existe quando a ferramenta devolveu erros parciais (arquivo com erro de sintaxe, por exemplo). Preserva a lista estruturada e o hash do bruto correspondente | Se houver |
| 8 | `normalizado.json` | Os achados convertidos ao `Achado v1` pelo adaptador. **Só existe se a normalização deu certo** | Após o bruto ser fechado |
| 9 | `manifesto.json` | O manifesto terminal, com estado final e `artefatos_sha256` de **todos** os arquivos acima | Por último |

### Como ler um `manifesto.json`

| Campo | Leitura |
|---|---|
| `estado` | `concluida` ou `falha`. Só há esses dois estados terminais |
| `falha_tipo` | `null`, `formato`, `contaminada`, `timeout`… Descreve a causa, não é um estado extra |
| `finalidade` | `coleta` ou `fumaca`. **É a regra mecânica que separa o experimento do teste.** Nenhum item de fumaça entra na análise |
| `tentativa` | Sempre incrementa. Nunca reaproveita diretório |
| `entrada_sha256` | O hash da árvore entregue. C1 e C2 do mesmo alvo têm que ter o mesmo valor |
| `imagem` / `imagem_digest` | Tag e ID local da imagem usada nessa execução específica |
| `codigo_saida` | Para o Bandit, `1` significa "achou algo" e é sucesso |
| `duracao_monotonica_segundos` | Relógio monotônico, imune a ajuste de hora |
| `artefatos_sha256` | Hash de cada artefato produzido. Fecha a cadeia de custódia |

### Como ler um `normalizado.json`

Um *array* de `Achado v1`. O ponto central do esquema é o par
**original + normalizado**:

```json
"severidade_original": "LOW",   "severidade": "baixa",
"confianca_original":  "HIGH",  "confianca":  "alta",
"cwe_original":        "502",   "cwe":        "CWE-502"
```

O campo `*_original` é o valor cru da ferramenta; o outro é a forma normalizada
por um mapa fechado. **Quando não existe mapa congelado, o normalizado fica
`null`** — o controlador nunca chuta. Por isso `recomendacao` é sempre `null` em C1
(o Bandit não emite recomendação) e `confianca` normalizada é sempre `null` em
C2 (o Semgrep não usa a escala fechada). `texto_original` guarda o resultado
nativo inteiro em JSON canônico, e `saida_bruta_sha256` liga o achado ao
`bruto.json` de onde veio.

### Subdiretório `resultados/fumaca-pre-m2/`

Execuções da fumaça do M1, arquivadas antes da coleta principal para não se
misturarem. Todas têm `finalidade=fumaca`.

---

## 5. Família E — evidência publicada (`evidencias/`)

### `corpus-realvuln-v1/`

| Arquivo | Conteúdo |
|---|---|
| `ALVO-NNNN-inventario.json` | O inventário canônico: `algoritmo: tree-sha256-v1`, `entrada_sha256`, número de arquivos, tamanho total e a lista ordenada de `{caminho, sha256, tamanho_bytes}`. **É a prova de que C1 e C2 receberam bytes idênticos** |
| `ALVO-NNNN-sanitizacao.json` | O que a política removeu naquele alvo: `arquivos_incluidos`, `entradas_excluidas` e a lista `exclusoes` |
| `resumo.json` | O corpus inteiro: tag e commit do RealVuln, hashes dos locks, e por alvo o commit, a URL de transporte, se usou espelho, o `entrada_sha256`, número de arquivos e tamanho. Traz também `ground_truth: {repositorios: 26, entradas: 817, vulnerabilidades: 697, armadilhas_fp: 120}` |
| `ground-truth-resumo.json` | Auditoria do *ground truth* por alvo, com hash do arquivo e verificação de que a URL do GT bate com a URL do manifesto (3 divergências registradas) |
| `validacao-oficial.json` | Saída literal do `validate_gt.py` **oficial** do benchmark, com `codigo_saida: 0`. É a validação de terceiros, não a do autor |

> Os 817/697/120 divergem dos 796/676/120 anunciados no README do próprio
> benchmark. A decisão AD-010 opta pelos arquivos *machine-readable*, que o
> validador oficial aprova, e registra a divergência em vez de escondê-la.

### `primeira-execucao/` — a fumaça do M1

`inventario-C1.json` e `inventario-C2.json` (que devem ser byte a byte iguais),
`manifesto-C1.json`, `manifesto-C2.json` e `resumo.json`. Todos carregam
`finalidade: fumaca` e `status: descartavel`. **Demonstram integração, não
desempenho.**

### `coleta-c1-c2/` — o M2

| Arquivo | Conteúdo |
|---|---|
| `configuracao.json` | **O *freeze*.** A configuração imutável que armou a coleta: comandos de C1 e C2, commit do controlador, os 26 alvos com commit e hash de entrada, os hashes dos cinco contratos congelados, o ID da imagem, os limites do contêiner (`cpus: 2`, `memoria: 3g`, `pids: 256`, `rede: none`, `rootfs: read-only`, `usuario: 10001:10001`), o `timeout_segundos: 900` e a decisão de risco embutida |
| `fila-inicial.json` | A fila no instante zero: 52 itens, todos `pendente`, `historico` vazio. Comparada com `execucoes/fila-c1-c2.json`, mostra tudo o que aconteceu |
| `manifestos/<execucao_id>-T<NNN>.json` | Os 63 manifestos terminais preservados (52 sucessos + 11 tentativas anteriores). O sufixo `T001`/`T003` é o número da tentativa |
| `auditoria-m2-t08.json` | O fechamento do marco. Ver abaixo |

### `coleta-c3/`, `coleta-c4/`, `coleta-c5/` e `coleta-c6/` — condições de IA

Cada `auditoria-m3-cN.json` resume cobertura, passagens do lote, retentativas,
falhas preservadas, achados descritivos, tokens, duração, metadados e verificações
de integridade. As auditorias não contêm respostas brutas nem pontuação contra o
oracle.

### Como ler `auditoria-m2-t08.json`

| Bloco | O que afirma |
|---|---|
| `fila` | 52 itens, 52 terminais, 52 concluídas, 0 falhas, 0 pendentes |
| `resultados` | 26 alvos, 26 pares C1/C2, 52 com `finalidade=coleta`, **11 tentativas adicionais preservadas**, 63 manifestos |
| `integridade` | 0 áreas de execução residuais, 0 arquivos `.part` órfãos, 0 contêineres ativos ao final, `fumaca_misturada: false`, `fumaca_pre_m2_arquivada: true` |
| `observacao` | O relato honesto: nove execuções C1 falharam por `formato`, o adaptador foi corrigido, elas foram **reabertas explicitamente** e concluídas na tentativa 3 com uma imagem corretiva. As falhas originais continuam em disco |

### `graficos-sast/`

`sast-resumo.csv` (uma linha por execução: id, alvo, condição, ferramenta,
tentativa, estado, duração, achados, arquivos com achado, CWEs distintas) e dois
SVG. São **descritivos**: não há TP, FP ou FN, porque isso depende do oracle e
pertence à etapa de pontuação.

### Arquivos de host

`host-observado-m2-*.json` registra as versões vistas no momento do gate.
`reavaliacao-risco-host-m2-*.json` compara com as versões oficiais correntes,
cita a CVE relevante e conclui pela aceitação. É o insumo do waiver do M2.

---

## 6. Fora das cinco famílias

| Local | Conteúdo |
|---|---|
| `oracle/realvuln-v1/benchmark-manifest.json` | O manifesto **oficial** do benchmark: 26 repositórios com URL e commit. Material de terceiros, nunca modificado |
| `oracle/realvuln-v1/ground-truth/<repo>/ground-truth.json` | A resposta: `findings[]` com `is_vulnerable`, classe da vulnerabilidade, arquivo, linhas e CWE. Inclui as armadilhas de falso positivo (`is_vulnerable: false`). **Acesso só na pontuação** |
| `oracle/realvuln-v1/validate_gt.py` | Validador oficial. Executado, nunca alterado |
| `tests/fixtures/bandit/*.json`, `tests/fixtures/semgrep/*.json` | Saídas artificiais para testar os adaptadores: achado completo, vazio, duplicado, inválido, parcial com erros, não finito. Não vêm do corpus |

---

## 7. Armadilha: existem duas convenções de hash

O mesmo nome de campo carrega valores diferentes conforme quem o escreveu:

| Convenção | Como | Quem usa | Exemplo para `config/corpus-realvuln-v1.lock.json` |
|---|---|---|---|
| **Bytes crus** | SHA-256 do arquivo como está em disco (`Get-FileHash`) | `scripts/adquirir-corpus.ps1` → `evidencias/corpus-realvuln-v1/resumo.json` | `c66cb933…` |
| **JSON canônico** | SHA-256 de `json.dumps(sort_keys=True, separators=(",",":"))` em UTF-8 | `runner/corpus.py` e `runner/configuracao.py` → `config/fila-c1-c2.lock.json`, `evidencias/coleta-c1-c2/configuracao.json` | `54e98c0d…` |

Os dois estão corretos e nenhum contradiz o outro: o segundo é imune a
reformatação e reordenação de chaves, o primeiro não. **Mas o campo se chama
`corpus_lock_sha256` nos dois casos**, sem indicar a convenção. Ao comparar
hashes entre artefatos, confirme antes qual convenção cada um usa.
