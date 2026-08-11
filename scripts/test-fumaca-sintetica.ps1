[CmdletBinding()]
param(
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$")]
    [string]$Imagem = "tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0",

    [ValidateRange(30, 3600)]
    [int]$TimeoutSegundos = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Wrapper = Join-Path $PSScriptRoot "executar-sast.ps1"
$Entrada = [IO.Path]::GetFullPath(
    (Join-Path $Repo "tests/fixtures/alvo-sintetico")
)
$Resultados = [IO.Path]::GetFullPath((Join-Path $Repo "resultados"))
$Lock = Join-Path $Repo "config/fontes.lock.json"
$Comparacao = [StringComparison]::OrdinalIgnoreCase
$Token = [guid]::NewGuid().ToString("N")
$Sufixo = [DateTime]::UtcNow.ToString(
    "yyyyMMddHHmmss",
    [Globalization.CultureInfo]::InvariantCulture
) + "-" + $Token.Substring(0, 10)
$Alvo = "ALVO-FUMACA-$Sufixo"
$Proprietarios = [Collections.Generic.List[object]]::new()
$Casos = [Collections.Generic.List[object]]::new()
$ErroFinal = $null
$FixtureExecutada = $false
$LimpezaErros = [Collections.Generic.List[string]]::new()

function Assert-True {
    param([bool]$Condicao, [string]$Mensagem)
    if (-not $Condicao) { throw $Mensagem }
}

function Assert-Equal {
    param($Esperado, $Observado, [string]$Mensagem)
    if ($Esperado -ne $Observado) {
        throw "$Mensagem; esperado=[$Esperado], observado=[$Observado]"
    }
}

function Assert-Sequence {
    param([object[]]$Esperado, [object[]]$Observado, [string]$Mensagem)
    Assert-Equal $Esperado.Count $Observado.Count "$Mensagem (tamanho)"
    for ($i = 0; $i -lt $Esperado.Count; $i++) {
        Assert-Equal ([string]$Esperado[$i]) ([string]$Observado[$i]) `
            "$Mensagem (índice $i)"
    }
}

function Assert-TextoMountSeguro {
    param([string]$Valor, [string]$Campo)
    if (-not $Valor -or $Valor.Contains(",") -or $Valor.Contains("`r") -or
        $Valor.Contains("`n") -or $Valor.IndexOf([char]0) -ge 0) {
        throw "$Campo contém vírgula, CR, LF ou NUL"
    }
}

function Test-Dentro {
    param([string]$Caminho, [string]$Raiz, [bool]$PermitirRaiz = $true)
    $raizLimpa = $Raiz.TrimEnd("\", "/")
    if ($Caminho.Equals($raizLimpa, $Comparacao)) { return $PermitirRaiz }
    return $Caminho.StartsWith(
        $raizLimpa + [IO.Path]::DirectorySeparatorChar,
        $Comparacao
    )
}

function Assert-ArvoreSemReparse {
    param([string]$Caminho, [string]$Campo, [switch]$ExigirArquivo)
    $raiz = Get-Item -LiteralPath $Caminho -Force -ErrorAction Stop
    Assert-True $raiz.PSIsContainer "$Campo deve ser diretório"
    Assert-True (
        ($raiz.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
    ) "$Campo não pode ser reparse point"
    $quantidade = 0
    $pilha = [Collections.Generic.Stack[IO.DirectoryInfo]]::new()
    $pilha.Push([IO.DirectoryInfo]$raiz)
    while ($pilha.Count -gt 0) {
        foreach ($item in $pilha.Pop().GetFileSystemInfos()) {
            Assert-True (
                ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
            ) "$Campo contém reparse point: $($item.FullName)"
            if ($item -is [IO.DirectoryInfo]) {
                $pilha.Push($item)
            }
            elseif ($item -is [IO.FileInfo]) {
                $quantidade++
            }
            else {
                throw "$Campo contém entrada não regular: $($item.FullName)"
            }
        }
    }
    if ($ExigirArquivo) {
        Assert-True ($quantidade -gt 0) "$Campo deve conter arquivo"
    }
}

function Assert-ArquivoRegular {
    param([string]$Caminho, [string]$Campo)
    $item = Get-Item -LiteralPath $Caminho -Force -ErrorAction Stop
    Assert-True (-not $item.PSIsContainer) "$Campo deve ser arquivo"
    Assert-True (
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
    ) "$Campo não pode ser reparse point"
}

function Read-Json {
    param([string]$Caminho, [string]$Campo)
    Assert-ArquivoRegular $Caminho $Campo
    try {
        return Get-Content -LiteralPath $Caminho -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "$Campo não contém JSON válido: $($_.Exception.Message)"
    }
}

function Get-Sha256 {
    param([string]$Caminho)
    Assert-ArquivoRegular $Caminho "artefato para SHA-256"
    return (Get-FileHash -LiteralPath $Caminho -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-DockerCapture {
    param([string[]]$Argumentos, [string]$Contexto)
    $linhas = @(& docker @Argumentos 2>&1)
    $codigo = $LASTEXITCODE
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $($linhas -join ' ')"
    }
    return @($linhas | ForEach-Object { [string]$_ })
}

function Assert-SemContainersSastResiduais {
    $ids = Invoke-DockerCapture @(
        "container", "ls", "--all", "--quiet", "--filter", "label=tcc.sast.owner"
    ) "inventário de contêineres SAST"
    $presentes = @($ids | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    Assert-Equal 0 $presentes.Count "não pode restar contêiner com label tcc.sast.owner"
}

function Get-ImagemLocal {
    $linhas = Invoke-DockerCapture @(
        "image", "inspect", "--format", "{{json .}}", $Imagem
    ) "docker image inspect"
    try {
        $info = ($linhas -join [Environment]::NewLine) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "docker image inspect não retornou JSON válido"
    }
    Assert-True ([string]$info.Id -match "^sha256:[0-9a-f]{64}$") `
        "imagem local não possui ID SHA-256 completo"
    Assert-Equal "linux" ([string]$info.Os) "imagem deve usar Linux"
    Assert-Equal "amd64" ([string]$info.Architecture) "imagem deve usar amd64"
    return $info
}

function Get-HashCanonicoContainer {
    param([string]$ImageId)
    Assert-TextoMountSeguro $Entrada "entrada"
    $codigo = "from runner.aquisicao import calcular_sha256_arvore; print(calcular_sha256_arvore('/entrada'))"
    $mount = "type=bind,src=$Entrada,dst=/entrada,readonly"
    $linhas = Invoke-DockerCapture @(
        "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "10001:10001",
        "--workdir", "/opt/tcc", "--init", "--pids-limit", "64",
        "--memory", "512m", "--memory-swap", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m,uid=10001,gid=10001,mode=1777",
        "--env", "HOME=/tmp/tcc-home", "--env", "PYTHONNOUSERSITE=1",
        "--env", "PYTHONSAFEPATH=1", "--mount", $mount, $ImageId,
        "/usr/local/bin/python", "-P", "-c", $codigo
    ) "cálculo canônico da entrada"
    $hashes = @($linhas | Where-Object { $_ -match "^[0-9a-f]{64}$" })
    Assert-Equal 1 $hashes.Count "cálculo canônico deve emitir um único SHA-256"
    return $hashes[0]
}

function Invoke-WrapperJson {
    param([hashtable]$Parametros, [string]$Contexto)
    $linhas = @(& $Wrapper @Parametros)
    try {
        return (($linhas | ForEach-Object { [string]$_ }) -join [Environment]::NewLine) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "$Contexto não retornou JSON válido: $($_.Exception.Message)"
    }
}

function New-PropriedadeSaida {
    param([string]$ExecucaoId)
    if (-not (Test-Path -LiteralPath $Resultados)) {
        New-Item -ItemType Directory -Path $Resultados -ErrorAction Stop | Out-Null
    }
    $itemResultados = Get-Item -LiteralPath $Resultados -Force -ErrorAction Stop
    Assert-True $itemResultados.PSIsContainer "resultados deve ser diretório"
    Assert-True (
        ($itemResultados.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
    ) "resultados não pode ser reparse point"
    $raiz = [IO.Path]::GetFullPath((Join-Path $Resultados $ExecucaoId))
    Assert-True (Test-Dentro $raiz $Resultados $false) "raiz própria saiu de resultados"
    Assert-True (-not (Test-Path -LiteralPath $raiz)) "raiz de execução já existe"
    New-Item -ItemType Directory -Path $raiz -ErrorAction Stop | Out-Null
    $marcador = Join-Path $raiz ".fumaca-sintetica-owner.json"
    [ordered]@{
        token = $Token
        execucao_id = $ExecucaoId
        criado_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath $marcador -Encoding UTF8
    $registro = [pscustomobject]@{
        execucao_id = $ExecucaoId
        raiz = $raiz
        saida = Join-Path $raiz "tentativa-001"
        marcador = $marcador
    }
    $Proprietarios.Add($registro)
    return $registro
}

function Remove-ResultadoProprio {
    param($Registro)
    $raiz = [IO.Path]::GetFullPath([string]$Registro.raiz)
    Assert-True (Test-Dentro $raiz $Resultados $false) "cleanup recusou raiz fora de resultados"
    Assert-True (
        [IO.Path]::GetFileName($raiz) -eq [string]$Registro.execucao_id
    ) "cleanup recusou raiz com nome inesperado"
    if (-not (Test-Path -LiteralPath $raiz)) { return }
    Assert-ArvoreSemReparse $raiz "resultado próprio"
    $dono = Read-Json $Registro.marcador "marcador de propriedade"
    Assert-Equal $Token ([string]$dono.token) "token de propriedade divergente"
    Assert-Equal ([string]$Registro.execucao_id) ([string]$dono.execucao_id) `
        "execução do marcador divergente"
    if (Test-Path -LiteralPath $Registro.saida) {
        Remove-Item -LiteralPath $Registro.saida -Recurse -Force -ErrorAction Stop
    }
    Remove-Item -LiteralPath $Registro.marcador -Force -ErrorAction Stop
    $itemRaiz = Get-Item -LiteralPath $raiz -Force
    Assert-Equal 0 $itemRaiz.GetFileSystemInfos().Count "raiz própria não ficou vazia"
    Remove-Item -LiteralPath $raiz -Force -ErrorAction Stop
}

function Test-Plano {
    param($Plano, [string]$Condicao, [string]$ExecucaoId, [string]$Saida, [string]$ImageId)
    Assert-True ([bool]$Plano.somente_planejar) "plano não foi marcado como planejamento"
    Assert-True ([bool]$Plano.watchdog_externo) "plano deve ativar watchdog host"
    Assert-Equal ($TimeoutSegundos + 120) ([int]$Plano.watchdog_limite_segundos) `
        "limite total do watchdog"
    Assert-Equal $ImageId ([string]$Plano.imagem.id) "plano deve usar ID local"
    Assert-Equal "linux" ([string]$Plano.imagem.os) "SO do plano"
    Assert-Equal "amd64" ([string]$Plano.imagem.arquitetura) "arquitetura do plano"
    $entradaMount = @($Plano.mounts | Where-Object { $_.destino -eq "/entrada" })
    Assert-Equal 1 $entradaMount.Count "plano deve ter um mount de entrada"
    Assert-True ([bool]$entradaMount[0].somente_leitura) "entrada deve ser readonly"
    Assert-True (
        ([IO.Path]::GetFullPath([string]$entradaMount[0].origem)).Equals($Entrada, $Comparacao)
    ) "C1/C2 devem usar a mesma entrada"
    $saidaMount = @($Plano.mounts | Where-Object { $_.destino -eq "/saida" })
    Assert-Equal 1 $saidaMount.Count "plano deve ter um mount de saída"
    Assert-True (-not [bool]$saidaMount[0].somente_leitura) "saída deve ser rw"
    Assert-True (
        ([IO.Path]::GetFullPath([string]$saidaMount[0].origem)).Equals($Saida, $Comparacao)
    ) "mount de saída diverge"
    $regrasMount = @($Plano.mounts | Where-Object {
        $_.destino -eq "/opt/regras-semgrep"
    })
    Assert-Equal $(if ($Condicao -eq "C2") { 1 } else { 0 }) `
        $regrasMount.Count "mount condicional de regras"
    $argsInternos = @($Plano.executor_argumentos)
    Assert-Equal "/usr/local/bin/python" $argsInternos[0] "Python interno absoluto"
    Assert-True ($argsInternos -contains "-P") "safe path deve ser explícito"
    Assert-True ($argsInternos -contains $ExecucaoId) "execução ausente do argv"
    Assert-True (-not (@($Plano.docker_argumentos) -contains "--rm")) `
        "execução auditável não pode usar --rm"
}

function Test-HashesManifesto {
    param($Manifesto, [string]$Saida)
    $declarados = @($Manifesto.artefatos_sha256.PSObject.Properties)
    Assert-True ($declarados.Count -ge 8) "manifesto deve hashear artefatos obrigatórios"
    foreach ($propriedade in $declarados) {
        $nome = [string]$propriedade.Name
        Assert-True ($nome -match "^[A-Za-z0-9][A-Za-z0-9._-]*$") `
            "nome de artefato inseguro no manifesto"
        $caminho = Join-Path $Saida $nome
        Assert-Equal ([string]$propriedade.Value) (Get-Sha256 $caminho) `
            "hash divergente para $nome"
    }
    $presentes = @(Get-ChildItem -LiteralPath $Saida -File -Force |
        Where-Object { $_.Name -ne "manifesto.json" } |
        ForEach-Object { $_.Name } | Sort-Object)
    $esperados = @($declarados | ForEach-Object { $_.Name } | Sort-Object)
    Assert-Sequence $esperados $presentes "inventário de artefatos"
}

function Test-ContratoContainer {
    param(
        [string]$Condicao,
        [string]$ExecucaoId,
        [string]$Saida,
        [string]$ImageId
    )
    Assert-TextoMountSeguro $Saida "evidência"
    $mount = "type=bind,src=$Saida,dst=/evidencia,readonly"
    $codigo = @'
import hashlib
import sys
from pathlib import Path

from runner.adaptadores.bandit import normalizar as normalizar_bandit
from runner.adaptadores.comum import Proveniencia, carregar_json_estrito
from runner.adaptadores.semgrep import normalizar as normalizar_semgrep
from runner.modelos import Achado, ManifestoExecucao

condicao, alvo, execucao_id = sys.argv[1:4]
saida = Path('/evidencia')
bruto = (saida / 'bruto.json').read_bytes()
normalizado = carregar_json_estrito(
    (saida / 'normalizado.json').read_bytes(),
    contexto='normalizado da fumaça',
)
if not isinstance(normalizado, list):
    raise RuntimeError('normalizado da fumaça deve ser lista')
manifesto = ManifestoExecucao.from_json(
    (saida / 'manifesto.json').read_text(encoding='utf-8')
)
if manifesto.execucao_id != execucao_id or manifesto.condicao != condicao:
    raise RuntimeError('manifesto não corresponde ao caso da fumaça')
validados = [Achado.from_dict(item).to_dict() for item in normalizado]
proveniencia = Proveniencia(
    alvo=alvo,
    repeticao=1,
    execucao_id=execucao_id,
    saida_bruta_sha256=hashlib.sha256(bruto).hexdigest(),
)
normalizador = normalizar_bandit if condicao == 'C1' else normalizar_semgrep
regerados = [item.to_dict() for item in normalizador(bruto, proveniencia)]
if regerados != validados:
    raise RuntimeError('adaptador não reproduziu o normalizado persistido')
print('contrato=ok')
'@
    $linhas = Invoke-DockerCapture @(
        "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "10001:10001",
        "--workdir", "/opt/tcc", "--init", "--pids-limit", "64",
        "--memory", "512m", "--memory-swap", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m,uid=10001,gid=10001,mode=1777",
        "--env", "HOME=/tmp/tcc-home", "--env", "PYTHONNOUSERSITE=1",
        "--env", "PYTHONSAFEPATH=1", "--mount", $mount, $ImageId,
        "/usr/local/bin/python", "-P", "-c", $codigo,
        $Condicao, $Alvo, $ExecucaoId
    ) "validação de modelos e adaptador $Condicao"
    Assert-Sequence @("contrato=ok") @($linhas) `
        "validação de modelos e adaptador $Condicao"
}

function Get-AchadoPorRegra {
    param([object[]]$Achados, [string]$Regra)
    $encontrados = @($Achados | Where-Object { $_.regra -eq $Regra })
    Assert-Equal 1 $encontrados.Count "regra $Regra deve aparecer exatamente uma vez"
    return $encontrados[0]
}

function Test-CasoExecutado {
    param(
        [string]$Condicao,
        [string]$ExecucaoId,
        [string]$Saida,
        [string]$EntradaSha256,
        [string]$ImageId,
        [string]$RegrasSha256
    )
    Assert-ArvoreSemReparse $Saida "evidência da fumaça" -ExigirArquivo
    if (Test-Path -LiteralPath (Join-Path $Saida "FIXTURE_EXECUTADA")) {
        $script:FixtureExecutada = $true
        throw "fixture foi executada, não apenas analisada"
    }
    foreach ($nome in @(
        "manifesto.pendente.json", "manifesto.em_execucao.json", "manifesto.json",
        "versoes.json", "processo.json", "stdout.bin", "stderr.bin", "bruto.json",
        "normalizado.json"
    )) {
        Assert-ArquivoRegular (Join-Path $Saida $nome) $nome
    }
    Assert-Equal 0 (@(Get-ChildItem -LiteralPath $Saida -Filter "*.part" -Force).Count) `
        "não podem restar arquivos .part"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Saida "avisos.json"))) `
        "fumaça sintética não deve emitir avisos parciais"
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Saida "watchdog-host.json"))) `
        "fumaça sintética não deve acionar watchdog host"

    $pendente = Read-Json (Join-Path $Saida "manifesto.pendente.json") "manifesto pendente"
    $emExecucao = Read-Json (Join-Path $Saida "manifesto.em_execucao.json") "manifesto em execução"
    $manifesto = Read-Json (Join-Path $Saida "manifesto.json") "manifesto terminal"
    $versoes = Read-Json (Join-Path $Saida "versoes.json") "versões"
    $processo = Read-Json (Join-Path $Saida "processo.json") "processo"
    $bruto = Read-Json (Join-Path $Saida "bruto.json") "bruto"
    $normalizadoDocumento = Read-Json (Join-Path $Saida "normalizado.json") "normalizado"
    $normalizado = @($normalizadoDocumento)

    Assert-Equal "pendente" ([string]$pendente.estado) "estado inicial"
    Assert-Equal "em_execucao" ([string]$emExecucao.estado) "estado intermediário"
    Assert-Equal "concluida" ([string]$manifesto.estado) "estado terminal"
    Assert-Equal $Condicao ([string]$manifesto.condicao) "condição do manifesto"
    Assert-Equal $ExecucaoId ([string]$manifesto.execucao_id) "ID do manifesto"
    Assert-Equal $Alvo ([string]$manifesto.alvo) "alvo do manifesto"
    Assert-Equal $EntradaSha256 ([string]$manifesto.entrada_sha256) "hash da entrada"
    Assert-Equal "fumaca" ([string]$manifesto.finalidade) "finalidade"
    Assert-Equal 1 ([int]$manifesto.tentativa) "tentativa"
    Assert-Equal $Imagem ([string]$manifesto.imagem) "imagem registrada"
    Assert-Equal $ImageId ([string]$manifesto.imagem_digest) "ID registrado"
    Assert-True ($null -eq $manifesto.falha_tipo) "conclusão não pode conter falha_tipo"
    Assert-True ([double]$manifesto.duracao_monotonica_segundos -ge 0) `
        "duração terminal inválida"
    Test-HashesManifesto $manifesto $Saida
    Test-ContratoContainer $Condicao $ExecucaoId $Saida $ImageId

    Assert-Equal "3.12.13" ([string]$versoes.python) "versão Python"
    Assert-Equal "1.9.4" ([string]$versoes.bandit) "versão Bandit"
    Assert-Equal "1.172.0" ([string]$versoes.semgrep) "versão Semgrep"
    if ($Condicao -eq "C2") {
        Assert-Equal $RegrasSha256 ([string]$versoes.regras_semgrep_sha256) `
            "hash das regras Semgrep"
    }
    Assert-True (-not [bool]$processo.timeout) "scanner não pode sofrer timeout"
    Assert-Equal $TimeoutSegundos ([int]$processo.timeout_segundos) "timeout registrado"
    Assert-Equal ([int]$manifesto.codigo_saida) ([int]$processo.codigo_saida) `
        "código de saída manifesto/processo"
    Assert-True ([double]$processo.duracao_monotonica_segundos -ge 0) `
        "duração do processo inválida"

    if ($Condicao -eq "C1") {
        Assert-Sequence @(
            "/usr/local/bin/bandit", "--recursive", "/entrada", "--format", "json",
            "--output", "/saida/bruto.json.part"
        ) @($processo.comando) "vetor real do Bandit"
        Assert-Sequence @(0, 1) @($processo.codigos_saida_esperados) `
            "códigos esperados do Bandit"
    }
    else {
        Assert-Sequence @(
            "/usr/local/bin/semgrep", "scan", "--config",
            "/opt/regras-semgrep/python", "--json", "--metrics=off", "--jobs", "1",
            "--output", "/saida/bruto.json.part", "/entrada"
        ) @($processo.comando) "vetor real do Semgrep"
        Assert-Sequence @(0) @($processo.codigos_saida_esperados) `
            "códigos esperados do Semgrep"
    }

    $brutoSha = Get-Sha256 (Join-Path $Saida "bruto.json")
    Assert-Equal 0 (@($bruto.errors).Count) "bruto não deve conter erros parciais"
    Assert-Equal 3 $normalizado.Count "cada condição deve produzir exatamente três achados"
    foreach ($achado in $normalizado) {
        Assert-Equal $Condicao ([string]$achado.condicao) "condição do achado"
        Assert-Equal $ExecucaoId ([string]$achado.execucao_id) "ID do achado"
        Assert-Equal $Alvo ([string]$achado.alvo) "alvo do achado"
        Assert-Equal $brutoSha ([string]$achado.saida_bruta_sha256) "hash bruto do achado"
        Assert-Equal "alvo_vulneravel.py" ([string]$achado.arquivo) `
            "achado deve apontar para a fixture"
    }

    $regras = @($normalizado | ForEach-Object { [string]$_.regra })
    if ($Condicao -eq "C1") {
        Assert-Equal "bandit" ([string]$manifesto.ferramenta) "ferramenta C1"
        Assert-True ([int]$manifesto.codigo_saida -in @(0, 1)) "código Bandit inválido"
        Assert-Sequence @("B307", "B404", "B602") @($regras | Sort-Object) `
            "regras Bandit observadas"
        $b404 = Get-AchadoPorRegra $normalizado "B404"
        $b602 = Get-AchadoPorRegra $normalizado "B602"
        $b307 = Get-AchadoPorRegra $normalizado "B307"
        Assert-Equal 3 ([int]$b404.linha_inicial) "linha B404"
        Assert-Equal 11 ([int]$b602.linha_inicial) "linha B602"
        Assert-Equal 12 ([int]$b307.linha_inicial) "linha B307"
        foreach ($achadoBandit in @($b404, $b602, $b307)) {
            Assert-Equal "CWE-78" ([string]$achadoBandit.cwe) "CWE Bandit"
            Assert-Equal "alta" ([string]$achadoBandit.confianca) `
                "confiança Bandit"
        }
        Assert-Equal "baixa" ([string]$b404.severidade) "severidade B404"
        Assert-Equal "alta" ([string]$b602.severidade) "severidade B602"
        Assert-Equal "media" ([string]$b307.severidade) "severidade B307"
        Assert-True (@($bruto.results | Where-Object { $_.test_id -eq "B602" }).Count -gt 0) `
            "bruto Bandit não contém B602"
        Assert-True (@($bruto.results | Where-Object { $_.test_id -eq "B307" }).Count -gt 0) `
            "bruto Bandit não contém B307"
    }
    else {
        Assert-Equal "semgrep" ([string]$manifesto.ferramenta) "ferramenta C2"
        Assert-Equal 0 ([int]$manifesto.codigo_saida) "código Semgrep"
        Assert-Equal "1.172.0" ([string]$bruto.version) "versão do bruto Semgrep"
        $regraAudit = "opt.regras-semgrep.python.lang.security.audit.dangerous-subprocess-use-audit"
        $regraShell = "opt.regras-semgrep.python.lang.security.audit.subprocess-shell-true"
        $regraEval = "opt.regras-semgrep.python.lang.security.audit.eval-detected"
        Assert-Sequence @($regraAudit, $regraEval, $regraShell) `
            @($regras | Sort-Object) "regras Semgrep observadas"
        $audit = Get-AchadoPorRegra $normalizado $regraAudit
        $shell = Get-AchadoPorRegra $normalizado $regraShell
        $eval = Get-AchadoPorRegra $normalizado $regraEval
        Assert-Equal 11 ([int]$audit.linha_inicial) "linha audit subprocess"
        Assert-Equal 11 ([int]$shell.linha_inicial) "linha shell=True"
        Assert-Equal 12 ([int]$eval.linha_inicial) "linha eval"
        Assert-Equal "CWE-78" ([string]$audit.cwe) "CWE audit subprocess"
        Assert-Equal "CWE-78" ([string]$shell.cwe) "CWE shell=True"
        Assert-Equal "CWE-95" ([string]$eval.cwe) "CWE eval"
        Assert-Equal "alta" ([string]$audit.severidade) "severidade audit subprocess"
        Assert-Equal "alta" ([string]$shell.severidade) "severidade shell=True"
        Assert-Equal "media" ([string]$eval.severidade) "severidade eval"
        foreach ($achadoSemgrep in @($audit, $shell, $eval)) {
            Assert-True ($null -eq $achadoSemgrep.confianca) `
                "confiança Semgrep deve permanecer nula"
        }
    }

    return [pscustomobject]@{
        condicao = $Condicao
        execucao_id = $ExecucaoId
        estado = [string]$manifesto.estado
        codigo_saida = [int]$manifesto.codigo_saida
        achados = $normalizado.Count
        regras_observadas = @($regras | Sort-Object -Unique)
        entrada_sha256 = $EntradaSha256
        bruto_sha256 = $brutoSha
        duracao_segundos = [double]$processo.duracao_monotonica_segundos
    }
}

try {
    Assert-ArquivoRegular $Wrapper "wrapper SAST"
    Assert-ArvoreSemReparse $Entrada "fixture sintética" -ExigirArquivo
    Assert-ArquivoRegular (Join-Path $Entrada "alvo_vulneravel.py") "fixture vulnerável"
    Assert-ArquivoRegular $Lock "lock de fontes"
    Assert-TextoMountSeguro $Repo "raiz do repositório"

    $imagemInfo = Get-ImagemLocal
    $ImageId = [string]$imagemInfo.Id
    Assert-SemContainersSastResiduais
    $EntradaSha256 = Get-HashCanonicoContainer $ImageId
    $fontes = Read-Json $Lock "lock de fontes"
    $RegrasSha256 = [string]$fontes.sources.semgrep_rules.bundle_sha256
    Assert-True ($RegrasSha256 -match "^[0-9a-f]{64}$") "hash de regras inválido no lock"

    foreach ($Condicao in @("C1", "C2")) {
        $ExecucaoId = "$Condicao-$Alvo-R01"
        $Saida = [IO.Path]::GetFullPath((Join-Path $Resultados (
            Join-Path $ExecucaoId "tentativa-001"
        )))
        $parametros = @{
            Condicao = $Condicao
            ExecucaoId = $ExecucaoId
            Alvo = $Alvo
            Entrada = $Entrada
            Saida = $Saida
            EntradaSha256 = $EntradaSha256
            Finalidade = "fumaca"
            Tentativa = 1
            Imagem = $Imagem
            ImagemDigest = $ImageId
            TimeoutSegundos = $TimeoutSegundos
        }
        $planejar = @{} + $parametros
        $planejar.SomentePlanejar = $true
        $plano = Invoke-WrapperJson $planejar "planejamento $Condicao"
        Test-Plano $plano $Condicao $ExecucaoId $Saida $ImageId

        $propriedade = New-PropriedadeSaida $ExecucaoId
        $resultadoWrapper = Invoke-WrapperJson $parametros "execução $Condicao"
        Assert-Equal "concluido" ([string]$resultadoWrapper.estado) `
            "wrapper deve concluir $Condicao"
        Assert-Equal $ImageId ([string]$resultadoWrapper.imagem_id) `
            "wrapper deve registrar imagem local"
        Assert-Equal 0 ([int]$resultadoWrapper.exit_code) "exit do executor interno"
        Assert-True (-not [bool]$resultadoWrapper.oom_killed) "execução sofreu OOM"

        $caso = Test-CasoExecutado `
            -Condicao $Condicao `
            -ExecucaoId $ExecucaoId `
            -Saida $propriedade.saida `
            -EntradaSha256 $EntradaSha256 `
            -ImageId $ImageId `
            -RegrasSha256 $RegrasSha256
        $HashDepois = Get-HashCanonicoContainer $ImageId
        Assert-Equal $EntradaSha256 $HashDepois `
            "hash canônico da entrada mudou após $Condicao"
        $caso | Add-Member -NotePropertyName entrada_sha256_depois `
            -NotePropertyValue $HashDepois
        $Casos.Add($caso)
    }
    Assert-Equal 2 $Casos.Count "fumaça deve concluir C1 e C2"
    Assert-Equal $Casos[0].entrada_sha256 $Casos[1].entrada_sha256 `
        "C1 e C2 devem usar hash da mesma entrada"
}
catch {
    $ErroFinal = $_.Exception.Message
}
finally {
    foreach ($registro in @($Proprietarios)) {
        try {
            Remove-ResultadoProprio $registro
        }
        catch {
            $LimpezaErros.Add(
                "cleanup $($registro.execucao_id): $($_.Exception.Message)"
            )
        }
    }
    try {
        Assert-SemContainersSastResiduais
    }
    catch {
        $LimpezaErros.Add("contêiner residual: $($_.Exception.Message)")
    }
}

if ($LimpezaErros.Count -gt 0) {
    $limpezaTexto = $LimpezaErros -join "; "
    if ($null -eq $ErroFinal) { $ErroFinal = $limpezaTexto }
    else { $ErroFinal = "$ErroFinal; $limpezaTexto" }
}

$relatorio = [ordered]@{
    schema_version = "1.0"
    tipo = "fumaca_sintetica_sast"
    alvo = $Alvo
    imagem = $Imagem
    imagem_id = $(if (Get-Variable ImageId -ErrorAction SilentlyContinue) {
        $ImageId
    } else { $null })
    casos = @($Casos)
    quantidade_casos = $Casos.Count
    fixture_executada = $FixtureExecutada
    resultados_removidos = ($LimpezaErros.Count -eq 0)
    estado = $(if ($null -eq $ErroFinal) { "aprovado" } else { "reprovado" })
    erro = $ErroFinal
}
$relatorio | ConvertTo-Json -Depth 10 -Compress
if ($null -ne $ErroFinal) { exit 1 }
