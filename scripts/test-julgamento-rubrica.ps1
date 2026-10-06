[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'ia/julgamento.ps1')

function Assert-True([bool]$Condicao, [string]$Mensagem) {
    if (-not $Condicao) { throw $Mensagem }
}

$schemaPath = Join-Path $Repo 'config/avaliacao-qualitativa/schema-julgamento.json'
$rubricaPath = Join-Path $Repo 'config/avaliacao-qualitativa/prompt-rubrica-v1.md'
$schemaTexto = [IO.File]::ReadAllText($schemaPath, $script:IaUtf8)
$schema = $schemaTexto | ConvertFrom-Json

# --- Fixture sintética (nenhum dado do corpus) -------------------------------
$hashCodigo = ('a' * 64)
$hashOrigem = ('b' * 64)
function New-EntradaTeste {
    param([string]$Recomendacao = 'Use consulta parametrizada.')
    return ([ordered]@{
        relatorio = [ordered]@{
            relatorio_id = 'REL-0001'; arquivo = 'app/db.py'; linha = '10'; cwe = 'CWE-89'
            severidade = 'alta'
            descricao = 'A entrada do usuário é concatenada na consulta SQL e permite injeção.'
            recomendacao = $Recomendacao
        }
        referencia = [ordered]@{ id = 'x-1'; file = 'app/db.py' }
        referencia_origem = [ordered]@{ caminho = 'oracle/x/ground-truth.json'; sha256 = $hashOrigem; escopo = 'entrada' }
        codigo = @([ordered]@{
            caminho = 'alvos/corpus-v1/ALVO-0001/app/db.py'; sha256 = $hashCodigo
            escopo = 'arquivo completo'; conteudo_numerado = '10: cur.execute("..." + q)'
        })
        aviso = 'dados'
    } | ConvertTo-Json -Depth 10) | ConvertFrom-Json
}

function New-CriterioTeste([int]$Nota, [string]$Trecho = 'trecho') {
    return [ordered]@{
        nota = $Nota; status = 'avaliado'
        evidencias = @([ordered]@{ fonte = 'relatorio.descricao'; trecho = $Trecho })
        justificativa = 'Justificativa específica.'
    }
}

function New-RegistroTeste {
    $criterios = [ordered]@{
        correcao_tecnica = New-CriterioTeste 4
        localizacao = New-CriterioTeste 5
        acionabilidade = New-CriterioTeste 3
        clareza_problema = New-CriterioTeste 1
        clareza_risco = New-CriterioTeste 1
        clareza_contexto = New-CriterioTeste 1
        clareza_concretude = New-CriterioTeste 0
        clareza_concisao = New-CriterioTeste 1
    }
    # 25 * (3/4 + 4/4 + 2/4 + 4/5) = 25 * 3.05 = 76.25
    return ([ordered]@{
        relatorio_id = 'REL-0001'
        criterios = $criterios
        score_total = 76.25
        abstencoes = @()
        limites = @('Análise estática.')
        material_consultado = @(
            [ordered]@{ caminho = 'material-cego.relatorio'; sha256 = $null; escopo = 'relato inline' },
            [ordered]@{ caminho = 'alvos/corpus-v1/ALVO-0001/app/db.py'; sha256 = $hashCodigo; escopo = 'arquivo completo' }
        )
    } | ConvertTo-Json -Depth 12) | ConvertFrom-Json
}

function Test-Registro($Registro, $Entrada = $null) {
    if ($null -eq $Entrada) { $Entrada = New-EntradaTeste }
    return Test-JulgRegistro -Registro $Registro -Schema $schema -Entrada $Entrada -IdEsperado 'REL-0001'
}

function Assert-Rejeita($Registro, [string]$Trecho, [string]$Descricao, $Entrada = $null) {
    $r = Test-Registro $Registro $Entrada
    Assert-True (-not $r.valido) "deveria rejeitar: $Descricao"
    Assert-True ([string]$r.erro).Contains($Trecho) `
        "rejeição de '$Descricao' com motivo inesperado: $($r.erro)"
}

# --- Aceitação e score -------------------------------------------------------
$base = New-RegistroTeste
$resultado = Test-Registro $base
Assert-True $resultado.valido "registro válido rejeitado: $($resultado.erro)"
Assert-True ((Get-JulgScoreDerivado $base.criterios) -eq 76.25) 'score derivado incorreto'

# --- Rejeições ---------------------------------------------------------------
$r = New-RegistroTeste; $r.score_total = 80.0
Assert-Rejeita $r 'diverge do derivado' 'score divergente'

$r = New-RegistroTeste; $r.criterios.correcao_tecnica.nota = 6
Assert-Rejeita $r 'fora da escala' 'nota fora da escala'

$r = New-RegistroTeste; $r.criterios.clareza_risco.nota = 2
Assert-Rejeita $r 'fora da escala' 'clareza fora de 0..1'

$r = New-RegistroTeste; $r.criterios.localizacao.nota = 4.5
Assert-Rejeita $r 'tipo incompatível' 'nota não inteira'

$r = New-RegistroTeste; $r.relatorio_id = 'REL-0002'
Assert-Rejeita $r 'esperado REL-0001' 'ID divergente'

$r = New-RegistroTeste; $r | Add-Member -NotePropertyName extra -NotePropertyValue 1
Assert-Rejeita $r 'campos inesperados' 'campo extra'

$r = New-RegistroTeste; $r.criterios.acionabilidade.status = 'talvez'
Assert-Rejeita $r 'fora do enum' 'status inválido'

$r = New-RegistroTeste; $r.criterios.acionabilidade.justificativa = '  '
Assert-Rejeita $r 'justificativa vazia' 'justificativa vazia'

$r = New-RegistroTeste; $r.criterios.acionabilidade.evidencias = @()
Assert-Rejeita $r 'evidência obrigatória' 'sem evidência'

$r = New-RegistroTeste; $r.criterios.acionabilidade.evidencias[0].trecho = ''
Assert-Rejeita $r 'fonte/trecho vazio' 'trecho vazio fora da exceção'

$r = New-RegistroTeste; $r.material_consultado[1].caminho = 'alvos/corpus-v1/ALVO-0001/outro.py'
Assert-Rejeita $r 'não fornecido' 'caminho de material inexistente'

$r = New-RegistroTeste; $r.material_consultado[1].sha256 = ('c' * 64)
Assert-Rejeita $r 'não fornecido' 'hash de material desconhecido'

$r = New-RegistroTeste; $r.material_consultado[1].sha256 = $hashOrigem
Assert-Rejeita $r 'não pertence ao caminho' 'hash de outro material'

# --- Abstenção ---------------------------------------------------------------
$r = New-RegistroTeste
$r.criterios.localizacao.nota = $null
$r.criterios.localizacao.status = 'abstencao'
$r.criterios.localizacao.evidencias = @()
$r.abstencoes = @('localizacao')
$r.score_total = $null
$resultado = Test-Registro $r
Assert-True $resultado.valido "abstenção coerente rejeitada: $($resultado.erro)"

$r.score_total = 70.0
Assert-Rejeita $r 'score deve ser null' 'score com abstenção'

$r = New-RegistroTeste
$r.criterios.localizacao.nota = $null
$r.criterios.localizacao.status = 'abstencao'
$r.score_total = $null
Assert-Rejeita $r 'abstenções não correspondem' 'abstenção não declarada'

# --- Exceção estrita para recomendação vazia ---------------------------------
function New-RegistroSemRecomendacao {
    $r = New-RegistroTeste
    $r.criterios.acionabilidade.nota = 1
    $r.criterios.acionabilidade.evidencias = @(
        [pscustomobject]@{ fonte = 'relatorio.recomendacao'; trecho = '' },
        [pscustomobject]@{ fonte = 'relatorio.descricao'; trecho = 'permite injeção' }
    )
    # 25 * (3/4 + 4/4 + 0 + 4/5) = 63.75
    $r.score_total = 63.75
    return $r
}
$entradaVazia = New-EntradaTeste -Recomendacao ''
$resultado = Test-Registro (New-RegistroSemRecomendacao) $entradaVazia
Assert-True $resultado.valido "ausência comprovada de recomendação rejeitada: $($resultado.erro)"

$r = New-RegistroSemRecomendacao
$r.criterios.acionabilidade.nota = 3
$r.score_total = 76.25
$resultado = Test-Registro $r $entradaVazia
Assert-True $resultado.valido "recomendação vazia com orientação na descrição rejeitada: $($resultado.erro)"

Assert-Rejeita (New-RegistroSemRecomendacao) 'fonte/trecho vazio' `
    'trecho vazio com recomendação preenchida' (New-EntradaTeste)

$r = New-RegistroSemRecomendacao
$r.criterios.acionabilidade.evidencias[1].trecho = 'texto que não está na descrição'
Assert-Rejeita $r 'fonte/trecho vazio' 'trecho de corroboração inexistente' $entradaVazia

$r = New-RegistroSemRecomendacao
$r.criterios.acionabilidade.evidencias = @($r.criterios.acionabilidade.evidencias[0])
Assert-Rejeita $r 'fonte/trecho vazio' 'ausência sem corroboração' $entradaVazia

# --- Extração de JSON --------------------------------------------------------
Assert-True (Get-JulgJsonDaResposta '{"a":1}').valido 'objeto puro deve ser aceito'
Assert-True (Get-JulgJsonDaResposta "``````json`n{`"a`":1}`n``````").valido 'cerca única deve ser aceita'
Assert-True (-not (Get-JulgJsonDaResposta 'Segue o resultado: {"a":1}').valido) 'prosa antes do JSON deve falhar'
Assert-True (-not (Get-JulgJsonDaResposta '').valido) 'resposta vazia deve falhar'
Assert-True (-not (Get-JulgJsonDaResposta '[{"a":1}]').valido) 'array na raiz deve falhar'

# --- Prompt ------------------------------------------------------------------
$rubricaTexto = [IO.File]::ReadAllText($rubricaPath, $script:IaUtf8)
$entradaTexto = (New-EntradaTeste) | ConvertTo-Json -Depth 10
$prompt = New-JulgPrompt -RubricaBase $rubricaTexto -SchemaTexto $schemaTexto `
    -EntradaTexto $entradaTexto -RelatorioId 'REL-0001'
foreach ($marcador in @('SCHEMA_JSON_INICIO','SCHEMA_JSON_FIM','<material-cego>','</material-cego>',
    'exatamente REL-0001','NÃO use qualquer ferramenta','Correção técnica 1..5')) {
    Assert-True $prompt.Contains($marcador) "prompt sem o trecho obrigatório: $marcador"
}
Assert-True (-not $prompt.Contains('C1') -or $prompt -notmatch 'condi[cç][aã]o\s*[:=]') `
    'o prompt não deve identificar a condição'
Assert-True (-not $prompt.Contains('chave-amostra')) 'o prompt não deve citar a chave de condições'

# --- Eventos do Cursor -------------------------------------------------------
$eventosOk = @(
    '{"type":"system","subtype":"init","session_id":"s-1","model":"Composer 2.5 Fast"}',
    '{"type":"thinking","subtype":"delta","text":"..."}',
    ('{"type":"result","subtype":"success","is_error":false,"result":"{\"a\":1}","session_id":"s-1",' +
        '"usage":{"inputTokens":3,"outputTokens":10,"cacheReadTokens":0,"cacheWriteTokens":7}}')
) -join "`n"
$interp = ConvertFrom-JulgEventosCursor $eventosOk
Assert-True ($interp.sessao_id -eq 's-1' -and $interp.modelo_exibido -like '*Composer 2.5*') 'sessão/modelo não interpretados'
Assert-True ([long]$interp.tokens_total -eq 20) 'tokens do Cursor mal interpretados'
Assert-True (@($interp.violacoes).Count -eq 0) 'não deveria haver violações'
$eventosFerramenta = $eventosOk + "`n" +
    '{"type":"tool_call","subtype":"started","tool_call":{"readToolCall":{"args":{}}}}'
Assert-True (@((ConvertFrom-JulgEventosCursor $eventosFerramenta).violacoes) -contains 'readToolCall') `
    'qualquer tool_call deve ser registrado como violação'
$falhou = $false
try { [void](ConvertFrom-JulgEventosCursor '{"type":"system","session_id":"x"}') } catch { $falhou = $true }
Assert-True $falhou 'ausência do evento result deve falhar'

# --- Executor ponta a ponta com agente falso ---------------------------------
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('julg-teste-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $entradas = Join-Path $tmp 'entradas'; $saida = Join-Path $tmp 'saida'
    New-Item -ItemType Directory -Path $entradas, $saida | Out-Null
    [IO.File]::WriteAllText((Join-Path $entradas 'REL-0001.json'),
        ((New-EntradaTeste) | ConvertTo-Json -Depth 10), $script:IaUtf8)

    $respostaFalsa = Join-Path $tmp 'resposta-falsa.json'
    [IO.File]::WriteAllText($respostaFalsa, ((New-RegistroTeste) | ConvertTo-Json -Depth 12 -Compress), $script:IaUtf8)

    $agenteFalso = Join-Path $tmp 'agente-falso.ps1'
    $conteudoAgente = @'
param([Parameter(ValueFromRemainingArguments = $true)]$Resto)
if ($Resto -contains '--version') { '9.9.9-teste'; exit 0 }
$modo = $env:AGENTE_FALSO_MODO
$entrada = [Console]::In.ReadToEnd()
$modelo = if ($modo -eq 'modelo-errado') { 'Auto' } else { 'Composer 2.5 Fast' }
$texto = switch ($modo) {
    'prosa' { 'Aqui está a avaliação, mas sem JSON.' }
    'score-errado' { [IO.File]::ReadAllText($env:AGENTE_FALSO_RESPOSTA_SCORE) }
    default { [IO.File]::ReadAllText($env:AGENTE_FALSO_RESPOSTA) }
}
$sistema = @{ type = 'system'; subtype = 'init'; session_id = "sessao-$modo"; model = $modelo }
$resultado = @{ type = 'result'; subtype = 'success'; is_error = $false; result = $texto
    session_id = "sessao-$modo"; usage = @{ inputTokens = 5; outputTokens = 7; cacheReadTokens = 0; cacheWriteTokens = 11 } }
($sistema | ConvertTo-Json -Compress)
if ($modo -eq 'ferramenta') {
    '{"type":"tool_call","subtype":"started","tool_call":{"shellToolCall":{"args":{}}}}'
}
($resultado | ConvertTo-Json -Compress)
'@
    [IO.File]::WriteAllText($agenteFalso, $conteudoAgente, [Text.UTF8Encoding]::new($true))
    $env:AGENTE_FALSO_RESPOSTA = $respostaFalsa
    $registroScore = New-RegistroTeste
    $registroScore.score_total = [double]$registroScore.score_total + 6.25
    $respostaScore = Join-Path $tmp 'resposta-score-errado.json'
    [IO.File]::WriteAllText($respostaScore, ($registroScore | ConvertTo-Json -Depth 12 -Compress), $script:IaUtf8)
    $env:AGENTE_FALSO_RESPOSTA_SCORE = $respostaScore

    $executor = Join-Path $PSScriptRoot 'ia/julgar-relato-cursor.ps1'
    function Invoke-Executor([int]$Tentativa, [string]$Modo) {
        $env:AGENTE_FALSO_MODO = $Modo
        $linhas = @(& $executor -RelatorioId 'REL-0001' -Tentativa $Tentativa `
            -EntradasDiretorio $entradas -SaidaDiretorio $saida `
            -ExecutavelCursor $agenteFalso -TimeoutSegundos 60 -ConfirmarExecucao 2>$null)
        return (($linhas -join "`n") | ConvertFrom-Json)
    }

    $plano = & $executor -RelatorioId 'REL-0001' -EntradasDiretorio $entradas `
        -SaidaDiretorio $saida -ExecutavelCursor $agenteFalso -SomentePlanejar | ConvertFrom-Json
    Assert-True ($plano.somente_planejar -and -not (Test-Path (Join-Path $saida 'REL-0001'))) `
        'o planejamento não deve criar artefatos'

    $m1 = Invoke-Executor 1 'ok'
    Assert-True ($m1.estado -eq 'concluida' -and $m1.resposta_valida) "execução válida falhou: $($m1.falha_mensagem)"
    Assert-True ($m1.modelo_solicitado -eq 'composer-2.5-fast') 'modelo solicitado inesperado'
    Assert-True ([long]$m1.tokens_total -eq 23 -and $m1.versao_cliente -eq '9.9.9-teste') 'tokens/versão não registrados'
    $pasta1 = Join-Path $saida 'REL-0001/tentativa-001'
    foreach ($arquivo in @('prompt.txt','eventos.jsonl','stderr.txt','resposta-bruta.txt','resposta.json','manifesto.json')) {
        Assert-True (Test-Path (Join-Path $pasta1 $arquivo)) "artefato ausente: $arquivo"
    }
    Assert-True ($m1.resposta_sha256 -eq (Get-IaSha256 (Join-Path $pasta1 'resposta.json'))) 'hash da resposta divergente'
    $cli = Get-Content (Join-Path $pasta1 'workspace/.cursor/cli.json') -Raw | ConvertFrom-Json
    Assert-True (@($cli.permissions.deny) -contains 'Shell(*)' -and @($cli.permissions.allow).Count -eq 0) `
        'a área do agente deve negar ferramentas'

    $m2 = Invoke-Executor 2 'prosa'
    Assert-True ($m2.estado -eq 'falha' -and $m2.falha_tipo -eq 'validacao') 'prosa deve ser rejeitada como validação'
    Assert-True (-not (Test-Path (Join-Path $saida 'REL-0001/tentativa-002/resposta.json'))) `
        'resposta inválida não deve gerar resposta.json'

    $m3 = Invoke-Executor 3 'ferramenta'
    Assert-True ($m3.estado -eq 'falha' -and $m3.falha_tipo -eq 'contaminada') 'tool_call deve contaminar a tentativa'

    $m4 = Invoke-Executor 4 'modelo-errado'
    Assert-True ($m4.estado -eq 'falha' -and $m4.falha_tipo -eq 'modelo') 'modelo diferente do solicitado deve falhar'

    $m5 = Invoke-Executor 5 'score-errado'
    Assert-True ($m5.estado -eq 'concluida' -and $m5.resposta_valida -and $m5.score_recalculado) `
        "score divergente deve ser recalculado: $($m5.falha_mensagem)"
    $pasta5 = Join-Path $saida 'REL-0001/tentativa-005'
    $gravado = Get-Content (Join-Path $pasta5 'resposta.json') -Raw | ConvertFrom-Json
    $original = Get-Content (Join-Path $pasta5 'resposta-bruta.txt') -Raw | ConvertFrom-Json
    Assert-True ([Math]::Abs([double]$gravado.score_total - [double](New-RegistroTeste).score_total) -lt 1e-5) `
        'score recalculado não corresponde às notas'
    Assert-True ([Math]::Abs([double]$original.score_total - [double]$m5.score_informado_pelo_modelo) -lt 1e-9) `
        'score informado pelo modelo deve permanecer na resposta bruta e no manifesto'
    Assert-True (-not $m1.score_recalculado) 'resposta correta não deve ser marcada como recalculada'

    $reaproveitou = $false
    try { [void](Invoke-Executor 1 'ok') } catch { $reaproveitou = $true }
    Assert-True $reaproveitou 'uma tentativa existente nunca pode ser sobrescrita'
}
finally {
    Remove-Item Env:AGENTE_FALSO_MODO, Env:AGENTE_FALSO_RESPOSTA, Env:AGENTE_FALSO_RESPOSTA_SCORE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output 'test-julgamento-rubrica: ok'
