# Auditoria: Capítulo 7 proposto x repositório real

**Data:** 2026-08-25
**Base auditada:** `main` em `af6fa31`
**Referência:** `07-desenvolvimento.tex`, revisão de 11/08/2026 09:49

Este documento compara, seção por seção, o que o Capítulo 7 promete com o que o
repositório contém hoje. Não altera o `.tex`: aponta o que precisa mudar.

---

## Resumo executivo

O artefato está **substancialmente à frente** do capítulo. O Capítulo 7 foi
escrito no fechamento do M1 (fumaça) e não foi atualizado depois do M2, que
concluiu a coleta censitária de C1 e C2 no mesmo dia, algumas horas depois.

| | Capítulo diz | Repositório tem |
|---|---|---|
| Coleta C1/C2 | "permanece futura" | **Concluída**: 52 execuções, 26 pares, 1.416 achados, auditoria fechada |
| Módulos | 6 módulos lógicos | 5 implementados; **Pontuação não existe** |
| `resultados/` | `brutos/` e `normalizados/` | `<execucao_id>/tentativa-NNN/` |
| Desvios | "não há desvios a relatar" | **Há pelo menos três** e são exatamente do tipo que a §7.9 manda relatar |
| C3–C6 | descritos em detalhe | apenas configuração congelada, `estado: aguarda-piloto` |

A boa notícia: as afirmações **técnicas verificáveis** do capítulo (comandos,
isolamento, campos preservados, cegamento) conferem. O problema é de
**tempo verbal e de estado**, não de veracidade do desenho. São 14 divergências,
listadas como C-1 a C-14.

---

## 1. Estrutura do repositório (§7.2, Tabela 1)

| Diretório previsto | Existe? | Observação |
|---|---|---|
| `benchmark/` | Sim | Contém também 4 subdiretórios obsoletos — ver D-3 e D-4 |
| `alvos/` | Sim | `alvos/corpus-v1/ALVO-0001..0026` + `alvos/execucoes/` (efêmero, vazio) |
| `oracle/` | Sim | Irmão de `alvos/`, jamais montado. Regra do capítulo respeitada |
| `runner/` | Sim | Sem os `prompts` e sem os `testes` que o capítulo aloca nele — ver C-3 |
| `docker/` | Sim | `regras-semgrep/` ignorado pelo Git, como a §7.5.3 promete |
| `execucoes/` | Sim | `fila-c1-c2.json` + o `.lock` de exclusão mútua |
| **`resultados/brutos/`** | **Não** | Ver C-2 |
| **`resultados/normalizados/`** | **Não** | Ver C-2 |

**Diretórios reais que a Tabela 1 não menciona:** `config/`, `scripts/`,
`tests/`, `docs/`, `evidencias/`, `build/`, `.specs/`, `spc-driven/`.

A ausência mais grave é `evidencias/`: é de lá que sai **todo número citado no
próprio capítulo**. Uma tabela de estrutura que não lista a fonte das evidências
deixa o leitor sem o caminho de verificação.

---

## 2. Módulos do harness (§7.3.1, Tabela 2)

| Módulo previsto | Implementado em | Estado |
|---|---|---|
| Aquisição | `runner/aquisicao.py`, `runner/corpus.py` | Completo |
| Preparação | `runner/preparacao.py` | Completo |
| Orquestração | `runner/fila.py`, `runner/coleta.py`, `runner/configuracao.py` | Completo |
| Executores | `runner/executor_sast.py` | **Parcial**: só SAST. Não há executor de sessão de IA |
| Adaptadores | `runner/adaptadores/{bandit,semgrep}.py` | **Parcial**: não há adaptador de resposta de IA |
| **Pontuação** | — | **Não existe** |

Nenhum arquivo do repositório invoca `oracle/realvuln-v1/validate_gt.py` como
avaliador nem calcula TP, FP, FN, TN, precisão, *recall*, F1/F2/F3 ou taxa de
falsos positivos. A §7.7 inteira é prospectiva. Isso está coerente com o
ROADMAP (marco M4), mas o capítulo não sinaliza.

---

## 3. Adaptador do Bandit (§7.5.2) — verificação linha a linha

| Afirmação do capítulo | Veredito | Evidência |
|---|---|---|
| "invocado recursivamente sobre a raiz sanitizada e emitirá JSON" | **Verdadeiro** | `--recursive /entrada --format json` |
| Forma-base do comando | **Verdadeiro e exato** | 37 manifestos registram o comando **byte a byte igual** ao bloco do capítulo, sem nenhuma opção extra |
| "O comando efetivo... será armazenado no manifesto" | **Verdadeiro** | Campo `comando` em todo `manifesto.json` |
| "incluindo opções de exclusão indispensáveis ao funcionamento" | **Vazio na prática** | Nenhuma exclusão foi necessária. A frase sugere que houve alguma; convém dizer que não houve |
| "O conjunto nativo de *plugins* será mantido" | **Verdadeiro** | Nenhum `--skip`, `--tests` ou `--ini` no comando |
| "nenhum filtro de severidade ou confiança será aplicado depois de conhecidos os resultados" | **Verdadeiro** | Nenhum `-l`, `-i`, `--severity-level` ou `--confidence-level` |
| "preservará identificador do teste, mensagem, arquivo, intervalo, severidade, confiança e CWE" | **Verdadeiro** | `test_id`→`regra`, `issue_text`→`descricao`, `filename`→`arquivo`, `line_number`+`line_range`→`linha_inicial`/`linha_final`, `issue_severity`, `issue_confidence`, `issue_cwe.id`→`CWE-N`. Preserva ainda `code`→`evidencia` e o resultado inteiro em `texto_original` |

### O que falta dizer (§7.5.2)

1. **Tempo verbal.** Está todo em futuro. O adaptador já rodou 26 vezes em
   coleta real.
2. **Código de saída 1 é sucesso.** O Bandit sai com `1` quando encontra
   achados. Sem essa frase, a Tabela 7 (que mostra "código 1; estado
   concluída") parece contraditória. Hoje isso só está em `docs/EXECUCAO.md`.
3. **Erros parciais também ocorrem no Bandit.** O capítulo só trata disso na
   seção do Semgrep. Na coleta real, ALVO-0023 e ALVO-0024 produziram
   `syntax error while parsing AST from file`, preservados em `avisos.json` com
   o hash do bruto. A simetria de tratamento deveria estar no texto.
4. **O adaptador foi corrigido durante a coleta.** Ver C-7 e C-8. Isso pertence
   à §7.9, não a esta seção, mas nasce aqui.

---

## 4. Adaptador do Semgrep CE (§7.5.3) — verificação linha a linha

| Afirmação do capítulo | Veredito | Evidência |
|---|---|---|
| "adquiridas do repositório oficial em diretório local ignorado pelo Git" | **Verdadeiro** | `/docker/regras-semgrep/` no `.gitignore`; procedimento em `docs/EXECUCAO.md` |
| "identificadas por origem, revisão e *hash*, e não são redistribuídas" | **Verdadeiro** | commit `40b8c63f75dc…`, árvore `sha256:29eb4185…`, 717 arquivos; decisão AD-004 |
| "somente o *bundle* verificado é montado como leitura em `/opt/regras-semgrep`; ele não integra a imagem" | **Verdadeiro** | O `Dockerfile` não copia regras; o `compose.yaml` monta `read_only: true` |
| "não há consulta ao registro remoto do Semgrep" | **Verdadeiro** | `--metrics=off`, `network_mode: none`, `SEMGREP_ENABLE_VERSION_CHECK=0`, `SEMGREP_SEND_METRICS=off` |
| Forma observada do comando | **Verdadeiro e exato** | 30 manifestos registram o comando **byte a byte igual** ao bloco do capítulo |
| "preservará identificador da regra, mensagem, caminho, intervalo, metadados CWE, severidade e conteúdo adicional" | **Verdadeiro** | `check_id`→`regra`, `extra.message`→`descricao`, `path`→`arquivo`, `start.line`/`end.line`, `extra.metadata.cwe`, `extra.severity`, mais `extra.lines`→`evidencia`, `extra.fix`→`recomendacao`, `extra.metadata.confidence`→`confianca_original` e o resultado inteiro em `texto_original` |
| "Erros de análise e arquivos ignorados serão mantidos no registro bruto" | **Verdadeiro e exercitado** | C2-ALVO-0023 registrou `PartialParsing` em `avisos.json`, com o bruto preservado |

### O que precisa ser corrigido (§7.5.3)

1. **"As regras públicas de segurança para Python" descreve mal o conjunto.**
   O que é montado é a árvore `python/` **inteira** do `semgrep-rules`: 717
   arquivos em 23 diretórios que incluem `correctness/`, `lang/` e regras de
   boas práticas por *framework*, não apenas os subdiretórios `security/`.
   O comando usa `--config /opt/regras-semgrep/python`, ou seja, **carrega
   tudo**.

   Isso não é um erro do experimento — é uma escolha legítima e congelada antes
   da coleta. Mas muda a leitura dos resultados: parte dos alertas de C2 é de
   corretude, não de segurança, e isso afeta diretamente a taxa de falsos
   positivos discutida no Capítulo 8. **Precisa estar escrito.**

2. **O adaptador exige `version == "1.172.0"` no documento.** Qualquer outra
   versão do Semgrep faz a normalização falhar de propósito. É um controle de
   reprodutibilidade forte e o capítulo não o menciona.

3. **A confiança normalizada é sempre nula em C2.** O Semgrep emite
   `extra.metadata.confidence`, preservado em `confianca_original`, mas não há
   mapa fechado para normalizá-la; `confianca` fica `null`. A Tabela 3 diz
   "Valor bruto preservado juntamente com a forma normalizada", o que sugere que
   as duas existem sempre. Vale uma ressalva.

4. **Tempo verbal.** "A forma efetivamente observada do comando foi" está
   correto, mas descreve a fumaça. Hoje é o comando de 26 execuções de coleta.

---

## 5. Divergências consolidadas

### C-1 — O capítulo afirma que a coleta principal não foi executada

**Onde:** parágrafos de abertura, §7.7 e §7.9.
**Realidade:** a coleta C1/C2 está **concluída e auditada**.

| Medida | Valor |
|---|---|
| Execuções na fila | 52 (26 alvos x 2 condições), todas terminais |
| Concluídas / falhas na fila final | 52 / 0 |
| Manifestos preservados | 63 (52 finais + 11 tentativas anteriores) |
| Achados normalizados | 1.416 (C1: 700, C2: 716) |
| Tempo somado | 921,5 s (C1: 40,1 s; C2: 881,4 s) |
| Fonte | `evidencias/coleta-c1-c2/auditoria-m2-t08.json`, `evidencias/graficos-sast/sast-resumo.csv` |

**Ação:** reescrever a abertura, a §7.7 e a §7.9. Os resultados em si pertencem
ao Capítulo 8, mas o Capítulo 7 precisa parar de dizer que não houve coleta.

### C-2 — `resultados/brutos/` e `resultados/normalizados/` não existem

Esta é a divergência que mais confunde na leitura do capítulo, então vale
detalhar. **O bruto e o tratado existem** — não estão em duas árvores separadas,
estão lado a lado dentro de cada tentativa:

```
resultados/C1-ALVO-0002-R01/tentativa-003/
├── manifesto.pendente.json      declaração antes de começar
├── manifesto.em_execucao.json   início registrado
├── stdout.bin / stderr.bin      fluxos crus
├── bruto.json          ←──────  O "BRUTO" do capítulo
├── processo.json                comando, exit code, duração, timeout
├── versoes.json                 versões observadas no contêiner
├── avisos.json                  erros parciais, se houver
├── normalizado.json    ←──────  O "TRATADO" do capítulo
└── manifesto.json               terminal, com artefatos_sha256 de todos acima
```

#### A garantia do capítulo é preservada, por outro mecanismo

O que a Tabela 1 quer garantir é que o normalizado **não possa** ser produzido
antes de o bruto estar fechado. Isso vale hoje, por quatro mecanismos:

1. O bruto é escrito como `bruto.json.part` e só renomeado depois que o processo
   termina;
2. o adaptador é **puro** — recebe bytes e proveniência, não abre disco, rede
   nem oracle;
3. cada achado carrega `saida_bruta_sha256`, que o amarra criptograficamente ao
   bruto de origem;
4. o `manifesto.json` terminal só é aceito quando `artefatos_sha256` cobre os
   dois arquivos.

Ou seja: a garantia é **temporal e criptográfica**, não topológica.

#### E o layout atual é melhor que o proposto

| | Duas árvores (capítulo) | Por tentativa (real) |
|---|---|---|
| Hierarquia | Duplicada: `brutos/C1-ALVO-0002-R01/tentativa-003/` **e** `normalizados/C1-…/tentativa-003/` | Uma só |
| Tentativa que falhou | Órfã em `brutos/`, sem par em `normalizados/` — difícil de auditar | A **ausência** de `normalizado.json` dentro da pasta já é o sinal |
| Auditoria de uma tentativa | Precisa cruzar dois lugares | Tudo que o manifesto hasheia está junto |

#### Mas há uma lacuna real, e é essa que você está sentindo

A Tabela 1 promete três coisas em `resultados/normalizados/`:

| Prometido | Existe? |
|---|---|
| "Achados no esquema comum" | **Sim** — `normalizado.json` |
| "correspondências" | **Não** — o casamento com o *ground truth* |
| "métricas derivadas" | **Não** — TP/FP/FN/TN, precisão, *recall*, F1/F2/F3 |

Duas das três **não existem em lugar nenhum**. São a saída do módulo de
Pontuação (C-5), que não foi implementado. Então a resposta honesta a "não vejo
nada" é: uma parte é diferença de nome, e outra parte genuinamente ainda não
foi construída.

#### Recomendação

Manter o layout por tentativa e mover a fronteira do capítulo para onde ela
realmente importa. O corte não é *bruto x normalizado* — os dois são produzidos
sem oracle. O corte é **coleta x pontuação**, porque a correspondência é o
primeiro artefato que toca o `oracle/`:

```
resultados/
├── C1-ALVO-0002-R01/tentativa-NNN/   COLETA — existe hoje
│                                     bruto + normalizado, sem oracle
└── pontuacao/                        PONTUAÇÃO — não existe (M4)
    ├── entrada-avaliador/            achados no formato do RealVuln
    ├── correspondencias/             saída do validate_gt.py oficial
    └── metricas/                     TP/FP/FN/TN e derivadas
```

Isso preserva a intenção da Tabela 1 (separar o que é preservado sem edição do
que é derivado) e ainda **fortalece o argumento de cegamento**, porque torna
visível na própria árvore de diretórios o ponto exato em que o oracle entra.

**Ação:** corrigir a Tabela 1 com o layout real e acrescentar `pontuacao/` como
previsto para o M4.

### C-3 — A Tabela 1 aloca no `runner/` coisas que estão fora dele

O capítulo diz que `runner/` contém "esquemas, adaptadores, *prompts* e testes".
Na prática: esquemas e adaptadores sim; **os *prompts* estão em
`config/agentes/`** e **os testes estão em `tests/`, na raiz**.

### C-4 — A Tabela 1 omite `config/`, `scripts/`, `tests/`, `docs/` e `evidencias/`

Ver seção 1. `evidencias/` é a omissão crítica.

### C-5 — Não existe módulo de Pontuação, e o avaliador oficial nem foi adquirido

Ver seção 2: a Tabela 2 lista seis módulos e cinco existem.

Há um agravante. A §7.7 diz que "os adaptadores converterão os achados ao
formato de entrada aceito pelo **avaliador oficial do RealVuln**". Esse avaliador
**não está em `oracle/`**, que contém apenas `benchmark-manifest.json`,
`ground-truth/` e `validate_gt.py`.

`validate_gt.py` não é o avaliador: ele confere se o *ground truth* está bem
formado. O avaliador de verdade é `score.py` mais o pacote `scorer/`
(`matcher.py` faz a correspondência por caminho, CWE e tolerância de linha;
`metrics.py` produz TP/FP/FN/TN, precisão, *recall*, F1, F2, F3 e FPR). Os
arquivos existem no commit fixado e já estão no repositório *bare* adquirido,
mas nunca foram extraídos nem hasheados.

O Capítulo 6, passo 1 do protocolo, exige registrar "os *hashes* do manifesto, do
*ground truth* e do avaliador oficial" — cumprido pela metade. Detalhes em
[`AUDITORIA-CAPITULO-06.md`](AUDITORIA-CAPITULO-06.md), item M-3.

**Ação:** extrair `score.py` e `scorer/` para `oracle/realvuln-v1/` e registrar
os hashes antes do M4. E distinguir no texto "validador do *ground truth*" de
"avaliador", porque hoje os dois capítulos usam a mesma palavra para os dois.

### C-6 — Duas convenções de hash sob o mesmo nome de campo

`corpus_lock_sha256` vale `c66cb933…` em `evidencias/corpus-realvuln-v1/resumo.json`
(SHA-256 dos bytes crus, via `Get-FileHash` no PowerShell) e `54e98c0d…` em
`config/fila-c1-c2.lock.json` e `evidencias/coleta-c1-c2/configuracao.json`
(SHA-256 do JSON canônico, via `runner/corpus.py`).

Os dois estão corretos e nenhum invalida o outro. Mas um leitor que compare os
dois artefatos conclui, erradamente, que o corpus mudou. **Ação:** documentar a
convenção — feito em `ARTEFATOS_JSON.md`, seção 7 — e, idealmente, renomear um
dos campos (`..._sha256_canonico`) numa próxima versão do esquema.

### C-7 — A imagem foi reconstruída no meio de um bloco de coleta

**O capítulo, §7.5.1:** "depois do congelamento de um bloco de coleta, essa
imagem não poderá ser reconstruída até o término do bloco."

**O que ocorreu:** das 52 execuções finais, 43 usaram a imagem congelada
`sha256:4680184d…` e **9 usaram uma imagem corretiva `sha256:fde946f0…`**,
construída durante o bloco para corrigir o adaptador do Bandit.

Isto é uma **violação literal da regra que o próprio capítulo estabelece**.
Está registrado com honestidade em `auditoria-m2-t08.json` e nos manifestos, mas
não aparece no capítulo. **Ação obrigatória:** relatar na §7.9 e decidir
explicitamente entre (a) reconhecer o desvio e justificá-lo, ou (b) reexecutar
as 9 tarefas com uma imagem única. A opção (a) é defensável; o silêncio não é.

### C-8 — Há desvios de coleta a relatar, ao contrário do que a §7.9 diz

**O capítulo:** "Até a versão atual deste capítulo, a coleta principal ainda não
foi executada e, portanto, não há desvios de coleta observados a relatar."

Desvios efetivamente observados:

| # | Desvio | Registro |
|---|---|---|
| 1 | **9 falhas C1 com `falha_tipo: formato`.** O adaptador do Bandit recusava `line_range` cujo primeiro elemento não era o `line_number`. Corrigido (commit `22f1ba8`), reaberto explicitamente e concluído na tentativa 3 | `execucoes/fila-c1-c2.json`, histórico dos itens; `auditoria-m2-t08.json` |
| 2 | **1 falha C2 com `falha_tipo: contaminada`** em C2-ALVO-0002 tentativa 1: "entrada ficou inválida depois da execução". Reexecutada na tentativa 2 | `resultados/C2-ALVO-0002-R01/tentativa-001/manifesto.json` |
| 3 | **1 interrupção** do processo controlador, que devolveu a tarefa à fila com nova tentativa, preservando a anterior | histórico de C1-ALVO-0025-R01 |

Sobre o desvio 1: a §7.9 exige que "a decisão não poderá depender de a execução
ter produzido resultado favorável". A correção foi num *bug de leitura de
formato* — o adaptador rejeitava saída válida do Bandit —, não numa escolha
motivada pelos achados. **É defensável.** Mas precisa estar escrito com essa
justificativa explícita, porque o adaptador foi alterado depois de ver saídas
reais.

### C-9 — A contagem de testes está desatualizada

**O capítulo, §7.7:** "o gate reuniu 132 testes Python, 18 testes do *wrapper* e
8 integrações Docker".

Hoje há **250 métodos `test_`** em 12 arquivos. O M2 acrescentou
`test_corpus.py` (51), `test_fila.py` (30), `test_coleta.py` (19) e
`test_configuracao.py` (8). O número 132 descreve o fechamento do M1.

*(Os contadores de wrapper e integração Docker não foram reexecutados nesta
auditoria — exigem Docker em execução. Devem ser remedidos com
`scripts/gate.ps1 build` antes da versão final do capítulo.)*

### C-10 — A Tabela 7 (§7.8) descreve a fumaça, não a configuração efetiva

O título é "Configuração observada no primeiro incremento" e os valores estão
**corretos para a fumaça**. Mas o capítulo os apresenta como "registro da
configuração efetiva", e a configuração efetiva da coleta é outra:

| Registro | Tabela 7 (fumaça) | Coleta real |
|---|---|---|
| Imagem | `sha256:a08aacb9…` | `sha256:4680184d…` (43 execuções) e `sha256:fde946f0…` (9) |
| Entrada | DSVW, 6 arquivos, 23.610 B | 26 alvos, hashes em `evidencias/coleta-c1-c2/configuracao.json` |
| C1 | 0,890 s, 1 achado | 26 execuções, 40,1 s somados, 700 achados |
| C2 | 29,873 s, 1 achado | 26 execuções, 881,4 s somados, 716 achados |

**Ação:** manter a Tabela 7 como "configuração da fumaça" e acrescentar uma
tabela nova com a configuração congelada da coleta.

### C-11 — `.specs/project/STATE.md` registra um ID de imagem que não existe

O bloco de *freeze* do M2-T06 cita `sha256:3aab47b08e5defe…`. Esse ID **não
aparece em nenhum manifesto** nem em `evidencias/coleta-c1-c2/configuracao.json`,
que registra `sha256:4680184d…`. É inconsistência interna do documento de
estado, não dos dados. **Ação:** corrigir o STATE.md.

### C-12 — Os locks do controlador estão dentro da imagem que analisa o alvo

O `.dockerignore` libera `config/*.json` e o `Dockerfile` faz
`COPY config/ /opt/tcc/config/`. Isso coloca **`corpus-realvuln-v1.lock.json`
— a tabela de correspondência entre `ALVO-NNNN` e o nome/URL reais —** dentro da
imagem em que Bandit e Semgrep são executados.

**Não compromete C1 e C2.** Bandit e Semgrep são binários determinísticos que
leem apenas `/entrada`; não existe caminho pelo qual esse arquivo influencie a
saída. Os resultados atuais são válidos.

**Mas contradiz a §7.2**, que diz que o domínio de controle não é alcançável a
partir da ferramenta, e **vira um problema real em C3–C6**, quando um agente com
capacidade de leitura livre estiver no lugar do binário. **Ação:** restringir o
`.dockerignore` a `!config/fontes.lock.json` (o único que o *preflight*
embarcado usa) antes de iniciar o M3.

### C-13 — Existe um manifesto `concluida` órfão: contar por diretório dá 53, não 52

Em `resultados/C2-ALVO-0001-R01/tentativa-001/manifesto.json` há um resultado
**completo e válido**, com `estado: concluida` e `normalizado.json`. A fila,
porém, registra essa tentativa como `interrompida`, com
`manifesto_relativo: null`, e considera terminal a tentativa 3.

O que aconteceu: o contêiner terminou e gravou o manifesto terminal, mas o
processo controlador foi interrompido antes de registrar o desfecho na fila.
**O comportamento está correto** — é exatamente o que a §7.3.1 prescreve, e a
tentativa antiga foi preservada em vez de sobrescrita.

A consequência é de contagem:

| Como você conta | Resultado |
|---|---|
| `estado: concluida` em `resultados/`, com `finalidade: coleta` | **53** |
| Itens `concluida` em `execucoes/fila-c1-c2.json` | **52** (correto) |

**A fila é a fonte autoritativa.** `scripts/gerar-graficos-sast.py` já acerta,
porque escolhe a maior tentativa por execução — o CSV tem 52 linhas. Mas
qualquer contagem futura feita direto no diretório vai inflar o número.
**Ação:** registrar essa regra no Capítulo 7 e, de preferência, marcar o
manifesto órfão com um campo explícito (`superseded_por: tentativa-003`).

### C-14 — O algoritmo que define a ordem da fila não está em nenhum capítulo

A §7.3.1 descreve a fila, os identificadores e os quatro estados, mas **não diz
como a ordem é produzida**. O Capítulo 6, linha 159, diz apenas que a ordem
"será aleatorizada por bloco".

A ordem real não é aleatória: é pseudoaleatória e reproduzível.

| Campo em `config/fila-c1-c2.lock.json` | Valor |
|---|---|
| `algoritmo_ordem` | `sha256-ranking-v1` |
| `semente` | `m2-c1-c2-2026-08-11-v1` |
| `corpus_lock_sha256` | amarra a ordem ao corpus exato |
| `ordem` | a lista literal das 52 execuções |

Isso é **melhor** que aleatorização simples, porque qualquer pessoa reproduz a
mesma sequência a partir da semente publicada — e é exatamente o que sustenta a
afirmação de que a ordem foi fixada antes dos resultados. Mas hoje esse
argumento só existe dentro de um arquivo de configuração; nenhum capítulo o
apresenta.

**Ação:** descrever o ranking SHA-256 com semente publicada na §7.3.1 e ajustar
a linha 159 do Capítulo 6. Ver
[`AUDITORIA-CAPITULO-06.md`](AUDITORIA-CAPITULO-06.md), item M-5.

---

## 6. O que pode ser apagado

### D-1 — `spc-driven/` (34 arquivos versionados)

Uma *skill* de planejamento — metodologia de trabalho com o assistente. Não é
artefato do TCC, não é citada por nenhum capítulo e nenhum código a referencia.

**Recomendado:** mover para fora do repositório (ou para `~/.claude/skills/`).
Se ficar, o Capítulo 7 precisa explicar por que uma ferramenta de processo está
versionada junto ao artefato — um avaliador vai perguntar.

### D-2 a D-5 — **executados em 25/08/2026**

Removidos depois de verificar que nenhum código, script, manifesto ou capítulo
os referenciava, e que a evidência vigente corresponde à coleta real (o
`entrada_sha256` de ALVO-0001 em `evidencias/corpus-realvuln-v1/` bate com
`evidencias/coleta-c1-c2/configuracao.json`).

| # | Removido | Era |
|---|---|---|
| D-2 | `build/` | 11 arquivos: logs de build Docker e três pares `.aux`/`.log`/`.pdf` do Capítulo 7. Recriado sob demanda |
| D-3 | `benchmark/.t09-inspecao-fb8f4310d5ff4d0eb3910870735f5331/` | 20 arquivos, 5 MB: clones rasos temporários da tarefa T09 do M1 |
| D-4 | `benchmark/corpus-realvuln-v1/superseded-{alvos,evidencia,oracle}/` | 1.778 arquivos, 50 MB: cópias substituídas na reaquisição do corpus. As vigentes estão em `alvos/corpus-v1/`, `evidencias/corpus-realvuln-v1/` e `oracle/realvuln-v1/` |
| D-5 | `resultados/C1-ALVO-TESTE-R01/` e o homônimo em `fumaca-pre-m2/` | Diretórios vazios deixados por `scripts/test-executar-sast.ps1` |

**Efeito:** 158 MB para 104 MB. Integridade conferida depois da remoção: 26
alvos sanitizados, 26 arquivos de *ground truth*, 55 arquivos de evidência do
corpus, 63 manifestos e 67 tentativas — todos inalterados.

*Pendente:* reexecutar `scripts/gate.ps1 build` para confirmar que a remoção não
afetou nenhum teste de integração.

### D-6 — Nada mais

Todo o resto tem função. Em particular, **não apague**:

| Item | Por quê |
|---|---|
| `config/host-risk-waiver.json` (o do M1) | Parece redundante diante do `-m2`, mas é o registro da decisão AD-005, com escopo diferente. Decisão AD-009 depende dele existir |
| `resultados/*/tentativa-001/` das 9 falhas Bandit | São a prova de que falhas não foram sobrescritas. Apagá-las destruiria o argumento central da §7.3.1 |
| `evidencias/primeira-execucao/` e `resultados/fumaca-pre-m2/` | Ver D-7 |
| `scripts/validar-repeticoes-ia.py` | Órfão hoje (espera `resultados/ia/`), mas é entrega do M3 |

---

## 7. O que existe mas deve ser desconsiderado nos números

Não são lixo: são artefatos válidos que **não podem entrar na análise**.

| Item | Marcação mecânica | Regra |
|---|---|---|
| `evidencias/primeira-execucao/` | `finalidade: fumaca`, `status: descartavel` | Demonstra integração. Não entra em nenhuma métrica do Capítulo 8 |
| `resultados/fumaca-pre-m2/` (4 execuções) | `finalidade: fumaca` | Idem. Já arquivada e verificada como não misturada (`fumaca_misturada: false`) |
| `config/host-risk-waiver.json` | `scope: ambiente-e-primeira-execucao-sast` | O waiver **vigente** para a coleta é o `-m2`. O do M1 é histórico |
| `evidencias/host-observado-m2-*.json` | — | Conteúdo também embutido em `configuracao.json` (`risco.host_observado`). Redundante, porém barato: mantenha como registro independente |
| As 11 tentativas não finais em `resultados/` | `estado: falha` no manifesto | Preservadas de propósito. Contam como falhas relatadas, nunca como resultados |
| `resultados/*/tentativa-*/manifesto.pendente.json` e `.em_execucao.json` | — | São o rastro do ciclo de vida, não resultados. Só o `manifesto.json` é terminal |

**A regra geral, e é boa:** `finalidade` (`coleta` ou `fumaca`) é a única chave
que separa experimento de teste, e ela é verificável por máquina. Todo script de
análise deve filtrar por ela — `gerar-graficos-sast.py` já faz isso.

---

## 8. O que falta construir

Em ordem de dependência, conforme o ROADMAP:

| # | Lacuna | Bloqueia |
|---|---|---|
| 1 | Executor e adaptador de sessão para Cursor e Codex | C3, C4 |
| 2 | Geração do `alertas-sast.json` por alvo, a partir de C1/C2 e sem oracle | C5, C6 |
| 3 | Módulo de Pontuação: converter achados ao formato do avaliador, invocá-lo, calcular TP/FP/FN/TN e as métricas | Capítulo 8 inteiro |
| 4 | Exportador cego da avaliação qualitativa (§7.7): remove identificação da ferramenta, aleatoriza ordem, gera formulários | Métricas qualitativas |
| 5 | Registro estruturado de desvios (§7.9) | A própria §7.9 |

---

## 9. Ações recomendadas, em ordem

**No texto do Capítulo 7** (nenhuma dessas foi aplicada; o `.tex` está intocado):

1. Reescrever abertura, §7.7 e §7.9 para o estado pós-M2 — C-1, C-8.
2. Corrigir a Tabela 1: layout real de `resultados/`, incluir `config/`,
   `scripts/`, `tests/`, `evidencias/` — C-2, C-3, C-4.
3. Marcar "Pontuação" como prevista e ainda não implementada — C-5.
4. Relatar o desvio da imagem corretiva na §7.9 — C-7.
5. Atualizar os números de teste depois de rodar `gate.ps1 build` — C-9.
6. Separar "configuração da fumaça" de "configuração da coleta" na §7.8 — C-10.
7. Ajustar §7.5.3: o conjunto de regras é a árvore `python/` completa, não só
   `security/` — seção 4, item 1.
8. Passar §7.5.2 e §7.5.3 para o passado e acrescentar: código de saída 1 do
   Bandit, erros parciais simétricos, `version` fixa exigida pelo adaptador do
   Semgrep, confiança normalizada nula em C2.
9. Declarar que a **fila** é a fonte autoritativa da contagem de execuções, não
   a varredura de `resultados/` — C-13.
10. Descrever na §7.3.1 o ranking SHA-256 com semente publicada que define a
    ordem da fila — C-14.

**No repositório:**

11. ~~Apagar D-2, D-3, D-4 e D-5.~~ **Feito em 25/08/2026.**
12. Extrair `score.py` e `scorer/` para `oracle/realvuln-v1/` e registrar seus
    hashes — C-5.
13. Corrigir o ID de imagem no `.specs/project/STATE.md` — C-11.
14. Atualizar o `ROADMAP.md`: M2 aparece como "EM ANDAMENTO/PLANEJADO" mas está
    concluído.
15. Restringir o `.dockerignore` a `config/fontes.lock.json` **antes** do
    M3 — C-12.
16. Decidir o destino de `spc-driven/` — D-1.

**Ver também:** [`AUDITORIA-CAPITULO-06.md`](AUDITORIA-CAPITULO-06.md), que trata
do protocolo. Dois achados de lá são **críticos e independentes** deste
documento: a população do corpus citada no Capítulo 6 (796/676) está errada
(M-1) e a atribuição de F3 como métrica principal do RealVuln não se sustenta
na fonte (M-2).
