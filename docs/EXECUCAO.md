# Execução e reprodução do primeiro marco

## Pré-requisitos

- Windows com PowerShell 5.1 ou posterior;
- Git for Windows;
- Docker Desktop com contêineres Linux em execução;
- acesso HTTPS ao GitHub somente durante aquisição e ao registry/PyPI somente durante o build inicial.

Não instale Python, Bandit ou Semgrep no host. A execução validada usou Git `2.46.2.windows.1`, WSL `2.0.14.0`, Docker Desktop `4.38.0` e Engine `27.5.1`. Essas versões do host foram aceitas pela exceção AD-005; ela não dispensa nenhum controle de origem, hash ou isolamento.

Execute os comandos a partir da raiz deste repositório.

## 1. Adquirir as regras Semgrep fixadas

As regras não são redistribuídas porque possuem licença própria. O commit permitido é `40b8c63f75dc7c22c8a77482d73bfb864b146f7e` e somente `python/` entra no bundle local.

Em uma cópia nova do repositório, execute:

```powershell
New-Item -ItemType Directory -Path benchmark -Force | Out-Null
$fonteRegras = Join-Path (Resolve-Path benchmark) "semgrep-rules-t02"
git clone --no-checkout https://github.com/semgrep/semgrep-rules.git $fonteRegras
git -C $fonteRegras config core.hooksPath NUL
git -C $fonteRegras config core.autocrlf false
git -C $fonteRegras config submodule.recurse false
git -C $fonteRegras checkout --detach 40b8c63f75dc7c22c8a77482d73bfb864b146f7e
New-Item -ItemType Directory -Path docker/regras-semgrep -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath (Join-Path $fonteRegras "python") `
  -Destination docker/regras-semgrep/python -Recurse -ErrorAction Stop
```

Não execute hooks, submódulos, testes ou outros arquivos adquiridos. O gate confere que a árvore `python/` contém 717 arquivos e possui SHA-256 canônico `29eb41850a07fee98955446524423ddd9e9f5040cbf7e301788b791386ee8309`. Uma divergência bloqueia C2.

## 2. Construir e verificar o ambiente

O gate `quick` executa os testes Python com a imagem local existente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 quick
```

O gate `full` também reconstrói a imagem e executa wrapper, integrações Docker e fumaça sintética:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 full
```

O gate exigido para fechar um marco acrescenta compilação, sonda de runtime, `pip check`, versões observadas e preflight embarcado:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 build
```

Resultado esperado: exit code zero, nenhum teste ignorado, Python `3.12.13`, Bandit `1.9.4` e Semgrep `1.172.0`. A sonda deve observar UID/GID `10001`, `CapEff=0`, `NoNewPrivs=1`, somente interface `lo`, raiz somente leitura e ausência de corpus/oracle.

## 3. Reproduzir a fumaça RealVuln

O script abaixo:

1. adquire somente a tag anotada `v1.0` do RealVuln e confere objeto e commit;
2. lê o manifesto fixado e adquire o DSVW no commit declarado;
3. recusa links, submódulos, metadados Git, oracle e ground truth;
4. prepara uma árvore opaca e outra cópia de regeneração;
5. compara os inventários e executa C1/C2 serialmente, sem rede;
6. preserva os brutos em `resultados/`, grava a evidência escolhida e remove os alvos temporários.

A evidência original é imutável. Para reproduzir sem sobrescrevê-la, escolha um identificador e diretório novos:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/executar-fumaca-realvuln.ps1 `
  -AlvoId ALVO-REPRO-LOCAL `
  -EvidenciaNome reproducao-local `
  -TimeoutSegundos 300
```

O script também recusa diretórios de resultado existentes. Em uma segunda reprodução, use outro `AlvoId` e outro `EvidenciaNome`. Nunca reutilize um diretório para substituir uma tentativa anterior.

## 4. Interpretar os artefatos

Cada execução gera em `resultados/<execucao_id>/tentativa-001/`:

- `manifesto.pendente.json`, `manifesto.em_execucao.json` e `manifesto.json`;
- `versoes.json` e `processo.json`;
- `stdout.bin`, `stderr.bin` e `bruto.json`;
- `normalizado.json` e, quando aplicável, aviso estruturado.

Os arquivos em `resultados/` são ignorados pelo Git. A evidência pequena contém:

- `inventario-C1.json` e `inventario-C2.json`, que devem ser byte a byte iguais;
- `manifesto-C1.json` e `manifesto-C2.json`, validados pelo esquema v1;
- `resumo.json`, com origem/commits, imagem, versões, comandos, tempos, códigos de saída, contagens e hashes dos artefatos ignorados.

`finalidade=fumaca` é a regra mecanicamente verificável que exclui essas execuções da coleta principal. `status=descartavel` descreve o ciclo da evidência e não cria um quinto estado no manifesto: o estado terminal correto de uma execução bem-sucedida continua sendo `concluida`.

## 5. Valores observados na execução registrada

| Item | Valor |
|---|---|
| RealVuln | tag `v1.0`, objeto `aa9f7321c8c53fe417b8faa517f1c4308b69b389`, commit `d98e9fc91273702c9547663b6906d1fc494d4fcc` |
| alvo de fumaça | DSVW no commit `7d40f4b7939c901610ed9b85724552d60e7d63fa`, exposto como `ALVO-0001` |
| entrada C1/C2 | 6 arquivos, 23.610 bytes, `60913ac90d496cf087a5fe6e9a4dbb04882c862a93f7d094eebb692d41467206` |
| imagem usada | `tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0`, ID observado `sha256:a08aacb91c2482fd2baa97cf06334b72839925893f6b80a3fe01d484ce794580` |
| C1 | 2026-08-11 12:34:42Z a 12:34:43Z; 0,890142602 s; exit `1`; 1 achado |
| C2 | 2026-08-11 12:34:46Z a 12:35:16Z; 29,872785753 s; exit `0`; 1 achado |

O exit code `1` do Bandit representa achados e é aceito pelo executor. Esses números demonstram integração, não desempenho: a fumaça usa um único alvo e não deve ser incorporada às métricas do Capítulo 8.

## 6. Escopo deste procedimento

Este procedimento reproduz apenas o ambiente e a fumaça do primeiro marco; ele
não refaz automaticamente as coletas principais. O corpus de 26 alvos e as
coletas C1–C6 já foram concluídos por seus executores específicos. C3–C6 são
documentadas em `EXECUCAO-IA.md`.

O oracle não foi consultado nas auditorias descritivas das condições de IA. A
pontuação e as métricas adjudicadas são uma etapa separada. Antes de distribuir
a imagem, continua obrigatória a revisão das licenças dos pacotes transitivos
indicada em `FONTES_E_INTEGRIDADE.md`.
