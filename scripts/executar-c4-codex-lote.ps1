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
$executor = Join-Path $PSScriptRoot 'executar-c4-codex.ps1'
$namespace = $Finalidade.ToLowerInvariant()
$repeticoesSelecionadas = @($Repeticoes.Split(',') | ForEach-Object { [int]$_ })
. (Join-Path $PSScriptRoot 'ia/comum.ps1')

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

function Get-EstadoTarefa {
    param(
        [Parameter(Mandatory = $true)][string]$Alvo,
        [Parameter(Mandatory = $true)][int]$Repeticao
    )
    $execucaoId = "C4-$Alvo-R$('{0:D2}' -f $Repeticao)"
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
            if ([string]$manifesto.condicao -eq 'C4' -and
                [string]$manifesto.alvo -eq $Alvo -and
                [int]$manifesto.repeticao -eq $Repeticao -and
                [string]$manifesto.finalidade -eq $Finalidade -and
                [string]$manifesto.modelo_solicitado -eq $Modelo -and
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
} else {
    $alvosSelecionados = $alvosDisponiveis
}
if ($alvosSelecionados.Count -eq 0) { throw 'nenhum alvo encontrado' }
if (-not $SomentePlanejar -and -not $ConfirmarExecucao) {
    throw 'lote externo exige -ConfirmarExecucao; use -SomentePlanejar antes de consumir tokens'
}

$tarefas = [Collections.Generic.List[object]]::new()
foreach ($repeticao in $repeticoesSelecionadas) {
    foreach ($alvo in $alvosSelecionados) {
        $estado = Get-EstadoTarefa -Alvo $alvo -Repeticao $repeticao
        $tarefas.Add([pscustomobject]@{
            alvo = $alvo
            repeticao = $repeticao
            execucao_id = $estado.execucao_id
            tentativa = [int]$estado.proxima_tentativa
            tentativa_sucesso = $estado.tentativa_sucesso
            concluida = $null -ne $estado.sucesso
        })
    }
}

if ($SomentePlanejar) {
    $pendentes = @($tarefas | Where-Object { -not $_.concluida })
    foreach ($tarefa in $pendentes) {
        # Valida alvo, inventario, argumentos e caminhos sem chamar o Codex.
        $planoTexto = & $executor -Alvo $tarefa.alvo -Repeticao $tarefa.repeticao `
            -Tentativa $tarefa.tentativa -Finalidade $Finalidade -Modelo $Modelo `
            -ExecutavelCodex $ExecutavelCodex -TimeoutSegundos $TimeoutSegundos `
            -SomentePlanejar
        [void]($planoTexto | ConvertFrom-Json -ErrorAction Stop)
    }
    [ordered]@{
        schema_version = '1.0'
        tipo = 'plano-lote-ia'
        condicao = 'C4'
        ferramenta = 'codex'
        finalidade = $Finalidade
        modelo = $Modelo
        alvos = $alvosSelecionados.Count
        repeticoes = $repeticoesSelecionadas
        tarefas_total = $tarefas.Count
        tarefas_concluidas = @($tarefas | Where-Object { $_.concluida }).Count
        chamadas_planejadas = $pendentes.Count
        ordem = @($tarefas | ForEach-Object {
            [ordered]@{
                execucao_id = $_.execucao_id
                alvo = $_.alvo
                repeticao = $_.repeticao
                tentativa = $_.tentativa
                acao = if ($_.concluida) { 'pular_concluida' } else { 'executar' }
            }
        })
    } | ConvertTo-Json -Depth 8 -Compress
    return
}

$pendentesExecucao = @($tarefas | Where-Object { -not $_.concluida })
Write-LoteProgresso "C4/${Finalidade}: $($tarefas.Count) tarefas; $($pendentesExecucao.Count) chamadas pendentes"
$resultados = [Collections.Generic.List[object]]::new()
$indice = 0
foreach ($tarefa in $tarefas) {
    $indice++
    if ($tarefa.concluida) {
        Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.execucao_id): ja concluida; pulando"
        $resultados.Add([pscustomobject]@{
            execucao_id = $tarefa.execucao_id
            tentativa = $tarefa.tentativa_sucesso
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
            -ExecutavelCodex $ExecutavelCodex -TimeoutSegundos $TimeoutSegundos `
            -ConfirmarExecucao)
        $manifesto = ($saidaExecutor -join "`n") | ConvertFrom-Json -ErrorAction Stop
        $resultado = if ([string]$manifesto.estado -eq 'concluida' -and [bool]$manifesto.resposta_valida) {
            'concluida'
        } else {
            'falha'
        }
        $resultados.Add([pscustomobject]@{
            execucao_id = $tarefa.execucao_id
            tentativa = $tarefa.tentativa
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
    condicao = 'C4'
    ferramenta = 'codex'
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
$loteId = 'C4-{0}-{1}' -f $namespace, [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$loteDir = Join-Path $repo "resultados/ia/$namespace/lotes/$loteId"
New-Item -ItemType Directory -Path $loteDir -ErrorAction Stop | Out-Null
$resumoPath = Join-Path $loteDir 'resumo.json'
$resumo['resumo_path'] = "resultados/ia/$namespace/lotes/$loteId/resumo.json"
$utf8 = [Text.UTF8Encoding]::new($false)
$resumoJson = $resumo | ConvertTo-Json -Depth 12 -Compress
[IO.File]::WriteAllText($resumoPath, $resumoJson + "`n", $utf8)
Write-LoteProgresso "lote encerrado; resumo=$resumoPath"
$resumo | ConvertTo-Json -Depth 12 -Compress
