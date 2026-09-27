[CmdletBinding()]
param(
    [switch]$Verificar,
    [string]$Saida = "evidencias/publicacao/inventario-dados-v1.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$saidaAbsoluta = [IO.Path]::GetFullPath((Join-Path $repo $Saida))
if (-not $saidaAbsoluta.StartsWith($repo, [StringComparison]::OrdinalIgnoreCase)) {
    throw "A saida deve permanecer dentro do repositorio"
}

$linhas = @(& git -C $repo -c core.quotePath=false ls-files --cached --others --exclude-standard -- alvos oracle execucoes resultados)
if ($LASTEXITCODE -ne 0) { throw "git ls-files falhou" }
$caminhos = [Collections.Generic.List[string]]::new()
foreach ($linha in $linhas) {
    $normalizado = ([string]$linha).Replace("\", "/").Trim()
    if ($normalizado) { $caminhos.Add($normalizado) }
}
$arrayCaminhos = $caminhos.ToArray()
[Array]::Sort($arrayCaminhos, [StringComparer]::Ordinal)

function Get-BytesSha256 {
    param([byte[]]$Bytes)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally { $sha.Dispose() }
}

$arquivos = [Collections.Generic.List[object]]::new()
foreach ($relativo in $arrayCaminhos) {
    $absoluto = [IO.Path]::GetFullPath((Join-Path $repo $relativo))
    if (-not $absoluto.StartsWith($repo, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Caminho fora do repositorio: $relativo"
    }
    $item = Get-Item -LiteralPath $absoluto -Force
    if ($item.PSIsContainer) { continue }
    $hash = (Get-FileHash -LiteralPath $absoluto -Algorithm SHA256).Hash.ToLowerInvariant()
    $arquivos.Add([pscustomobject][ordered]@{
        caminho = $relativo
        tamanho_bytes = [long]$item.Length
        sha256 = $hash
    })
}

function Get-ResumoGrupo {
    param([string]$Nome, [object[]]$Registros)
    $texto = (($Registros | ForEach-Object {
        "{0}`t{1}`t{2}`n" -f $_.caminho, $_.tamanho_bytes, $_.sha256
    }) -join "")
    return [pscustomobject][ordered]@{
        grupo = $Nome
        arquivos = @($Registros).Count
        tamanho_bytes = [long](($Registros | Measure-Object tamanho_bytes -Sum).Sum)
        tree_sha256 = Get-BytesSha256 ([Text.UTF8Encoding]::new($false).GetBytes($texto))
    }
}

$grupos = [Collections.Generic.List[object]]::new()
foreach ($raiz in "alvos", "oracle", "execucoes", "resultados") {
    $grupo = @($arquivos | Where-Object { $_.caminho.StartsWith("$raiz/", [StringComparison]::Ordinal) })
    $grupos.Add((Get-ResumoGrupo $raiz $grupo))
}
$textoGlobal = (($arquivos | ForEach-Object {
    "{0}`t{1}`t{2}`n" -f $_.caminho, $_.tamanho_bytes, $_.sha256
}) -join "")

$documento = [ordered]@{
    schema_version = "1.0"
    tipo = "inventario-publicacao-dados"
    algoritmo = "sha256(path-tab-size-tab-sha256-lf)"
    escopo = @("alvos", "oracle", "execucoes", "resultados")
    politica = [ordered]@{
        corpus_integral_publicado = @(
            "ALVO-0002", "ALVO-0003", "ALVO-0005", "ALVO-0007",
            "ALVO-0008", "ALVO-0012", "ALVO-0014", "ALVO-0016",
            "ALVO-0017", "ALVO-0018", "ALVO-0019", "ALVO-0020",
            "ALVO-0023", "ALVO-0024", "ALVO-0025", "ALVO-0026"
        )
        corpus_somente_por_origem_commit_e_hash = @(
            "ALVO-0001", "ALVO-0004", "ALVO-0006", "ALVO-0009",
            "ALVO-0010", "ALVO-0011", "ALVO-0013", "ALVO-0015",
            "ALVO-0021", "ALVO-0022"
        )
        entradas_ia_integrais = "somente para corpus integral publicado"
        eventos_codex = "publicados para todos os 26 alvos; nao incorporam o prompt"
        eventos_cursor = "publicados somente para corpus integral; incorporam o prompt"
    }
    resumo = [ordered]@{
        arquivos = $arquivos.Count
        tamanho_bytes = [long](($arquivos | Measure-Object tamanho_bytes -Sum).Sum)
        publicacao_sha256 = Get-BytesSha256 ([Text.UTF8Encoding]::new($false).GetBytes($textoGlobal))
        grupos = $grupos
    }
    arquivos = $arquivos
}

if ($Verificar) {
    if (-not (Test-Path -LiteralPath $saidaAbsoluta -PathType Leaf)) {
        throw "Inventario ausente: $Saida"
    }
    $gravado = Get-Content -Raw -LiteralPath $saidaAbsoluta | ConvertFrom-Json
    if ($gravado.resumo.publicacao_sha256 -ne $documento.resumo.publicacao_sha256) {
        throw "Inventario divergente: esperado=$($gravado.resumo.publicacao_sha256), observado=$($documento.resumo.publicacao_sha256)"
    }
    if ([int]$gravado.resumo.arquivos -ne $documento.resumo.arquivos) {
        throw "Contagem divergente"
    }
    if ([long]$gravado.resumo.tamanho_bytes -ne $documento.resumo.tamanho_bytes) {
        throw "Tamanho divergente"
    }
    Write-Output "Inventario aprovado: $($documento.resumo.arquivos) arquivos; sha256=$($documento.resumo.publicacao_sha256)"
    exit 0
}

$diretorioSaida = Split-Path -Parent $saidaAbsoluta
if (-not (Test-Path -LiteralPath $diretorioSaida)) {
    New-Item -ItemType Directory -Path $diretorioSaida | Out-Null
}
$json = $documento | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($saidaAbsoluta, $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Inventario gravado: $Saida ($($documento.resumo.arquivos) arquivos)"
