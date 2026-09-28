# Fluxo, restrições e rastreabilidade C1–C6

Este documento responde três perguntas: qual arquivo arma cada condição, como
as restrições foram aplicadas e por que existem `execucoes/`, `resultados/` e
`evidencias/`.

## O papel de cada diretório

| Diretório | Papel | Pode ser fonte de métrica? |
|---|---|---|
| `execucoes/` | estado mutável do controlador e área de trabalho mínima de cada chamada | não diretamente |
| `resultados/` | registro primário, imutável e separado por tentativa | sim |
| `evidencias/` | síntese derivada, inventário e fechamento de um marco | sim, desde que ligada aos primários por hash |

Uma tentativa de IA usa dois caminhos:

```text
execucoes/ia/<piloto|coleta>/C<3-6>-ALVO-NNNN-RNN/tentativa-NNN/
resultados/ia/<piloto|coleta>/C<3-6>-ALVO-NNNN-RNN/tentativa-NNN/
```

O primeiro recebe somente o schema e a configuração local de permissões. O
segundo recebe prompt, payload, eventos, `stderr`, resposta bruta, resposta
validada e manifesto. Nenhuma tentativa é sobrescrita.

O piloto C4 foi originalmente produzido antes da introdução dos namespaces e
ficou na raiz de `execucoes/ia/` e `resultados/ia/`. Na publicação, seus três
diretórios foram movidos para `piloto/` sem alterar conteúdo. Os manifestos
mantêm `area_execucao` e `comando` históricos, o que permite auditar o caminho
real usado em 17 de setembro de 2026.

## Mapa dos seis cenários

| Condição | Entrada | Executor público | Adaptador/configuração | Evidência de fechamento |
|---|---|---|---|---|
| C1 | código | `scripts/executar-coleta-c1-c2.ps1` | `runner/adaptadores/bandit.py`, `config/fila-c1-c2.lock.json` | `evidencias/coleta-c1-c2/auditoria-m2-t08.json` |
| C2 | código | `scripts/executar-coleta-c1-c2.ps1` | `runner/adaptadores/semgrep.py`, `config/fila-c1-c2.lock.json` | `evidencias/coleta-c1-c2/auditoria-m2-t08.json` |
| C3 | código | `scripts/executar-c3-cursor-lote.ps1` | `scripts/ia/executar-cursor.ps1`, `config/agentes/cursor-c3-v1.json` | `evidencias/coleta-c3/auditoria-m3-c3.json` |
| C4 | código | `scripts/executar-c4-codex-lote.ps1` | `scripts/ia/executar-codex.ps1`, `config/agentes/codex-c4-v1.json` | `evidencias/coleta-c4/auditoria-m3-c4.json` |
| C5 | código + alertas | `scripts/executar-c5-cursor-sast-lote.ps1` | adaptador Cursor, perfil C3 e lock de alertas | `evidencias/coleta-c5/auditoria-m3-c5.json` |
| C6 | código + alertas | `scripts/executar-c6-codex-sast-lote.ps1` | adaptador Codex, `config/agentes/codex-c6-v1.json` | `evidencias/coleta-c6/auditoria-m3-c6.json` |

C5 reutiliza deliberadamente `cursor-c3-v1.json`: produto, modelo, prompt,
schema e restrições são os mesmos de C3; a única diferença experimental é
a inclusão dos alertas. C5 e C6 consomem os mesmos 26 arquivos gerados por
`scripts/gerar-alertas-sast.ps1`, congelados em
`config/agentes/alertas-sast-c6-v1.lock.json`.

## Arquivos efetivamente entregues aos agentes

Todos os agentes recebem:

1. `config/agentes/prompt-relatorio-ia-v1.txt`;
2. um `payload-codigo.json` montado somente com arquivos Python que constam no
   inventário sanitizado do alvo;
3. o contrato `config/agentes/schema-relatorio-ia-v1.json` para validação local.

C5 e C6 recebem adicionalmente
`execucoes/ia/alertas/ALVO-NNNN-alertas-sast.json`. O oracle, os locks que
revelam a origem do alvo, resultados de outras condições e o repositório
original não entram no prompt nem na área de trabalho.

No Codex, `--ignore-rules`, `--ignore-user-config` e o diretório efêmero evitam
herança de instruções pessoais. No Cursor, a área criada para a tentativa não
contém `AGENTS.md`, `CLAUDE.md` ou `.cursor/rules`: ela contém somente o schema,
`.cursor/cli.json` e, quando aplicável, `.cursor/sandbox.json`; o código segue
pelo prompt em `stdin`. O cliente Cursor nativo ainda dependeu da autenticação e
do estado global da instalação do usuário, que não foram congelados como uma
fronteira de segurança. Essa ameaça à validade está registrada em
[`ISOLAMENTO-E-SAIDAS-CURSOR.md`](ISOLAMENTO-E-SAIDAS-CURSOR.md).

## Como a restrição foi implementada

A restrição não depende de uma única frase no prompt. Ela possui camadas:

1. **Sanitização da entrada.** `config/politica-sanitizacao-v1.json` remove
   `.git`, caches, dependências, `ground-truth`, `oracle`, soluções, write-ups e
   modos Git não permitidos. `scripts/adquirir-corpus.ps1` aplica a política e
   compara a árvore produzida com o inventário SHA-256.
2. **Prompt comum.** `prompt-relatorio-ia-v1.txt` proíbe executar código,
   testes, shell, rede, SAST, busca, MCP e consulta ao oracle. O código e os
   alertas são delimitados como dados não confiáveis.
3. **Codex.** `scripts/ia/executar-codex.ps1` usa `--sandbox read-only`,
   `--ephemeral`, `--ignore-user-config`, `--ignore-rules` e
   `approval_policy="never"`. Eventos de execução de comando, mudança de
   arquivo, MCP ou busca invalidam a tentativa.
4. **Cursor.** `scripts/ia/executar-cursor.ps1` cria `.cursor/cli.json` com
   `allow: Read(**)` e `deny: Write(**), Shell(*)`, usa `--mode=ask` e rejeita
   qualquer `tool_call` que não seja leitura. No modo WSL também cria
   `sandbox.json` somente leitura, sem `/tmp`, cache compartilhado ou rede. A
   coleta registrada usou o modo nativo, cujo argumento de sandbox aparece
   como `disabled`; nesse modo, a barreira observável foi a política de
   permissões da CLI mais a rejeição pós-execução. Essa limitação não é
   ocultada. `Read(**)` expressa capacidade potencial, não leitura efetiva. A
   auditoria dos 193 fluxos de evento C3/C5 encontrou zero `tool_call`; detalhes,
   saídas e limitações estão em
   [`ISOLAMENTO-E-SAIDAS-CURSOR.md`](ISOLAMENTO-E-SAIDAS-CURSOR.md).
5. **Validação local.** `scripts/ia/comum.ps1` valida JSON, propriedades,
   caminhos, linhas, hashes, modelo e eventos proibidos antes de marcar uma
   tentativa como concluída. A IA não decide se a própria saída é válida.
6. **Segregação do oracle.** A avaliação contra ground truth ocorre somente
   depois do fechamento. As auditorias C3–C6 declaram `oracle_consultado=false`.

## Particularidade histórica do C4

C4 não usou outra metodologia. Ele foi o primeiro lote de IA concluído e 70
unidades selecionadas vieram de uma versão anterior do executor, sem o campo
`modelo_verificacao` e sem validação forte de arquivo/linha. Oito unidades foram
reprocessadas com o validador atual. Seis manifestos antigos continuavam
marcados como `concluida`, mas foram substituídos na seleção; nenhum foi
apagado. A auditoria C4 registra os dois hashes de configuração, as 90
tentativas, a seleção final e os hashes das sete passagens de lote.

Para confirmar sem consumir API:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/executar-c4-codex-lote.ps1 `
  -Finalidade coleta -Repeticoes '1,2,3' -SomentePlanejar
```

O resultado esperado é `tarefas_total=78`, `tarefas_concluidas=78` e
`chamadas_planejadas=0`.
