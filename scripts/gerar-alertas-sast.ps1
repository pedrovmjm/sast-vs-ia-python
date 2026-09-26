[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^ALVO-[0-9]{4}$')]
    [string]$Alvo,

    [string]$Destino,

    [switch]$SomentePlanejar
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Utf8 = [Text.UTF8Encoding]::new($false)

function Assert-True([bool]$Condicao, [string]$Mensagem) {
    if (-not $Condicao) { throw $Mensagem }
}

function Read-Json([string]$Caminho) {
    try {
        return Get-Content -LiteralPath $Caminho -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch { throw "JSON inválido em $Caminho`: $($_.Exception.Message)" }
}

function Get-Sha256([string]$Caminho) {
    return (Get-FileHash -LiteralPath $Caminho -Algorithm SHA256).Hash.ToLowerInvariant()
}

if (-not $Destino) {
    $Destino = Join-Path $Repo "execucoes/ia/alertas/$Alvo-alertas-sast.json"
}
elseif (-not [IO.Path]::IsPathRooted($Destino)) {
    $Destino = Join-Path $Repo $Destino
}
$Destino = [IO.Path]::GetFullPath($Destino)
$raizPermitida = [IO.Path]::GetFullPath((Join-Path $Repo 'execucoes/ia/alertas')).TrimEnd('\','/')
$comparacao = [StringComparison]::OrdinalIgnoreCase
Assert-True ($Destino.StartsWith($raizPermitida + [IO.Path]::DirectorySeparatorChar, $comparacao)) `
    'destino deve ficar sob execucoes/ia/alertas/'
Assert-True (-not (Test-Path -LiteralPath $Destino)) "destino já existe: $Destino"

$fontes = [Collections.Generic.List[object]]::new()
$achadosFonte = [Collections.Generic.List[object]]::new()
foreach ($condicao in @('C1','C2')) {
    $execucaoId = "$condicao-$Alvo-R01"
    $execucao = Join-Path $Repo "resultados/$execucaoId"
    Assert-True (Test-Path -LiteralPath $execucao -PathType Container) `
        "resultado SAST ausente: $execucaoId"
    $candidatas = [Collections.Generic.List[object]]::new()
    foreach ($tentativaDir in @(Get-ChildItem -LiteralPath $execucao -Directory -Filter 'tentativa-*')) {
        $manifestoPath = Join-Path $tentativaDir.FullName 'manifesto.json'
        $normalizadoPath = Join-Path $tentativaDir.FullName 'normalizado.json'
        if (-not (Test-Path -LiteralPath $manifestoPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $normalizadoPath -PathType Leaf)) { continue }
        $manifesto = Read-Json $manifestoPath
        if ([string]$manifesto.estado -eq 'concluida' -and
            [string]$manifesto.finalidade -eq 'coleta' -and
            [string]$manifesto.condicao -eq $condicao -and
            [string]$manifesto.alvo -eq $Alvo) {
            $candidatas.Add([pscustomobject]@{
                tentativa = [int]$manifesto.tentativa
                manifesto = $manifesto
                manifesto_path = $manifestoPath
                normalizado_path = $normalizadoPath
            })
        }
    }
    Assert-True ($candidatas.Count -gt 0) "nenhuma tentativa concluída de $execucaoId"
    $selecionada = @($candidatas | Sort-Object tentativa)[-1]
    $normalizado = Read-Json $selecionada.normalizado_path
    $lista = @($normalizado)
    $fontes.Add([ordered]@{
        condicao = $condicao
        ferramenta = [string]$selecionada.manifesto.ferramenta
        execucao_id = $execucaoId
        tentativa = [int]$selecionada.tentativa
        manifesto_sha256 = Get-Sha256 $selecionada.manifesto_path
        normalizado_sha256 = Get-Sha256 $selecionada.normalizado_path
        achados = $lista.Count
    })
    foreach ($achado in $lista) {
        $achadosFonte.Add([pscustomobject]@{ condicao = $condicao; achado = $achado })
    }
}

$grupos = [ordered]@{}
foreach ($entrada in $achadosFonte) {
    $a = $entrada.achado
    $chave = @(
        [string]$a.arquivo,
        [string]$a.linha_inicial,
        [string]$a.linha_final,
        [string]$a.cwe,
        [string]$a.severidade,
        [string]$a.descricao
    ) -join [string][char]0x1f
    if (-not $grupos.Contains($chave)) {
        $grupos[$chave] = [pscustomobject]@{
            arquivo = [string]$a.arquivo
            linha_inicial = $a.linha_inicial
            linha_final = $a.linha_final
            cwe = $a.cwe
            severidade = $a.severidade
            descricao = [string]$a.descricao
            origens = [Collections.Generic.List[object]]::new()
        }
    }
    $grupos[$chave].origens.Add([ordered]@{
        condicao = [string]$entrada.condicao
        ferramenta = [string]$a.ferramenta
        execucao_id = [string]$a.execucao_id
        regra = $a.regra
        confianca = $a.confianca
    })
}

$alertas = [Collections.Generic.List[object]]::new()
foreach ($grupo in @($grupos.Values | Sort-Object arquivo,linha_inicial,linha_final,cwe,descricao)) {
    $alertas.Add([ordered]@{
        arquivo = $grupo.arquivo
        linha_inicial = $grupo.linha_inicial
        linha_final = $grupo.linha_final
        cwe = $grupo.cwe
        severidade = $grupo.severidade
        descricao = $grupo.descricao
        origens = @($grupo.origens | Sort-Object condicao,ferramenta,regra)
    })
}

$documento = [ordered]@{
    schema_version = '1.0'
    tipo = 'alertas-sast-v1'
    alvo = $Alvo
    politica_uniao = 'deduplicacao-exata-v1'
    campos_da_chave = @('arquivo','linha_inicial','linha_final','cwe','severidade','descricao')
    fontes = @($fontes)
    quantidade_antes_deduplicacao = $achadosFonte.Count
    quantidade_alertas = $alertas.Count
    alertas = @($alertas)
}

if ($SomentePlanejar) {
    [ordered]@{
        schema_version = '1.0'
        tipo = 'plano-alertas-sast'
        alvo = $Alvo
        destino = $Destino
        fontes = @($fontes)
        quantidade_antes_deduplicacao = $achadosFonte.Count
        quantidade_alertas = $alertas.Count
    } | ConvertTo-Json -Depth 10 -Compress
    return
}

$pai = Split-Path -Parent $Destino
if (-not (Test-Path -LiteralPath $pai)) {
    New-Item -ItemType Directory -Path $pai -Force -ErrorAction Stop | Out-Null
}
$json = $documento | ConvertTo-Json -Depth 20 -Compress
[IO.File]::WriteAllText($Destino, $json + "`n", $Utf8)
[ordered]@{
    schema_version = '1.0'
    tipo = 'alertas-sast-gerados'
    alvo = $Alvo
    destino = $Destino
    sha256 = Get-Sha256 $Destino
    quantidade_alertas = $alertas.Count
} | ConvertTo-Json -Compress
