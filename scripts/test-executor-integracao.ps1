[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Imagem = "tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0"
$InputC1 = [IO.Path]::GetFullPath((Join-Path $Repo "tests/fixtures/bandit"))
$InputC2 = [IO.Path]::GetFullPath((Join-Path $Repo "tests/fixtures/semgrep"))
$Regras = [IO.Path]::GetFullPath((Join-Path $Repo "docker/regras-semgrep"))
$BuildRoot = [IO.Path]::GetFullPath((Join-Path $Repo "build/integracao-executor"))
$ExecucaoRoot = [IO.Path]::GetFullPath(
    (Join-Path $BuildRoot ([guid]::NewGuid().ToString("N")))
)
$SaidaC1 = Join-Path $ExecucaoRoot "saida-c1"
$SaidaC2 = Join-Path $ExecucaoRoot "saida-c2"
$script:Passaram = 0
$script:Falharam = 0

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

function Test-Caso {
    param([string]$Nome, [scriptblock]$Corpo)
    try {
        & $Corpo
        $script:Passaram++
        Write-Host "PASS integração Docker: $Nome"
    }
    catch {
        $script:Falharam++
        Write-Host "FAIL integração Docker: $Nome -- $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Assert-SemReparseNosComponentes {
    param([string]$Caminho)
    $atual = [IO.Path]::GetFullPath($Caminho)
    while ($atual.StartsWith($Repo, [StringComparison]::OrdinalIgnoreCase)) {
        $item = Get-Item -LiteralPath $atual -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and
            (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "reparse point proibido na integração: $atual"
        }
        if ($atual.Equals($Repo, [StringComparison]::OrdinalIgnoreCase)) { break }
        $pai = [IO.Path]::GetDirectoryName($atual)
        if (-not $pai -or $pai.Equals($atual, [StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $atual = $pai
    }
}

function Invoke-Docker {
    param([string[]]$Argumentos, [string]$Contexto)
    $linhas = @(& docker @Argumentos 2>&1)
    $codigo = $LASTEXITCODE
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $($linhas -join ' ')"
    }
    return @($linhas | ForEach-Object { [string]$_ })
}

function New-ArgsEndurecidos {
    param([string]$Nome, [string]$Entrada, [string]$Saida)
    return @(
        "--pull", "never",
        "--name", $Nome,
        "--label", "tcc.sast.integration=t07",
        "--restart", "no",
        "--platform", "linux/amd64",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "10001:10001",
        "--workdir", "/opt/tcc",
        "--init",
        "--pids-limit", "256",
        "--memory", "3g",
        "--memory-swap", "3g",
        "--cpus", "2",
        "--stop-timeout", "5",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=1777",
        "--env", "HOME=/tmp/tcc-home",
        "--env", "PYTHONNOUSERSITE=1",
        "--env", "PYTHONSAFEPATH=1",
        "--env", "SEMGREP_ENABLE_VERSION_CHECK=0",
        "--env", "SEMGREP_SEND_METRICS=off",
        "--mount", "type=bind,src=$Entrada,dst=/entrada,readonly",
        "--mount", "type=bind,src=$Saida,dst=/saida"
    )
}

function Invoke-RuntimeProbe {
    param(
        [ValidateSet("C1", "C2")][string]$Condicao,
        [string]$Entrada,
        [string]$Saida,
        [string]$ImageId
    )
    $nome = "tcc-sast-probe-$($Condicao.ToLowerInvariant())-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
    $args = [System.Collections.Generic.List[string]]::new()
    $args.Add("run")
    foreach ($arg in (New-ArgsEndurecidos -Nome $nome -Entrada $Entrada -Saida $Saida)) {
        $args.Add([string]$arg)
    }
    if ($Condicao -eq "C2") {
        $args.Add("--mount")
        $args.Add("type=bind,src=$Regras,dst=/opt/regras-semgrep,readonly")
    }
    $args.Add("--rm")
    $args.Add($ImageId)
    $args.Add("/usr/local/bin/python")
    $args.Add("-P")
    $args.Add("-c")
    $regrasExpr = if ($Condicao -eq "C2") {
        "Path('/opt/regras-semgrep')"
    }
    else { "None" }
    $codigo = @"
import json, os
from pathlib import Path
from runner.executor_sast import ConfiguracaoExecucao, _ler_mounts, _obter_versoes, _validar_ambiente, _verificar_regras
c = ConfiguracaoExecucao(condicao='$Condicao', execucao_id='$Condicao-PROBE-R01', alvo='PROBE', entrada_commit=None, entrada_sha256='0'*64, finalidade='fumaca', tentativa=1, imagem='$Imagem', imagem_digest='$ImageId', timeout_segundos=30, regras_dir=$regrasExpr)
_validar_ambiente(c)
m = _ler_mounts()
doc = {'uid': os.getuid(), 'gid': os.getgid(), 'interfaces': sorted(p.name for p in Path('/sys/class/net').iterdir() if p.is_dir()), 'root_opcoes': sorted(m[Path('/')]), 'tmp_opcoes': sorted(m[Path('/tmp')]), 'entrada_opcoes': sorted(m[Path('/entrada')]), 'saida_opcoes': sorted(m[Path('/saida')]), 'regras_presente': Path('/opt/regras-semgrep').exists(), 'versoes': _obter_versoes(c)}
if '$Condicao' == 'C2': doc['regras_sha256'] = _verificar_regras(c); doc['regras_opcoes'] = sorted(m[Path('/opt/regras-semgrep')])
print(json.dumps(doc, sort_keys=True))
"@
    $args.Add($codigo)
    $linhas = @(Invoke-Docker -Argumentos @($args) -Contexto "probe runtime $Condicao")
    try {
        return (($linhas -join [Environment]::NewLine) |
            ConvertFrom-Json -ErrorAction Stop)
    }
    catch {
        throw "probe runtime $Condicao não retornou JSON válido: $($linhas -join ' ')"
    }
}

if ($Repo.Contains(",") -or $Repo.Contains("`r") -or $Repo.Contains("`n")) {
    throw "raiz do repositório contém delimitador incompatível com mount"
}
foreach ($caminho in @($InputC1, $InputC2, $Regras)) {
    if (-not (Test-Path -LiteralPath $caminho -PathType Container)) {
        throw "pré-requisito da integração ausente: $caminho"
    }
    Assert-SemReparseNosComponentes -Caminho $caminho
}
if (-not $ExecucaoRoot.StartsWith(
    $BuildRoot + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "diretório temporário da integração escapou de build/"
}

Assert-SemReparseNosComponentes -Caminho $ExecucaoRoot
New-Item -ItemType Directory -Path $SaidaC1 -Force | Out-Null
New-Item -ItemType Directory -Path $SaidaC2 -Force | Out-Null
Assert-SemReparseNosComponentes -Caminho $ExecucaoRoot
$containerRecursos = $null
$ImageId = $null
try {
    $imagemJson = (Invoke-Docker -Argumentos @(
        "image", "inspect", "--format", "{{json .}}", $Imagem
    ) -Contexto "inspect da imagem") -join [Environment]::NewLine
    $imagemInfo = $imagemJson | ConvertFrom-Json
    $ImageId = [string]$imagemInfo.Id

    Test-Caso "imagem local é ID SHA-256 linux/amd64" {
        Assert-True ($ImageId -match "^sha256:[0-9a-f]{64}$") "ID local inválido"
        Assert-Equal "linux" ([string]$imagemInfo.Os) "SO da imagem"
        Assert-Equal "amd64" ([string]$imagemInfo.Architecture) "arquitetura da imagem"
    }

    $probeC1 = Invoke-RuntimeProbe -Condicao C1 -Entrada $InputC1 -Saida $SaidaC1 -ImageId $ImageId
    Test-Caso "C1 aplica UID/GID e rede none no runtime real" {
        Assert-Equal 10001 ([int]$probeC1.uid) "UID C1"
        Assert-Equal 10001 ([int]$probeC1.gid) "GID C1"
        Assert-Equal "lo" ([string]($probeC1.interfaces -join ",")) "interfaces C1"
    }
    Test-Caso "C1 usa root ro, tmpfs rw, entrada ro e saída rw" {
        Assert-True (@($probeC1.root_opcoes) -contains "ro") "rootfs C1 não é ro"
        Assert-True (@($probeC1.tmp_opcoes) -contains "rw") "/tmp C1 não é rw"
        Assert-True (@($probeC1.entrada_opcoes) -contains "ro") "/entrada C1 não é ro"
        Assert-True (@($probeC1.saida_opcoes) -contains "rw") "/saida C1 não é rw"
        Assert-True (-not [bool]$probeC1.regras_presente) "C1 recebeu regras Semgrep"
    }
    Test-Caso "imagem contém somente versões fixadas dos analisadores" {
        Assert-Equal "3.12.13" ([string]$probeC1.versoes.python) "Python"
        Assert-Equal "1.9.4" ([string]$probeC1.versoes.bandit) "Bandit"
        Assert-Equal "1.172.0" ([string]$probeC1.versoes.semgrep) "Semgrep"
    }

    $probeC2 = Invoke-RuntimeProbe -Condicao C2 -Entrada $InputC2 -Saida $SaidaC2 -ImageId $ImageId
    Test-Caso "C2 monta regras somente leitura e passa validação de ambiente" {
        Assert-True ([bool]$probeC2.regras_presente) "C2 não recebeu regras"
        Assert-True (@($probeC2.regras_opcoes) -contains "ro") "regras C2 não são ro"
        Assert-Equal "lo" ([string]($probeC2.interfaces -join ",")) "interfaces C2"
    }
    Test-Caso "C2 comprova o hash canônico fixado das regras" {
        Assert-Equal "29eb41850a07fee98955446524423ddd9e9f5040cbf7e301788b791386ee8309" ([string]$probeC2.regras_sha256) "hash das regras"
    }

    $containerRecursos = "tcc-sast-probe-recursos-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
    $argsRecursos = [System.Collections.Generic.List[string]]::new()
    $argsRecursos.Add("run")
    $argsRecursos.Add("--detach")
    foreach ($arg in (New-ArgsEndurecidos -Nome $containerRecursos -Entrada $InputC1 -Saida $SaidaC1)) {
        $argsRecursos.Add([string]$arg)
    }
    $argsRecursos.Add($ImageId)
    $argsRecursos.Add("/usr/local/bin/python")
    $argsRecursos.Add("-P")
    $argsRecursos.Add("-c")
    $argsRecursos.Add("import time; time.sleep(30)")
    Invoke-Docker -Argumentos @($argsRecursos) -Contexto "container de inspeção de recursos" | Out-Null
    $inspectTexto = (Invoke-Docker -Argumentos @(
        "container", "inspect", "--format", "{{json .}}", $containerRecursos
    ) -Contexto "inspect de recursos") -join [Environment]::NewLine
    $containerInfo = $inspectTexto | ConvertFrom-Json

    Test-Caso "Docker aplica capabilities, no-new-privileges e rootfs ro" {
        Assert-True ([bool]$containerInfo.HostConfig.ReadonlyRootfs) "ReadonlyRootfs=false"
        Assert-True (@($containerInfo.HostConfig.CapDrop) -contains "ALL") "CapDrop ALL ausente"
        Assert-True (@($containerInfo.HostConfig.SecurityOpt) -contains "no-new-privileges") "no-new-privileges ausente"
        Assert-Equal "none" ([string]$containerInfo.HostConfig.NetworkMode) "NetworkMode"
    }
    Test-Caso "Docker aplica limites reais de PIDs, memória e CPU" {
        Assert-Equal 256 ([int64]$containerInfo.HostConfig.PidsLimit) "PidsLimit"
        Assert-Equal 3221225472 ([int64]$containerInfo.HostConfig.Memory) "Memory"
        Assert-Equal 3221225472 ([int64]$containerInfo.HostConfig.MemorySwap) "MemorySwap"
        Assert-Equal 2000000000 ([int64]$containerInfo.HostConfig.NanoCpus) "NanoCpus"
    }
}
finally {
    if ($containerRecursos) {
        $existente = @(& docker container inspect --format "{{json .}}" $containerRecursos 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $info = (($existente | ForEach-Object { [string]$_ }) -join [Environment]::NewLine) | ConvertFrom-Json
            $nome = ([string]$info.Name).TrimStart("/")
            $rotulo = [string]$info.Config.Labels.'tcc.sast.integration'
            if ($nome -eq $containerRecursos -and $rotulo -eq "t07" -and
                ($null -eq $ImageId -or [string]$info.Image -eq $ImageId)) {
                if ([bool]$info.State.Running) {
                    & docker container stop --time 1 ([string]$info.Id) 2>&1 | Out-Null
                }
                & docker container rm ([string]$info.Id) 2>&1 | Out-Null
            }
        }
    }
    $resolvido = [IO.Path]::GetFullPath($ExecucaoRoot)
    if ($resolvido.StartsWith(
        $BuildRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    ) -and (Test-Path -LiteralPath $resolvido)) {
        Assert-SemReparseNosComponentes -Caminho $resolvido
        Remove-Item -LiteralPath $resolvido -Recurse -Force
    }
}

Write-Host "$script:Passaram teste(s) de integração passaram; $script:Falharam falharam."
if ($script:Falharam -ne 0) { exit 1 }
