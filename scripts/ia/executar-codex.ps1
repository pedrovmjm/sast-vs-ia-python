[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('C4','C6')]
    [string]$Condicao,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^ALVO-[0-9]{4}$')]
    [string]$Alvo,

    [ValidateRange(1,3)]
    [int]$Repeticao = 1,

    [ValidateRange(1,2147483647)]
    [int]$Tentativa = 1,

    [ValidateSet('piloto','coleta')]
    [string]$Finalidade = 'piloto',

    [ValidateNotNullOrEmpty()]
    [string]$Modelo = 'gpt-5.6-luna',

    [ValidateNotNullOrEmpty()]
    [string]$ExecutavelCodex = 'codex',

    [ValidateRange(1,86400)]
    [int]$TimeoutSegundos = 3600,

    [string]$AlertasSast,

    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'comum.ps1')

$execucaoId = "$Condicao-$Alvo-R$('{0:D2}' -f $Repeticao)"
$tentativaNome = 'tentativa-{0:D3}' -f $Tentativa
$namespace = $Finalidade.ToLowerInvariant()
$area = Join-Path $script:IaRepo "execucoes/ia/$namespace/$execucaoId/$tentativaNome"
$argumentos = @(
    'exec', '-', '--cd', $area,
    '--model', $Modelo,
    '--sandbox', 'read-only',
    '--ephemeral',
    '--ignore-user-config',
    '--ignore-rules',
    '--skip-git-repo-check',
    '--json',
    '-c', 'approval_policy="never"'
)
$hibrido = $Condicao -eq 'C6'
if ($SomentePlanejar) {
    Get-IaAlvo $Alvo | Out-Null
    if ($hibrido) {
        Assert-Ia (-not [string]::IsNullOrWhiteSpace($AlertasSast)) `
            "$Condicao exige alertas-sast.json"
        Assert-Ia (Test-Path -LiteralPath $AlertasSast -PathType Leaf) `
            "alertas SAST ausentes: $AlertasSast"
        $alertasDoc = Read-IaJson $AlertasSast
        Assert-Ia ([string]$alertasDoc.tipo -eq 'alertas-sast-v1') `
            'arquivo de alertas possui tipo inesperado'
        Assert-Ia ([string]$alertasDoc.alvo -eq $Alvo) `
            'arquivo de alertas pertence a outro alvo'
        $configC6Path = Join-Path $script:IaRepo 'config/agentes/codex-c6-v1.json'
        $configC6 = Read-IaJson $configC6Path
        $lockPath = Join-Path $script:IaRepo ([string]$configC6.alertas_sast_lock)
        Assert-Ia ((Get-IaSha256 $lockPath) -eq [string]$configC6.alertas_sast_lock_sha256) `
            'hash do lock de alertas SAST de C6 diverge da configuração'
        $lock = Read-IaJson $lockPath
        $entradaLock = @($lock.alvos | Where-Object { [string]$_.alvo -eq $Alvo })
        Assert-Ia ($entradaLock.Count -eq 1) `
            "lock de alertas SAST não contém exatamente um $Alvo"
        Assert-Ia ((Get-IaSha256 $AlertasSast) -eq [string]$entradaLock[0].sha256) `
            "hash dos alertas SAST diverge do lock para $Alvo"
    }
    $plano = New-IaPlanoBase -Condicao $Condicao -Ferramenta 'codex' -Alvo $Alvo `
        -Repeticao $Repeticao -Tentativa $Tentativa -Finalidade $Finalidade `
        -Modelo $Modelo -Executavel $ExecutavelCodex -Argumentos $argumentos `
        -Hibrido $hibrido -Alertas $AlertasSast -TimeoutSegundos $TimeoutSegundos
    $plano | ConvertTo-Json -Depth 10 -Compress
    return
}

$interpretador = {
    param([string]$stdout)
    $eventos = @(ConvertFrom-IaJsonl $stdout)
    $sessao = $null
    $modeloExibido = $null
    $resposta = $null
    $tokensEntrada = $null
    $tokensSaida = $null
    $tokensTotal = $null
    $erroFerramenta = $null
    $violacoes = [Collections.Generic.List[string]]::new()
    foreach ($evento in $eventos) {
        $tipo = [string](Get-IaValor $evento 'type')
        if ($tipo -eq 'thread.started') {
            $sessao = Get-IaValor $evento 'thread_id'
        }
        $modeloEvento = Get-IaValor $evento 'model'
        if ($null -ne $modeloEvento) { $modeloExibido = [string]$modeloEvento }
        if ($tipo -eq 'item.completed') {
            $item = Get-IaValor $evento 'item'
            $itemTipo = [string](Get-IaValor $item 'type')
            if ($itemTipo -eq 'agent_message') {
                $texto = Get-IaValor $item 'text'
                if ($null -ne $texto) { $resposta = [string]$texto }
            }
            if ($itemTipo -in @('command_execution','file_change','mcp_tool_call','web_search')) {
                $violacoes.Add($itemTipo)
            }
        }
        if ($tipo -eq 'error') {
            $mensagemErro = Get-IaValor $evento 'message'
            if ($null -ne $mensagemErro) { $erroFerramenta = [string]$mensagemErro }
        }
        if ($tipo -eq 'turn.failed') {
            $erroTurno = Get-IaValor $evento 'error'
            $mensagemErro = Get-IaValor $erroTurno 'message'
            if ($null -ne $mensagemErro) { $erroFerramenta = [string]$mensagemErro }
        }
        if ($tipo -eq 'turn.completed') {
            $uso = Get-IaValor $evento 'usage'
            $entrada = Get-IaValor $uso 'input_tokens'
            $saida = Get-IaValor $uso 'output_tokens'
            $total = Get-IaValor $uso 'total_tokens'
            if ($null -ne $entrada) { $tokensEntrada = [long]$entrada }
            if ($null -ne $saida) { $tokensSaida = [long]$saida }
            if ($null -ne $total) { $tokensTotal = [long]$total }
            elseif ($null -ne $tokensEntrada -and $null -ne $tokensSaida) {
                $tokensTotal = $tokensEntrada + $tokensSaida
            }
        }
    }
    return [pscustomobject]@{
        resposta = $resposta
        sessao_id = $sessao
        modelo_exibido = $modeloExibido
        modelo_verificacao = if ($modeloExibido) { 'evento_jsonl' } else { 'nao_exposto_jsonl_codex' }
        tokens_entrada = $tokensEntrada
        tokens_saida = $tokensSaida
        tokens_total = $tokensTotal
        erro_ferramenta = $erroFerramenta
        violacoes = [object[]]@($violacoes | Sort-Object -Unique)
    }
}

$obterVersao = {
    $linhas = @(& $ExecutavelCodex --version 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "não foi possível obter versão do Codex" }
    return ($linhas -join ' ').Trim()
}

$manifesto = Invoke-IaExecucao -Condicao $Condicao -Ferramenta codex -Produto Codex `
    -Alvo $Alvo -Repeticao $Repeticao -Tentativa $Tentativa -Finalidade $Finalidade `
    -Modelo $Modelo -Executavel $ExecutavelCodex -Argumentos $argumentos `
    -TimeoutSegundos $TimeoutSegundos -AlertasPath $AlertasSast `
    -Interpretador $interpretador -ObterVersao $obterVersao `
    -ConfirmarExecucao:$ConfirmarExecucao
$manifesto | ConvertTo-Json -Depth 20 -Compress
