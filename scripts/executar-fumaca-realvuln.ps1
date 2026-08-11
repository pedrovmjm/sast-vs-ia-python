[CmdletBinding()]
param(
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$")]
    [string]$Imagem = "tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0",

    [ValidateRange(30, 3600)]
    [int]$TimeoutSegundos = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$BenchmarkRoot = [IO.Path]::GetFullPath((Join-Path $Repo "benchmark"))
$AlvosRoot = [IO.Path]::GetFullPath((Join-Path $Repo "alvos"))
$ResultadosRoot = [IO.Path]::GetFullPath((Join-Path $Repo "resultados"))
$EvidenciasRoot = [IO.Path]::GetFullPath((Join-Path $Repo "evidencias"))
$EvidenciaFinal = [IO.Path]::GetFullPath((Join-Path $EvidenciasRoot "primeira-execucao"))
$Wrapper = Join-Path $PSScriptRoot "executar-sast.ps1"
$Token = [guid]::NewGuid().ToString("N")
$Trabalho = [IO.Path]::GetFullPath((Join-Path $BenchmarkRoot ".t09-$Token"))
$EvidenciaTemporaria = [IO.Path]::GetFullPath((Join-Path $EvidenciasRoot ".primeira-execucao-$Token"))
$AlvoId = "ALVO-0001"
$AlvoRegeneradoId = "ALVO-REGENERADO-T09"
$AlvoPath = [IO.Path]::GetFullPath((Join-Path $AlvosRoot $AlvoId))
$AlvoRegeneradoPath = [IO.Path]::GetFullPath((Join-Path $AlvosRoot $AlvoRegeneradoId))
$RealVulnUrl = "https://github.com/kolega-ai/Real-Vuln-Benchmark.git"
$RealVulnTagObject = "aa9f7321c8c53fe417b8faa517f1c4308b69b389"
$RealVulnCommit = "d98e9fc91273702c9547663b6906d1fc494d4fcc"
$RepoId = "realvuln-dsvw"
$RepoUrl = "https://github.com/stamparm/DSVW"
$RepoCommit = "7d40f4b7939c901610ed9b85724552d60e7d63fa"
$ImagemInfo = $null
$Concluida = $false

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

function Test-Dentro {
    param([string]$Caminho, [string]$Raiz, [bool]$PermitirRaiz = $true)
    $limpa = $Raiz.TrimEnd("\", "/")
    if ($Caminho.Equals($limpa, [StringComparison]::OrdinalIgnoreCase)) {
        return $PermitirRaiz
    }
    return $Caminho.StartsWith(
        $limpa + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Invoke-Git {
    param([string[]]$Argumentos, [string]$Contexto)
    $preferenciaAnterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $linhas = @(& git @Argumentos 2>&1)
        $codigo = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $preferenciaAnterior
    }
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $($linhas -join ' ')"
    }
    return @($linhas | ForEach-Object { [string]$_ })
}

function Invoke-Docker {
    param([string[]]$Argumentos, [string]$Contexto)
    $preferenciaAnterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $linhas = @(& docker @Argumentos 2>&1)
        $codigo = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $preferenciaAnterior
    }
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $($linhas -join ' ')"
    }
    return @($linhas | ForEach-Object { [string]$_ })
}

function Read-Json {
    param([string]$Caminho, [string]$Contexto)
    $item = Get-Item -LiteralPath $Caminho -Force -ErrorAction Stop
    Assert-True (-not $item.PSIsContainer) "$Contexto deve ser arquivo"
    Assert-True (
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
    ) "$Contexto não pode ser reparse point"
    try {
        return Get-Content -LiteralPath $Caminho -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "$Contexto não contém JSON válido: $($_.Exception.Message)"
    }
}

function Get-Sha256 {
    param([string]$Caminho)
    return (Get-FileHash -LiteralPath $Caminho -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-ImagemLocal {
    $linhas = Invoke-Docker @(
        "image", "inspect", "--format", "{{json .}}", $Imagem
    ) "inspeção da imagem"
    $info = ($linhas -join [Environment]::NewLine) | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$info.Id -match "^sha256:[0-9a-f]{64}$") "ID da imagem inválido"
    Assert-Equal "linux" ([string]$info.Os) "SO da imagem"
    Assert-Equal "amd64" ([string]$info.Architecture) "arquitetura da imagem"
    return $info
}

function Invoke-Preparacao {
    param([string]$Origem, [string]$Destino, [string]$Inventario)
    $origemMount = "type=bind,src=$Origem,dst=/origem,readonly"
    $alvosMount = "type=bind,src=$AlvosRoot,dst=/alvos"
    $evidenciaMount = "type=bind,src=$EvidenciaTemporaria,dst=/evidencia"
    $destinoContainer = if ($Destino -eq $AlvoPath) {
        "/alvos/$AlvoId"
    } else {
        "/alvos/$AlvoRegeneradoId"
    }
    $inventarioContainer = "/evidencia/$([IO.Path]::GetFileName($Inventario))"
    Invoke-Docker @(
        "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "10001:10001",
        "--pids-limit", "64", "--memory", "512m", "--memory-swap", "512m",
        "--cpus", "1", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m,uid=10001,gid=10001,mode=1777",
        "--env", "HOME=/tmp/tcc-home", "--env", "PYTHONSAFEPATH=1",
        "--mount", $origemMount, "--mount", $alvosMount, "--mount", $evidenciaMount,
        [string]$ImagemInfo.Id, "/usr/local/bin/python", "-P", "-m",
        "runner.preparacao", "preparar", "--origem", "/origem",
        "--destino", $destinoContainer, "--inventario", $inventarioContainer
    ) "preparação do alvo $destinoContainer" | Out-Null
}

function Remove-ArvorePropria {
    param([string]$Caminho, [string]$RaizPermitida)
    $full = [IO.Path]::GetFullPath($Caminho)
    Assert-True (Test-Dentro $full $RaizPermitida $false) "cleanup recusou caminho fora da raiz"
    if (-not (Test-Path -LiteralPath $full)) { return }
    $item = Get-Item -LiteralPath $full -Force
    Assert-True (
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
    ) "cleanup recusou reparse point"
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
}

try {
    foreach ($raiz in @($BenchmarkRoot, $AlvosRoot, $ResultadosRoot, $EvidenciasRoot)) {
        if (-not (Test-Path -LiteralPath $raiz)) {
            New-Item -ItemType Directory -Path $raiz -ErrorAction Stop | Out-Null
        }
        $item = Get-Item -LiteralPath $raiz -Force
        Assert-True $item.PSIsContainer "raiz deve ser diretório: $raiz"
        Assert-True (
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
        ) "raiz não pode ser reparse point: $raiz"
    }
    Assert-True (-not (Test-Path -LiteralPath $EvidenciaFinal)) `
        "evidência final já existe e não será sobrescrita"
    Assert-True (-not (Test-Path -LiteralPath $AlvoPath)) "alvo opaco já existe"
    Assert-True (-not (Test-Path -LiteralPath $AlvoRegeneradoPath)) "alvo regenerado já existe"

    New-Item -ItemType Directory -Path $Trabalho -ErrorAction Stop | Out-Null
    New-Item -ItemType Directory -Path $EvidenciaTemporaria -ErrorAction Stop | Out-Null
    $realvulnGit = Join-Path $Trabalho "realvuln.git"
    $alvoGit = Join-Path $Trabalho "alvo.git"
    $exportacao = Join-Path $Trabalho "exportacao"

    Invoke-Git @("init", "--bare", $realvulnGit) "git init RealVuln" | Out-Null
    Invoke-Git @("--git-dir=$realvulnGit", "remote", "add", "origin", $RealVulnUrl) "origem RealVuln" | Out-Null
    Invoke-Git @("--git-dir=$realvulnGit", "fetch", "--depth=1", "origin", "refs/tags/v1.0:refs/tags/v1.0") "aquisição RealVuln v1.0" | Out-Null
    $tagLinhas = @(Invoke-Git @("--git-dir=$realvulnGit", "rev-parse", "refs/tags/v1.0") "objeto da tag")
    $commitLinhas = @(Invoke-Git @("--git-dir=$realvulnGit", "rev-parse", "refs/tags/v1.0^{}") "commit da tag")
    $tag = ([string]$tagLinhas[0]).Trim()
    $commit = ([string]$commitLinhas[0]).Trim()
    Assert-Equal $RealVulnTagObject $tag "objeto da tag RealVuln"
    Assert-Equal $RealVulnCommit $commit "commit RealVuln"

    $manifestoTexto = (Invoke-Git @(
        "--git-dir=$realvulnGit", "show", "$RealVulnCommit`:benchmark-manifest.json"
    ) "leitura do manifesto v1.0") -join [Environment]::NewLine
    $manifesto = $manifestoTexto | ConvertFrom-Json -ErrorAction Stop
    Assert-Equal "1.0.0" ([string]$manifesto.benchmark_version) "versão do manifesto"
    $entrada = $manifesto.repos.$RepoId
    Assert-True ($null -ne $entrada) "alvo de fumaça ausente do manifesto"
    Assert-Equal $RepoUrl ([string]$entrada.repo_url) "URL do alvo"
    Assert-Equal $RepoCommit ([string]$entrada.commit_sha) "commit do alvo"

    Invoke-Git @("init", "--bare", $alvoGit) "git init do alvo" | Out-Null
    Invoke-Git @("--git-dir=$alvoGit", "remote", "add", "origin", $RepoUrl) "origem do alvo" | Out-Null
    Invoke-Git @("--git-dir=$alvoGit", "fetch", "--depth=1", "origin", $RepoCommit) "aquisição do alvo fixado" | Out-Null
    $tipoCommitLinhas = @(Invoke-Git @("--git-dir=$alvoGit", "cat-file", "-t", $RepoCommit) "tipo do commit")
    $tipoCommit = ([string]$tipoCommitLinhas[0]).Trim()
    Assert-Equal "commit" $tipoCommit "objeto adquirido"
    $arvore = Invoke-Git @(
        "--git-dir=$alvoGit", "ls-tree", "-r", "--full-tree",
        "--format=%(objectmode) %(objecttype) %(path)", $RepoCommit
    ) "inspeção da árvore do alvo"
    Assert-True ($arvore.Count -gt 0) "árvore do alvo não pode estar vazia"
    foreach ($linha in $arvore) {
        Assert-True ($linha -match "^100(644|755) blob (.+)$") "entrada Git não regular proibida: $linha"
        $relativo = $Matches[2]
        Assert-True (-not $relativo.Contains("..")) "caminho Git inseguro: $relativo"
        Assert-True (-not $relativo.StartsWith("/")) "caminho Git absoluto proibido: $relativo"
        Assert-True ($relativo -ne ".gitmodules") "submódulo proibido no alvo"
    }
    New-Item -ItemType Directory -Path $exportacao -ErrorAction Stop | Out-Null
    Invoke-Git @(
        "--git-dir=$alvoGit", "--work-tree=$exportacao", "checkout", "--force",
        $RepoCommit, "--", "."
    ) "exportação sem metadados Git" | Out-Null
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $exportacao ".git"))) `
        "exportação não pode conter metadados Git"

    $ImagemInfo = Get-ImagemLocal
    $inventarioC1Path = Join-Path $EvidenciaTemporaria "inventario-C1.json"
    $inventarioC2Path = Join-Path $EvidenciaTemporaria "inventario-C2.json"
    $inventarioRegeneradoPath = Join-Path $EvidenciaTemporaria "inventario-regenerado.json"
    Invoke-Preparacao $exportacao $AlvoPath $inventarioC1Path
    Invoke-Preparacao $exportacao $AlvoRegeneradoPath $inventarioRegeneradoPath
    $inventarioC1 = Read-Json $inventarioC1Path "inventário C1"
    $inventarioRegenerado = Read-Json $inventarioRegeneradoPath "inventário regenerado"
    Assert-Equal ([string]$inventarioC1.entrada_sha256) ([string]$inventarioRegenerado.entrada_sha256) "hash regenerado"
    Assert-Equal (Get-Sha256 $inventarioC1Path) (Get-Sha256 $inventarioRegeneradoPath) "inventários regenerados"
    Copy-Item -LiteralPath $inventarioC1Path -Destination $inventarioC2Path -ErrorAction Stop
    Assert-Equal (Get-Sha256 $inventarioC1Path) (Get-Sha256 $inventarioC2Path) "inventários C1/C2"
    Remove-ArvorePropria $AlvoRegeneradoPath $AlvosRoot

    $hashEntrada = [string]$inventarioC1.entrada_sha256
    $casos = [Collections.Generic.List[object]]::new()
    foreach ($condicao in @("C1", "C2")) {
        $execucaoId = "$condicao-$AlvoId-R01"
        $saida = Join-Path (Join-Path $ResultadosRoot $execucaoId) "tentativa-001"
        Assert-True (-not (Test-Path -LiteralPath $saida)) "resultado já existe: $saida"
        & $Wrapper -Condicao $condicao -ExecucaoId $execucaoId -Alvo $AlvoId `
            -Entrada $AlvoPath -Saida $saida -EntradaCommit $RepoCommit `
            -EntradaSha256 $hashEntrada -Finalidade fumaca -Tentativa 1 `
            -Imagem $Imagem -ImagemDigest ([string]$ImagemInfo.Id) `
            -TimeoutSegundos $TimeoutSegundos | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "wrapper $condicao falhou" }
        $manifestoExecucao = Read-Json (Join-Path $saida "manifesto.json") "manifesto $condicao"
        $versoes = Read-Json (Join-Path $saida "versoes.json") "versões $condicao"
        $normalizado = @(Read-Json (Join-Path $saida "normalizado.json") "normalizado $condicao")
        Assert-Equal "concluida" ([string]$manifestoExecucao.estado) "estado $condicao"
        Assert-Equal "fumaca" ([string]$manifestoExecucao.finalidade) "finalidade $condicao"
        Assert-Equal $hashEntrada ([string]$manifestoExecucao.entrada_sha256) "entrada $condicao"
        Assert-Equal $RepoCommit ([string]$manifestoExecucao.entrada_commit) "commit $condicao"
        $manifestoEvidencia = Join-Path $EvidenciaTemporaria "manifesto-$condicao.json"
        Copy-Item -LiteralPath (Join-Path $saida "manifesto.json") -Destination $manifestoEvidencia -ErrorAction Stop
        $casos.Add([ordered]@{
            condicao = $condicao
            execucao_id = $execucaoId
            estado = [string]$manifestoExecucao.estado
            finalidade = [string]$manifestoExecucao.finalidade
            inicio_utc = [string]$manifestoExecucao.inicio_utc
            termino_utc = [string]$manifestoExecucao.termino_utc
            duracao_monotonica_segundos = [double]$manifestoExecucao.duracao_monotonica_segundos
            codigo_saida = [int]$manifestoExecucao.codigo_saida
            comando = @($manifestoExecucao.comando)
            versoes = $versoes
            achados = $normalizado.Count
            bruto_sha256 = Get-Sha256 (Join-Path $saida "bruto.json")
            normalizado_sha256 = Get-Sha256 (Join-Path $saida "normalizado.json")
            manifesto_sha256 = Get-Sha256 $manifestoEvidencia
            bruto_relativo = "resultados/$execucaoId/tentativa-001/bruto.json"
        })
    }

    $resumo = [ordered]@{
        schema_version = "1.0"
        status = "descartavel"
        finalidade = "fumaca"
        gerado_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.ffffffZ")
        alvo = [ordered]@{
            id_opaco = $AlvoId
            realvuln_id = $RepoId
            url = $RepoUrl
            commit = $RepoCommit
            realvuln_url = $RealVulnUrl
            realvuln_tag = "v1.0"
            realvuln_tag_object = $RealVulnTagObject
            realvuln_commit = $RealVulnCommit
        }
        entrada = [ordered]@{
            algoritmo = "tree-sha256-v1"
            sha256 = $hashEntrada
            arquivos = [int]$inventarioC1.arquivos
            tamanho_total_bytes = [int64]$inventarioC1.tamanho_total_bytes
            inventarios_c1_c2_iguais = $true
            regeneracao_verificada = $true
        }
        imagem = [ordered]@{
            referencia = $Imagem
            id = [string]$ImagemInfo.Id
            os = [string]$ImagemInfo.Os
            arquitetura = [string]$ImagemInfo.Architecture
        }
        execucoes = @($casos)
        exclusao_coleta_principal = "finalidade=fumaca"
    }
    $resumoPath = Join-Path $EvidenciaTemporaria "resumo.json"
    $utf8 = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText(
        $resumoPath,
        ($resumo | ConvertTo-Json -Depth 12) + [Environment]::NewLine,
        $utf8
    )
    Remove-Item -LiteralPath $inventarioRegeneradoPath -Force -ErrorAction Stop
    Move-Item -LiteralPath $EvidenciaTemporaria -Destination $EvidenciaFinal -ErrorAction Stop
    $Concluida = $true
    Write-Host "Fumaça RealVuln concluída: $EvidenciaFinal"
    Write-Host "entrada_sha256=$hashEntrada"
}
finally {
    if (Test-Path -LiteralPath $AlvoRegeneradoPath) {
        Remove-ArvorePropria $AlvoRegeneradoPath $AlvosRoot
    }
    if (Test-Path -LiteralPath $AlvoPath) {
        Remove-ArvorePropria $AlvoPath $AlvosRoot
    }
    if (Test-Path -LiteralPath $Trabalho) {
        Remove-ArvorePropria $Trabalho $BenchmarkRoot
    }
    if (-not $Concluida -and (Test-Path -LiteralPath $EvidenciaTemporaria)) {
        Remove-ArvorePropria $EvidenciaTemporaria $EvidenciasRoot
    }
}
