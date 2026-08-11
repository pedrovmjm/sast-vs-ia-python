[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$Wrapper = Join-Path $PSScriptRoot "executar-sast.ps1"
$FixtureRoot = Join-Path $Repo "tests/fixtures/alvo-sintetico"
$ResultsRoot = Join-Path $Repo "resultados"
$RulesRoot = Join-Path $Repo "docker/regras-semgrep"
$ImageId = "sha256:" + ("1" * 64)
$ContainerId = "a" * 64
$CriouFixtureRoot = -not (Test-Path -LiteralPath $FixtureRoot)
$CriouResultsRoot = -not (Test-Path -LiteralPath $ResultsRoot)
$CriouRulesRoot = $false
$RulesFixtureFile = Join-Path $RulesRoot "python/regra-wrapper-test.yml"
$TestRoot = Join-Path $FixtureRoot ("wrapper-" + [guid]::NewGuid().ToString("N"))

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

function Assert-Sequence {
    param([object[]]$Esperado, [object[]]$Observado, [string]$Mensagem)
    Assert-Equal $Esperado.Count $Observado.Count "$Mensagem (tamanho)"
    for ($i = 0; $i -lt $Esperado.Count; $i++) {
        Assert-Equal ([string]$Esperado[$i]) ([string]$Observado[$i]) "$Mensagem (índice $i)"
    }
}

function Assert-ThrowsLike {
    param([scriptblock]$Acao, [string]$Padrao)
    try {
        & $Acao
    }
    catch {
        if ($_.Exception.Message -notmatch $Padrao) {
            throw "Exceção não corresponde a /$Padrao/: $($_.Exception.Message)"
        }
        return
    }
    throw "Era esperada exceção correspondente a /$Padrao/"
}

function Test-Caso {
    param([string]$Nome, [scriptblock]$Corpo)
    try {
        & $Corpo
        $script:Passaram++
        Write-Host "PASS $Nome"
    }
    catch {
        $script:Falharam++
        Write-Host "FAIL $Nome -- $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Reset-DockerMock {
    $global:TccDockerCalls = [System.Collections.Generic.List[object]]::new()
    $global:TccMockImageId = $ImageId
    $global:TccMockImageOs = "linux"
    $global:TccMockImageArch = "amd64"
    $global:TccMockRunExit = 0
    $global:TccMockStateExit = 0
    $global:TccMockRunning = $false
    $global:TccMockOom = $false
    $global:TccMockStateImage = $ImageId
    $global:TccMockContainer = $null
    $global:TccMockRemoved = $false
    $global:TccMockNameExists = $false
}

function global:docker {
    $argv = @($args | ForEach-Object { [string]$_ })
    $global:TccDockerCalls.Add($argv)

    if ($argv.Count -ge 2 -and $argv[0] -eq "image" -and $argv[1] -eq "inspect") {
        $global:LASTEXITCODE = 0
        return ([pscustomobject]@{
            Id = $global:TccMockImageId
            Os = $global:TccMockImageOs
            Architecture = $global:TccMockImageArch
        } | ConvertTo-Json -Compress)
    }

    if ($argv.Count -ge 1 -and $argv[0] -eq "run") {
        $nameIndex = [Array]::IndexOf($argv, "--name")
        $labelIndex = [Array]::IndexOf($argv, "--label")
        $imageIndex = [Array]::IndexOf($argv, $global:TccMockImageId)
        $nome = $argv[$nameIndex + 1]
        $label = $argv[$labelIndex + 1]
        $token = $label.Substring($label.IndexOf("=") + 1)
        $global:TccMockContainer = [pscustomobject]@{
            Id = $ContainerId
            Name = "/$nome"
            Image = $global:TccMockStateImage
            Config = [pscustomobject]@{
                Image = $argv[$imageIndex]
                Labels = [pscustomobject]@{ "tcc.sast.owner" = $token }
            }
            State = [pscustomobject]@{
                Running = $global:TccMockRunning
                OOMKilled = $global:TccMockOom
                ExitCode = $global:TccMockStateExit
            }
        }
        $global:LASTEXITCODE = $global:TccMockRunExit
        return "saída controlada do executor"
    }

    if ($argv.Count -ge 2 -and $argv[0] -eq "container" -and $argv[1] -eq "ls") {
        $global:LASTEXITCODE = 0
        if ($global:TccMockNameExists) { return $ContainerId }
        return ""
    }

    if ($argv.Count -ge 2 -and $argv[0] -eq "container" -and $argv[1] -eq "inspect") {
        if ($null -eq $global:TccMockContainer) {
            $global:LASTEXITCODE = 1
            return ""
        }
        $global:LASTEXITCODE = 0
        return ($global:TccMockContainer | ConvertTo-Json -Depth 8 -Compress)
    }

    if ($argv.Count -ge 2 -and $argv[0] -eq "container" -and $argv[1] -eq "rm") {
        $global:TccMockRemoved = $true
        $global:TccMockContainer = $null
        $global:LASTEXITCODE = 0
        return $ContainerId
    }

    $global:LASTEXITCODE = 125
    return "docker mock: chamada inesperada: $($argv -join ' ')"
}

function New-Parametros {
    param([string]$Condicao = "C1", [switch]$Executar)
    $execucaoId = "$Condicao-ALVO-TESTE-R01"
    $saida = Join-Path $ResultsRoot (Join-Path $execucaoId "tentativa-001")
    $dados = @{
        Condicao = $Condicao
        ExecucaoId = $execucaoId
        Alvo = "ALVO-TESTE"
        Entrada = $TestRoot
        Saida = $saida
        EntradaSha256 = "b" * 64
        Finalidade = "fumaca"
        Tentativa = 1
        Imagem = "tcc-sast:teste"
        ImagemDigest = $ImageId
        TimeoutSegundos = 30
    }
    if (-not $Executar) { $dados.SomentePlanejar = $true }
    return $dados
}

function Invoke-Planejamento {
    param([hashtable]$Parametros)
    $texto = (& $Wrapper @Parametros | Out-String).Trim()
    return $texto | ConvertFrom-Json
}

try {
    New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $TestRoot "app.py") -Value "print('fixture')" -Encoding UTF8
    New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null

    Test-Caso "planejamento C1 fixa isolamento, recursos, mounts e CLI" {
        Reset-DockerMock
        $p = New-Parametros
        $plano = Invoke-Planejamento $p

        Assert-Equal 1 $global:TccDockerCalls.Count "planejamento deve somente inspecionar imagem"
        Assert-Equal $ImageId $plano.imagem.id "ID local resolvido"
        Assert-Equal "linux" $plano.imagem.os "SO da imagem"
        Assert-Equal "amd64" $plano.imagem.arquitetura "arquitetura da imagem"
        Assert-True ([bool]$plano.watchdog_externo) "watchdog externo deve estar ativo"
        Assert-Equal 150 ([int]$plano.watchdog_limite_segundos) "limite total do watchdog"
        Assert-Equal "scanner_interno_e_container_host" $plano.controle_timeout "camadas de timeout"
        Assert-Equal 2 $plano.mounts.Count "C1 deve ter somente entrada e saída"
        Assert-Equal "/entrada" $plano.mounts[0].destino "mount de entrada"
        Assert-True ([bool]$plano.mounts[0].somente_leitura) "entrada deve ser ro"
        Assert-Equal "/saida" $plano.mounts[1].destino "mount de saída"
        Assert-True (-not [bool]$plano.mounts[1].somente_leitura) "saída deve ser rw"

        $argsDocker = @($plano.docker_argumentos)
        foreach ($obrigatorio in @(
            "--pull", "never", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001", "--workdir", "/opt/tcc", "--init",
            "--pids-limit", "256", "--memory", "3g", "--memory-swap", "3g",
            "--cpus", "2", "--stop-timeout", "5", "--tmpfs"
        )) {
            Assert-True ($argsDocker -contains $obrigatorio) "flag ausente: $obrigatorio"
        }
        Assert-True (-not ($argsDocker -contains "--rm")) "docker run não pode usar --rm"
        Assert-True ($argsDocker -contains "--restart") "política de restart deve ser explícita"
        Assert-True ($argsDocker -contains "no") "restart deve ser no"
        foreach ($ambiente in @(
            "HOME=/tmp/tcc-home", "PYTHONNOUSERSITE=1", "PYTHONSAFEPATH=1",
            "SEMGREP_ENABLE_VERSION_CHECK=0", "SEMGREP_SEND_METRICS=off"
        )) {
            Assert-True ($argsDocker -contains $ambiente) "env fixo ausente: $ambiente"
        }
        Assert-True (-not (($argsDocker -join " ") -match "oracle|docker.sock")) "plano não pode expor oracle/socket"

        Assert-Sequence @(
            "/usr/local/bin/python", "-P", "-m", "runner.executor_sast",
            "--condicao", "C1", "--execucao-id", "C1-ALVO-TESTE-R01",
            "--alvo", "ALVO-TESTE", "--entrada-sha256", ("b" * 64),
            "--finalidade", "fumaca", "--tentativa", "1",
            "--imagem", "tcc-sast:teste", "--imagem-digest", $ImageId,
            "--timeout-segundos", "30"
        ) @($plano.executor_argumentos) "CLI interna exata"
    }

    Test-Caso "C2 monta somente bundle fixo readonly" {
        Reset-DockerMock
        if (-not (Test-Path -LiteralPath $RulesRoot)) {
            New-Item -ItemType Directory -Force -Path (Join-Path $RulesRoot "python") | Out-Null
            Set-Content -LiteralPath $RulesFixtureFile -Value "rules: []" -Encoding UTF8
            $script:CriouRulesRoot = $true
        }
        $p = New-Parametros -Condicao C2
        $plano = Invoke-Planejamento $p
        Assert-Equal 3 $plano.mounts.Count "C2 deve ter três mounts"
        Assert-Equal "/opt/regras-semgrep" $plano.mounts[2].destino "destino fixo das regras"
        Assert-True ([bool]$plano.mounts[2].somente_leitura) "regras devem ser ro"
        Assert-True (($plano.docker_argumentos -join " ") -match "/opt/regras-semgrep") "mount de regras ausente"
    }

    Test-Caso "entrada_commit opcional ocupa posição canônica" {
        Reset-DockerMock
        $p = New-Parametros
        $p.EntradaCommit = "c" * 40
        $plano = Invoke-Planejamento $p
        $argsInternos = @($plano.executor_argumentos)
        $i = [Array]::IndexOf($argsInternos, "--entrada-commit")
        Assert-True ($i -gt 0) "flag de commit ausente"
        Assert-Equal ("c" * 40) $argsInternos[$i + 1] "commit repassado"
    }

    Test-Caso "rejeita entrada fora das raízes permitidas" {
        Reset-DockerMock
        $p = New-Parametros
        $p.Entrada = $Repo
        Assert-ThrowsLike { & $Wrapper @p | Out-Null } "entrada.*alvos|alvo-sintetico"
        Assert-Equal 0 $global:TccDockerCalls.Count "não deve consultar Docker"
    }

    Test-Caso "rejeita saída fora de resultados" {
        Reset-DockerMock
        $p = New-Parametros
        $p.Saida = Join-Path $TestRoot "saida"
        Assert-ThrowsLike { & $Wrapper @p | Out-Null } "resultados"
    }

    Test-Caso "rejeita saída sem identidade e tentativa canônicas" {
        Reset-DockerMock
        $p = New-Parametros
        $p.Saida = Join-Path $ResultsRoot "arbitraria"
        Assert-ThrowsLike { & $Wrapper @p | Out-Null } "exclusiva|tentativa-001"
    }

    Test-Caso "rejeita delimitadores perigosos em caminhos" {
        foreach ($sufixo in @("com,virgula", "com`nlinha", "com`rretorno", "com$([char]0)nul")) {
            Reset-DockerMock
            $p = New-Parametros
            $p.Saida = Join-Path $ResultsRoot $sufixo
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "mount|CR|LF|NUL|caractere"
        }
    }

    Test-Caso "rejeita saída existente não vazia" {
        Reset-DockerMock
        $p = New-Parametros
        New-Item -ItemType Directory -Force -Path $p.Saida | Out-Null
        Set-Content -LiteralPath (Join-Path $p.Saida "anterior.txt") -Value "não sobrescrever"
        try {
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "vazia|sobrescrever"
        }
        finally {
            Remove-Item -LiteralPath $p.Saida -Recurse -Force
        }
    }

    Test-Caso "rejeita digest informado diferente da imagem local" {
        Reset-DockerMock
        $p = New-Parametros
        $p.ImagemDigest = "sha256:" + ("2" * 64)
        Assert-ThrowsLike { & $Wrapper @p | Out-Null } "digest|ID.*imagem"
    }

    Test-Caso "rejeita imagem que não seja linux amd64" {
        Reset-DockerMock
        $global:TccMockImageArch = "arm64"
        $p = New-Parametros
        Assert-ThrowsLike { & $Wrapper @p | Out-Null } "linux/amd64"
    }

    Test-Caso "rejeita ID semântico de outra condição ou alvo" {
        Reset-DockerMock
        $p = New-Parametros
        $p.ExecucaoId = "C2-ALVO-TESTE-R01"
        Assert-ThrowsLike { & $Wrapper @p | Out-Null } "execucao.*C1-ALVO-TESTE-R01"
        Assert-Equal 0 $global:TccDockerCalls.Count "ID inválido deve falhar antes do Docker"
    }

    Test-Caso "execução usa ID local, verifica estado e remove contêiner próprio parado" {
        Reset-DockerMock
        $p = New-Parametros -Executar
        try {
            $resultado = Invoke-Planejamento $p
            Assert-Equal "concluido" $resultado.estado "estado do wrapper"
            Assert-True $global:TccMockRemoved "contêiner próprio parado deve ser removido"
            $run = @($global:TccDockerCalls | Where-Object { $_[0] -eq "run" })[0]
            Assert-True ($run -contains $ImageId) "run deve usar ID, não tag"
            Assert-True (-not ($run -contains "--rm")) "run não usa --rm"
        }
        finally {
            if (Test-Path -LiteralPath $p.Saida) { Remove-Item -LiteralPath $p.Saida -Recurse -Force }
        }
    }

    Test-Caso "precheck recusa nome de contêiner já existente" {
        Reset-DockerMock
        $global:TccMockNameExists = $true
        $p = New-Parametros -Executar
        try {
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "nome.*cont.iner|exclusivo"
            $runs = @($global:TccDockerCalls | Where-Object { $_[0] -eq "run" })
            Assert-True ($runs.Count -eq 0) "não deve executar nome ocupado"
        }
        finally {
            if (Test-Path -LiteralPath $p.Saida) { Remove-Item -LiteralPath $p.Saida -Recurse -Force }
        }
    }

    Test-Caso "exclusão mútua impede duas execuções SAST no host" {
        Reset-DockerMock
        $plano = Invoke-Planejamento (New-Parametros)
        $job = Start-Job -ArgumentList $plano.exclusao_mutua -ScriptBlock {
            param($NomeMutex)
            $mutex = [System.Threading.Mutex]::new($false, $NomeMutex)
            try {
                $null = $mutex.WaitOne()
                "mutex-pronto"
                Start-Sleep -Seconds 15
                $mutex.ReleaseMutex()
            }
            finally {
                $mutex.Dispose()
            }
        }
        try {
            $pronto = $false
            for ($i = 0; $i -lt 100; $i++) {
                if (@(Receive-Job $job -Keep) -contains "mutex-pronto") {
                    $pronto = $true
                    break
                }
                Start-Sleep -Milliseconds 50
            }
            Assert-True $pronto "job não adquiriu mutex a tempo"
            $p = New-Parametros -Executar
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "outra.*SAST.*host"
            $runs = @($global:TccDockerCalls | Where-Object { $_[0] -eq "run" })
            Assert-True ($runs.Count -eq 0) "execução concorrente não deve chamar docker run"
        }
        finally {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }
    }

    Test-Caso "OOMKilled reprova mas ainda limpa contêiner próprio parado" {
        Reset-DockerMock
        $global:TccMockOom = $true
        $global:TccMockRunExit = 137
        $global:TccMockStateExit = 137
        $p = New-Parametros -Executar
        try {
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "OOMKilled|mem.ria"
            Assert-True $global:TccMockRemoved "contêiner parado deve ser limpo após OOM"
        }
        finally {
            if (Test-Path -LiteralPath $p.Saida) { Remove-Item -LiteralPath $p.Saida -Recurse -Force }
        }
    }

    Test-Caso "exit divergente reprova e é conferido com docker run" {
        Reset-DockerMock
        $global:TccMockRunExit = 1
        $global:TccMockStateExit = 2
        $p = New-Parametros -Executar
        try {
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "exit|c.digo"
            Assert-True $global:TccMockRemoved "contêiner parado próprio deve ser removido"
        }
        finally {
            if (Test-Path -LiteralPath $p.Saida) { Remove-Item -LiteralPath $p.Saida -Recurse -Force }
        }
    }

    Test-Caso "não remove contêiner ainda em execução" {
        Reset-DockerMock
        $global:TccMockRunning = $true
        $p = New-Parametros -Executar
        try {
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "ainda.*execu|Running"
            Assert-True (-not $global:TccMockRemoved) "contêiner em execução não pode ser removido"
        }
        finally {
            if (Test-Path -LiteralPath $p.Saida) { Remove-Item -LiteralPath $p.Saida -Recurse -Force }
        }
    }

    Test-Caso "não remove contêiner cuja identidade não comprova propriedade" {
        Reset-DockerMock
        $global:TccMockStateImage = "sha256:" + ("9" * 64)
        $p = New-Parametros -Executar
        try {
            Assert-ThrowsLike { & $Wrapper @p | Out-Null } "Image|imagem|propriedade"
            Assert-True (-not $global:TccMockRemoved) "imagem divergente impede remoção"
        }
        finally {
            if (Test-Path -LiteralPath $p.Saida) { Remove-Item -LiteralPath $p.Saida -Recurse -Force }
        }
    }
}
finally {
    Remove-Item function:\docker -ErrorAction SilentlyContinue
    @(
        "TccDockerCalls", "TccMockImageId", "TccMockImageOs", "TccMockImageArch",
        "TccMockRunExit", "TccMockStateExit", "TccMockRunning", "TccMockOom",
        "TccMockStateImage", "TccMockContainer", "TccMockRemoved", "TccMockNameExists"
    ) | ForEach-Object {
        Remove-Variable -Name $_ -Scope Global -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $TestRoot) {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force
    }
    if ($CriouRulesRoot -and (Test-Path -LiteralPath $RulesFixtureFile)) {
        Remove-Item -LiteralPath $RulesFixtureFile -Force
        $pythonRules = Join-Path $RulesRoot "python"
        if ((Get-Item -LiteralPath $pythonRules).GetFileSystemInfos().Count -eq 0) {
            Remove-Item -LiteralPath $pythonRules -Force
        }
        if ((Get-Item -LiteralPath $RulesRoot).GetFileSystemInfos().Count -eq 0) {
            Remove-Item -LiteralPath $RulesRoot -Force
        }
    }
    if ($CriouFixtureRoot -and (Test-Path -LiteralPath $FixtureRoot)) {
        $item = Get-Item -LiteralPath $FixtureRoot
        if ($item.GetFileSystemInfos().Count -eq 0) {
            Remove-Item -LiteralPath $FixtureRoot -Force
        }
    }
    if ($CriouResultsRoot -and (Test-Path -LiteralPath $ResultsRoot)) {
        $item = Get-Item -LiteralPath $ResultsRoot
        if ($item.GetFileSystemInfos().Count -eq 0) {
            Remove-Item -LiteralPath $ResultsRoot -Force
        }
    }
}

Write-Host "$script:Passaram teste(s) passaram; $script:Falharam falharam."
if ($script:Falharam -ne 0) { exit 1 }
