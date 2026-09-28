[CmdletBinding()]
param(
    [switch]$Verificar,
    [switch]$GerarInventario,
    [switch]$AceitarLicencaSemgrep,
    [string]$Destino = "docker/regras-semgrep",
    [string]$Inventario = "evidencias/publicacao/inventario-regras-semgrep-v1.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$RepoPrefixo = $Repo.TrimEnd("\", "/") + [IO.Path]::DirectorySeparatorChar
$DockerRoot = [IO.Path]::GetFullPath((Join-Path $Repo "docker"))
$DockerPrefixo = $DockerRoot.TrimEnd("\", "/") + [IO.Path]::DirectorySeparatorChar
$BenchmarkRoot = [IO.Path]::GetFullPath((Join-Path $Repo "benchmark"))
$DestinoFull = [IO.Path]::GetFullPath((Join-Path $Repo $Destino))
$InventarioFull = [IO.Path]::GetFullPath((Join-Path $Repo $Inventario))
$FontesPath = Join-Path $Repo "config/fontes.lock.json"
$ConfiguracaoPath = Join-Path $Repo "evidencias/coleta-c1-c2/configuracao.json"
$LicencaUrl = "https://semgrep.dev/legal/rules-license/"

if ($Verificar -and $GerarInventario) {
    throw "Escolha somente -Verificar ou -GerarInventario"
}
if (-not $DestinoFull.StartsWith($DockerPrefixo, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Destino deve permanecer dentro de docker/"
}
if (-not $InventarioFull.StartsWith($RepoPrefixo, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Inventario deve permanecer dentro do repositorio"
}

$Fontes = Get-Content -Raw -LiteralPath $FontesPath -Encoding UTF8 |
    ConvertFrom-Json -ErrorAction Stop
$Configuracao = Get-Content -Raw -LiteralPath $ConfiguracaoPath -Encoding UTF8 |
    ConvertFrom-Json -ErrorAction Stop
$Fonte = $Fontes.sources.semgrep_rules
$Url = [string]$Fonte.url
$Commit = [string]$Fonte.commit
$PythonTreeEsperada = [string]$Fonte.bundle_sha256
$BundleTreeHistorica = [string]$Configuracao.hashes.regras_bundle_sha256

function Assert-True {
    param([bool]$Condicao, [string]$Mensagem)
    if (-not $Condicao) { throw $Mensagem }
}

function Get-Sha256Bytes {
    param([byte[]]$Bytes)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally { $sha.Dispose() }
}

function Get-RegistrosArvore {
    param([string]$Raiz, [switch]$IgnorarMetadadosGit)

    $raizFull = [IO.Path]::GetFullPath($Raiz).TrimEnd("\", "/")
    $raizItem = Get-Item -LiteralPath $raizFull -Force -ErrorAction Stop
    Assert-True $raizItem.PSIsContainer "Raiz deve ser diretorio: $raizFull"
    Assert-True (($raizItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
        "Raiz nao pode ser reparse point: $raizFull"

    $pendentes = [Collections.Generic.Stack[string]]::new()
    $pendentes.Push($raizFull)
    $registros = [Collections.Generic.List[object]]::new()
    while ($pendentes.Count -gt 0) {
        $diretorio = $pendentes.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $diretorio -Force) {
            $relativo = $item.FullName.Substring($raizFull.Length).TrimStart("\", "/").Replace("\", "/")
            if ($IgnorarMetadadosGit -and
                ($relativo -eq ".git" -or $relativo.StartsWith(".git/", [StringComparison]::Ordinal))) {
                continue
            }
            Assert-True (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
                "Link ou reparse point proibido no bundle: $relativo"
            if ($item.PSIsContainer) {
                $pendentes.Push($item.FullName)
                continue
            }
            $sha = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            $sortKey = [BitConverter]::ToString([Text.Encoding]::UTF8.GetBytes($relativo))
            $registros.Add([pscustomobject][ordered]@{
                caminho = $relativo
                tamanho_bytes = [long]$item.Length
                sha256 = $sha
                _sort_key = $sortKey
            })
        }
    }
    return @($registros | Sort-Object -Property _sort_key | Select-Object caminho, tamanho_bytes, sha256)
}

function Get-TreeSha256 {
    param([object[]]$Registros, [string]$Prefixo = "")

    Assert-True ($Registros.Count -gt 0) "Arvore vazia"
    $incremental = [Security.Cryptography.IncrementalHash]::CreateHash(
        [Security.Cryptography.HashAlgorithmName]::SHA256
    )
    try {
        $incremental.AppendData([Text.Encoding]::UTF8.GetBytes("tree-sha256-v1`0"))
        foreach ($registro in $Registros) {
            $caminho = [string]$registro.caminho
            if ($Prefixo) {
                Assert-True $caminho.StartsWith($Prefixo, [StringComparison]::Ordinal) `
                    "Caminho fora do prefixo esperado: $caminho"
                $caminho = $caminho.Substring($Prefixo.Length)
            }
            $linha = "{0}`0{1}`0{2}`n" -f $caminho, $registro.tamanho_bytes, $registro.sha256
            $incremental.AppendData([Text.Encoding]::UTF8.GetBytes($linha))
        }
        return ([BitConverter]::ToString($incremental.GetHashAndReset())).Replace("-", "").ToLowerInvariant()
    }
    finally { $incremental.Dispose() }
}

function Get-EstadoBundle {
    param([string]$Raiz)

    $todos = @(Get-RegistrosArvore -Raiz $Raiz -IgnorarMetadadosGit)
    $python = @($todos | Where-Object {
        ([string]$_.caminho).StartsWith("python/", [StringComparison]::Ordinal)
    })
    $bundleTree = Get-TreeSha256 -Registros $todos
    $pythonTree = Get-TreeSha256 -Registros $python -Prefixo "python/"
    return [pscustomobject][ordered]@{
        todos = $todos
        python = $python
        bundle_tree_sha256 = $bundleTree
        python_tree_sha256 = $pythonTree
    }
}

function Assert-Pinos {
    param($Estado)
    Assert-True ($Estado.todos.Count -eq 732) `
        "Bundle deve conter 732 arquivos; observado=$($Estado.todos.Count)"
    Assert-True ($Estado.python.Count -eq 717) `
        "python/ deve conter 717 arquivos; observado=$($Estado.python.Count)"
    Assert-True ($Estado.python_tree_sha256 -eq $PythonTreeEsperada) `
        "Hash de python/ diverge; esperado=$PythonTreeEsperada observado=$($Estado.python_tree_sha256)"
}

function Assert-Inventario {
    param($Estado)
    Assert-True (Test-Path -LiteralPath $InventarioFull -PathType Leaf) `
        "Inventario publicado ausente: $Inventario"
    $gravado = Get-Content -Raw -LiteralPath $InventarioFull -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$gravado.origem.url -eq $Url) "URL do inventario diverge"
    Assert-True ([string]$gravado.origem.commit -eq $Commit) "Commit do inventario diverge"
    Assert-True ([string]$gravado.resumo.worktree_tree_sha256 -eq $Estado.bundle_tree_sha256) `
        "Hash do worktree diverge do inventario"
    Assert-True ([string]$gravado.resumo.python_tree_sha256 -eq $Estado.python_tree_sha256) `
        "Hash de python/ diverge do inventario"
    $esperados = @($gravado.arquivos)
    Assert-True ($esperados.Count -eq $Estado.todos.Count) "Contagem do inventario diverge"
    for ($i = 0; $i -lt $esperados.Count; $i++) {
        $esperado = $esperados[$i]
        $observado = $Estado.todos[$i]
        Assert-True (
            [string]$esperado.caminho -ceq [string]$observado.caminho -and
            [long]$esperado.tamanho_bytes -eq [long]$observado.tamanho_bytes -and
            [string]$esperado.sha256 -eq [string]$observado.sha256
        ) "Arquivo diverge do inventario na posicao $i"
    }
}

function Write-Inventario {
    param($Estado)
    $documento = [ordered]@{
        schema_version = "1.0"
        tipo = "inventario-regras-semgrep-nao-redistribuidas"
        conteudo_das_regras_incluido = $false
        motivo = "A Semgrep Rules License v1.0 proibe distribuir ou disponibilizar as regras a terceiros."
        licenca = [ordered]@{
            nome = "Semgrep Rules License v1.0"
            url = $LicencaUrl
        }
        origem = [ordered]@{
            tipo = "git"
            url = $Url
            commit = $Commit
            sparse_checkout = @("python")
        }
        algoritmo_arvore = "sha256(tree-sha256-v1-nul-path-nul-size-nul-content-sha256-lf)"
        observacao_hash_historico = $(
            "A configuracao congelada registrou um hash da raiz que incluia metadados " +
            "locais .git. Esse valor e preservado como evidencia historica, mas nao e " +
            "usado para reconstruir as regras. O hash python_tree_sha256 identifica os " +
            "717 arquivos efetivamente fornecidos ao Semgrep."
        )
        resumo = [ordered]@{
            arquivos_worktree = $Estado.todos.Count
            arquivos_python = $Estado.python.Count
            tamanho_worktree_bytes = [long](($Estado.todos | Measure-Object tamanho_bytes -Sum).Sum)
            tamanho_python_bytes = [long](($Estado.python | Measure-Object tamanho_bytes -Sum).Sum)
            worktree_tree_sha256 = $Estado.bundle_tree_sha256
            python_tree_sha256 = $Estado.python_tree_sha256
            configuracao_historica_tree_sha256 = $BundleTreeHistorica
            configuracao_historica_inclui_metadados_git = $true
        }
        arquivos = $Estado.todos
    }
    $diretorio = Split-Path -Parent $InventarioFull
    if (-not (Test-Path -LiteralPath $diretorio)) {
        New-Item -ItemType Directory -Path $diretorio -ErrorAction Stop | Out-Null
    }
    $json = $documento | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($InventarioFull, $json + "`n", [Text.UTF8Encoding]::new($false))
}

function Invoke-Git {
    param([string[]]$Argumentos, [string]$Contexto)
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $saida = @(& git -c core.hooksPath=NUL -c protocol.file.allow=never @Argumentos 2>&1)
        $codigo = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $anterior }
    if ($codigo -ne 0) {
        throw "$Contexto falhou (codigo $codigo): $($saida -join ' ')"
    }
    return @($saida | ForEach-Object { [string]$_ })
}

function Remove-ArvoreTemporaria {
    param([string]$Caminho, [string]$RaizPermitida)
    if (-not (Test-Path -LiteralPath $Caminho)) { return }
    $full = [IO.Path]::GetFullPath($Caminho)
    $prefixo = [IO.Path]::GetFullPath($RaizPermitida).TrimEnd("\", "/") +
        [IO.Path]::DirectorySeparatorChar
    Assert-True $full.StartsWith($prefixo, [StringComparison]::OrdinalIgnoreCase) `
        "Limpeza recusou caminho fora da raiz permitida"
    $item = Get-Item -LiteralPath $full -Force
    Assert-True (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
        "Limpeza recusou reparse point"
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
}

if ($Verificar -or $GerarInventario) {
    Assert-True (Test-Path -LiteralPath $DestinoFull -PathType Container) `
        "Bundle local ausente: $Destino"
    $estado = Get-EstadoBundle -Raiz $DestinoFull
    Assert-Pinos $estado
    if ($GerarInventario) {
        Write-Inventario $estado
        Write-Output "Inventario gravado: $Inventario ($($estado.todos.Count) arquivos)"
    }
    else {
        Assert-Inventario $estado
        Write-Output "Regras aprovadas: commit=$Commit; worktree=$($estado.bundle_tree_sha256); python=$($estado.python_tree_sha256)"
    }
    exit 0
}

Assert-True $AceitarLicencaSemgrep `
    "Leia $LicencaUrl e execute novamente com -AceitarLicencaSemgrep"
Assert-True (-not (Test-Path -LiteralPath $DestinoFull)) `
    "Destino ja existe e nao sera sobrescrito: $Destino"
if (-not (Test-Path -LiteralPath $BenchmarkRoot)) {
    New-Item -ItemType Directory -Path $BenchmarkRoot -ErrorAction Stop | Out-Null
}
$token = [guid]::NewGuid().ToString("N")
$cache = Join-Path $BenchmarkRoot ".semgrep-rules-$token"
$temporario = Join-Path (Split-Path -Parent $DestinoFull) ".regras-semgrep-$token"

try {
    Invoke-Git @("clone", "--filter=blob:none", "--no-checkout", "--no-tags", $Url, $cache) `
        "clone das regras Semgrep" | Out-Null
    Invoke-Git @("-C", $cache, "config", "core.autocrlf", "false") `
        "configuracao de fim de linha" | Out-Null
    Invoke-Git @("-C", $cache, "config", "submodule.recurse", "false") `
        "bloqueio de submodulos" | Out-Null
    Invoke-Git @("-C", $cache, "fetch", "--depth=1", "origin", $Commit) `
        "aquisicao do commit fixado" | Out-Null
    $observado = [string](Invoke-Git @("-C", $cache, "rev-parse", "FETCH_HEAD^{commit}") `
        "resolucao do commit")[0]
    Assert-True ($observado.Trim() -eq $Commit) "Commit adquirido diverge do lock"
    Invoke-Git @("-C", $cache, "sparse-checkout", "init", "--cone") `
        "inicio do sparse checkout" | Out-Null
    Invoke-Git @("-C", $cache, "sparse-checkout", "set", "python") `
        "selecao de python/" | Out-Null
    Invoke-Git @("-C", $cache, "checkout", "--detach", $Commit) `
        "checkout do commit fixado" | Out-Null

    New-Item -ItemType Directory -Path $temporario -ErrorAction Stop | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $cache -Force) {
        if ($item.Name -eq ".git") { continue }
        Assert-True (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
            "Entrada insegura no checkout: $($item.Name)"
        Copy-Item -LiteralPath $item.FullName -Destination $temporario -Recurse -ErrorAction Stop
    }
    $estado = Get-EstadoBundle -Raiz $temporario
    Assert-Pinos $estado
    Assert-Inventario $estado
    Move-Item -LiteralPath $temporario -Destination $DestinoFull -ErrorAction Stop
    Write-Output "Regras adquiridas e verificadas em $Destino"
}
finally {
    Remove-ArvoreTemporaria -Caminho $cache -RaizPermitida $BenchmarkRoot
    Remove-ArvoreTemporaria -Caminho $temporario -RaizPermitida (Split-Path -Parent $DestinoFull)
}
