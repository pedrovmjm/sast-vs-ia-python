[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('C3','C5')]
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
    [string]$Modelo = 'gpt-5.6-luna-medium',

    [ValidateSet('WSL','Nativo')]
    [string]$ModoCursor = 'Nativo',

    [string]$DistribuicaoWsl,

    [ValidateNotNullOrEmpty()]
    [string]$ExecutavelCursor = 'agent',

    [ValidateRange(1,86400)]
    [int]$TimeoutSegundos = 3600,

    [string]$AlertasSast,

    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'comum.ps1')

function Resolve-CursorNativo {
    param(
        [Parameter(Mandatory = $true)][string]$Comando,
        [switch]$PermitirAusente
    )

    $resolvido = @(Get-Command $Comando -CommandType Application,ExternalScript `
        -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($resolvido.Count -eq 0) {
        if ($PermitirAusente) {
            return [pscustomobject]@{ executavel = $Comando; prefixo_argumentos = @() }
        }
        throw "Cursor Agent nativo não encontrado no PATH: $Comando"
    }

    $origem = [string]$resolvido[0].Source
    if (-not $origem) { $origem = [string]$resolvido[0].Path }
    Assert-Ia ([bool]$origem) "não foi possível resolver o caminho do Cursor Agent: $Comando"

    $extensao = [IO.Path]::GetExtension($origem).ToLowerInvariant()
    if ($extensao -in @('.cmd','.bat')) {
        $companheiroPowerShell = [IO.Path]::ChangeExtension($origem, '.ps1')
        Assert-Ia (Test-Path -LiteralPath $companheiroPowerShell -PathType Leaf) `
            "launcher $extensao do Cursor não possui wrapper PowerShell correspondente: $origem"
        $origem = $companheiroPowerShell
        $extensao = '.ps1'
    }

    if ($extensao -eq '.ps1') {
        $windowsPowerShell = Join-Path $env:SystemRoot `
            'System32/WindowsPowerShell/v1.0/powershell.exe'
        Assert-Ia (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf) `
            'Windows PowerShell não encontrado para iniciar o Cursor Agent nativo'
        return [pscustomobject]@{
            executavel = $windowsPowerShell
            prefixo_argumentos = @(
                '-NoLogo', '-NoProfile', '-NonInteractive',
                '-ExecutionPolicy', 'Bypass', '-File', $origem
            )
        }
    }

    return [pscustomobject]@{ executavel = $origem; prefixo_argumentos = @() }
}

$execucaoId = "$Condicao-$Alvo-R$('{0:D2}' -f $Repeticao)"
$tentativaNome = 'tentativa-{0:D3}' -f $Tentativa
$namespace = $Finalidade.ToLowerInvariant()
$area = Join-Path $script:IaRepo "execucoes/ia/$namespace/$execucaoId/$tentativaNome"
$hibrido = $Condicao -eq 'C5'

$executavelEfetivo = $ExecutavelCursor
$prefixoCursorNativo = @()
$sandboxCursor = if ($ModoCursor -eq 'Nativo') { 'disabled' } else { 'enabled' }
$argumentosCursor = @(
    '-p', '--trust', '--mode=ask', '--sandbox', $sandboxCursor,
    '--model', $Modelo, '--output-format', 'stream-json'
)
$argumentos = @($argumentosCursor)
if ($ModoCursor -eq 'WSL') {
    $executavelEfetivo = 'wsl.exe'
    $areaWsl = '<AREA_WSL_RESOLVIDA_NA_EXECUCAO>'
    if (-not $SomentePlanejar) {
        $prefixoWsl = if ($DistribuicaoWsl) { @('-d',$DistribuicaoWsl) } else { @() }
        $linhas = @(& wsl.exe @prefixoWsl -- wslpath -a $area 2>&1)
        if ($LASTEXITCODE -ne 0 -or -not $linhas) {
            throw "não foi possível converter a área para caminho WSL: $($linhas -join ' ')"
        }
        $areaWsl = ([string]$linhas[-1]).Trim()
    }
    $argumentos = @()
    if ($DistribuicaoWsl) { $argumentos += @('-d',$DistribuicaoWsl) }
    $argumentos += @('--cd', $areaWsl, '--exec', $ExecutavelCursor)
    $argumentos += @($argumentosCursor)
}
else {
    $launcher = Resolve-CursorNativo -Comando $ExecutavelCursor `
        -PermitirAusente:$SomentePlanejar
    $executavelEfetivo = [string]$launcher.executavel
    $prefixoCursorNativo = @($launcher.prefixo_argumentos)
    $argumentos = @($prefixoCursorNativo) + @($argumentosCursor)
}

if ($SomentePlanejar) {
    Get-IaAlvo $Alvo | Out-Null
    if ($hibrido -and $AlertasSast) {
        Assert-Ia (Test-Path -LiteralPath $AlertasSast -PathType Leaf) `
            "alertas SAST ausentes: $AlertasSast"
    }
    $plano = New-IaPlanoBase -Condicao $Condicao -Ferramenta 'cursor' -Alvo $Alvo `
        -Repeticao $Repeticao -Tentativa $Tentativa -Finalidade $Finalidade `
        -Modelo $Modelo -Executavel $executavelEfetivo -Argumentos $argumentos `
        -Hibrido $hibrido -Alertas $AlertasSast -TimeoutSegundos $TimeoutSegundos
    $plano.modo_cursor = $ModoCursor
    $plano.distribuicao_wsl = $DistribuicaoWsl
    $plano | ConvertTo-Json -Depth 10 -Compress
    return
}

$prepararArea = {
    param([string]$diretorio)
    $cursorDir = Join-Path $diretorio '.cursor'
    New-Item -ItemType Directory -Path $cursorDir -ErrorAction Stop | Out-Null
    $sandbox = [ordered]@{
        type = 'workspace_readonly'
        disableTmpWrite = $true
        enableSharedBuildCache = $false
        networkPolicy = [ordered]@{ default = 'deny'; allow = @(); deny = @() }
    }
    $permissoes = [ordered]@{
        permissions = [ordered]@{
            allow = @('Read(**)')
            deny = @('Write(**)','Shell(*)')
        }
    }
    if ($ModoCursor -eq 'WSL') {
        Write-IaJsonNovo (Join-Path $cursorDir 'sandbox.json') $sandbox
    }
    Write-IaJsonNovo (Join-Path $cursorDir 'cli.json') $permissoes
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
    $violacoes = [Collections.Generic.List[string]]::new()
    foreach ($evento in $eventos) {
        $tipo = [string](Get-IaValor $evento 'type')
        if ($tipo -eq 'system') {
            $sessaoEvento = Get-IaValor $evento 'session_id'
            $modeloEvento = Get-IaValor $evento 'model'
            if ($null -ne $sessaoEvento) { $sessao = [string]$sessaoEvento }
            if ($null -ne $modeloEvento) { $modeloExibido = [string]$modeloEvento }
        }
        if ($tipo -eq 'tool_call') {
            $chamada = Get-IaValor $evento 'tool_call'
            $tiposChamada = @($chamada.PSObject.Properties.Name)
            foreach ($tipoChamada in $tiposChamada) {
                if ($tipoChamada -ne 'readToolCall') { $violacoes.Add([string]$tipoChamada) }
            }
        }
        if ($tipo -eq 'result') {
            $texto = Get-IaValor $evento 'result'
            if ($null -ne $texto) { $resposta = [string]$texto }
            $sessaoEvento = Get-IaValor $evento 'session_id'
            if ($null -ne $sessaoEvento) { $sessao = [string]$sessaoEvento }
            $uso = Get-IaValor $evento 'usage'
            if ($null -ne $uso) {
                $tokens = ConvertFrom-IaUsoCursor $uso
                $tokensEntrada = $tokens.entrada
                $tokensSaida = $tokens.saida
                $tokensTotal = $tokens.total
            }
        }
    }
    Assert-Ia ($null -ne $resposta) 'JSONL do Cursor não contém evento result terminal'
    return [pscustomobject]@{
        resposta = $resposta
        sessao_id = $sessao
        modelo_exibido = $modeloExibido
        modelo_verificacao = if ($modeloExibido) { 'evento_jsonl' } else { 'nao_exposto_jsonl_cursor' }
        tokens_entrada = $tokensEntrada
        tokens_saida = $tokensSaida
        tokens_total = $tokensTotal
        violacoes = [object[]]@($violacoes | Sort-Object -Unique)
    }
}

$obterVersao = if ($ModoCursor -eq 'WSL') {
    {
        $argsVersao = @()
        if ($DistribuicaoWsl) { $argsVersao += @('-d',$DistribuicaoWsl) }
        $argsVersao += @('--exec',$ExecutavelCursor,'--version')
        $linhas = @(& wsl.exe @argsVersao 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'não foi possível obter versão do Cursor Agent no WSL' }
        return ($linhas -join ' ').Trim()
    }
} else {
    {
        $argumentosVersao = @($prefixoCursorNativo) + @('--version')
        $linhas = @(& $executavelEfetivo @argumentosVersao 2>&1)
        if ($LASTEXITCODE -ne 0) { throw 'não foi possível obter versão do Cursor Agent' }
        return ($linhas -join ' ').Trim()
    }
}

$manifesto = Invoke-IaExecucao -Condicao $Condicao -Ferramenta cursor -Produto Cursor `
    -Alvo $Alvo -Repeticao $Repeticao -Tentativa $Tentativa -Finalidade $Finalidade `
    -Modelo $Modelo -Executavel $executavelEfetivo -Argumentos $argumentos `
    -TimeoutSegundos $TimeoutSegundos -AlertasPath $AlertasSast `
    -Interpretador $interpretador -PrepararArea $prepararArea -ObterVersao $obterVersao `
    -ConfirmarExecucao:$ConfirmarExecucao
$manifesto | ConvertTo-Json -Depth 20 -Compress
