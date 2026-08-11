# Design: ambiente e primeira execução SAST

**Spec:** `.specs/features/ambiente-e-primeira-execucao-sast/spec.md`
**Status:** APROVADO
**Design de origem:** `07-desenvolvimento.tex`

## Visão da arquitetura

O host Windows fornece somente Git, PowerShell e Docker. A imagem controladora contém Python, Bandit e Semgrep. Entradas de terceiros são adquiridas em diretórios ignorados; o código autoral e os manifestos de proveniência permanecem rastreados.

```text
config/fontes.lock.json + exceção do host ──→ bootstrap/verificação ──→ benchmark/ e regras locais
                                      │
fixture/alvo sanitizado ──somente leitura──→ contêiner SAST sem rede
                                      │
                                      ├──→ bruto imutável + metadados
                                      └──→ adaptador ──→ esquema comum
                                                               │
                                                  evidência descartável
```

O `oracle/` não participa deste incremento. Isso torna impossível completar achados a partir das respostas e reduz a superfície de vazamento.

## Análise de reutilização

| Componente | Localização | Uso |
|---|---|---|
| Manifesto RealVuln v1.0 | upstream fixado em `d98e9f...` | fonte dos 26 URLs/commits e do ground truth |
| Validador RealVuln | upstream fixado | executado sem modificação antes da fumaça |
| Formato JSON Bandit | Bandit 1.9.4 | entrada do adaptador C1 |
| Formato JSON Semgrep | Semgrep 1.172.0 | entrada do adaptador C2 |
| `unittest` e biblioteca padrão | Python 3.12.13 | testes sem dependências extras do harness |

Não há código autoral pré-existente para reutilizar. A pontuação oficial será integrada em marco posterior, sem reimplementação neste incremento.

## Componentes

### Manifesto de fontes

- **Finalidade:** registrar URL oficial, versão/tag, commit/digest, licença observada e política de integridade.
- **Localização:** `config/fontes.lock.json` e `docs/FONTES_E_INTEGRIDADE.md`.
- **Interface:** lida pela CLI `python -m runner fontes verificar`.
- **Dependências:** biblioteca padrão, Git e Docker.

### Aquisição

- **Finalidade:** adquirir RealVuln/regras somente na revisão aprovada e verificar os identificadores observados.
- **Localização:** `runner/aquisicao.py`.
- **Interfaces:** `verificar_fontes()`, `adquirir_realvuln()`, `adquirir_regras_semgrep()`.
- **Restrição:** sem execução de scripts baixados durante a aquisição.

### Preflight do host

- **Finalidade:** comparar versões observadas às recomendadas e registrar a decisão de continuar.
- **Localização:** `config/host-risk-waiver.json` e `runner/aquisicao.py`.
- **Interface:** `verificar_versoes_host(observadas, politica, excecao)`.
- **Decisão:** a exceção AD-005 transforma somente incompatibilidades de versão em avisos; ausência de ferramenta, origem/hash divergente e controles de isolamento continuam bloqueantes.

### Imagem controladora

- **Finalidade:** fornecer ambiente único para harness, Bandit e Semgrep.
- **Localização:** `docker/Dockerfile`, `docker/requirements.in`, `docker/requirements.lock`, `compose.yaml`.
- **Base:** índice OCI validado `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`; build imposto em `linux/amd64` pelo manifesto `sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af`.
- **Dependências:** Bandit 1.9.4 e Semgrep 1.172.0 em lock de 69 wheels para CPython 3.12/linux-amd64, todos fixados por SHA-256.

### Esquema comum

- **Finalidade:** representar achados e metadados sem inferência.
- **Localização:** `runner/modelos.py`, `runner/schemas/achado-v1.schema.json`, `runner/schemas/execucao-v1.schema.json`.
- **Interfaces:** `Achado.from_dict()`, `Achado.to_dict()` e validações explícitas.
- **Decisão:** dataclasses e validação autoral mínima; nenhuma dependência de runtime além da biblioteca padrão.

### Adaptadores C1 e C2

- **Finalidade:** converter saídas nativas preservadas para o esquema comum.
- **Localização:** `runner/adaptadores/bandit.py`, `runner/adaptadores/semgrep.py`.
- **Interfaces:** `normalizar(documento, proveniencia) -> list[Achado]`.
- **Restrição:** não acessam `benchmark/ground-truth` nem `oracle/`.

No Bandit, os mapas congelados são `LOW/MEDIUM/HIGH` para `baixa/media/alta`, tanto em severidade quanto em confiança. Somente `issue_cwe.id` inteiro positivo produz `CWE-N`; regra, mensagem ou código nunca são usados para inferir CWE. Duplicatas e a ordem nativa permanecem intactas para a etapa posterior de deduplicação. Assim como no Semgrep, `errors` não vazio emite aviso tipado ligado ao hash do bruto.

No Semgrep, o mapa congelado é `INFO/WARNING/ERROR` para `baixa/media/alta`. A confiança nativa é preservada, mas permanece sem forma normalizada até existir mapeamento público aprovado. CWE é extraída somente de `extra.metadata.cwe`; quando houver uma lista, a primeira ocorrência sintaticamente válida `CWE-N` é usada e a lista original inteira é mantida. `errors` não vazios emitem aviso tipado com cópia dos erros e hash do bruto; T07 deve persistir esse aviso.

### Executor Docker

- **Finalidade:** criar contêiner efêmero por ferramenta/alvo e preservar comando, tempos, estado e bruto.
- **Localização:** `scripts/executar-sast.ps1` no host e `runner/executor_sast.py` dentro do contêiner.
- **Controles:** `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, usuário não root, alvo `ro`, saída dedicada `rw`, `tmpfs`, CPU/memória/PIDs/timeout fixados.
- **Topologia:** o PowerShell é o único componente que chama Docker; o executor Python inicia apenas o scanner. O socket Docker nunca é montado e não há Python no host.
- **Identidade da imagem:** o host inspeciona a tag, exige `linux/amd64`, executa pelo `.Id` local `sha256:...` com `--pull never` e registra tag e ID separadamente.
- **Montagens:** `/entrada:ro` e `/saida:rw` são as únicas comuns; C2 recebe adicionalmente o bundle local verificado em `/opt/regras-semgrep:ro`.
- **Timeouts:** o processo interno encerra o grupo do scanner no limite fixado; um watchdog PowerShell limita o contêiner inteiro ao timeout interno mais 120 segundos e preserva `watchdog-host.json` se precisar interrompê-lo.

### Validação sintética e evidência de fumaça

- **T08 — validação sintética:** `scripts/test-fumaca-sintetica.ps1` reutiliza a única CLI pública, `scripts/executar-sast.ps1`, para executar C1 e C2 serialmente. `runner.executor_sast` permanece um entrypoint interno do contêiner. As tentativas usam `finalidade=fumaca`, estado terminal `concluida` e diretórios temporários em `resultados/`, ignorados e removidos pelo próprio teste após a validação.
- **T09 — fumaça RealVuln:** os manifestos pequenos e o resumo verificável ficam em `evidencias/primeira-execucao/`; os brutos continuam em `resultados/` ignorado. Essa evidência também usa `finalidade=fumaca` e é excluída da coleta principal por sua finalidade, não por um estado adicional.
- **Conteúdo:** versões, IDs/digests, comandos, hashes de entrada/saída, durações, códigos de saída, contagens, finalidade e estado do manifesto.

## Modelos de dados

### Achado v1

| Campo | Tipo | Regra |
|---|---|---|
| `schema_version` | string | sempre `1.0` |
| `condicao`, `ferramenta`, `alvo`, `repeticao`, `execucao_id` | string/int | proveniência obrigatória |
| `arquivo`, `linha_inicial`, `linha_final` | string/int/null | caminho relativo; inteiros positivos |
| `regra` | string/null | identificador nativo, sem inferência |
| `cwe_original`, `severidade_original`, `confianca_original` | string/list/null | valor emitido pela ferramenta; a CWE original pode ser plural |
| `cwe`, `severidade`, `confianca` | string/null | forma normalizada; permanece nula sem mapeamento público congelado |
| `descricao`, `evidencia`, `recomendacao`, `texto_original` | string/null | nunca completados pelo adaptador |
| `saida_bruta_sha256` | string | referência obrigatória ao bruto encerrado |

### Manifesto de execução v1

Registra `execucao_id`, condição, ferramenta, bloco, alvo, repetição, commit/hash da entrada, comando em vetor, imagem/digest, finalidade, início/término UTC, duração monotônica, código de saída, estado, tipo/mensagem de falha, tentativa e hashes dos artefatos. A finalidade `fumaca` separa evidência descartável do ciclo de vida; os estados permanecem `pendente`, `em_execucao`, `concluida` e `falha`. Um timeout usa `estado=falha` e `falha_tipo=timeout`.

Os JSON Schemas fecham campos, tipos e implicações estruturais. Comparações entre campos que o JSON Schema Draft 2020-12 não expressa de forma portável — ordem entre início/término e entre linhas inicial/final — aparecem em `x-tcc-semantic-invariants` e são bloqueadas por `Achado.from_dict()` e `ManifestoExecucao.from_dict()`. Uma execução somente pode ser `concluida` quando ao menos um artefato de saída já possui hash.

## Tratamento de erros

| Cenário | Tratamento | Efeito |
|---|---|---|
| origem/revisão/hash divergente | parar antes do download subsequente ou execução | erro de proveniência |
| versão do host abaixo da recomendada | bloquear sem exceção; emitir aviso auditável com AD-005 | execução permitida somente pela aceitação explícita |
| Docker indisponível | não instalar Python nem executar fallback no host | gate bloqueado |
| timeout/código não esperado | persistir stdout/stderr/bruto e marcar falha | fumaça reprova |
| JSON inválido | preservar bytes e não normalizar heurísticamente | falha de formato |
| campo ausente | emitir `null` | sem inferência |
| licença não compatível | não adquirir/publicar; registrar decisão | tarefa bloqueada até decisão explícita |

## Decisões técnicas

| Decisão | Escolha | Justificativa |
|---|---|---|
| Python do host | não instalar | Docker existente é suficiente e mais reproduzível |
| Dependências do harness | biblioteca padrão | reduz cadeia de suprimentos; ferramentas SAST continuam fixadas |
| RealVuln | tag v1.0 desembrulhada para commit | a branch atual é v2 e mudaria o corpus |
| Regras Semgrep | commit upstream, caminho e hash canônico fixados; bundle local ignorado montado `ro` somente em C2 | licença proíbe redistribuição; a imagem e o remoto não recebem uma cópia |
| Versões atuais do host | continuar pela exceção AD-005 | risco aceito pelo usuário; controles compensatórios permanecem |
| Resultados de fumaça | separados por `finalidade=fumaca`; sintéticos são temporários e RealVuln recebe resumo em `evidencias/` | impede contaminação da coleta principal sem inventar estado fora do esquema |
| Escrita de evidência | arquivo temporário + rename | evita manifesto parcialmente gravado |

## Controles de segurança

- O código vulnerável é tratado como dado, nunca importado nem executado.
- O socket Docker não é montado dentro do contêiner de análise.
- Nenhuma credencial é passada a C1/C2.
- Rede é permitida apenas em etapas explícitas de aquisição/construção; a análise usa `none`.
- `oracle/` e `benchmark/ground-truth` não são montados no contêiner de análise.
