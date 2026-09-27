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
    [string]$Modelo = 'gpt-5.6-luna-medium',

    [ValidateSet('WSL','Nativo')]
    [string]$ModoCursor = 'Nativo',

    [string]$DistribuicaoWsl,

    [ValidateNotNullOrEmpty()]
    [string]$ExecutavelCursor = 'agent',

    [ValidateRange(1,86400)]
    [int]$TimeoutSegundos = 3600,

    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao,
    [switch]$PararEmFalha
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$executor = Join-Path $PSScriptRoot 'executar-c3-cursor.ps1'
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

function Get-CursorFixado {
    if ($ModoCursor -eq 'WSL') {
        $argsVersao = @()
        if ($DistribuicaoWsl) { $argsVersao += @('-d', $DistribuicaoWsl) }
        $argsVersao += @('--exec', $ExecutavelCursor, '--version')
        $linhas = @(& wsl.exe @argsVersao 2>&1)
        if ($LASTEXITCODE -ne 0 -or $linhas.Count -eq 0) {
            throw "não foi possível obter a versão do Cursor no WSL: $($linhas -join ' ')"
        }
        return [pscustomobject]@{
            versao = ([string]$linhas[-1]).Trim()
            executavel = $ExecutavelCursor
            fixado_por_caminho = $false
        }
    }

    $resolvido = @(Get-Command $ExecutavelCursor -CommandType Application,ExternalScript `
        -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($resolvido.Count -eq 0) {
        throw "Cursor Agent nativo não encontrado no PATH: $ExecutavelCursor"
    }
    $origem = [string]$resolvido[0].Source
    if (-not $origem) { $origem = [string]$resolvido[0].Path }
    $extensao = [IO.Path]::GetExtension($origem).ToLowerInvariant()
    if ($extensao -in @('.cmd','.bat')) {
        $companheiro = [IO.Path]::ChangeExtension($origem, '.ps1')
        if (-not (Test-Path -LiteralPath $companheiro -PathType Leaf)) {
            throw "launcher $extensao do Cursor não possui wrapper PowerShell: $origem"
        }
        $origem = $companheiro
        $extensao = '.ps1'
    }

    if ($extensao -eq '.ps1') {
        $windowsPowerShell = Join-Path $env:SystemRoot `
            'System32/WindowsPowerShell/v1.0/powershell.exe'
        $linhas = @(& $windowsPowerShell -NoLogo -NoProfile -NonInteractive `
            -ExecutionPolicy Bypass -File $origem --version 2>&1)
        if ($LASTEXITCODE -ne 0 -or $linhas.Count -eq 0) {
            throw "não foi possível obter a versão do Cursor nativo: $($linhas -join ' ')"
        }
        $versao = ([string]$linhas[-1]).Trim()
        $diretorioOrigem = Split-Path -Parent $origem
        $fixado = if (Test-Path -LiteralPath (Join-Path $diretorioOrigem 'node.exe') -PathType Leaf) {
            $origem
        } else {
            Join-Path $diretorioOrigem "versions/$versao/cursor-agent.ps1"
        }
        if (-not (Test-Path -LiteralPath $fixado -PathType Leaf)) {
            throw "versão observada do Cursor não pode ser fixada por caminho: $fixado"
        }
        return [pscustomobject]@{
            versao = $versao
            executavel = $fixado
            fixado_por_caminho = $true
        }
    }

    $linhas = @(& $origem --version 2>&1)
    if ($LASTEXITCODE -ne 0 -or $linhas.Count -eq 0) {
        throw "não foi possível obter a versão do Cursor nativo: $($linhas -join ' ')"
    }
    return [pscustomobject]@{
        versao = ([string]$linhas[-1]).Trim()
        executavel = $origem
        fixado_por_caminho = $true
    }
}

$cursorFixado = Get-CursorFixado
$versaoCursor = [string]$cursorFixado.versao
$executavelCursorFixado = [string]$cursorFixado.executavel
$configPath = Join-Path $repo 'config/agentes/cursor-c3-v1.json'
$configHash = Get-IaSha256 $configPath

function Get-EstadoTarefa {
    param(
        [Parameter(Mandatory = $true)][string]$Alvo,
        [Parameter(Mandatory = $true)][int]$Repeticao
    )
    $execucaoId = "C3-$Alvo-R$('{0:D2}' -f $Repeticao)"
    $raiz = Join-Path $repo "resultados/ia/$namespace/$execucaoId"
    $maiorTentativa = 0
    $sucesso = $null
    $alvoInfo = Get-IaAlvo $Alvo
    if (Test-Path -LiteralPath $raiz -PathType Container) {
        foreach ($diretorio in @(Get-ChildItem -LiteralPath $raiz -Directory -ErrorAction Stop |
            Sort-Object Name)) {
            if ($diretorio.Name -notmatch '^tentativa-([0-9]{3,})$') { continue }
            $numero = [int]$Matches[1]
            if ($numero -gt $maiorTentativa) { $maiorTentativa = $numero }
            $manifestoPath = Join-Path $diretorio.FullName 'manifesto.json'
            if (-not (Test-Path -LiteralPath $manifestoPath -PathType Leaf)) { continue }
            $manifesto = Read-ManifestoSeguro $manifestoPath
            $respostaPath = Join-Path $diretorio.FullName 'resposta-bruta.txt'
            $respostaAindaValida = $false
            $respostaHashValido = $false
            if (Test-Path -LiteralPath $respostaPath -PathType Leaf) {
                $respostaBruta = Get-Content -LiteralPath $respostaPath -Raw -Encoding UTF8
                $respostaAindaValida = [bool](
                    Test-IaRelatorio -Resposta $respostaBruta -EntradaRaiz ([string]$alvoInfo.entrada)
                ).valido
                $respostaHash = Get-IaSha256 $respostaPath
                $respostaHashValido = $respostaHash -eq [string]$manifesto.resposta_bruta_sha256
            }
            if ([string]$manifesto.condicao -eq 'C3' -and
                [string]$manifesto.alvo -eq $Alvo -and
                [int]$manifesto.repeticao -eq $Repeticao -and
                [string]$manifesto.finalidade -eq $Finalidade -and
                [string]$manifesto.modelo_solicitado -eq $Modelo -and
                [string]$manifesto.modelo_exibido -ne '' -and
                [string]$manifesto.modelo_verificacao -eq 'evento_jsonl' -and
                [string]$manifesto.versao_cliente -eq $versaoCursor -and
                [string]$manifesto.configuracao_sha256 -eq $configHash -and
                [string]$manifesto.entrada_sha256 -eq [string]$alvoInfo.entrada_sha256 -and
                [string]$manifesto.sessao_id -ne '' -and
                $null -ne $manifesto.tokens_entrada -and
                $null -ne $manifesto.tokens_saida -and
                $null -ne $manifesto.tokens_total -and
                @($manifesto.violacoes).Count -eq 0 -and
                [string]$manifesto.estado -eq 'concluida' -and
                [bool]$manifesto.resposta_valida -and
                $respostaAindaValida -and $respostaHashValido) {
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
        $planoTexto = & $executor -Alvo $tarefa.alvo -Repeticao $tarefa.repeticao `
            -Tentativa $tarefa.tentativa -Finalidade $Finalidade -Modelo $Modelo `
            -ModoCursor $ModoCursor -DistribuicaoWsl $DistribuicaoWsl `
            -ExecutavelCursor $executavelCursorFixado -TimeoutSegundos $TimeoutSegundos `
            -SomentePlanejar
        [void](($planoTexto -join "`n") | ConvertFrom-Json -ErrorAction Stop)
    }
    [ordered]@{
        schema_version = '1.0'
        tipo = 'plano-lote-ia'
        condicao = 'C3'
        ferramenta = 'cursor'
        finalidade = $Finalidade
        modelo = $Modelo
        modo_cursor = $ModoCursor
        versao_cursor_fixada = $versaoCursor
        executavel_cursor_fixado = $executavelCursorFixado
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
Write-LoteProgresso "C3/${Finalidade}: $($tarefas.Count) tarefas; $($pendentesExecucao.Count) chamadas pendentes; Cursor $versaoCursor"
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
            -ModoCursor $ModoCursor -DistribuicaoWsl $DistribuicaoWsl `
            -ExecutavelCursor $executavelCursorFixado -TimeoutSegundos $TimeoutSegundos `
            -ConfirmarExecucao)
        $manifesto = ($saidaExecutor -join "`n") | ConvertFrom-Json -ErrorAction Stop
        $resultado = if ([string]$manifesto.estado -eq 'concluida' -and
            [bool]$manifesto.resposta_valida) { 'concluida' } else { 'falha' }
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
    condicao = 'C3'
    ferramenta = 'cursor'
    finalidade = $Finalidade
    modelo = $Modelo
    modo_cursor = $ModoCursor
    versao_cursor_fixada = $versaoCursor
    executavel_cursor_fixado = $executavelCursorFixado
    inicio_ordem = @($tarefas | ForEach-Object { $_.execucao_id })
    tarefas_total = $tarefas.Count
    tarefas_processadas = $resultados.Count
    concluidas = @($resultados | Where-Object { $_.resultado -eq 'concluida' }).Count
    puladas_concluidas = @($resultados | Where-Object { $_.resultado -eq 'pulada_concluida' }).Count
    falhas = @($resultados | Where-Object { $_.resultado -in @('falha','falha_lote') }).Count
    resultados = @($resultados)
}
$loteId = 'C3-{0}-{1}' -f $namespace, [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$loteDir = Join-Path $repo "resultados/ia/$namespace/lotes/$loteId"
New-Item -ItemType Directory -Path $loteDir -ErrorAction Stop | Out-Null
$resumoPath = Join-Path $loteDir 'resumo.json'
$resumo['resumo_path'] = "resultados/ia/$namespace/lotes/$loteId/resumo.json"
$utf8 = [Text.UTF8Encoding]::new($false)
$resumoJson = $resumo | ConvertTo-Json -Depth 12 -Compress
[IO.File]::WriteAllText($resumoPath, $resumoJson + "`n", $utf8)
Write-LoteProgresso "lote encerrado; resumo=$resumoPath"
$resumo | ConvertTo-Json -Depth 12 -Compress
