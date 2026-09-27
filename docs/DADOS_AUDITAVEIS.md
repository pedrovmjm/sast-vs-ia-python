# Dados auditáveis e limites de redistribuição

Este repositório publica o máximo de material que permite refazer a cadeia de
custódia sem redistribuir código sem licença identificada, uma chave privada de
teste ou as regras Semgrep cuja licença proíbe redistribuição. "Não publicado"
não significa "não auditável": cada um dos 26 alvos possui URL, commit, lista
de arquivos, tamanho e SHA-256, além de um procedimento automático de aquisição.

## O que é publicado

| Grupo | Conteúdo | Cobertura |
|---|---|---:|
| `alvos/corpus-v1/` | snapshots sanitizados com licença preservada | 16/26 alvos |
| `evidencias/corpus-realvuln-v1/` | origem, commit, inventário por arquivo, hashes e sanitização | 26/26 alvos |
| `oracle/realvuln-v1/` | manifesto, ground truth e validador oficiais | integral |
| `execucoes/` | fila, alertas congelados e áreas de trabalho dos agentes | integral |
| `resultados/` | manifestos, respostas, saídas SAST, lotes e eventos publicáveis | todas as condições |
| `evidencias/coleta-*` | fechamentos compactos derivados dos resultados | C1–C6 |

Os snapshots integrais publicados são:

| Alvo | Licença observada | Arquivo preservado |
|---|---|---|
| ALVO-0002 | MIT | `LICENSE.md` |
| ALVO-0003 | MIT | `LICENSE.md` |
| ALVO-0005 | domínio público/Unlicense | `LICENSE` |
| ALVO-0007 | permissiva no estilo MIT | `LICENSE` |
| ALVO-0008 | GPL-3.0 | `LICENSE` |
| ALVO-0012 | MIT | `LICENSE.txt` |
| ALVO-0014 | MIT | `LICENSE.md` |
| ALVO-0016 | GPL-3.0 | `LICENSE` |
| ALVO-0017 | MIT | `LICENSE.md` |
| ALVO-0018 | MIT | `LICENSE` |
| ALVO-0019 | MIT | `LICENSE` |
| ALVO-0020 | MIT | `LICENSE` |
| ALVO-0023 | GPL-3.0 | `LICENSE` |
| ALVO-0024 | GPL-3.0 | `LICENSE` |
| ALVO-0025 | MIT | `LICENSE` |
| ALVO-0026 | MIT | `LICENSE` |

## O que é reconstruível, mas não redistribuído

- ALVO-0001, 0006, 0009, 0010, 0011, 0013, 0015, 0021 e 0022 não possuem
  licença explícita na raiz da revisão adquirida;
- ALVO-0004 possui MIT, mas o snapshot contém `ssl/key.pem`, uma chave privada
  de demonstração. Ele fica fora do Git para evitar que scanners e usuários a
  confundam com uma credencial operacional;
- `benchmark/` é cache de aquisição com repositórios Git completos. Publicá-lo
  duplicaria históricos de terceiros sem acrescentar prova além dos commits e
  inventários já registrados;
- `docker/regras-semgrep/` não é publicado porque o Semgrep Rules License 1.0
  permite uso, mas proíbe disponibilizar as regras a terceiros. O commit e os
  hashes permanecem em `config/fontes.lock.json` e
  `docs/FONTES_E_INTEGRIDADE.md`.

Para esses dez alvos, `payload-codigo.json`, `prompt.txt` e os eventos Cursor
também ficam fora do Git, pois incorporam o código integral. Manifestos, hashes,
respostas dos agentes, resultados SAST, alertas e eventos Codex continuam
publicados. Os eventos Codex foram verificados e não incorporam a entrada;
eventos Cursor incorporam o prompt e seguem a mesma decisão do corpus.

## Reconstrução dos 26 alvos

Em um checkout limpo, com Docker Desktop disponível:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/adquirir-corpus.ps1 `
  -RaizDados .reproducao-auditoria
```

`-RaizDados` mantém cache, alvos, oracle e novas evidências sob um diretório
isolado. O script nunca sobrescreve o material publicado. Sem esse parâmetro,
ele preserva o comportamento original e grava nas pastas da raiz, desde que os
destinos ainda não existam.

O script:

1. fixa o RealVuln na tag e no commit registrados;
2. adquire cada alvo no commit de `config/corpus-realvuln-v1.lock.json`;
3. usa somente os espelhos previamente autorizados no lock de espelhos;
4. aplica `config/politica-sanitizacao-v1.json` sem seguir symlinks;
5. gera o oracle e os inventários;
6. só promove os diretórios temporários se todos os hashes forem válidos.

Compare o `entrada_sha256` de
`.reproducao-auditoria/evidencias/corpus-realvuln-v1/resumo.json` com o
`evidencias/corpus-realvuln-v1/resumo.json` publicado. A lista completa de
hashes por arquivo está em `ALVO-NNNN-inventario.json` nos dois diretórios.

## Inventário da publicação

`evidencias/publicacao/inventario-dados-v1.json` lista caminho, tamanho e
SHA-256 de cada arquivo publicado sob `alvos/`, `oracle/`, `execucoes/` e
`resultados/`. Para verificar o checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/gerar-inventario-publicacao.ps1 -Verificar
```

O hash global usa registros ordenados no formato
`caminho<TAB>tamanho<TAB>sha256<LF>`. Assim, a verificação não depende do
formato interno do JSON.

## Segurança

Os alvos são intencionalmente vulneráveis. Trate-os como dados: não importe,
não execute, não instale dependências e não exponha aplicações na rede. Os
scripts do experimento montam o corpus somente para leitura e executam as
ferramentas em contêiner sem rede, sem capabilities e sem `docker.sock`.

O corpus licenciado ainda contém dados deliberadamente inseguros de laboratório,
como JWTs de teste, arquivos chamados `secret.*`, uma baseline de scanner e uma
lista fictícia de senhas vazadas. Eles fazem parte do comportamento vulnerável
avaliado e não são credenciais deste projeto. A varredura pré-publicação não
encontrou chave privada nem token de provedor em arquivo textual incluído; uma
sequência aleatória com prefixo `AKIA` foi observada no banco binário público
`GeoLite2-Country.mmdb`.
