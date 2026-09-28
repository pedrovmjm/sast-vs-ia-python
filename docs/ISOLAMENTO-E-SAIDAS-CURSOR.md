# Isolamento, `Read(**)` e saídas do Cursor

Este documento responde a três perguntas auditáveis sobre C3 e C5:

1. o que a permissão `Read(**)` autorizava;
2. se há evidência de que o Cursor leu o restante do repositório;
3. onde estão a resposta da IA e os demais artefatos de cada tentativa.

## Conclusão curta

`Read(**)` é uma **capacidade permitida**, não um registro de acesso. Segundo a
[documentação de permissões do Cursor CLI](https://docs.cursor.com/cli/reference/permissions),
`Read(pathOrGlob)` controla leituras por caminho ou *glob*, caminhos relativos são
resolvidos no workspace atual e regras `deny` prevalecem sobre `allow`.

Nas coletas deste artefato, o workspace atual não era a raiz do repositório. Cada
processo foi iniciado em uma pasta exclusiva como:

```text
execucoes/ia/coleta/C3-ALVO-0001-R01/tentativa-001/
```

Essa pasta continha apenas:

- `.cursor/cli.json`;
- `.cursor/sandbox.json`, nas tentativas em que foi criado;
- `schema-relatorio-ia-v1.json`.

O código do alvo não foi copiado para esse workspace. O controlador serializou os
arquivos Python em `PAYLOAD_CODIGO_JSON` e enviou o prompt completo pela entrada
padrão do processo. Portanto, a IA recebeu e analisou o código — isso é parte
necessária do experimento — mas não precisou usar uma ferramenta de leitura para
obtê-lo.

A auditoria de todos os `eventos.jsonl` de C3 e C5 encontrou **zero eventos
`tool_call`**. Assim, não há evidência de chamada explícita de `Read`, `Write`,
`Shell` ou outra ferramenta. Também não foram encontrados `AGENTS.md`,
`CLAUDE.md`, código do alvo ou arquivos de outras condições nos workspaces das
tentativas.

## Permissão potencial versus acesso observado

O arquivo `.cursor/cli.json` usado em cada tentativa contém:

```json
{"permissions":{"allow":["Read(**)"],"deny":["Write(**)","Shell(*)"]}}
```

Isso significa:

- `Read(**)`: uma chamada de leitura relativa ao workspace poderia ser aceita;
- `Write(**)`: chamadas de escrita por arquivo eram negadas;
- `Shell(*)`: chamadas de shell eram negadas.

Não significa que todos os arquivos correspondentes ao *glob* foram lidos ou
enviados ao modelo. A ocorrência de uma ferramenta apareceria no fluxo JSONL
como `type: "tool_call"`; o adaptador também inspeciona esse evento e marca como
contaminada qualquer chamada que não seja `readToolCall`.

O diretório efetivo é definido em `scripts/ia/comum.ps1` por
`ProcessStartInfo.WorkingDirectory`. O primeiro evento `system` de cada sessão
iniciada registra esse mesmo `cwd`. A auditoria compara o sufixo registrado com
`execucoes/ia/<fase>/<execucao>/<tentativa>` e falha se houver divergência.

## Evidência quantitativa

O arquivo
`evidencias/publicacao/auditoria-acesso-cursor-v1.json` foi gerado por
`scripts/auditar-acesso-cursor.ps1`. Ele inclui SHA-256 e contagem de eventos de
cada `eventos.jsonl`, além deste resumo:

| Condição/fase | Tentativas | Concluídas | Falhas preservadas | `resposta.json` | `tool_call` | `cwd` inválido |
|---|---:|---:|---:|---:|---:|---:|
| C3/piloto | 4 | 1 | 3 | 1 | 0 | 0 |
| C3/coleta | 97 | 78 | 19 | 78 | 0 | 0 |
| C5/piloto | 1 | 1 | 0 | 1 | 0 | 0 |
| C5/coleta | 91 | 78 | 13 | 78 | 0 | 0 |

Duas tentativas iniciais do piloto C3 falharam antes de emitir o evento
`system`; por isso existem 193 manifestos/eventos, mas 191 registros de `cwd`.
Todos os 191 apontam para a área exclusiva da tentativa.

Para refazer a conferência sobre o acervo local integral:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/auditar-acesso-cursor.ps1 -Verificar
```

Os eventos que incorporam código de alvos sem autorização de redistribuição não
são publicados integralmente. O JSON de auditoria preserva o SHA-256 de cada
arquivo analisado, e o mesmo hash aparece no `manifesto.json` correspondente.

## Como o código chegou ao modelo

O fluxo implementado em `scripts/ia/comum.ps1` é:

1. validar o alvo e seu inventário;
2. ler somente os arquivos Python do corpus sanitizado;
3. gerar `payload-codigo.json`;
4. concatenar o prompt-base, o payload e, em C5, os alertas SAST;
5. criar uma área de trabalho nova e uma pasta de resultados nova;
6. iniciar o Cursor com a área da tentativa como `WorkingDirectory`;
7. escrever o prompt em UTF-8 diretamente no `stdin`;
8. capturar `stdout` e `stderr` sem executar a resposta;
9. extrair o evento terminal `result` e validar localmente o JSON retornado.

O Cursor não recebeu caminhos para `oracle/`, `resultados/` ou outros alvos no
prompt. O prompt ordena explicitamente analisar somente o payload e proíbe busca,
rede, MCP, shell, execução de código, SAST e consulta ao oracle.

## Onde está a saída real da IA

`execucoes/` não guarda a resposta. Essa árvore é apenas a área de trabalho e o
estado operacional. A saída primária está em `resultados/`:

```text
resultados/ia/<piloto|coleta>/<C3|C5>-ALVO-NNNN-RNN/tentativa-NNN/
```

Cada tentativa pode conter:

| Arquivo | Função |
|---|---|
| `eventos.jsonl` | `stdout` integral do Cursor em formato de eventos; contém os eventos `system`, `user`, `assistant`, `thinking` e `result` emitidos pelo cliente. |
| `resposta-bruta.txt` | texto do campo `result`, exatamente como retornado pela IA. |
| `resposta.json` | resposta após validação local de JSON, schema, caminhos e linhas; só existe quando válida. |
| `manifesto.json` | comando, modelo, sessão, tempos, tokens, estado e SHA-256 de todos os artefatos. |
| `prompt.txt` | bytes exatos enviados por `stdin`. |
| `payload-codigo.json` | arquivos Python e conteúdo entregues ao modelo. |
| `alertas-sast.json` | entrada adicional de C5; não existe em C3. |
| `stderr.txt` | saída de erro do cliente. |

No piloto C3, as tentativas 1 e 2 terminaram sem resposta; a tentativa 3 produziu
resposta, mas falhou na validação de intervalo de linhas; a tentativa 4 foi a
primeira válida. Sua saída está em:

```text
resultados/ia/piloto/C3-ALVO-0001-R01/tentativa-004/resposta.json
```

O conjunto experimental, por sua vez, está em `resultados/ia/coleta/`: são 78
respostas válidas selecionadas para C3 e 78 para C5. As tentativas anteriores
continuam preservadas e não são contadas como respostas vazias.

## Arquivos de configuração envolvidos

Os arquivos usados pelo controlador foram:

- `config/agentes/cursor-c3-v1.json`: perfil congelado compartilhado por C3 e C5;
- `config/agentes/prompt-relatorio-ia-v1.txt`: instrução enviada ao modelo;
- `config/agentes/schema-relatorio-ia-v1.json`: validação local da resposta;
- `scripts/ia/comum.ps1`: payload, prompt, processo, captura e manifesto;
- `scripts/ia/executar-cursor.ps1`: argumentos do Cursor e permissões da tentativa.

O modelo não abriu esses arquivos por ferramenta. O controlador leu os três
primeiros, verificou seus hashes e enviou somente o prompt montado. O schema foi
copiado para a área da tentativa para validação e rastreabilidade.

## Limitações e ameaça à validade

A formulação defensável é **“não houve acesso adicional observado”**, não
“acesso adicional era impossível”. Há quatro razões:

1. a coleta principal usou o Cursor nativo no Windows com `--sandbox disabled`;
2. `cli.json` é uma política do cliente, não um isolamento obrigatório do sistema
   operacional;
3. a [documentação de segurança do Cursor](https://cursor.com/docs/agent/security)
   descreve essas proteções como barreiras de melhor esforço;
4. os eventos mostram chamadas explícitas de ferramentas, mas não demonstram
   processos internos do provedor que não sejam expostos no protocolo.

Além disso, embora o comando preservado nos manifestos use `--mode=ask`, o evento
`system` desta versão do cliente registrou `permissionMode: "default"` em todas
as 191 sessões iniciadas. O artefato não interpreta esse rótulo como prova de
isolamento; apoia a conclusão no `cwd`, no conteúdo mínimo do workspace, na
política registrada, na ausência de `tool_call` e nos hashes dos artefatos.

Para uma repetição futura mais restrita, `Read(**)` pode ser negado, pois o código
já segue no prompt. Essa alteração não deve ser aplicada retroativamente aos
arquivos da coleta encerrada: mudaria a configuração experimental e exigiria uma
nova coleta C3/C5 para manter comparabilidade.
