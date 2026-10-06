[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^REL-[0-9]{4}$')]
    [string]$RelatorioId,

    [ValidateRange(1,2147483647)]
    [int]$Tentativa = 1,

    [ValidateNotNullOrEmpty()]
    [string]$Modelo = 'composer-2.5-fast',

    # Expressão regular que o modelo exibido no evento de sistema deve satisfazer.
    # Impede que um fallback silencioso (por exemplo, Auto) seja aceito.
    [ValidateNotNullOrEmpty()]
    [string]$PadraoModeloExibido = 'Composer\s*2\.5\s*Fast',

    [string]$EntradasDiretorio,
    [string]$SaidaDiretorio,
    [string]$Rubrica,
    [string]$Schema,

    [ValidateNotNullOrEmpty()]
    [string]$ExecutavelCursor = 'agent',

    [ValidateRange(1,86400)]
    [int]$TimeoutSegundos = 900,

    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'julgamento.ps1')

$privado = Join-Path $script:IaRepo 'build/avaliacao-qualitativa-processo'
foreach ($par in @(
    @{ nome = 'EntradasDiretorio'; padrao = (Join-Path $privado 'entradas') },
    @{ nome = 'SaidaDiretorio'; padrao = (Join-Path $privado 'execucoes-cursor') },
    @{ nome = 'Rubrica'; padrao = (Join-Path $script:IaRepo 'config/avaliacao-qualitativa/prompt-rubrica-v1.md') },
    @{ nome = 'Schema'; padrao = (Join-Path $script:IaRepo 'config/avaliacao-qualitativa/schema-julgamento.json') }
)) {
    $atual = (Get-Variable -Name $par.nome).Value
    if ([string]::IsNullOrWhiteSpace($atual)) { $atual = $par.padrao }
    elseif (-not [IO.Path]::IsPathRooted($atual)) { $atual = Join-Path $script:IaRepo $atual }
    Set-Variable -Name $par.nome -Value ([IO.Path]::GetFullPath($atual))
}

function Resolve-CursorNativo {
    param([Parameter(Mandatory = $true)][string]$Comando, [switch]$PermitirAusente)
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
        $companheiro = [IO.Path]::ChangeExtension($origem, '.ps1')
        Assert-Ia (Test-Path -LiteralPath $companheiro -PathType Leaf) `
            "launcher $extensao do Cursor não possui wrapper PowerShell correspondente: $origem"
        $origem = $companheiro
        $extensao = '.ps1'
    }
    if ($extensao -eq '.ps1') {
        $windowsPowerShell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
        Assert-Ia (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf) `
            'Windows PowerShell não encontrado para iniciar o Cursor Agent nativo'
        return [pscustomobject]@{
            executavel = $windowsPowerShell
            prefixo_argumentos = @('-NoLogo','-NoProfile','-NonInteractive',
                '-ExecutionPolicy','Bypass','-File',$origem)
        }
    }
    return [pscustomobject]@{ executavel = $origem; prefixo_argumentos = @() }
}

$entradaPath = Join-Path $EntradasDiretorio "$RelatorioId.json"
foreach ($obrigatorio in @($entradaPath, $Rubrica, $Schema)) {
    Assert-Ia (Test-Path -LiteralPath $obrigatorio -PathType Leaf) "arquivo obrigatório ausente: $obrigatorio"
}
$tentativaNome = 'tentativa-{0:D3}' -f $Tentativa
$area = Join-Path (Join-Path $SaidaDiretorio $RelatorioId) $tentativaNome
$rotulo = "$RelatorioId/$tentativaNome"

$argumentosCursor = @('-p','--trust','--mode=ask','--sandbox','disabled',
    '--model',$Modelo,'--output-format','stream-json')
$launcher = Resolve-CursorNativo -Comando $ExecutavelCursor -PermitirAusente:$SomentePlanejar
$executavel = [string]$launcher.executavel
$prefixo = @($launcher.prefixo_argumentos)
$argumentos = @($prefixo) + @($argumentosCursor)

if ($SomentePlanejar) {
    [ordered]@{
        schema_version = '1.0'
        tipo = 'plano-julgamento-rubrica'
        somente_planejar = $true
        relatorio_id = $RelatorioId
        tentativa = $Tentativa
        modelo_solicitado = $Modelo
        executavel = $executavel
        argumentos = @($argumentos)
        prompt_por_stdin = $true
        timeout_segundos = $TimeoutSegundos
        entrada = $entradaPath
        entrada_sha256 = Get-IaSha256 $entradaPath
        rubrica_sha256 = Get-IaSha256 $Rubrica
        schema_sha256 = Get-IaSha256 $Schema
        saida = $area
    } | ConvertTo-Json -Depth 10 -Compress
    return
}

Assert-Ia $ConfirmarExecucao `
    'execução externa exige -ConfirmarExecucao; use -SomentePlanejar para inspeção sem custo'
Assert-Ia (-not (Test-Path -LiteralPath $area)) "tentativa já existe: $area"

$entradaTexto = [IO.File]::ReadAllText($entradaPath, $script:IaUtf8)
$schemaTexto = [IO.File]::ReadAllText($Schema, $script:IaUtf8)
$rubricaTexto = [IO.File]::ReadAllText($Rubrica, $script:IaUtf8)
$entrada = $entradaTexto | ConvertFrom-Json -ErrorAction Stop
$schemaDoc = $schemaTexto | ConvertFrom-Json -ErrorAction Stop
Assert-Ia ([string]$entrada.relatorio.relatorio_id -ceq $RelatorioId) `
    "entrada pertence a outro relatório: $RelatorioId"

$prompt = New-JulgPrompt -RubricaBase $rubricaTexto -SchemaTexto $schemaTexto `
    -EntradaTexto $entradaTexto -RelatorioId $RelatorioId

New-Item -ItemType Directory -Path $area -ErrorAction Stop | Out-Null
$workspace = Join-Path $area 'workspace'
$cursorDir = Join-Path $workspace '.cursor'
New-Item -ItemType Directory -Path $cursorDir -ErrorAction Stop | Out-Null
# Todo o material vai no prompt; a sessão não precisa de ferramenta alguma.
Write-IaJsonNovo (Join-Path $cursorDir 'cli.json') ([ordered]@{
    permissions = [ordered]@{ allow = @(); deny = @('Read(**)','Write(**)','Shell(*)') }
})
$promptPath = Join-Path $area 'prompt.txt'
Write-IaTextoNovo $promptPath $prompt

$versao = $null
try {
    $linhasVersao = @(& $executavel @($prefixo + @('--version')) 2>&1)
    if ($LASTEXITCODE -eq 0 -and $linhasVersao.Count -gt 0) { $versao = ([string]$linhasVersao[-1]).Trim() }
}
catch { $versao = $null }

Write-IaProgresso "${rotulo}: prompt preparado; iniciando Cursor Agent ($Modelo)"
$inicio = Get-IaTimestampUtc
$relogio = [Diagnostics.Stopwatch]::StartNew()
$processo = $null
$erroInterno = $null
try {
    $processo = Invoke-IaProcesso -Executavel $executavel -Argumentos $argumentos `
        -Diretorio $workspace -EntradaPadrao $prompt -TimeoutSegundos $TimeoutSegundos `
        -IntervaloProgressoSegundos 10 -Rotulo $rotulo
}
catch { $erroInterno = $_.Exception.Message }
$relogio.Stop()
$termino = Get-IaTimestampUtc

$stdout = if ($null -eq $processo) { '' } else { [string]$processo.stdout }
$stderr = if ($null -eq $processo) { [string]$erroInterno } else { [string]$processo.stderr }
Write-IaTextoNovo (Join-Path $area 'eventos.jsonl') $stdout
Write-IaTextoNovo (Join-Path $area 'stderr.txt') $stderr

$interpretado = $null
$erroInterpretacao = $null
if ($null -ne $processo) {
    try { $interpretado = ConvertFrom-JulgEventosCursor $stdout }
    catch { $erroInterpretacao = $_.Exception.Message }
}
$respostaBruta = if ($null -eq $interpretado) { '' } else { [string]$interpretado.resposta }
Write-IaTextoNovo (Join-Path $area 'resposta-bruta.txt') $respostaBruta

$validacao = [pscustomobject]@{ valido = $false; erro = 'sem resposta do modelo'; avisos = @() }
$scoreRecalculado = $false
$scoreInformado = $null
$respostaPath = Join-Path $area 'resposta.json'
if ($respostaBruta) {
    $extraido = Get-JulgJsonDaResposta $respostaBruta
    if (-not $extraido.valido) {
        $validacao = [pscustomobject]@{ valido = $false; erro = [string]$extraido.erro; avisos = @() }
    }
    else {
        try {
            $registro = $extraido.texto | ConvertFrom-Json -ErrorAction Stop
            $textoFinal = $extraido.texto
            # O score é função determinística das notas. O modelo erra a aritmética
            # com frequência; o valor informado é guardado no manifesto e o derivado
            # das notas passa a constar de resposta.json. Nenhuma nota é alterada, e
            # a resposta original permanece intacta em resposta-bruta.txt.
            if ($null -ne (Get-IaValor $registro 'criterios')) {
                $derivado = $null
                try { $derivado = Get-JulgScoreDerivado $registro.criterios } catch { $derivado = $null }
                $informado = Get-IaValor $registro 'score_total'
                if ($null -ne $derivado -and
                    ($null -eq $informado -or [Math]::Abs([double]$informado - $derivado) -gt 1e-5)) {
                    $scoreInformado = $informado
                    $registro.score_total = $derivado
                    $scoreRecalculado = $true
                    $textoFinal = $registro | ConvertTo-Json -Depth 30
                    $registro = $textoFinal | ConvertFrom-Json -ErrorAction Stop
                }
            }
            $validacao = Test-JulgRegistro -Registro $registro -Schema $schemaDoc `
                -Entrada $entrada -IdEsperado $RelatorioId
            if ($validacao.valido) { Write-IaTextoNovo $respostaPath $textoFinal }
        }
        catch {
            $validacao = [pscustomobject]@{
                valido = $false; erro = "JSON inválido: $($_.Exception.Message)"; avisos = @()
            }
        }
    }
}

$estado = 'concluida'; $falhaTipo = $null; $falhaMensagem = $null
$modeloExibido = if ($null -eq $interpretado) { $null } else { $interpretado.modelo_exibido }
if ($null -eq $processo) {
    $estado = 'falha'; $falhaTipo = 'interna'; $falhaMensagem = $erroInterno
}
elseif (-not $processo.terminou) {
    $estado = 'falha'; $falhaTipo = 'timeout'
    $falhaMensagem = "limite de $TimeoutSegundos segundos excedido"
}
elseif ([int]$processo.codigo_saida -ne 0) {
    $estado = 'falha'; $falhaTipo = 'codigo_saida'
    $falhaMensagem = if ($null -ne $interpretado -and $interpretado.erro_ferramenta) {
        [string]$interpretado.erro_ferramenta
    } else { "CLI terminou com código $($processo.codigo_saida)" }
}
elseif ($erroInterpretacao) {
    $estado = 'falha'; $falhaTipo = 'formato'; $falhaMensagem = $erroInterpretacao
}
elseif ($interpretado.erro_ferramenta) {
    $estado = 'falha'; $falhaTipo = 'ferramenta'; $falhaMensagem = [string]$interpretado.erro_ferramenta
}
elseif (@($interpretado.violacoes).Count -gt 0) {
    $estado = 'falha'; $falhaTipo = 'contaminada'
    $falhaMensagem = "ferramenta proibida observada: $(@($interpretado.violacoes) -join ', ')"
}
elseif (-not $modeloExibido -or $modeloExibido -notmatch $PadraoModeloExibido) {
    $estado = 'falha'; $falhaTipo = 'modelo'
    $falhaMensagem = "modelo exibido '$modeloExibido' não satisfaz o padrão '$PadraoModeloExibido'"
}
elseif (-not $versao) {
    $estado = 'falha'; $falhaTipo = 'preflight'; $falhaMensagem = 'versão do Cursor Agent não observada'
}
elseif ($null -eq $interpretado.sessao_id -or $null -eq $interpretado.tokens_total) {
    $estado = 'falha'; $falhaTipo = 'formato'; $falhaMensagem = 'sessão ou tokens ausentes no JSONL'
}
elseif (-not $validacao.valido) {
    $estado = 'falha'; $falhaTipo = 'validacao'; $falhaMensagem = [string]$validacao.erro
}

$hashes = Get-IaArtefatosHash $area
[object[]]$violacoes = @()
if ($null -ne $interpretado) { $violacoes = [object[]]@($interpretado.violacoes) }
$manifesto = [ordered]@{
    schema_version = '1.0'
    tipo = 'manifesto-julgamento-rubrica-v1'
    relatorio_id = $RelatorioId
    tentativa = $Tentativa
    estado = $estado
    falha_tipo = $falhaTipo
    falha_mensagem = $falhaMensagem
    entrada_sha256 = Get-IaSha256 $entradaPath
    schema_sha256 = Get-IaSha256 $Schema
    rubrica_sha256 = Get-IaSha256 $Rubrica
    prompt_execucao_sha256 = Get-IaSha256 $promptPath
    modelo_solicitado = $Modelo
    modelo_exibido = $modeloExibido
    padrao_modelo_exibido = $PadraoModeloExibido
    versao_cliente = $versao
    sessao_id = if ($null -eq $interpretado) { $null } else { $interpretado.sessao_id }
    inicio_utc = $inicio
    termino_utc = $termino
    duracao_segundos = [Math]::Round($relogio.Elapsed.TotalSeconds, 6)
    tokens_entrada = if ($null -eq $interpretado) { $null } else { $interpretado.tokens_entrada }
    tokens_saida = if ($null -eq $interpretado) { $null } else { $interpretado.tokens_saida }
    tokens_total = if ($null -eq $interpretado) { $null } else { $interpretado.tokens_total }
    resposta_bruta_sha256 = [string]$hashes['resposta-bruta.txt']
    resposta_sha256 = if ($validacao.valido) { [string]$hashes['resposta.json'] } else { $null }
    resposta_valida = [bool]$validacao.valido
    score_recalculado = $scoreRecalculado
    score_informado_pelo_modelo = $scoreInformado
    avisos_material = @($validacao.avisos)
    violacoes = $violacoes
    comando = @($executavel) + @($argumentos)
    prompt_por_stdin = $true
    timeout_segundos = $TimeoutSegundos
    codigo_saida = if ($null -eq $processo) { $null } else { $processo.codigo_saida }
    artefatos_sha256 = $hashes
}
Write-IaJsonNovo (Join-Path $area 'manifesto.json') $manifesto
Write-IaProgresso "${rotulo}: manifesto gravado; estado=$estado; resposta_valida=$([bool]$validacao.valido)"
$manifesto | ConvertTo-Json -Depth 20 -Compress
