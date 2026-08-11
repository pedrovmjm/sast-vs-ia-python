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
- **Base:** `python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`.
- **Dependências:** Bandit 1.9.4 e Semgrep 1.172.0 com lock/hashes completos.

### Esquema comum

- **Finalidade:** representar achados e metadados sem inferência.
- **Localização:** `runner/modelos.py`, `runner/schemas/achado-v1.schema.json`.
- **Interfaces:** `Achado.from_dict()`, `Achado.to_dict()` e validações explícitas.
- **Decisão:** dataclasses e validação autoral mínima; nenhuma dependência de runtime além da biblioteca padrão.

### Adaptadores C1 e C2

- **Finalidade:** converter saídas nativas preservadas para o esquema comum.
- **Localização:** `runner/adaptadores/bandit.py`, `runner/adaptadores/semgrep.py`.
- **Interfaces:** `normalizar(documento, proveniencia) -> list[Achado]`.
- **Restrição:** não acessam `benchmark/ground-truth` nem `oracle/`.

### Executor Docker

- **Finalidade:** criar contêiner efêmero por ferramenta/alvo e preservar comando, tempos, estado e bruto.
- **Localização:** `runner/executor_sast.py`.
- **Controles:** `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, usuário não root, alvo `ro`, saída dedicada `rw`, `tmpfs`, CPU/memória/PIDs/timeout fixados.

### Evidência de fumaça

- **Finalidade:** registrar uma execução verificável sem integrá-la à coleta.
- **Localização:** `evidencias/primeira-execucao/` para manifestos pequenos; brutos permanecem em `resultados/` ignorado.
- **Conteúdo:** versões, digests, comandos, hashes de entrada/saída, durações, códigos de saída, contagens e status `descartavel`.

## Modelos de dados

### Achado v1

| Campo | Tipo | Regra |
|---|---|---|
| `schema_version` | string | sempre `1.0` |
| `condicao`, `ferramenta`, `alvo`, `repeticao`, `execucao_id` | string/int | proveniência obrigatória |
| `arquivo`, `linha_inicial`, `linha_final` | string/int/null | caminho relativo; inteiros positivos |
| `regra`, `cwe`, `severidade`, `confianca` | string/null | valor bruto e normalizado separados quando necessário |
| `descricao`, `evidencia`, `recomendacao`, `texto_original` | string/null | nunca completados pelo adaptador |
| `saida_bruta_sha256` | string | referência obrigatória ao bruto encerrado |

### Manifesto de execução v1

Registra `execucao_id`, condição, ferramenta, alvo, repetição, hash da entrada, comando em vetor, imagem/digest, início/término UTC, duração monotônica, código de saída, estado, tentativa e hashes dos artefatos.

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
| Regras Semgrep | aquisição local fixada, sem commit | licença proíbe redistribuição |
| Versões atuais do host | continuar pela exceção AD-005 | risco aceito pelo usuário; controles compensatórios permanecem |
| Resultados de fumaça | separados e `descartavel` | impede contaminação da coleta principal |
| Escrita de evidência | arquivo temporário + rename | evita manifesto parcialmente gravado |

## Controles de segurança

- O código vulnerável é tratado como dado, nunca importado nem executado.
- O socket Docker não é montado dentro do contêiner de análise.
- Nenhuma credencial é passada a C1/C2.
- Rede é permitida apenas em etapas explícitas de aquisição/construção; a análise usa `none`.
- `oracle/` e `benchmark/ground-truth` não são montados no contêiner de análise.
