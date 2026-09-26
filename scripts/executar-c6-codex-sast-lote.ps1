[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('piloto','coleta')]
    [string]$Finalidade,

    [Parameter(Mandatory = $true)]
    [ValidateSet('1','2','3','1,2,3')]
    [string]$Repeticoes,

    [ValidatePattern('^ALVO-[0-9]{4}$')]
    [string[]]$Alvos,

    [string]$AlertasDiretorio,

    [string]$LockAlertas,

    [ValidateNotNullOrEmpty()]
    [string]$Modelo = 'gpt-5.6-luna',

    [ValidateNotNullOrEmpty()]
    [string]$ExecutavelCodex = 'codex',

    [ValidateRange(1,86400)]
    [int]$TimeoutSegundos = 3600,

    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao,
    [switch]$PararEmFalha
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$executor = Join-Path $PSScriptRoot 'executar-c6-codex-sast.ps1'
$namespace = $Finalidade.ToLowerInvariant()
$repeticoesSelecionadas = @($Repeticoes.Split(',') | ForEach-Object { [int]$_ })
. (Join-Path $PSScriptRoot 'ia/comum.ps1')

if ([string]::IsNullOrWhiteSpace($AlertasDiretorio)) {
    $AlertasDiretorio = Join-Path $repo 'execucoes/ia/alertas'
}
elseif (-not [IO.Path]::IsPathRooted($AlertasDiretorio)) {
    $AlertasDiretorio = Join-Path $repo $AlertasDiretorio
}
$AlertasDiretorio = [IO.Path]::GetFullPath($AlertasDiretorio)
if ([string]::IsNullOrWhiteSpace($LockAlertas)) {
    $LockAlertas = Join-Path $repo 'config/agentes/alertas-sast-c6-v1.lock.json'
}
elseif (-not [IO.Path]::IsPathRooted($LockAlertas)) {
    $LockAlertas = Join-Path $repo $LockAlertas
}
$LockAlertas = [IO.Path]::GetFullPath($LockAlertas)
Assert-Ia (Test-Path -LiteralPath $LockAlertas -PathType Leaf) `
    "lock de alertas SAST ausente: $LockAlertas"
$lockDocumento = Read-IaJson $LockAlertas
Assert-Ia ([string]$lockDocumento.tipo -eq 'lock-alertas-sast-v1') `
    'tipo inesperado no lock de alertas SAST'

function Write-LoteProgresso {
    param([Parameter(Mandatory = $true)][string]$Mensagem)
    $timestamp = [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')
    [Console]::Error.WriteLine("[LOTE $timestamp] $Mensagem")
}

function Read-ManifestoSeguro {
    param([Parameter(Mandatory = $true)][string]$Caminho)
    try {
        return Get-Content -LiteralPath $Caminho -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "manifesto invalido: $Caminho`: $($_.Exception.Message)"
    }
}

function Get-AlertasAlvo {
    param([Parameter(Mandatory = $true)][string]$Alvo)
    $caminho = Join-Path $AlertasDiretorio "$Alvo-alertas-sast.json"
    Assert-Ia (Test-Path -LiteralPath $caminho -PathType Leaf) `
        "alertas SAST ausentes para ${Alvo}: $caminho"
    $documento = Read-IaJson $caminho
    Assert-Ia ([string]$documento.tipo -eq 'alertas-sast-v1') `
        "tipo de alertas inesperado para $Alvo"
    Assert-Ia ([string]$documento.alvo -eq $Alvo) `
        "arquivo de alertas pertence a outro alvo: $Alvo"
    $fontes = @($documento.fontes | ForEach-Object { [string]$_.condicao } | Sort-Object -Unique)
    Assert-Ia (($fontes -join ',') -eq 'C1,C2') `
        "alertas de $Alvo devem preservar fontes C1 e C2"
    $entradaLock = @($lockDocumento.alvos | Where-Object { [string]$_.alvo -eq $Alvo })
    Assert-Ia ($entradaLock.Count -eq 1) `
        "lock de alertas SAST não contém exatamente um $Alvo"
    $sha256 = Get-IaSha256 $caminho
    Assert-Ia ($sha256 -eq [string]$entradaLock[0].sha256) `
        "hash dos alertas SAST diverge do lock para $Alvo"
    Assert-Ia ([int]$documento.quantidade_alertas -eq [int]$entradaLock[0].quantidade_alertas) `
        "quantidade de alertas diverge do lock para $Alvo"
    return [pscustomobject]@{
        caminho = $caminho
        sha256 = $sha256
        quantidade_alertas = [int]$documento.quantidade_alertas
    }
}

function Get-EstadoTarefa {
    param(
        [Parameter(Mandatory = $true)][string]$Alvo,
        [Parameter(Mandatory = $true)][int]$Repeticao,
        [Parameter(Mandatory = $true)][string]$AlertasSha256
    )
    $execucaoId = "C6-$Alvo-R$('{0:D2}' -f $Repeticao)"
    $raiz = Join-Path $repo "resultados/ia/$namespace/$execucaoId"
    $maiorTentativa = 0
    $sucesso = $null
    if (Test-Path -LiteralPath $raiz -PathType Container) {
        foreach ($diretorio in @(Get-ChildItem -LiteralPath $raiz -Directory -ErrorAction Stop)) {
            if ($diretorio.Name -notmatch '^tentativa-([0-9]{3,})$') { continue }
            $numero = [int]$Matches[1]
            if ($numero -gt $maiorTentativa) { $maiorTentativa = $numero }
            $manifestoPath = Join-Path $diretorio.FullName 'manifesto.json'
            if (-not (Test-Path -LiteralPath $manifestoPath -PathType Leaf)) { continue }
            $manifesto = Read-ManifestoSeguro $manifestoPath
            $respostaPath = Join-Path $diretorio.FullName 'resposta-bruta.txt'
            $respostaAindaValida = $false
            if (Test-Path -LiteralPath $respostaPath -PathType Leaf) {
                $respostaBruta = Get-Content -LiteralPath $respostaPath -Raw -Encoding UTF8
                $entradaRaiz = Join-Path $repo "alvos/corpus-v1/$Alvo"
                $respostaAindaValida = [bool](
                    Test-IaRelatorio -Resposta $respostaBruta -EntradaRaiz $entradaRaiz
                ).valido
            }
            if ([string]$manifesto.condicao -eq 'C6' -and
                [string]$manifesto.alvo -eq $Alvo -and
                [int]$manifesto.repeticao -eq $Repeticao -and
                [string]$manifesto.finalidade -eq $Finalidade -and
                [string]$manifesto.modelo_solicitado -eq $Modelo -and
                [string]$manifesto.alertas_sast_sha256 -eq $AlertasSha256 -and
                [string]$manifesto.estado -eq 'concluida' -and
                [bool]$manifesto.resposta_valida -and
                $respostaAindaValida) {
                $sucesso = $manifesto
            }
        }
    }
    return [pscustomobject]@{
        execucao_id = $execucaoId
        sucesso = $sucesso
        tentativa_sucesso = if ($null -eq $sucesso) { $null } else { [int]$sucesso.tentativa }
        proxima_tentativa = $maiorTentativa + 1
    }
}

$alvosDisponiveis = @(Get-ChildItem -LiteralPath (Join-Path $repo 'alvos/corpus-v1') `
    -Directory -ErrorAction Stop | Where-Object { $_.Name -match '^ALVO-[0-9]{4}$' } |
    Sort-Object Name | Select-Object -ExpandProperty Name)
if ($null -ne $Alvos -and $Alvos.Count -gt 0) {
    $alvosSelecionados = @($Alvos | Sort-Object -Unique)
    foreach ($alvo in $alvosSelecionados) {
        if ($alvo -notin $alvosDisponiveis) { throw "alvo inexistente no corpus: $alvo" }
    }
}
else {
    $alvosSelecionados = $alvosDisponiveis
}
if ($alvosSelecionados.Count -eq 0) { throw 'nenhum alvo encontrado' }
if (-not $SomentePlanejar -and -not $ConfirmarExecucao) {
    throw 'lote externo exige -ConfirmarExecucao; use -SomentePlanejar antes de consumir tokens'
}

$alertasPorAlvo = @{}
foreach ($alvo in $alvosSelecionados) {
    $alertasPorAlvo[$alvo] = Get-AlertasAlvo -Alvo $alvo
}

$tarefas = [Collections.Generic.List[object]]::new()
foreach ($repeticao in $repeticoesSelecionadas) {
    foreach ($alvo in $alvosSelecionados) {
        $alertas = $alertasPorAlvo[$alvo]
        $estado = Get-EstadoTarefa -Alvo $alvo -Repeticao $repeticao `
            -AlertasSha256 $alertas.sha256
        $tarefas.Add([pscustomobject]@{
            alvo = $alvo
            repeticao = $repeticao
            execucao_id = $estado.execucao_id
            tentativa = [int]$estado.proxima_tentativa
            tentativa_sucesso = $estado.tentativa_sucesso
            concluida = $null -ne $estado.sucesso
            alertas_path = [string]$alertas.caminho
            alertas_sha256 = [string]$alertas.sha256
            quantidade_alertas = [int]$alertas.quantidade_alertas
        })
    }
}

if ($SomentePlanejar) {
    $pendentes = @($tarefas | Where-Object { -not $_.concluida })
    foreach ($tarefa in $pendentes) {
        $planoTexto = & $executor -Alvo $tarefa.alvo -Repeticao $tarefa.repeticao `
            -Tentativa $tarefa.tentativa -Finalidade $Finalidade -Modelo $Modelo `
            -AlertasSast $tarefa.alertas_path -ExecutavelCodex $ExecutavelCodex `
            -TimeoutSegundos $TimeoutSegundos -SomentePlanejar
        [void]($planoTexto | ConvertFrom-Json -ErrorAction Stop)
    }
    [ordered]@{
        schema_version = '1.0'
        tipo = 'plano-lote-ia'
        condicao = 'C6'
        ferramenta = 'codex'
        hibrido = $true
        finalidade = $Finalidade
        modelo = $Modelo
        alvos = $alvosSelecionados.Count
        repeticoes = $repeticoesSelecionadas
        tarefas_total = $tarefas.Count
        tarefas_concluidas = @($tarefas | Where-Object { $_.concluida }).Count
        chamadas_planejadas = $pendentes.Count
        alertas_total_por_repeticao = ($alertasPorAlvo.Values |
            Measure-Object quantidade_alertas -Sum).Sum
        ordem = @($tarefas | ForEach-Object {
            [ordered]@{
                execucao_id = $_.execucao_id
                alvo = $_.alvo
                repeticao = $_.repeticao
                tentativa = $_.tentativa
                alertas_sast_sha256 = $_.alertas_sha256
                quantidade_alertas = $_.quantidade_alertas
                acao = if ($_.concluida) { 'pular_concluida' } else { 'executar' }
            }
        })
    } | ConvertTo-Json -Depth 8 -Compress
    return
}

$pendentesExecucao = @($tarefas | Where-Object { -not $_.concluida })
Write-LoteProgresso "C6/${Finalidade}: $($tarefas.Count) tarefas; $($pendentesExecucao.Count) chamadas pendentes"
$resultados = [Collections.Generic.List[object]]::new()
$indice = 0
foreach ($tarefa in $tarefas) {
    $indice++
    if ($tarefa.concluida) {
        Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.execucao_id): ja concluida; pulando"
        $resultados.Add([pscustomobject]@{
            execucao_id = $tarefa.execucao_id
            tentativa = $tarefa.tentativa_sucesso
            alertas_sast_sha256 = $tarefa.alertas_sha256
            resultado = 'pulada_concluida'
            estado = 'concluida'
            falha = $null
        })
        continue
    }

    Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.execucao_id)/tentativa-$('{0:D3}' -f $tarefa.tentativa): iniciando"
    try {
        $saidaExecutor = @(& $executor -Alvo $tarefa.alvo -Repeticao $tarefa.repeticao `
            -Tentativa $tarefa.tentativa -Finalidade $Finalidade -Modelo $Modelo `
            -AlertasSast $tarefa.alertas_path -ExecutavelCodex $ExecutavelCodex `
            -TimeoutSegundos $TimeoutSegundos -ConfirmarExecucao)
        $manifesto = ($saidaExecutor -join "`n") | ConvertFrom-Json -ErrorAction Stop
        $resultado = if ([string]$manifesto.estado -eq 'concluida' -and [bool]$manifesto.resposta_valida) {
            'concluida'
        }
        else {
            'falha'
        }
        $resultados.Add([pscustomobject]@{
            execucao_id = $tarefa.execucao_id
            tentativa = $tarefa.tentativa
            alertas_sast_sha256 = $tarefa.alertas_sha256
            resultado = $resultado
            estado = [string]$manifesto.estado
            falha = $manifesto.falha_mensagem
        })
        if ($resultado -eq 'falha') {
            Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.execucao_id): falha; seguindo para a proxima tarefa"
            if ($PararEmFalha) { break }
        }
    }
    catch {
        $resultados.Add([pscustomobject]@{
            execucao_id = $tarefa.execucao_id
            tentativa = $tarefa.tentativa
            alertas_sast_sha256 = $tarefa.alertas_sha256
            resultado = 'falha_lote'
            estado = 'falha'
            falha = $_.Exception.Message
        })
        Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.execucao_id): falha do lote; seguindo para a proxima tarefa"
        if ($PararEmFalha) { break }
    }
}

$resumo = [ordered]@{
    schema_version = '1.0'
    tipo = 'resumo-lote-ia'
    condicao = 'C6'
    ferramenta = 'codex'
    hibrido = $true
    finalidade = $Finalidade
    modelo = $Modelo
    inicio_ordem = @($tarefas | ForEach-Object { $_.execucao_id })
    tarefas_total = $tarefas.Count
    tarefas_processadas = $resultados.Count
    concluidas = @($resultados | Where-Object { $_.resultado -eq 'concluida' }).Count
    puladas_concluidas = @($resultados | Where-Object { $_.resultado -eq 'pulada_concluida' }).Count
    falhas = @($resultados | Where-Object { $_.resultado -in @('falha','falha_lote') }).Count
    resultados = @($resultados)
}
$loteId = 'C6-{0}-{1}' -f $namespace, [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$loteDir = Join-Path $repo "resultados/ia/$namespace/lotes/$loteId"
New-Item -ItemType Directory -Path $loteDir -ErrorAction Stop | Out-Null
$resumoPath = Join-Path $loteDir 'resumo.json'
$resumo['resumo_path'] = "resultados/ia/$namespace/lotes/$loteId/resumo.json"
$utf8 = [Text.UTF8Encoding]::new($false)
$resumoJson = $resumo | ConvertTo-Json -Depth 12 -Compress
[IO.File]::WriteAllText($resumoPath, $resumoJson + "`n", $utf8)
Write-LoteProgresso "lote encerrado; resumo=$resumoPath"
$resumo | ConvertTo-Json -Depth 12 -Compress
