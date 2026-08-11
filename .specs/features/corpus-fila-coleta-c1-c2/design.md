# Design: corpus, fila e coleta C1/C2

**Spec:** `.specs/features/corpus-fila-coleta-c1-c2/spec.md`
**Status:** APROVADO
**Design de origem:** `07-desenvolvimento.tex`

## Arquitetura

```text
RealVuln v1.0 fixado
  ├─ manifesto ──> lock autoral de 26 fontes ──> clones bare ignorados
  ├─ ground-truth + validador ──> oracle ignorado + evidência de hashes
  └─ commits-alvo ──> exportação Git ──> sanitização congelada
                                      ├─> ALVO-NNNN canônico ignorado
                                      └─> inventário rastreado

lock do corpus + configuração congelada
  └─> fila 52 itens (ordem SHA-256) ──serial─> área nova ──> executar-sast.ps1
                                              │               ├─ bruto ignorado
                                              │               └─ manifesto terminal
                                              └─ cleanup       └─ evidência rastreada
```

O oracle e a correspondência ID opaco↔repositório ficam fora de qualquer mount de scanner. O orquestrador do host conhece somente os metadados necessários para adquirir/preparar; o contêiner de análise recebe uma árvore opaca e não recebe fila, lock, manifesto RealVuln ou diretório ancestral.

## Artefatos autorais

| Artefato | Responsabilidade |
|---|---|
| `config/politica-sanitizacao-v1.json` | regra fechada, uniforme e congelada de exclusão |
| `config/corpus-realvuln-v1.lock.json` | 26 IDs opacos, URLs/commits e metadados do release |
| `config/fila-c1-c2.lock.json` | conjunto e ordem congelados de 52 execuções |
| `runner/corpus.py` | validação estrita do manifesto/lock, IDs, política e inventários |
| `runner/fila.py` | modelo da fila, transições atômicas, retomada e auditoria |
| `runner/preparacao.py` | cópia sanitizada e inventário canônico sem executar alvo |
| `scripts/adquirir-corpus.ps1` | Git no host, exportação segura e invocação do preparador em Docker |
| `scripts/executar-coleta-c1-c2.ps1` | congelamento, fila serial, áreas novas, wrapper e evidência |
| `evidencias/corpus-realvuln-v1/` | resumo, hashes e inventários sem código/ground truth |
| `evidencias/coleta-c1-c2/` | configuração, fila final, manifestos e resumo sem bruto |

`benchmark/`, `alvos/`, `oracle/`, `execucoes/` e `resultados/` permanecem ignorados.

## Lock do corpus

O lock é derivado uma única vez do `benchmark-manifest.json` no commit RealVuln aprovado. Ele exige exatamente os IDs `ALVO-0001` a `ALVO-0026`, ordenados pelo `repo_id` upstream para evitar escolha discricionária. Cada entrada contém `alvo`, `realvuln_id`, URL HTTPS exata e commit completo. A correspondência é rastreada para reprodução, mas nunca montada em scanners; o identificador usado em comandos e achados é somente o opaco.

O documento registra tag/objeto/commit RealVuln, versão `1.0.0`, identificadores upstream e SHA-256 completo dos bytes do manifesto exportado. Chaves duplicadas, campos extras, URL não HTTPS, userinfo, porta não padrão, query/fragment, IDs/URLs/commits duplicados e conjunto diferente de 26 são bloqueantes.

## Política de sanitização v1

A política opera somente por caminho e tipo de objeto, nunca por conteúdo ou resultado. Ela preserva arquivos regulares do commit e exclui:

- metadados VCS: `.git`, `.hg`, `.svn`, `.gitmodules`;
- respostas: componentes `ground-truth`, `oracle`, `solution(s)`, `walkthrough(s)`, `writeup(s)`;
- ambientes/dependências instaladas: `.venv`, `venv`, `env`, `node_modules`;
- caches/gerados: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.nox`, `htmlcov`, `dist`, e extensões `pyc`, `pyo`, `class`;
- metadados de sistema/download: `.DS_Store`, `Thumbs.db`, `Zone.Identifier`;
- caminhos exatos `ui/static/css/fonts` no ALVO-0020 e `bad/payloads/payload.js`/`good/payloads/payload.js` no ALVO-0026, versionados como links Git internos para conteúdo já presente.

`build/` não é excluído genericamente porque pode conter fonte pertencente ao projeto; somente padrões inequivocamente gerados entram na v1. README, documentação e testes são preservados salvo quando o próprio caminho identifica explicitamente solução/walkthrough. Qualquer alteração cria uma nova versão e invalida todos os inventários, nunca apenas um alvo.

O exportador Git recusa submódulos (`160000`), modos diferentes de blobs regulares (`100644`/`100755`) e links (`120000`) não publicados. Os três links conhecidos são omitidos por pathspec antes da extração; modo, objeto, destino textual e ação ficam na evidência, e nenhum link é seguido ou materializado. Essa escolha evita materialização dependente do host; qualquer novo objeto recusado interrompe a coleta e exige revisão antes de scanner.

## Ground truth e validador

O RealVuln fixado é exportado para `oracle/realvuln-v1/` com o validador e os 26 arquivos de ground truth. O validador oficial é executado sem modificação em contêiner separado, sem rede, com origem somente leitura e sem mounts de alvos/resultados. Sua saída, exit code e hash do script são preservados. Uma validação autoral adicional contabiliza arquivos, entradas, vulnerabilidades e armadilhas e calcula SHA-256 completo por arquivo; ela não modifica rótulos.

Quando uma URL primária não anuncia mais o commit, o transporte pode recorrer somente a `config/espelhos-corpus-realvuln-v1.lock.json`. O fetch continua exigindo o SHA-1 completo do manifesto; o resumo preserva URL oficial, URL de transporte e indicador de espelho. Branches e commits substitutos permanecem proibidos.

Esse passo ocorre antes da preparação e não compartilha contêiner ou mount com C1/C2.

## Inventário e regeneração

O algoritmo permanece `tree-sha256-v1`: prefixo de domínio, caminho POSIX UTF-8, NUL, tamanho decimal, NUL, SHA-256 do conteúdo e LF, ordenados pelos bytes do caminho. O documento lista todos os arquivos, total de bytes e hash da árvore.

Para cada alvo, a aquisição cria duas preparações independentes a partir do mesmo commit e exige documentos de inventário byte a byte iguais. A cópia de regeneração é descartada; a canônica é preservada em `alvos/corpus-v1/ALVO-NNNN`. Antes de cada execução, uma nova área é copiada da canônica e inventariada novamente; divergência bloqueia a tarefa antes do scanner.

## Fila congelada e retomada

O lock da fila contém o produto cartesiano dos 26 alvos com C1/C2 e repetição 1. A ordem usa:

```text
chave = SHA-256("fila-c1-c2-v1\0" || seed_utf8 || "\0" || execucao_id_utf8)
ordem = sort(chave, execucao_id)
```

A semente é publicada antes da coleta. Isso fornece uma permutação independente de implementações de PRNG. O runtime copia o lock para `execucoes/fila-c1-c2.json` e adiciona `estado`, `tentativa`, timestamps, referência ao manifesto terminal e falha.

Transições válidas:

```text
pendente ──claim──> em_execucao ──sucesso──> concluida
                            └────falha────> falha
em_execucao órfã ──retomar──> pendente (tentativa seguinte; anterior preservada)
```

Toda escrita usa arquivo temporário, `fsync` e rename. O documento possui `revision` crescente e hash do lock; alteração externa, perda de item ou transição inválida é recusada. Apenas uma tarefa pode estar `em_execucao`, coerente com a exclusão mútua do wrapper.

## Congelamento da coleta

Antes de inicializar a fila runtime, o orquestrador registra:

- commit do controlador e worktree limpo;
- lock do corpus/fila/política por SHA-256;
- imagem tag, ID local, OS/arquitetura e versões internas;
- commit/hash das regras Semgrep;
- comandos determinados pelo executor, limites e timeout;
- versões Git/WSL/Docker e decisão de risco com escopo M2;
- timestamps UTC e fuso do host.

O hash canônico dessa configuração entra na fila e em cada evidência. A cada claim, imagem, regras, locks e worktree são revalidados. Uma divergência pausa o bloco antes de criar nova tentativa. O gate `build` deve passar antes do congelamento; depois disso a imagem não é reconstruída até todas as tarefas terminarem.

## Orquestração das 52 execuções

Para cada item, o host:

1. reclama atomicamente o item e obtém tentativa;
2. cria `alvos/execucoes/<execucao_id>-TNNN/` a partir da árvore canônica;
3. compara o inventário ao lock do corpus;
4. chama a única CLI pública `scripts/executar-sast.ps1` com `finalidade=coleta`;
5. valida o manifesto terminal e hashes dos artefatos;
6. copia somente o manifesto terminal para evidência rastreada;
7. transiciona a fila para `concluida` ou `falha`;
8. remove a área de entrada própria, nunca o bruto.

Falhas C1/C2 são independentes. Não há retry automático de falha terminal. Uma interrupção sem manifesto terminal é retomada em tentativa nova; o diretório anterior continua em `resultados/`.

## Evidência final

O resumo final exige 52 itens terminais e contém:

- cobertura exata 26×2, contagens por condição/estado/falha;
- janela UTC e soma/mediana descritiva de duração operacional, sem métrica de detecção;
- configuração e hashes congelados;
- commit/hash/arquivos/bytes por alvo;
- hashes da fila inicial/final e dos 52 manifestos;
- referências relativas a bruto/normalizado ignorados;
- lista explícita de falhas para aplicação posterior do modo estrito.

Resultados de fumaça são excluídos porque sua finalidade é `fumaca`; somente manifestos com `finalidade=coleta` e configuração congelada correta entram no M2.

## Segurança e licenças

- Nenhum código de alvo, hook, submódulo, teste, instalador ou aplicação é executado.
- Rede existe apenas nos clones/builds explícitos; validação, preparação e análise ficam offline.
- Clones bare e oracle nunca são ancestrais de mounts de scanner.
- Regras, corpus, oracle e brutos continuam ignorados e não entram na imagem.
- A exceção AD-005 não se estende implicitamente ao M2; sem decisão prévia válida, a coleta não é armada.
- Revisão de licenças transitivas é necessária antes de distribuir imagem, mas não para uso local sem publicação.
