# Estratégia de testes e gates

## Princípio

O host não precisa de Python. Testes e verificações Python são executados no contêiner `controlador`. Código de repositórios vulneráveis nunca é importado ou executado; fixtures próprias representam os formatos necessários.

## Matriz de cobertura

| Camada criada ou modificada | Tipo obrigatório | Seguro em paralelo? | Observação |
|---|---|---:|---|
| funções puras, modelos e validação de esquema | unidade | Sim | `unittest`, sem rede e sem Docker aninhado |
| adaptador de JSON Bandit/Semgrep | unidade | Sim | usa fixtures próprias, nunca o ground truth |
| aquisição, inventário e sanitização | integração | Não | usa diretórios temporários e Git/Docker local |
| executor de contêiner e isolamento | integração | Não | inspeciona mounts, rede, usuário e limites |
| fluxo completo de fumaça | e2e | Não | serial, descartável e fora da coleta principal |
| documentação e manifestos estáticos | nenhum | Sim | validação sintática e `git diff --check` |

## Comandos de gate

Os comandos tornam-se executáveis depois de T03 criar a imagem e o `compose.yaml`.

| Gate | Comando |
|---|---|
| quick | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 quick` |
| full | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 full` |
| build | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 build` |

O gate `build` valida o Compose, reconstrói a imagem, compila para o `tmpfs`, executa todos os testes, roda a sonda de isolamento, aplica `pip check`, confere as versões e executa o preflight embarcado sem mounts.

Enquanto T03 não estiver concluída, documentos usam `git diff --check` e validação JSON nativa do PowerShell como gate provisório.

## Integridade dos testes

- Cada tarefa registra a contagem antes e depois do gate.
- Testes pertencem à mesma tarefa e ao mesmo commit da implementação.
- Nenhum teste pode ser removido, ignorado ou enfraquecido para obter aprovação.
- Testes que medem tempo ou isolamento Docker são sempre seriais.
- Saídas de fumaça não são aceitas como dados da coleta principal.
