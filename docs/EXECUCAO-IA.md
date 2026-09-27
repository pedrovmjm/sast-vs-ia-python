# Execução dos cenários C3–C6

Os executores são separados por cenário e cada ferramenta possui um adaptador
próprio. Cada chamada executa uma única unidade
`(condição, alvo, repetição, tentativa)`.

| Cenário | Ferramenta | Entrada | Script público |
|---|---|---|---|
| C3 | Cursor | código Python | `scripts/executar-c3-cursor.ps1` |
| C4 | Codex | código Python | `scripts/executar-c4-codex.ps1` |
| C5 | Cursor | código Python + alertas C1/C2 | `scripts/executar-c5-cursor-sast.ps1` |
| C6 | Codex | código Python + alertas C1/C2 | `scripts/executar-c6-codex-sast.ps1` |

Os lotes usam `scripts/executar-c3-cursor-lote.ps1` para C3,
`scripts/executar-c4-codex-lote.ps1` para C4,
`scripts/executar-c5-cursor-sast-lote.ps1` para C5 e
`scripts/executar-c6-codex-sast-lote.ps1` para C6.

O caminho C1/C2 → alertas → prompt → agente → manifesto é documentado neste
arquivo; o formato dos contratos e das evidências está em
[`ARTEFATOS_JSON.md`](ARTEFATOS_JSON.md).

Os adaptadores compartilhados ficam em `scripts/ia/executar-cursor.ps1` e
`scripts/ia/executar-codex.ps1`. Normalmente eles não devem ser chamados
diretamente.

## 1. Preparar as ferramentas

Execute os comandos a partir da raiz do repositório.

### Codex

O executável precisa estar disponível no `PATH` do Windows:

```powershell
codex --version
codex login
```

O executor usa `codex exec` em sessão efêmera, sandbox somente leitura,
aprovação `never` e saída JSONL. O schema comum é validado localmente, da mesma
forma que no Cursor; ele não é passado como `--output-schema`, porque a saída
estruturada do Codex exige objeto na raiz e o protocolo usa uma lista JSON. Consulte a
[documentação oficial do modo não interativo do Codex](https://learn.chatgpt.com/docs/non-interactive-mode).

### Cursor Agent

O modo padrão neste repositório é o Cursor Agent nativo para Windows, executado
diretamente pelo PowerShell. O projeto permanece no caminho Windows; não é
necessário copiá-lo para o WSL. Instale a CLI conforme a
[documentação oficial do Cursor](https://cursor.com/docs/cli/installation):

```powershell
irm 'https://cursor.com/install?win32=true' | iex
```

Em hosts cuja política bloqueia a execução direta de `agent.ps1`, use um
PowerShell filho com a política limitada ao processo para verificar e
autenticar a instalação:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "agent --version"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "agent login"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "agent status"
```

Os scripts C3/C5 resolvem o launcher `agent.ps1` instalado, iniciam-no por um
PowerShell filho com `-ExecutionPolicy Bypass` e preservam `stdin`, `stdout`,
`stderr` e o código de saída. Para usar deliberadamente uma instalação no WSL,
informe `-ModoCursor WSL`, `-ExecutavelCursor agent` e, se necessário,
`-DistribuicaoWsl Ubuntu`.

No Windows, a CLI informa que seu sandbox de sistema está disponível somente
em macOS/Linux. Por isso, o modo nativo passa
`--trust --mode=ask --sandbox disabled` e cria `.cursor/cli.json` com
`Write(**)` e `Shell(*)` negados. `--trust` evita a pergunta interativa para
cada área nova; ele não libera ferramentas. O executor não usa `--force` nem
`--yolo`. No WSL, o executor mantém `--sandbox enabled` e também cria
`.cursor/sandbox.json`. O serviço do Cursor continua precisando de conexão para
responder. As configurações seguem as referências oficiais de
[permissões da CLI](https://docs.cursor.com/cli/reference/permissions) e
[sandbox](https://docs.cursor.com/reference/sandbox).

O Cursor identifica o perfil principal de GPT-5.6 Luna como
`gpt-5.6-luna-medium`; esse identificador exato fica congelado em
`cursor-c3-v1.json` e é usado tanto em C3 quanto em C5.

Nas versões atuais da CLI, o evento terminal separa `inputTokens`,
`cacheReadTokens` e `cacheWriteTokens`. O manifesto soma esses componentes em
`tokens_entrada`, preserva `outputTokens` em `tokens_saida` e calcula
`tokens_total` quando a CLI não fornece o total diretamente. Os componentes
originais continuam preservados em `eventos.jsonl`.

Não coloque chaves de API em parâmetros, scripts ou arquivos do repositório.
Use o login local das CLIs ou os mecanismos seguros do ambiente de CI.

## 2. Validar sem consumir API

O teste abaixo não chama Cursor nem Codex:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/test-executores-ia.ps1
```

Também é possível inspecionar cada comando antes da execução:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c3-cursor.ps1 -Alvo ALVO-0001 -SomentePlanejar
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c4-codex.ps1 -Alvo ALVO-0001 -SomentePlanejar
```

`-SomentePlanejar` valida o alvo e imprime um plano JSON, mas não cria uma
sessão externa e não consome tokens.

### Progresso e timeout

As execuções reais de Cursor e Codex usam timeout padrão de 3.600 segundos
(uma hora). O valor observado aparece no plano e no manifesto e pode ser
sobrescrito, por exemplo, com `-TimeoutSegundos 7200`.

Durante uma execução real, o adaptador escreve mensagens de progresso em
`stderr`: validação do alvo, preparação dos artefatos, PID do processo, tempo
decorrido a cada dez segundos, código de saída, validação da resposta e caminho
do manifesto. O relatório JSON terminal permanece sozinho em `stdout`, para que
automações possam consumi-lo sem remover as mensagens de acompanhamento.

## 3. Gerar a entrada híbrida de C5/C6

C5 e C6 precisam da união normalizada dos resultados já coletados em C1 e C2.
Gere-a uma vez para o alvo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gerar-alertas-sast.ps1 -Alvo ALVO-0001
```

O arquivo será criado em
`execucoes/ia/alertas/ALVO-0001-alertas-sast.json`. O gerador seleciona a
tentativa concluída mais recente de C1 e C2, preserva a origem e deduplica sem
consultar o oracle. Ele recusa sobrescrever um arquivo existente.

Para C5 e C6, os 26 arquivos preparados devem corresponder ao lock
`config/agentes/alertas-sast-c6-v1.lock.json`. O executor valida o SHA-256 e a
contagem de cada alvo antes de montar o prompt. O conjunto congelado contém
1.410 alertas; diferenças de hash bloqueiam planejamento e execução.

Depois disso, os planos híbridos podem ser conferidos:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c5-cursor-sast.ps1 -Alvo ALVO-0001 -SomentePlanejar
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c6-codex-sast.ps1 -Alvo ALVO-0001 -SomentePlanejar
```

## 4. Executar o piloto obrigatório

As chamadas externas só começam quando `-ConfirmarExecucao` é informado. Isso
evita consumo acidental de tokens. Para o piloto de `ALVO-0001`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c3-cursor.ps1 `
  -Alvo ALVO-0001 -Repeticao 1 -Finalidade piloto -ConfirmarExecucao

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c4-codex.ps1 `
  -Alvo ALVO-0001 -Repeticao 1 -Finalidade piloto -ConfirmarExecucao

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c5-cursor-sast.ps1 `
  -Alvo ALVO-0001 -Repeticao 1 -Finalidade piloto -ConfirmarExecucao

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-c6-codex-sast.ps1 `
  -Alvo ALVO-0001 -Repeticao 1 -Finalidade piloto -ConfirmarExecucao
```

Antes de liberar a coleta completa, confira nos quatro manifestos:

- `estado` igual a `concluida`;
- `resposta_valida` igual a `true`;
- modelo solicitado, modelo exibido e `modelo_verificacao`;
- identificador de sessão e contadores de tokens;
- lista `violacoes` vazia;
- igualdade de `prompt_base_sha256` e `schema_saida_sha256` entre os cenários;
- igualdade de `alertas_sast_sha256` entre C5 e C6.

A disponibilidade de `gpt-5.6-luna` em cada produto deve ser comprovada nesse
piloto. Uma divergência fica registrada no manifesto e deve bloquear a coleta
até decisão metodológica.

No Codex CLI, o fluxo oficial de `codex exec --json` documenta os eventos de
sessão, itens, conclusão, uso e erro, mas não garante um campo com o modelo
efetivamente servido. Nessa situação, o executor preserva
`modelo_exibido=null` e registra `modelo_verificacao=nao_exposto_jsonl_codex`.
O valor solicitado continua comprovado pelo vetor `comando`; ele não deve ser
copiado para `modelo_exibido`, pois isso transformaria solicitação em observação.

## 5. Executar em lote

Piloto e coleta usam namespaces separados. Assim, uma execução aprovada em
`resultados/ia/piloto/` nunca ocupa nem substitui uma unidade de
`resultados/ia/coleta/`.

### Lote C3

O planejamento completo de C3 valida as 26 entradas e as três repetições sem
consumir API:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c3-cursor-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
```

O plano deve informar 78 tarefas. O lote real é sequencial, fixa por caminho a
versão nativa do Cursor observada no início da passagem e exige confirmação:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c3-cursor-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -ConfirmarExecucao
```

Por padrão, uma falha é preservada e o lote segue para as demais unidades. Ao
repetir o mesmo comando, unidades válidas com a mesma configuração, modelo e
versão são puladas, enquanto falhas recebem automaticamente o próximo número de
tentativa. `-PararEmFalha` interrompe a passagem na primeira falha. `-Alvos` e
`-Repeticoes` permitem planejar ou executar um subconjunto específico.

Por exemplo, para refazer somente `ALVO-0007`, repetição 2, se essa unidade
estiver pendente ou tiver falhado:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c3-cursor-lote.ps1 `
  -Finalidade coleta -Repeticoes '2' -Alvos ALVO-0007 -ConfirmarExecucao
```

Se ela já estiver válida, o comando apenas a identifica como concluída e não
faz uma nova chamada ao Cursor. Se houver tentativas com falha, elas não são
apagadas e a retomada usa automaticamente o próximo número de tentativa.

### Lote C4

Para inspecionar o lote C4 dos 26 alvos sem chamar o Codex:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes "1,2,3" -SomentePlanejar
```

Uma passagem por todos os alvos contém 26 chamadas:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes "1" -ConfirmarExecucao
```

A coleta C4 completa, com três repetições independentes por alvo, contém 78
chamadas sequenciais:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes "1,2,3" -ConfirmarExecucao
```

O executor pula unidades já concluídas e válidas. Se uma tentativa falhar, o
lote preserva seus artefatos, segue para a próxima unidade e, quando executado
novamente, usa o próximo número de tentativa. Use `-PararEmFalha` quando for
preferível interromper o lote na primeira falha.

Antes de pular uma unidade, o lote revalida `resposta-bruta.txt` com a versão
atual do validador. Portanto, uma resposta aceita por uma versão antiga, mas
que contenha arquivo inexistente ou linha fora do arquivo, recebe uma nova
tentativa sem apagar nem alterar a anterior.

### Lote C5 com os alertas SAST congelados

Antes da coleta completa, planeje e execute o piloto de um alvo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c5-cursor-sast-lote.ps1 `
  -Finalidade piloto -Repeticoes '1' -Alvos ALVO-0001 -SomentePlanejar
```

O plano esperado contém uma tarefa, 25 alertas e o SHA-256
`9b79fc9eee4d719b5067c37a70b52e1dea2d0126018f1b0145bccfe802161b16`.
Para executar o piloto, substitua `-SomentePlanejar` por
`-ConfirmarExecucao`. Audite o manifesto antes de liberar a coleta completa.

Depois da aprovação do piloto, planeje as 78 unidades sem chamar o Cursor:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c5-cursor-sast-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
```

Para executar a coleta C5 completa:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c5-cursor-sast-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -ConfirmarExecucao
```

O lote valida os hashes congelados dos alertas, fixa a versão do Cursor por
caminho e continua após falhas. Ao repetir o comando, unidades válidas são
puladas e cada unidade pendente usa automaticamente a próxima tentativa. Para
refazer somente `ALVO-0007`, repetição 2:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c5-cursor-sast-lote.ps1 `
  -Finalidade coleta -Repeticoes '2' -Alvos ALVO-0007 -ConfirmarExecucao
```

Use `-PararEmFalha` somente quando quiser interromper a passagem na primeira
falha. Sem essa opção, os artefatos da falha são preservados e o lote continua.

### Fechamento das coletas C3 e C5

As duas coletas Cursor foram encerradas em 27 de setembro de 2026. O
planejamento atual informa 78 tarefas concluídas e zero chamadas planejadas em
cada condição.

| Condição | Tentativas | Válidas | Falhas preservadas | Unidades com retentativa |
|---|---:|---:|---:|---:|
| C3 | 97 | 78 | 19 | 14 |
| C5 | 91 | 78 | 13 | 3 |

Todas as falhas foram de formato; não houve falha de transporte ou da CLI. Em
C3, 18 respostas referenciaram linhas fora do arquivo e uma referenciou arquivo
inexistente. Em C5, as 13 falhas referenciaram linhas fora do arquivo. As
evidências compactas estão em `evidencias/coleta-c3/auditoria-m3-c3.json` e
`evidencias/coleta-c5/auditoria-m3-c5.json`. As respostas brutas publicáveis
estão em `resultados/`; entradas integrais seguem a política de licenças em
[`DADOS_AUDITAVEIS.md`](DADOS_AUDITAVEIS.md).

### Planejar C6 com os alertas SAST congelados

Antes de qualquer chamada externa, confira o piloto de um alvo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c6-codex-sast-lote.ps1 `
  -Finalidade piloto -Repeticoes '1' -Alvos ALVO-0001 -SomentePlanejar
```

O plano esperado contém uma tarefa, 25 alertas e o SHA-256
`9b79fc9eee4d719b5067c37a70b52e1dea2d0126018f1b0145bccfe802161b16`.
Para executar esse piloto, substitua `-SomentePlanejar` por
`-ConfirmarExecucao`. Não execute o lote completo antes de auditar o manifesto
do piloto.

Depois da aprovação, o plano da coleta completa é:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c6-codex-sast-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
```

Antes da coleta, esse plano informava 26 alvos, 78 tarefas, zero concluídas e
78 chamadas planejadas. A execução real exige trocar `-SomentePlanejar` por
`-ConfirmarExecucao`. Cada unidade só é reutilizada quando resposta, modelo
solicitado e hash dos alertas ainda são válidos.

### Fechamento da coleta C6

A coleta C6 foi encerrada em 26 de setembro de 2026. O plano atual informa 78
tarefas concluídas e zero chamadas planejadas. Foram necessárias 92 chamadas:
78 tentativas válidas e 14 falhas de formato preservadas em sete unidades.
Quatro passagens do lote produziram, respectivamente:

| Passagem | Concluídas novas | Puladas | Falhas |
|---:|---:|---:|---:|
| 1 | 71 | 0 | 7 |
| 2 | 2 | 71 | 5 |
| 3 | 3 | 73 | 2 |
| 4 | 2 | 76 | 0 |

As falhas foram 13 intervalos de linha fora do arquivo e uma referência a
arquivo inexistente. Nenhuma foi falha de transporte ou da CLI. Os artefatos
anteriores permanecem imutáveis; o resumo auditável está em
`evidencias/coleta-c6/auditoria-m3-c6.json`.

Para confirmar o fechamento sem consumir API, execute novamente o planejamento.
O resultado esperado agora é `tarefas_concluidas=78` e
`chamadas_planejadas=0`.

### Fechamento da correção de C4

O diagnóstico de 17 de setembro de 2026 encontrou oito unidades pendentes:

- R01: `ALVO-0003`, `ALVO-0009`, `ALVO-0013` e `ALVO-0016`;
- R02: `ALVO-0007`, `ALVO-0015` e `ALVO-0016`;
- R03: `ALVO-0009`.

Primeiro confira o plano, sem consumir API:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
```

Se quiser uma visão compacta do plano no PowerShell:

```powershell
$texto = & powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
$plano = ($texto -join "`n") | ConvertFrom-Json
$plano | Select-Object tarefas_total, tarefas_concluidas, chamadas_planejadas
$plano.ordem | Where-Object acao -eq 'executar'
```

Em 17 de setembro, o plano intermediário tinha 70 concluídas e oito chamadas.
Essas chamadas já foram executadas. O plano final esperado agora tem 78 tarefas
concluídas e zero chamadas planejadas:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
```

As novas saídas usaram tentativas adicionais e as anteriores permanecem
imutáveis. Setenta manifestos selecionados foram produzidos pela versão anterior
do executor: usam `cli_versao`, guardam o hash da resposta em
`artefatos_sha256["resposta-bruta.txt"]` e não trazem `modelo_verificacao`.
Esses campos devem ser compatibilizados na auditoria, nunca reescritos nos
manifestos históricos.

O fechamento equivalente está em
`evidencias/coleta-c4/auditoria-m3-c4.json`: 78 unidades válidas, 90 tentativas
preservadas e os dois hashes de configuração observados. A explicação do
layout legado e da seleção das tentativas está em
[`FLUXO-E-RASTREABILIDADE.md`](FLUXO-E-RASTREABILIDADE.md).

## Tentativas, falhas e artefatos

Uma unidade não é sobrescrita. Se `tentativa-001` falhar, repita a mesma unidade
com `-Tentativa 2`; a falha anterior permanece preservada.

Os artefatos são gravados em:

```text
execucoes/ia/<FINALIDADE>/<CENARIO>-<ALVO>-R<NN>/tentativa-<NNN>/
resultados/ia/<FINALIDADE>/<CENARIO>-<ALVO>-R<NN>/tentativa-<NNN>/
```

Em `resultados/ia/` ficam o prompt efetivo, payload de código, eventos JSONL,
stderr, resposta bruta, resposta JSON validada quando aplicável e
`manifesto.json`. Mesmo timeout, erro da CLI ou resposta inválida gera um
manifesto terminal; não é convertido silenciosamente em “zero achados”.

O código Python é enviado no próprio prompt pela entrada padrão. Antes disso,
o executor confere todos os arquivos contra o inventário congelado do alvo. O
agente não recebe caminho para `oracle/` nem autorização para executar o código
ou ferramentas SAST.
