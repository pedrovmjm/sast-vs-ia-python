[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("C1", "C2")]
    [string]$Condicao,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    [string]$ExecucaoId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    [string]$Alvo,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Entrada,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Saida,

    [ValidatePattern("^[0-9a-f]{40}$")]
    [string]$EntradaCommit,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[0-9a-f]{64}$")]
    [string]$EntradaSha256,

    [Parameter(Mandatory = $true)]
    [ValidateSet("coleta", "piloto", "fumaca")]
    [string]$Finalidade,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$Tentativa,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Imagem,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^sha256:[0-9a-f]{64}$")]
    [string]$ImagemDigest,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 86400)]
    [int]$TimeoutSegundos,

    [switch]$SomentePlanejar
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$AlvosRoot = [System.IO.Path]::GetFullPath((Join-Path $Repo "alvos"))
$FixtureRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $Repo "tests/fixtures/alvo-sintetico")
)
$ResultadosRoot = [System.IO.Path]::GetFullPath((Join-Path $Repo "resultados"))
$RegrasRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $Repo "docker/regras-semgrep")
)
$RegrasPython = [System.IO.Path]::GetFullPath((Join-Path $RegrasRoot "python"))
$ComparacaoPath = [System.StringComparison]::OrdinalIgnoreCase

function Assert-TextoSeguro {
    param(
        [Parameter(Mandatory = $true)][string]$Valor,
        [Parameter(Mandatory = $true)][string]$Campo,
        [switch]$PermitirDoisPontos,
        [switch]$PermitirBarra
    )

    if (-not $Valor -or $Valor.IndexOf([char]0) -ge 0 -or
        $Valor.Contains("`r") -or $Valor.Contains("`n")) {
        throw "$Campo contém caractere CR, LF ou NUL proibido"
    }
    if ($Valor.Contains(",")) {
        throw "$Campo contém vírgula proibida em argumento de mount"
    }
}

function ConvertTo-PathAbsoluto {
    param([string]$Valor, [string]$Campo)
    Assert-TextoSeguro -Valor $Valor -Campo $Campo
    try {
        if ([System.IO.Path]::IsPathRooted($Valor)) {
            $full = [System.IO.Path]::GetFullPath($Valor)
        }
        else {
            $full = [System.IO.Path]::GetFullPath((Join-Path $Repo $Valor))
        }
    }
    catch {
        throw "$Campo não é caminho válido: $($_.Exception.Message)"
    }
    Assert-TextoSeguro -Valor $full -Campo $Campo
    return $full.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Test-PathDentro {
    param(
        [string]$Caminho,
        [string]$Raiz,
        [bool]$PermitirRaiz = $true
    )
    $raizLimpa = $Raiz.TrimEnd("\", "/")
    if ($Caminho.Equals($raizLimpa, $ComparacaoPath)) {
        return $PermitirRaiz
    }
    $prefixo = $raizLimpa + [System.IO.Path]::DirectorySeparatorChar
    return $Caminho.StartsWith($prefixo, $ComparacaoPath)
}

function Test-PathsSobrepostos {
    param([string]$Primeiro, [string]$Segundo)
    return (Test-PathDentro $Primeiro $Segundo $true) -or
        (Test-PathDentro $Segundo $Primeiro $true)
}

function Assert-SemReparseNosComponentes {
    param([string]$Caminho, [string]$Campo)

    $atual = $Caminho
    while ($atual -and (Test-PathDentro $atual $Repo $true)) {
        $item = Get-Item -LiteralPath $atual -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and
            (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "$Campo contém reparse point proibido: $atual"
        }
        if ($atual.Equals($Repo, $ComparacaoPath)) { break }
        $pai = [System.IO.Path]::GetDirectoryName($atual)
        if (-not $pai -or $pai.Equals($atual, $ComparacaoPath)) { break }
        $atual = $pai.TrimEnd("\", "/")
    }
}

function Assert-ArvoreRegular {
    param(
        [string]$Caminho,
        [string]$Campo,
        [switch]$ExigirArquivo
    )

    Assert-SemReparseNosComponentes -Caminho $Caminho -Campo $Campo
    $raiz = Get-Item -LiteralPath $Caminho -Force -ErrorAction Stop
    if (-not $raiz.PSIsContainer) {
        throw "$Campo deve ser diretório"
    }

    $arquivos = 0
    $pendentes = [System.Collections.Generic.Stack[System.IO.DirectoryInfo]]::new()
    $pendentes.Push([System.IO.DirectoryInfo]$raiz)
    while ($pendentes.Count -gt 0) {
        $diretorio = $pendentes.Pop()
        foreach ($item in $diretorio.GetFileSystemInfos()) {
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "$Campo contém reparse point proibido: $($item.FullName)"
            }
            if ($item -is [System.IO.DirectoryInfo]) {
                $pendentes.Push($item)
            }
            elseif ($item -is [System.IO.FileInfo]) {
                $arquivos++
            }
            else {
                throw "$Campo contém entrada que não é arquivo regular"
            }
        }
    }
    if ($ExigirArquivo -and $arquivos -eq 0) {
        throw "$Campo deve conter ao menos um arquivo regular"
    }
}

function Assert-SaidaNovaOuVazia {
    param([string]$Caminho)
    Assert-SemReparseNosComponentes -Caminho $Caminho -Campo "saída"
    if (-not (Test-Path -LiteralPath $Caminho)) { return }
    $item = Get-Item -LiteralPath $Caminho -Force
    if (-not $item.PSIsContainer) { throw "saída deve ser diretório" }
    if ($item.GetFileSystemInfos().Count -ne 0) {
        throw "saída deve ser nova ou vazia; artefatos anteriores não serão sobrescritos"
    }
}

function Invoke-DockerJson {
    param([string[]]$Argumentos, [string]$Contexto)
    $linhas = @(& docker @Argumentos 2>&1)
    $codigo = $LASTEXITCODE
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $(($linhas | ForEach-Object { [string]$_ }) -join ' ')"
    }
    $texto = ($linhas | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    try {
        return $texto | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "$Contexto não retornou JSON válido"
    }
}

function Get-ContainerInfo {
    param([string]$Nome, [switch]$PermitirAusente)
    $argsInspect = @("container", "inspect", "--format", "{{json .}}", $Nome)
    $linhas = @(& docker @argsInspect 2>&1)
    $codigo = $LASTEXITCODE
    if ($codigo -ne 0) {
        if ($PermitirAusente) { return $null }
        throw "docker container inspect falhou para o contêiner exclusivo $Nome"
    }
    $texto = ($linhas | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    try {
        return $texto | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "docker container inspect não retornou JSON válido"
    }
}

function Assert-ContainerNomeAusente {
    param([string]$Nome)
    $argsLista = @(
        "container", "ls", "--all", "--quiet",
        "--filter", "name=^/$Nome$"
    )
    $linhas = @(& docker @argsLista 2>&1)
    $codigo = $LASTEXITCODE
    if ($codigo -ne 0) {
        throw "precheck do nome exclusivo do contêiner falhou (código $codigo)"
    }
    $ids = @($linhas | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($ids.Count -ne 0) {
        throw "nome exclusivo do contêiner já existe: $Nome"
    }
}

function Get-MutexNome {
    param([string]$Raiz)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Raiz.ToLowerInvariant())
        $hash = $sha.ComputeHash($bytes)
    }
    finally {
        $sha.Dispose()
    }
    $sufixo = ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
    return "TccSastExecutor-$($sufixo.Substring(0, 24))"
}

function Invoke-DockerRunLimitado {
    param(
        [string[]]$Argumentos,
        [int]$LimiteSegundos
    )

    $comandoDocker = Get-Command docker -ErrorAction Stop
    if ($comandoDocker.CommandType -eq [System.Management.Automation.CommandTypes]::Function) {
        $linhas = @(& docker @Argumentos 2>&1)
        return [pscustomobject]@{
            codigo = $LASTEXITCODE
            saida = @($linhas | ForEach-Object { [string]$_ })
            watchdog = $false
        }
    }

    $argumentoUnico = ,([string[]]$Argumentos)
    $job = Start-Job -ArgumentList $argumentoUnico -ScriptBlock {
        param([string[]]$DockerArgumentos)
        $linhas = @(& docker @DockerArgumentos 2>&1)
        [pscustomobject]@{
            marcador = "tcc-docker-run"
            codigo = $LASTEXITCODE
            saida = @($linhas | ForEach-Object { [string]$_ })
        }
    }
    try {
        $concluido = Wait-Job -Job $job -Timeout $LimiteSegundos
        if ($null -eq $concluido) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            return [pscustomobject]@{
                codigo = $null
                saida = @()
                watchdog = $true
            }
        }
        $recebidos = @(Receive-Job -Job $job -ErrorAction Stop)
        $registro = @($recebidos | Where-Object {
            $_.PSObject.Properties.Name -contains "marcador" -and
            $_.marcador -eq "tcc-docker-run"
        }) | Select-Object -Last 1
        if ($null -eq $registro) {
            throw "job do docker run não retornou registro de conclusão"
        }
        return [pscustomobject]@{
            codigo = [int]$registro.codigo
            saida = @($registro.saida | ForEach-Object { [string]$_ })
            watchdog = $false
        }
    }
    finally {
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}

function Write-WatchdogArtifact {
    param(
        [string]$Saida,
        [string]$Execucao,
        [int]$TentativaNumero,
        [int]$LimiteSegundos,
        [string]$ContainerNome,
        [string]$ContainerId,
        [string]$ImageId
    )

    $destino = Join-Path $Saida "watchdog-host.json"
    $temporario = "$destino.tmp"
    if ((Test-Path -LiteralPath $destino) -or (Test-Path -LiteralPath $temporario)) {
        throw "artefato do watchdog já existe e não será sobrescrito"
    }
    $documento = [ordered]@{
        schema_version = "1.0"
        execucao_id = $Execucao
        tentativa = $TentativaNumero
        estado = "falha"
        falha_tipo = "interrompida"
        motivo = "watchdog externo excedeu o limite total do contêiner"
        limite_total_segundos = $LimiteSegundos
        ocorrido_utc = [DateTime]::UtcNow.ToString(
            "yyyy-MM-ddTHH:mm:ss.ffffffZ",
            [Globalization.CultureInfo]::InvariantCulture
        )
        container_nome = $ContainerNome
        container_id = $ContainerId
        imagem_id = $ImageId
    }
    $json = $documento | ConvertTo-Json -Depth 5 -Compress
    $utf8 = [Text.UTF8Encoding]::new($false)
    $arquivo = [IO.FileStream]::new(
        $temporario,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None,
        4096,
        [IO.FileOptions]::WriteThrough
    )
    try {
        $bytes = $utf8.GetBytes($json)
        $arquivo.Write($bytes, 0, $bytes.Length)
        $arquivo.Flush($true)
    }
    finally {
        $arquivo.Dispose()
    }
    Move-Item -LiteralPath $temporario -Destination $destino -ErrorAction Stop
}

function Test-ContainerProprio {
    param($Info, [string]$Nome, [string]$Token, [string]$ImageId)
    if ($null -eq $Info) { return $false }
    try {
        $nomeObservado = ([string]$Info.Name).TrimStart("/")
        $tokenObservado = [string]$Info.Config.Labels.'tcc.sast.owner'
        $imagemConfigurada = [string]$Info.Config.Image
        $imagemEfetiva = [string]$Info.Image
        return $nomeObservado -eq $Nome -and
            $tokenObservado -eq $Token -and
            $imagemConfigurada -eq $ImageId -and
            $imagemEfetiva -eq $ImageId
    }
    catch {
        return $false
    }
}

Assert-TextoSeguro -Valor $Repo -Campo "raiz do repositório"
Assert-TextoSeguro -Valor $Imagem -Campo "imagem"
if ($Imagem -notmatch "^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$") {
    throw "imagem deve ser referência local simples e segura"
}

$execucaoEsperada = "$Condicao-$Alvo-R01"
if ($ExecucaoId -ne $execucaoEsperada) {
    throw "execucao_id deve ser exatamente $execucaoEsperada para C1/C2"
}

$EntradaFull = ConvertTo-PathAbsoluto -Valor $Entrada -Campo "entrada"
$SaidaFull = ConvertTo-PathAbsoluto -Valor $Saida -Campo "saída"
if (-not (Test-Path -LiteralPath $EntradaFull -PathType Container)) {
    throw "entrada deve ser diretório existente"
}
$entradaPermitida = (Test-PathDentro $EntradaFull $AlvosRoot $false) -or
    (Test-PathDentro $EntradaFull $FixtureRoot $true)
if (-not $entradaPermitida) {
    throw "entrada deve ficar sob alvos/ ou tests/fixtures/alvo-sintetico"
}
if (-not (Test-PathDentro $SaidaFull $ResultadosRoot $false)) {
    throw "saída deve ficar sob resultados/"
}
$saidaEsperada = [IO.Path]::GetFullPath((Join-Path $ResultadosRoot (
    Join-Path $ExecucaoId ("tentativa-{0:D3}" -f $Tentativa)
)))
if (-not $SaidaFull.Equals($saidaEsperada, $ComparacaoPath)) {
    throw "saída deve ser exclusiva em resultados/$ExecucaoId/tentativa-$('{0:D3}' -f $Tentativa)"
}
if (Test-PathsSobrepostos $EntradaFull $SaidaFull) {
    throw "entrada e saída não podem se sobrepor"
}

Assert-ArvoreRegular -Caminho $EntradaFull -Campo "entrada" -ExigirArquivo
if (Test-Path -LiteralPath $ResultadosRoot) {
    if (-not (Test-Path -LiteralPath $ResultadosRoot -PathType Container)) {
        throw "raiz resultados/ deve ser diretório"
    }
    Assert-SemReparseNosComponentes -Caminho $ResultadosRoot -Campo "resultados"
}
Assert-SaidaNovaOuVazia -Caminho $SaidaFull

$mounts = [System.Collections.Generic.List[object]]::new()
$mounts.Add([pscustomobject]@{
    origem = $EntradaFull
    destino = "/entrada"
    somente_leitura = $true
})
$mounts.Add([pscustomobject]@{
    origem = $SaidaFull
    destino = "/saida"
    somente_leitura = $false
})

if ($Condicao -eq "C2") {
    Assert-TextoSeguro -Valor $RegrasRoot -Campo "regras Semgrep"
    if (-not (Test-Path -LiteralPath $RegrasRoot -PathType Container) -or
        -not (Test-Path -LiteralPath $RegrasPython -PathType Container)) {
        throw "C2 exige bundle local fixo docker/regras-semgrep/python"
    }
    Assert-ArvoreRegular -Caminho $RegrasRoot -Campo "regras Semgrep"
    Assert-ArvoreRegular -Caminho $RegrasPython -Campo "config Python do Semgrep" -ExigirArquivo
    if ((Test-PathsSobrepostos $RegrasRoot $EntradaFull) -or
        (Test-PathsSobrepostos $RegrasRoot $SaidaFull)) {
        throw "regras, entrada e saída não podem se sobrepor"
    }
    $mounts.Add([pscustomobject]@{
        origem = $RegrasRoot
        destino = "/opt/regras-semgrep"
        somente_leitura = $true
    })
}

$imagemInfo = Invoke-DockerJson -Argumentos @(
    "image", "inspect", "--format", "{{json .}}", $Imagem
) -Contexto "docker image inspect"
if ([string]$imagemInfo.Id -notmatch "^sha256:[0-9a-f]{64}$") {
    throw "docker image inspect retornou ID de imagem inválido"
}
if ([string]$imagemInfo.Id -ne $ImagemDigest) {
    throw "digest informado diverge do ID da imagem local inspecionada"
}
if ([string]$imagemInfo.Os -ne "linux" -or
    [string]$imagemInfo.Architecture -ne "amd64") {
    throw "imagem local deve ser linux/amd64"
}
$ImageId = [string]$imagemInfo.Id
$watchdogLimiteSegundos = $TimeoutSegundos + 120

$mutexNome = Get-MutexNome -Raiz $Repo
$token = [guid]::NewGuid().ToString("N")
$nomeBase = $ExecucaoId.ToLowerInvariant()
$containerName = "tcc-sast-$nomeBase-t$Tentativa-$($token.Substring(0, 12))"
$executorArgs = [System.Collections.Generic.List[string]]::new()
foreach ($arg in @(
    "/usr/local/bin/python", "-P", "-m", "runner.executor_sast",
    "--condicao", $Condicao,
    "--execucao-id", $ExecucaoId,
    "--alvo", $Alvo
)) { $executorArgs.Add([string]$arg) }
if ($EntradaCommit) {
    $executorArgs.Add("--entrada-commit")
    $executorArgs.Add($EntradaCommit)
}
foreach ($arg in @(
    "--entrada-sha256", $EntradaSha256,
    "--finalidade", $Finalidade,
    "--tentativa", [string]$Tentativa,
    "--imagem", $Imagem,
    "--imagem-digest", $ImagemDigest,
    "--timeout-segundos", [string]$TimeoutSegundos
)) { $executorArgs.Add([string]$arg) }

$dockerArgs = [System.Collections.Generic.List[string]]::new()
foreach ($arg in @(
    "run",
    "--pull", "never",
    "--name", $containerName,
    "--label", "tcc.sast.owner=$token",
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
    "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=1777"
)) { $dockerArgs.Add([string]$arg) }
foreach ($ambiente in @(
    "HOME=/tmp/tcc-home",
    "PYTHONNOUSERSITE=1",
    "PYTHONSAFEPATH=1",
    "SEMGREP_ENABLE_VERSION_CHECK=0",
    "SEMGREP_SEND_METRICS=off"
)) {
    $dockerArgs.Add("--env")
    $dockerArgs.Add($ambiente)
}
foreach ($mount in $mounts) {
    $spec = "type=bind,src=$($mount.origem),dst=$($mount.destino)"
    if ($mount.somente_leitura) { $spec += ",readonly" }
    $dockerArgs.Add("--mount")
    $dockerArgs.Add($spec)
}
$dockerArgs.Add($ImageId)
foreach ($arg in $executorArgs) { $dockerArgs.Add($arg) }

$plano = [ordered]@{
    schema_version = "1.0"
    somente_planejar = [bool]$SomentePlanejar
    container_nome = $containerName
    exclusao_mutua = $mutexNome
    watchdog_externo = $true
    watchdog_limite_segundos = $watchdogLimiteSegundos
    controle_timeout = "scanner_interno_e_container_host"
    imagem = [ordered]@{
        solicitada = $Imagem
        id = $ImageId
        os = [string]$imagemInfo.Os
        arquitetura = [string]$imagemInfo.Architecture
    }
    mounts = @($mounts)
    docker_argumentos = @($dockerArgs)
    executor_argumentos = @($executorArgs)
}

if ($SomentePlanejar) {
    $plano | ConvertTo-Json -Depth 10 -Compress
    return
}

$mutex = [System.Threading.Mutex]::new($false, $mutexNome)
$mutexAdquirido = $false
$resultado = $null
try {
    try {
        $mutexAdquirido = $mutex.WaitOne(0)
    }
    catch [System.Threading.AbandonedMutexException] {
        $mutexAdquirido = $true
    }
    if (-not $mutexAdquirido) {
        throw "outra execução SAST já detém a exclusão mútua do host"
    }

    Assert-ContainerNomeAusente -Nome $containerName
    if (-not (Test-Path -LiteralPath $ResultadosRoot)) {
        New-Item -ItemType Directory -Path $ResultadosRoot -ErrorAction Stop | Out-Null
        Assert-SemReparseNosComponentes -Caminho $ResultadosRoot -Campo "resultados"
    }
    if (-not (Test-Path -LiteralPath $SaidaFull)) {
        New-Item -ItemType Directory -Path $SaidaFull -ErrorAction Stop | Out-Null
    }
    Assert-SaidaNovaOuVazia -Caminho $SaidaFull

    $containerInfo = $null
    $runCodigo = $null
    $runSaida = @()
    try {
        $runResultado = Invoke-DockerRunLimitado `
            -Argumentos @($dockerArgs) `
            -LimiteSegundos $watchdogLimiteSegundos
        $runSaida = @($runResultado.saida)
        $runCodigo = $runResultado.codigo
        $containerInfo = Get-ContainerInfo `
            -Nome $containerName `
            -PermitirAusente:([bool]$runResultado.watchdog)
        if ([bool]$runResultado.watchdog) {
            if ($null -ne $containerInfo -and
                -not (Test-ContainerProprio $containerInfo $containerName $token $ImageId)) {
                throw "watchdog encontrou contêiner cuja propriedade não foi comprovada"
            }
            if ($null -ne $containerInfo -and [bool]$containerInfo.State.Running) {
                $stopSaida = @(& docker container stop --time 5 $containerName 2>&1)
                if ($LASTEXITCODE -ne 0) {
                    $killSaida = @(& docker container kill $containerName 2>&1)
                    if ($LASTEXITCODE -ne 0) {
                        throw "watchdog não conseguiu parar contêiner próprio: $($stopSaida + $killSaida -join ' ')"
                    }
                }
                $containerInfo = Get-ContainerInfo -Nome $containerName
            }
            if ($null -ne $containerInfo -and [bool]$containerInfo.State.Running) {
                throw "watchdog deixou contêiner próprio em execução"
            }
            Write-WatchdogArtifact `
                -Saida $SaidaFull `
                -Execucao $ExecucaoId `
                -TentativaNumero $Tentativa `
                -LimiteSegundos $watchdogLimiteSegundos `
                -ContainerNome $containerName `
                -ContainerId $(if ($null -eq $containerInfo) { "" } else { [string]$containerInfo.Id }) `
                -ImageId $ImageId
            throw "watchdog externo interrompeu o contêiner após $watchdogLimiteSegundos segundos"
        }
        if (-not (Test-ContainerProprio $containerInfo $containerName $token $ImageId)) {
            throw "Image/nome/label do contêiner não comprovam propriedade do wrapper"
        }
        if ([bool]$containerInfo.State.Running) {
            throw "contêiner próprio ainda está em execução (Running=true)"
        }
        if ([bool]$containerInfo.State.OOMKilled) {
            throw "execução reprovada: OOMKilled=true (limite de memória atingido)"
        }
        $exitInspecionado = [int]$containerInfo.State.ExitCode
        if ($exitInspecionado -ne [int]$runCodigo) {
            throw "código de exit inspecionado ($exitInspecionado) diverge do docker run ($runCodigo)"
        }
        if ([int]$runCodigo -ne 0) {
            throw "executor interno terminou com código de exit $runCodigo"
        }

        $resultado = [ordered]@{
            schema_version = "1.0"
            estado = "concluido"
            container_id = [string]$containerInfo.Id
            imagem_id = $ImageId
            exit_code = $exitInspecionado
            oom_killed = [bool]$containerInfo.State.OOMKilled
            docker_saida = @($runSaida | ForEach-Object { [string]$_ })
        }
    }
    finally {
        $atual = Get-ContainerInfo -Nome $containerName -PermitirAusente
        if ($null -ne $atual -and
            (Test-ContainerProprio $atual $containerName $token $ImageId) -and
            -not [bool]$atual.State.Running) {
            $rmSaida = @(& docker container rm ([string]$atual.Id) 2>&1)
            $rmCodigo = $LASTEXITCODE
            if ($rmCodigo -ne 0) {
                throw "falha ao remover contêiner próprio parado: $($rmSaida -join ' ')"
            }
        }
    }
}
finally {
    if ($mutexAdquirido) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}

$resultado | ConvertTo-Json -Depth 8 -Compress
