[CmdletBinding()]
param(
    [string]$Configuracao = "evidencias/coleta-c1-c2/configuracao.json",
    [switch]$SomentePlanejar,
    [switch]$RetomarOrfa
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$ConfigRoot = Join-Path $Repo "config"
$CorpusRoot = Join-Path $Repo "alvos/corpus-v1"
$AreasRoot = Join-Path $Repo "alvos/execucoes"
$ExecucoesRoot = Join-Path $Repo "execucoes"
$ResultadosRoot = Join-Path $Repo "resultados"
$InventariosRoot = Join-Path $Repo "evidencias/corpus-realvuln-v1"
$EvidenciasRoot = Join-Path $Repo "evidencias/coleta-c1-c2"
$ManifestosRoot = Join-Path $EvidenciasRoot "manifestos"
$FilaHost = Join-Path $ExecucoesRoot "fila-c1-c2.json"
$FilaLock = Join-Path $ConfigRoot "fila-c1-c2.lock.json"
$CorpusLock = Join-Path $ConfigRoot "corpus-realvuln-v1.lock.json"
$Politica = Join-Path $ConfigRoot "politica-sanitizacao-v1.json"
$RegrasRoot = Join-Path $Repo "docker/regras-semgrep"
$RiscoM2 = Join-Path $ConfigRoot "host-risk-waiver-m2.json"
$Wrapper = Join-Path $PSScriptRoot "executar-sast.ps1"

function Invoke-JsonCommand {
    param([string]$Programa, [string[]]$Argumentos, [string]$Contexto)
    $linhas = @(& $Programa @Argumentos 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "$Contexto falhou (código $LASTEXITCODE): $($linhas -join ' ')"
    }
    try {
        return (($linhas | ForEach-Object { [string]$_ }) -join "`n") |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch { throw "$Contexto não retornou JSON válido" }
}

function Invoke-ComposePython {
    param([string[]]$Argumentos, [string]$Contexto)
    $dockerArgs = @(
        "compose", "run", "--rm", "controlador", "python"
    ) + $Argumentos
    return Invoke-JsonCommand -Programa "docker" -Argumentos $dockerArgs -Contexto $Contexto
}

function Invoke-ImagemPython {
    param(
        [string[]]$Argumentos,
        [string[]]$Mounts,
        [string]$Contexto,
        [string]$ImageId
    )
    $dockerArgs = [Collections.Generic.List[string]]::new()
    foreach ($arg in @(
        "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "10001:10001",
        "--workdir", "/opt/tcc", "--init", "--pids-limit", "64",
        "--memory", "512m", "--memory-swap", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m,uid=10001,gid=10001,mode=1777",
        "--env", "HOME=/tmp/tcc-home", "--env", "PYTHONNOUSERSITE=1",
        "--env", "PYTHONSAFEPATH=1"
    )) { $dockerArgs.Add($arg) }
    foreach ($mount in $Mounts) { $dockerArgs.Add("--mount"); $dockerArgs.Add($mount) }
    $dockerArgs.Add($ImageId)
    $dockerArgs.Add("python")
    foreach ($arg in $Argumentos) { $dockerArgs.Add($arg) }
    return Invoke-JsonCommand "docker" @($dockerArgs) $Contexto
}

function Get-CanonicalJsonHash {
    param([string]$Arquivo, [string]$ImageId)
    $pai = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Arquivo))
    $nome = [IO.Path]::GetFileName($Arquivo)
    $resultado = Invoke-ImagemPython @(
        "-m", "runner.coleta", "hash-json", "--arquivo", "/dados/$nome"
    ) @("type=bind,src=$pai,dst=/dados,readonly") "hash canônico de $nome" $ImageId
    return [string]$resultado.sha256
}

function Assert-Freeze {
    param($Config)
    $head = (& git -C $Repo rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne [string]$Config.controlador_commit) {
        throw "commit do controlador diverge da configuração congelada"
    }
    & git -C $Repo diff --quiet --exit-code
    if ($LASTEXITCODE -ne 0) { throw "worktree rastreado foi alterado depois do freeze" }
    & git -C $Repo diff --cached --quiet --exit-code
    if ($LASTEXITCODE -ne 0) { throw "index Git foi alterado depois do freeze" }

    $imagem = Invoke-JsonCommand "docker" @(
        "image", "inspect", "--format", "{{json .}}", [string]$Config.imagem.tag
    ) "inspeção da imagem congelada"
    if ([string]$imagem.Id -ne [string]$Config.imagem.id -or
        [string]$imagem.Os -ne "linux" -or [string]$imagem.Architecture -ne "amd64") {
        throw "imagem local diverge da configuração congelada"
    }
    foreach ($entrada in @(
        @($CorpusLock, "corpus_lock_sha256"),
        @($FilaLock, "fila_lock_sha256"),
        @($Politica, "politica_sha256"),
        @($RiscoM2, "host_risk_decision_sha256")
    )) {
        $observado = Get-CanonicalJsonHash $entrada[0] ([string]$Config.imagem.id)
        if ($observado -ne [string]$Config.hashes.($entrada[1])) {
            throw "$($entrada[1]) diverge da configuração congelada"
        }
    }
    if (-not (Test-Path -LiteralPath $RegrasRoot -PathType Container)) {
        throw "bundle local de regras Semgrep está ausente"
    }
    $codigoHash = "from runner.aquisicao import calcular_sha256_arvore; import json; print(json.dumps({'sha256': calcular_sha256_arvore('/regras')}, separators=(',', ':')))"
    $regras = Invoke-ImagemPython -Argumentos @("-c", $codigoHash) -Mounts @(
        "type=bind,src=$RegrasRoot,dst=/regras,readonly"
    ) -Contexto "hash do bundle de regras" -ImageId ([string]$Config.imagem.id)
    if ([string]$regras.sha256 -ne [string]$Config.hashes.regras_bundle_sha256) {
        throw "bundle de regras diverge da configuração congelada"
    }
}

function Invoke-Fila {
    param([string[]]$Comando, [string]$ConfigHash, [string]$ImageId)
    $argumentosFila = @(
        "-m", "runner.fila", "--estado", "/estado/fila-c1-c2.json",
        "--fila-lock", "/config/fila-c1-c2.lock.json",
        "--corpus-lock", "/config/corpus-realvuln-v1.lock.json",
        "--configuracao-sha256", $ConfigHash
    ) + $Comando
    return Invoke-ImagemPython -Argumentos $argumentosFila -Mounts @(
        "type=bind,src=$ExecucoesRoot,dst=/estado",
        "type=bind,src=$ConfigRoot,dst=/config,readonly"
    ) -Contexto "operação da fila" -ImageId $ImageId
}

if ($SomentePlanejar) {
    $plano = Invoke-JsonCommand "docker" @(
        "compose", "run", "--rm", "controlador", "python", "-m", "runner.coleta",
        "plano-seco", "--fila-lock", "/workspace/config/fila-c1-c2.lock.json",
        "--corpus-lock", "/workspace/config/corpus-realvuln-v1.lock.json",
        "--inventarios-dir", "/workspace/evidencias/corpus-realvuln-v1"
    ) "plano seco da coleta"
    $plano | ConvertTo-Json -Depth 8 -Compress
    return
}

$ConfigPath = if ([IO.Path]::IsPathRooted($Configuracao)) {
    [IO.Path]::GetFullPath($Configuracao)
} else { [IO.Path]::GetFullPath((Join-Path $Repo $Configuracao)) }
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "configuração congelada ausente: $ConfigPath"
}
$Config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 |
    ConvertFrom-Json -ErrorAction Stop
if ([string]$Config.schema_version -ne "1.0" -or
    [string]$Config.tipo -ne "configuracao-coleta-c1-c2" -or
    [string]$Config.imagem.id -notmatch "^sha256:[0-9a-f]{64}$" -or
    [int]$Config.timeout_segundos -lt 1) {
    throw "configuração congelada possui identidade ou valores inválidos"
}
$ImageId = [string]$Config.imagem.id
Assert-Freeze $Config
$ConfigHash = Get-CanonicalJsonHash $ConfigPath $ImageId

foreach ($diretorio in @($AreasRoot, $ExecucoesRoot, $ManifestosRoot)) {
    if (-not (Test-Path -LiteralPath $diretorio)) {
        New-Item -ItemType Directory -Path $diretorio -ErrorAction Stop | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $FilaHost)) {
    Invoke-Fila @("inicializar") $ConfigHash $ImageId | Out-Null
    $filaInicial = Join-Path $EvidenciasRoot "fila-inicial.json"
    if (Test-Path -LiteralPath $filaInicial) { throw "fila inicial de evidência já existe" }
    Copy-Item -LiteralPath $FilaHost -Destination $filaInicial -ErrorAction Stop
}

$runtime = Get-Content -LiteralPath $FilaHost -Raw -Encoding UTF8 | ConvertFrom-Json
$ativa = @($runtime.itens | Where-Object { $_.estado -eq "em_execucao" })
if ($ativa.Count -gt 0) {
    if (-not $RetomarOrfa) {
        throw "fila possui tentativa órfã; use -RetomarOrfa depois de auditar a interrupção"
    }
    $item = $ativa[0]
    $areaAntiga = Join-Path $AreasRoot ("{0}-T{1:D3}" -f $item.execucao_id, [int]$item.tentativa)
    if (Test-Path -LiteralPath $areaAntiga) {
        Invoke-ImagemPython @(
            "-m", "runner.coleta", "limpar-area", "--caminho", "/areas/$($item.execucao_id)-T$("{0:D3}" -f [int]$item.tentativa)",
            "--execucao-id", [string]$item.execucao_id, "--tentativa", [string]$item.tentativa
        ) @("type=bind,src=$AreasRoot,dst=/areas") "limpeza da área órfã" $ImageId | Out-Null
    }
    Invoke-Fila @(
        "retomar-orfa", "--execucao-id", [string]$item.execucao_id,
        "--tentativa", [string]$item.tentativa
    ) $ConfigHash $ImageId | Out-Null
}

while ($true) {
    Assert-Freeze $Config
    $claim = Invoke-Fila @("claim") $ConfigHash $ImageId
    if ($null -eq $claim) { break }
    $execucaoId = [string]$claim.execucao_id
    $alvo = [string]$claim.alvo
    $condicao = [string]$claim.condicao
    $tentativa = [int]$claim.tentativa
    $numero = "{0:D3}" -f $tentativa
    $areaNome = "$execucaoId-T$numero"
    $areaHost = Join-Path $AreasRoot $areaNome
    $saidaRelativa = "resultados/$execucaoId/tentativa-$numero"
    $saidaHost = Join-Path $Repo $saidaRelativa
    $manifestoHost = Join-Path $saidaHost "manifesto.json"
    $corpusAlvo = Join-Path $CorpusRoot $alvo
    $inventarioHost = Join-Path $InventariosRoot "$alvo-inventario.json"
    $entradaCorpus = $Config.corpus.alvos | Where-Object { $_.alvo -eq $alvo }
    if ($null -eq $entradaCorpus) { throw "configuração não contém $alvo" }
    $terminal = $false
    try {
        Invoke-ImagemPython @(
            "-m", "runner.coleta", "preparar", "--origem", "/origem",
            "--destino", "/areas/$areaNome", "--inventario", "/inventario.json"
        ) @(
            "type=bind,src=$corpusAlvo,dst=/origem,readonly",
            "type=bind,src=$AreasRoot,dst=/areas",
            "type=bind,src=$inventarioHost,dst=/inventario.json,readonly"
        ) "preparação de $execucaoId" $ImageId | Out-Null

        $erroWrapper = $null
        try {
            & $Wrapper -Condicao $condicao -ExecucaoId $execucaoId -Alvo $alvo `
                -Entrada $areaHost -Saida $saidaHost `
                -EntradaCommit ([string]$entradaCorpus.commit) `
                -EntradaSha256 ([string]$entradaCorpus.entrada_sha256) `
                -Finalidade coleta -Tentativa $tentativa `
                -Imagem ([string]$Config.imagem.tag) -ImagemDigest $ImageId `
                -TimeoutSegundos ([int]$Config.timeout_segundos) | Out-Null
        }
        catch { $erroWrapper = $_ }
        if (-not (Test-Path -LiteralPath $manifestoHost -PathType Leaf)) {
            if ($null -ne $erroWrapper) { throw $erroWrapper }
            throw "wrapper não produziu manifesto terminal para $execucaoId"
        }

        $recibo = Invoke-ImagemPython @(
            "-m", "runner.coleta", "validar-manifesto", "--manifesto", "/saida/manifesto.json",
            "--execucao-id", $execucaoId, "--alvo", $alvo, "--condicao", $condicao,
            "--tentativa", [string]$tentativa, "--entrada-commit", [string]$entradaCorpus.commit,
            "--entrada-sha256", [string]$entradaCorpus.entrada_sha256,
            "--imagem", [string]$Config.imagem.tag, "--imagem-digest", $ImageId
        ) @("type=bind,src=$saidaHost,dst=/saida,readonly") "auditoria de $execucaoId" $ImageId

        $evidenciaNome = "$execucaoId-T$numero.json"
        Invoke-ImagemPython @(
            "-m", "runner.coleta", "copiar-evidencia", "--origem", "/saida/manifesto.json",
            "--destino", "/evidencia/$evidenciaNome"
        ) @(
            "type=bind,src=$saidaHost,dst=/saida,readonly",
            "type=bind,src=$ManifestosRoot,dst=/evidencia"
        ) "cópia de evidência de $execucaoId" $ImageId | Out-Null

        $filaArgs = @(
            "finalizar", "--execucao-id", $execucaoId, "--tentativa", [string]$tentativa,
            "--resultado", [string]$recibo.estado,
            "--manifesto-relativo", "$saidaRelativa/manifesto.json"
        )
        if ($recibo.estado -eq "falha") { $filaArgs += @("--falha-tipo", [string]$recibo.falha_tipo) }
        Invoke-Fila $filaArgs $ConfigHash $ImageId | Out-Null
        $terminal = $true
    }
    finally {
        if (Test-Path -LiteralPath $areaHost) {
            Invoke-ImagemPython @(
                "-m", "runner.coleta", "limpar-area", "--caminho", "/areas/$areaNome",
                "--execucao-id", $execucaoId, "--tentativa", [string]$tentativa
            ) @("type=bind,src=$AreasRoot,dst=/areas") "limpeza de $execucaoId" $ImageId | Out-Null
        }
    }
    if (-not $terminal) { throw "$execucaoId ficou órfã; preserve a saída e retome explicitamente" }
}

$resumo = Invoke-ImagemPython @(
    "-m", "runner.coleta", "resumir", "--fila", "/estado/fila-c1-c2.json"
) @("type=bind,src=$ExecucoesRoot,dst=/estado,readonly") "resumo da coleta" $ImageId
$resumo | ConvertTo-Json -Depth 8 -Compress
