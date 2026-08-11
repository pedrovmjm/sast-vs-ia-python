# Fontes, proveniência e integridade

**Data da validação:** 2026-08-10
**Política:** consultar primeiro código/documentos do projeto, depois documentação oficial e registros primários. Nenhum artefato é executado por estar apenas “disponível”: origem, versão, integridade, licença e finalidade devem estar registradas.

## Resultado da validação

| Artefato | Origem primária | Versão/revisão escolhida | Integridade/proveniência | Licença observada | Decisão |
|---|---|---|---|---|---|
| Git for Windows | [git-for-windows/git](https://github.com/git-for-windows/git/releases) | host `2.46.2.windows.1`; corrente observada `2.55.0.windows.3` | binário do host e release oficial; a versão do host está em intervalos afetados por avisos de segurança | GPL-2.0 e licenças dos componentes | continuar por exceção explícita AD-005; não relaxar URL/commit/hooks |
| WSL | [documentação Microsoft](https://learn.microsoft.com/windows/wsl/install) | host `2.0.14.0`; Docker atual requer ao menos `2.1.5` | `wsl --version` e requisito oficial do Docker Desktop | componentes Microsoft/Linux conforme distribuição | continuar por exceção explícita AD-005; registrar versão em cada execução |
| RealVuln | [kolega-ai/Real-Vuln-Benchmark](https://github.com/kolega-ai/Real-Vuln-Benchmark) | tag `v1.0`; commit `d98e9fc91273702c9547663b6906d1fc494d4fcc` | `git ls-remote --tags`; manifesto upstream declara `benchmark_version: 1.0.0` e `ground_truth_content_hash: sha256:a57347fbdf2a` | conflito: `LICENSE` contém MIT; `pyproject.toml` declara Apache-2.0 | adquirir sem alterar; preservar avisos; não usar `main` |
| Python | [imagem oficial Docker](https://hub.docker.com/_/python) | `3.12.13-slim-bookworm` | índice OCI `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`; revisão da imagem `3362634339580d3232e65a66dd5a36c47ae7ff14` | PSF e licenças dos componentes Debian | usar por tag completa + digest |
| Bandit | [PyPI/PyCQA](https://pypi.org/project/bandit/1.9.4/) e [fonte](https://github.com/PyCQA/bandit/tree/92ae8b82fb422a639f0ed8d99e96cea769594e08) | `1.9.4` | wheel `bandit-1.9.4-py3-none-any.whl`: SHA-256 `f89ffa663767f5a0585ea075f01020207e966a9c0f2b9ef56a57c7963a3f6f8e`; PyPI Trusted Publishing/Sigstore; tag no commit `92ae8b...` | Apache-2.0 | instalar somente por lock completo com hashes |
| Semgrep CE | [PyPI/Semgrep](https://pypi.org/project/semgrep/1.172.0/) e [releases](https://github.com/semgrep/semgrep/releases/tag/v1.172.0) | `1.172.0`; commit `651f37efa397bf066e1cf627414eeabe40b07e27` | wheel Linux x86-64 manylinux 2.34: SHA-256 `d8b94af4266a575287ad2cd844573743ab4fe58f6bfb6d9229327807937eade3`; PyPI Trusted Publishing/Sigstore | LGPL-2.1-or-later para o engine | instalar somente por lock completo com hashes |
| Regras Semgrep CE | [semgrep/semgrep-rules](https://github.com/semgrep/semgrep-rules) | commit `40b8c63f75dc7c22c8a77482d73bfb864b146f7e`; caminho `python/` | 717 arquivos regulares; árvore canônica `sha256:29eb41850a07fee98955446524423ddd9e9f5040cbf7e301788b791386ee8309` | [Semgrep Rules License v1.0](https://semgrep.dev/legal/rules-license/) | adquirir localmente; não redistribuir no Git remoto |
| Docker Desktop/Engine | [release notes oficiais](https://docs.docker.com/desktop/release-notes/) | host `4.38.0`/Engine `27.5.1`; recomendado `4.86.0`/`29.7.2` em 2026-08-10 | versões observadas localmente e release notes oficiais | Docker Subscription Service Agreement e licenças dos componentes | continuar por exceção explícita AD-005 e manter isolamento compensatório |

## Evidências do RealVuln v1.0

O `git ls-remote` oficial retornou:

```text
aa9f7321c8c53fe417b8faa517f1c4308b69b389 refs/tags/v1.0
d98e9fc91273702c9547663b6906d1fc494d4fcc refs/tags/v1.0^{}
```

O segundo valor é o commit desembrulhado da tag anotada e será a revisão obrigatória. O [manifesto v1.0](https://raw.githubusercontent.com/kolega-ai/Real-Vuln-Benchmark/d98e9fc91273702c9547663b6906d1fc494d4fcc/benchmark-manifest.json) contém 26 URLs e commits, exatamente o corpus descrito nos capítulos. A [branch atual](https://github.com/kolega-ai/Real-Vuln-Benchmark) já publica v2.0.0 com 66 repositórios; portanto, clonar a branch padrão alteraria o experimento.

Os campos upstream `ground_truth_content_hash` e `default_prompt_version` usam apenas 12 dígitos hexadecimais depois do prefixo `sha256:`. Eles serão tratados como identificadores abreviados, não como SHA-256 completos; o harness calculará e armazenará hashes SHA-256 completos dos artefatos efetivamente adquiridos. A documentação v1 também apresenta variação entre F2 e F3 como medida primária; antes da avaliação final, a implementação do scorer fixado será inspecionada e a escolha efetiva registrada.

### Divergência de licença

Na revisão fixada, o [arquivo `LICENSE`](https://raw.githubusercontent.com/kolega-ai/Real-Vuln-Benchmark/d98e9fc91273702c9547663b6906d1fc494d4fcc/LICENSE) contém o texto MIT, enquanto o [`pyproject.toml`](https://raw.githubusercontent.com/kolega-ai/Real-Vuln-Benchmark/d98e9fc91273702c9547663b6906d1fc494d4fcc/pyproject.toml) declara `Apache-2.0`. Este projeto não escolherá silenciosamente qual metadado “vence”. A cópia será mantida fora do histórico autoral, com os arquivos upstream intactos; qualquer distribuição pública deverá registrar a divergência ou obter esclarecimento dos mantenedores.

Cada um dos 26 repositórios-alvo mantém ainda sua própria licença. Os snapshots ficarão fora do Git autoral e não serão redistribuídos até que exista um inventário de licença por alvo.

## Regras do Semgrep

O engine Semgrep CE é LGPL-2.1-or-later, mas as regras mantidas no repositório oficial possuem licença própria. A [licença das regras](https://semgrep.dev/legal/rules-license/) limita o uso e proíbe redistribuição. O [comunicado oficial](https://semgrep.dev/blog/2024/important-updates-to-semgrep-oss/) informa que indivíduos, auditores e pentesters estão entre os casos não afetados pela mudança, mas isso não autoriza republicar os arquivos.

Consequências para o TCC:

- `docker/regras-semgrep/` será gerado localmente e ignorado pelo Git;
- origem, commit, lista de arquivos e SHA-256 do bundle serão publicados;
- durante a análise, Semgrep usará somente essa cópia local, com `--metrics=off` e `--network none`;
- se os termos não forem aceitáveis para o uso acadêmico concreto, C2 ficará bloqueada até esclarecimento do mantenedor; não será trocada por regras escolhidas depois de observar resultados.

Na T02, o commit foi adquirido com hooks, submódulos, conversão de fim de linha e protocolo local desativados. Antes do checkout esparso de `python/`, a árvore foi inspecionada e continha apenas blobs regulares. O hash canônico usa, em ordem de caminho UTF-8, `caminho relativo POSIX`, tamanho e SHA-256 de cada arquivo; assim, independe de mtime e ordem de criação. A cópia permanece em `docker/regras-semgrep/`, ignorada pelo Git.

O lock e a aceitação de risco também são identificados por SHA-256 para inclusão posterior nas evidências: `fontes.lock.json` = `b1323d8f999698fa23554864985b0a346e530d02ef4ff592040806ba681c5173`; `host-risk-waiver.json` = `38e22933c7d7d4a0699ebb7c084a6451f9e586f2f151a350ab790526763a9cf7`.

## Docker: estado atual e gate de segurança

Estado observado no host:

```text
Docker Desktop 4.38.0
Docker Engine 27.5.1
containerd 1.7.25
runc 1.1.12
```

A documentação oficial lista hoje Docker Desktop 4.86.0 com Engine 29.7.2. Entre essas versões foram publicados diversos [avisos de segurança](https://docs.docker.com/security/security-announcements/) e correções no Engine 29. Em 2026-08-10, o usuário aceitou explicitamente esse risco do sistema e autorizou continuar com as versões atuais.

Política aplicada durante a exceção:

1. o preflight registra as versões de Git, WSL, Docker Desktop e Engine e associa a exceção AD-005;
2. versões abaixo das recomendadas geram aviso, não bloqueio, enquanto a exceção estiver válida;
3. origem, commit e hashes continuam sendo bloqueios obrigatórios, sem bypass;
4. nenhum hook, submódulo, instalador, dependência, teste ou aplicação dos alvos é executado;
5. a análise mantém [rede `none`](https://docs.docker.com/engine/network/drivers/none/), usuário não root, filesystem somente leitura, `no-new-privileges` e capabilities removidas.

## Modelo de ameaça para downloads e execução

- Repositórios do corpus são intencionalmente vulneráveis e potencialmente hostis.
- Nenhum `requirements.txt`, `setup.py`, teste, aplicação ou hook pertencente a um alvo será executado.
- Clones usam URL HTTPS explícita e commit completo; submódulos não são inicializados automaticamente.
- O benchmark é validado antes de seus utilitários serem executados; os arquivos usados são fixados e têm hash registrado.
- Imagens e pacotes flutuantes (`latest`, branch padrão ou faixa de versão) não entram na coleta.
- Instalação de pacotes ocorre somente durante o build; contêineres de análise ficam sem rede.
- O socket Docker, diretórios ancestrais, `oracle/`, credenciais e configuração Git do host não são montados nos contêineres.

## Itens deliberadamente ainda não validados

Cursor, OpenAI Codex, modelos e cotas serão validados no início do marco M3 porque versões e disponibilidade são mutáveis. Nenhuma afirmação futura sobre esses produtos será tratada como configuração observada antes do piloto.
