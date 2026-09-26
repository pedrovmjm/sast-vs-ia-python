# Auditoria: Capítulo 6 (Metodologia) x repositório real

**Data:** 2026-08-25
**Base auditada:** `main` em `af6fa31`
**Referência:** `06-metodologia.tex`, revisão de 11/08/2026 09:48
**Companheiro:** [`AUDITORIA-CAPITULO-07.md`](AUDITORIA-CAPITULO-07.md)

---

## Resumo executivo

O Capítulo 6 é o **protocolo**, e é legítimo que esteja em tempo futuro mesmo
depois de C1 e C2 terem rodado — ele descreve o que o estudo se comprometeu a
fazer, não o que já aconteceu. Por isso, **não recomendo converter o capítulo
para o passado**; isso é papel dos Capítulos 7 e 8.

O problema aqui é de outra natureza: há **dois números e uma afirmação
metodológica que estão factualmente errados** ou não sustentados pela fonte que
o próprio capítulo cita. São 12 achados, M-1 a M-12.

| Severidade | Achados |
|---|---|
| **Crítico** (número ou afirmação incorreta no texto) | M-1, M-2 |
| **Importante** (promessa do protocolo não cumprida ou mal descrita) | M-3, M-4, M-5 |
| **Médio** (ambiguidade ou risco para o M3) | M-6, M-7 |
| **Menor / oportunidade** | M-8 |
| **Verificado, está correto** | M-9, M-10, M-11 |
| **Lacuna compartilhada com o Cap. 7** | M-12 |

---

## M-1 (crítico) — A população do corpus está errada: 796/676 deve ser 817/697

**Onde:** linha 64 ("796 entradas manualmente rotuladas, das quais 676
representam vulnerabilidades e 120 representam padrões seguros") e a
Tabela~\ref{tab:ambiente-experimental}, linha "Dados" ("796 entradas
rotuladas").

**O que o repositório mede:**

| Fonte | Entradas | Vulnerabilidades | Armadilhas |
|---|---|---|---|
| README do RealVuln v1.0 (o que o capítulo cita) | 796 | 676 | 120 |
| **Arquivos de *ground truth* do mesmo commit** | **817** | **697** | **120** |

Os 817 vêm de `evidencias/corpus-realvuln-v1/ground-truth-resumo.json` e são
**aprovados pelo validador oficial** do benchmark, com código de saída 0
(`evidencias/corpus-realvuln-v1/validacao-oficial.json`).

A decisão **AD-010** já resolveu isso a favor dos arquivos *machine-readable*:
remover 21 rótulos para reproduzir a manchete do README alteraria o oracle
oficial sem critério publicado. A própria decisão registra que "os números de
população dos capítulos precisarão ser corrigidos".

**Ação:** trocar 796→817 e 676→697 nos dois lugares e acrescentar uma nota de
rodapé registrando a divergência com o README do benchmark e a razão da escolha.
Esconder a divergência seria pior que tê-la: registrá-la é evidência de rigor.

---

## M-2 (crítico) — "F3, métrica principal do RealVuln" não se sustenta: a fonte se contradiz

**Onde:** linha 145 — "**F3**: média harmônica ponderada que atribui peso nove
vezes maior ao *recall*, métrica principal do RealVuln".

O README do RealVuln v1.0, **no mesmo commit**, diz as duas coisas:

| Local no README | Afirma |
|---|---|
| Linha 5 (cabeçalho) | "Primary metric is **F3 Score** (0–100, recall-weighted 9:1)" |
| Linha 243 (seção de pontuação) | "**Primary metric: F2 Score** (0–100 scale). F-beta with beta=2 weights recall 4x more than precision" |
| Linhas 63 e 119 (estrutura) | "Scoring engine — **F2**, precision, recall…" |
| Linhas 252–253 (tabela de fórmulas) | Apresenta **somente** a fórmula de F2 |

O código resolve o impasse: `scorer/metrics.py` calcula **as duas**, lado a
lado, na mesma `ScoreCard`:

```python
f2: float = 0.0        # F-beta with beta=2, recall-weighted
f2_score: float = 0.0  # F2 × 100, 0-100 scale
f3: float = 0.0        # F-beta with beta=3, recall-weighted (9:1)
f3_score: float = 0.0  # F3 × 100, 0-100 scale
```

**Ação:** aplicar aqui a mesma doutrina do AD-010 — o *machine-readable* prevalece
sobre a manchete. Reportar **F2 e F3 lado a lado**, sem eleger uma como "a
métrica principal do RealVuln", e registrar em nota que a documentação v1.0 é
internamente inconsistente e que o motor de pontuação emite ambas.

Isso é mais forte que escolher uma: o capítulo já se compromete a calcular F1,
F2 e F3 (linhas 143–145), então nada de novo precisa ser computado. Muda só a
frase que atribui primazia a F3.

---

## M-3 (importante) — O avaliador oficial não foi adquirido nem hasheado

**Onde:** protocolo, passo 1 (linha 248) — "Fixar o *commit* da versão 1.0 do
RealVuln e registrar os *hashes* do manifesto, do *ground truth* e **do
avaliador oficial**."

**Realidade:** `oracle/realvuln-v1/` contém apenas:

```
benchmark-manifest.json
ground-truth/            (26 arquivos)
validate_gt.py           ← VALIDADOR do ground truth
```

`validate_gt.py` **não é o avaliador**. Ele confere se o *ground truth* está
bem formado. O avaliador de verdade é outro conjunto de arquivos, presente no
commit fixado mas **nunca extraído**:

```
score.py
scorer/__init__.py
scorer/matcher.py      ← correspondência por caminho, CWE e tolerância de linha
scorer/metrics.py      ← TP/FP/FN/TN, precisão, recall, F1/F2/F3, FPR
tests/test_matcher.py
tests/test_metrics.py
```

Nenhum hash de avaliador aparece em `config/fontes.lock.json` nem em
`evidencias/`. O passo 1 do protocolo, portanto, **está cumprido pela metade**.

A boa notícia: os arquivos estão no repositório bare já adquirido
(`benchmark/corpus-realvuln-v1/realvuln.git`), então é extração e hash, não nova
aquisição.

**Ação:** extrair `score.py` e `scorer/` para `oracle/realvuln-v1/`, registrar os
hashes em `config/fontes.lock.json` e em uma evidência, **antes** do M4. E
distinguir no texto "validador do *ground truth*" de "avaliador/pontuador",
porque hoje o Capítulo 6 usa "avaliador" para os dois.

---

## M-4 (importante) — "regras de segurança para Python" descreve mal o conjunto

**Onde:** linha 120 — "O Semgrep Community Edition utilizará um conjunto público
de regras **de segurança** para Python".

**Realidade:** o bundle montado é a árvore `python/` **inteira** do
`semgrep-rules`: 717 arquivos em 23 diretórios que incluem `correctness/`,
`lang/` e regras de boas práticas por *framework*. `security/` é apenas um
subdiretório dentro de alguns deles. O comando usa
`--config /opt/regras-semgrep/python`, ou seja, carrega tudo.

Isso não invalida nada — a escolha foi congelada antes da coleta e o próprio
capítulo se compromete a publicar "os arquivos efetivamente carregados". Mas
muda a leitura do Capítulo 8: **parte dos 716 alertas de C2 é de corretude, não
de segurança**, e todo alerta sem correspondência no *ground truth* conta como
falso positivo. Chamar o conjunto de "regras de segurança" faz a taxa de FP de
C2 parecer pior do que a descrição justifica.

**Ação:** trocar por "o conjunto público de regras Python do repositório oficial
do Semgrep (árvore `python/` completa, incluindo regras de corretude e de boas
práticas além das de segurança)". Mesma correção vale para o Capítulo 7,
§7.5.3 — ver `AUDITORIA-CAPITULO-07.md`, seção 4.

---

## M-5 (importante) — O algoritmo de ordenação não está em nenhum dos dois capítulos

**Onde:** linha 159 — "A ordem dos repositórios será **aleatorizada** por bloco".

**Realidade:** a ordem não é aleatória, é **pseudoaleatória reproduzível**:

| Campo | Valor |
|---|---|
| `algoritmo_ordem` | `sha256-ranking-v1` |
| `semente` | `m2-c1-c2-2026-08-11-v1` |
| `corpus_lock_sha256` | amarra a ordem ao corpus exato |

Está publicado em `config/fila-c1-c2.lock.json`, com a lista literal das 52
execuções. **O Capítulo 7 também não descreve o algoritmo** — a §7.3.1 fala da
fila e dos estados, mas não de como a ordem é produzida.

Isso é melhor do que aleatorização simples, porque é auditável e reproduzível.
Mas é um detalhe crítico de reprodutibilidade que hoje só existe num arquivo de
configuração.

**Ação:** descrever o ranking SHA-256 com semente publicada em um dos dois
capítulos — a §7.3.1 é o lugar natural — e ajustar a linha 159 para
"pseudoaleatorizada por ranking criptográfico com semente publicada".

---

## M-6 (médio) — Colisão de terminologia: "contaminada" tem dois significados

**No Capítulo 6**, Tabela~\ref{tab:ameacas-validade}: "Uso inadvertido de SAST
pelo braço IA — … descarte documentado de **execução contaminada**". Aqui,
contaminada = o agente de IA usou uma ferramenta proibida.

**Na implementação**, `falha_tipo: "contaminada"` significa outra coisa. O único
caso real, em `C2-ALVO-0002-R01/tentativa-001`, registra:

```
"falha_mensagem": "entrada ficou inválida depois da execução:
                   raiz do bundle deve ser diretório real: /entrada"
```

Ou seja: a árvore de entrada deixou de conferir depois da execução. É uma
verificação de integridade, não uma violação de ferramenta.

Um leitor que cruzar o capítulo com os manifestos vai concluir, erradamente, que
uma execução SAST usou ferramenta proibida.

**Ação:** separar os termos. Sugestão: manter `contaminada` para a violação de
ferramenta (que é o sentido do Capítulo 6) e renomear o caso de integridade para
`entrada_alterada` ou `integridade_entrada`. Se renomear o campo for custoso,
basta documentar os dois sentidos explicitamente.

---

## M-7 (médio) — A promessa de não expor "os manifestos internos" está em risco

**Onde:** protocolo, passo 3 (linha 250) — "verificar que as áreas de trabalho
não expõem o diretório `ground-truth`, o avaliador ou **os manifestos
internos**".

`corpus-realvuln-v1.lock.json` é exatamente um manifesto interno: é a tabela que
traduz `ALVO-0007` no nome, na URL e no commit reais. E ele **está dentro da
imagem** que executa as análises, porque o `.dockerignore` libera `config/*.json`
e o `Dockerfile` faz `COPY config/ /opt/tcc/config/`.

**Não compromete C1 e C2.** Bandit e Semgrep leem apenas `/entrada`; não há
caminho pelo qual esse arquivo influencie a saída. Os resultados atuais valem.

**Vira problema real em C3–C6**, quando um agente com leitura livre estiver no
lugar do binário determinístico.

**Ação:** restringir o `.dockerignore` a `!config/fontes.lock.json` — o único que
o *preflight* embarcado usa — antes de iniciar o M3. Mesmo item que
`AUDITORIA-CAPITULO-07.md`, C-12.

---

## M-8 (oportunidade) — O avaliador oficial entrega o J de Youden de graça

`scorer/metrics.py` já calcula, além de tudo o que o Capítulo 6 pede:

```python
tpr: float = 0.0        # TP / (TP + FN) — same as recall
fpr: float = 0.0        # FP / (FP + TN)
youden_j: float = 0.0   # TPR - FPR
```

O J de Youden resume num único número o compromisso entre sensibilidade e
especificidade — exatamente a tensão da QP1. Não custa nada: sai da mesma
`ScoreCard`, sem cálculo adicional nem nova coleta.

**Ação (opcional):** acrescentar J de Youden à lista da
Subseção~\ref{subsec:metricas-quantitativas-metodologia}. Se preferir não
ampliar o escopo, ignore — é oportunidade, não defeito.

---

## M-9 a M-11 — Verificados e corretos

Vale registrar o que **passou** na auditoria, porque são os pontos que um
avaliador provavelmente vai querer conferir.

### M-9 — Separar sobrecarga de contêiner do tempo do analisador (linha 153)

O capítulo promete registrar "o tempo de inicialização do contêiner e o tempo
interno do analisador". Está cumprido: `manifesto.json` traz a duração total e
`processo.json` a duração do analisador. A diferença é a sobrecarga.

| Execução | Total | Analisador | Sobrecarga |
|---|---|---|---|
| C1-ALVO-0001 | 1,071 s | 0,715 s | 0,356 s |
| C1-ALVO-0014 | 4,103 s | 1,931 s | 2,172 s |
| C2-ALVO-0005 | 30,872 s | 25,768 s | 5,104 s |

### M-10 — Bandit sem supressões nem filtros (linha 120)

"O Bandit será executado com seu conjunto nativo de *plugins* e sem supressões
ajustadas após a observação dos resultados." Verificado nos 37 manifestos: o
comando não tem `--skip`, `--tests`, `--ini`, `-l`, `-i`, `--severity-level` nem
`--confidence-level`.

### M-11 — Validação do *ground truth* antes da coleta (linha 82)

"Antes da coleta, o arquivo será validado pelo verificador disponibilizado pelo
benchmark e seu *hash* será registrado." Cumprido: `validacao-oficial.json`
(código de saída 0, 26 repositórios aprovados) e `ground-truth-resumo.json`
(SHA-256 por arquivo, mais a verificação de que a URL do GT confere com a do
manifesto — 3 divergências registradas, não escondidas).

O capítulo pode citar essas evidências nominalmente em vez de deixá-las como
promessa.

---

## M-12 — Lacuna compartilhada: a união SAST para C5/C6

**Onde:** linha 128 ("A união SAST fornecida às condições híbridas será
deduplicada antes da nova execução dos agentes") e passo 8 do protocolo
(linha 255).

Não implementada. É a mesma lacuna do `alertas-sast.json` no Capítulo 7 (item
C-9). Pertence ao M3 e não exige mudança de texto — só de estado.

---

## Ordem sugerida de correção

**Muda número ou afirmação no texto — fazer antes de qualquer revisão:**

1. **M-1** — 796→817 e 676→697, nos dois lugares, com nota sobre a divergência.
2. **M-2** — parar de atribuir primazia a F3; reportar F2 e F3, registrando a
   inconsistência da documentação do benchmark.
3. **M-4** — descrever corretamente o conjunto de regras do Semgrep.
4. **M-5** — descrever o ranking SHA-256 com semente publicada.

**Muda o repositório:**

5. **M-3** — extrair e hashear `score.py` e `scorer/` para `oracle/realvuln-v1/`.
6. **M-7** — restringir o `.dockerignore` antes do M3.
7. **M-6** — desambiguar `contaminada`.

**Opcional:**

8. **M-8** — acrescentar J de Youden.

**Nada a fazer:** M-9, M-10, M-11 (verificados) e M-12 (estado, não texto).

---

## Sobre o tempo verbal do Capítulo 6

Diferente do Capítulo 7, **o Capítulo 6 deve continuar prospectivo**. Ele
define o compromisso metodológico assumido antes da coleta, e é justamente essa
anterioridade que dá força ao argumento de que nada foi escolhido depois de ver
os resultados. Converter para o passado enfraqueceria o capítulo.

O que precisa mudar é factual: números errados, uma atribuição de primazia que a
fonte não sustenta, e três descrições que não correspondem ao que foi
efetivamente congelado.
