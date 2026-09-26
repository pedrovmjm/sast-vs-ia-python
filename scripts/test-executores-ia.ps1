[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'ia/comum.ps1')

function Assert-True([bool]$Condicao, [string]$Mensagem) {
    if (-not $Condicao) { throw $Mensagem }
}

$cursorConfigPath = Join-Path $Repo 'config/agentes/cursor-c3-v1.json'
$codexConfigPath = Join-Path $Repo 'config/agentes/codex-c4-v1.json'
$codexC6ConfigPath = Join-Path $Repo 'config/agentes/codex-c6-v1.json'
$cursorConfig = Read-IaJson $cursorConfigPath
$codexConfig = Read-IaJson $codexConfigPath
$codexC6Config = Read-IaJson $codexC6ConfigPath
Assert-True ([string]$cursorConfig.prompt -eq [string]$codexConfig.prompt) `
    'Cursor e Codex devem apontar para o mesmo arquivo de prompt'
Assert-True ([string]$cursorConfig.prompt_sha256 -eq [string]$codexConfig.prompt_sha256) `
    'Cursor e Codex devem congelar exatamente o mesmo prompt'
Assert-True ([string]$cursorConfig.schema_saida -eq [string]$codexConfig.schema_saida) `
    'Cursor e Codex devem apontar para o mesmo schema'
Assert-True ([string]$cursorConfig.schema_saida_sha256 -eq [string]$codexConfig.schema_saida_sha256) `
    'Cursor e Codex devem congelar exatamente o mesmo schema'
Assert-True ([string]$cursorConfig.modelo_solicitado -eq [string]$codexConfig.modelo_solicitado) `
    'Cursor e Codex devem solicitar o mesmo modelo'
Assert-True ([string]$codexC6Config.condicao -eq 'C6') `
    'configuração híbrida do Codex deve declarar C6'
Assert-True ([string]$codexC6Config.prompt_sha256 -eq [string]$codexConfig.prompt_sha256) `
    'C4 e C6 devem congelar exatamente o mesmo prompt-base'
Assert-True ([string]$codexC6Config.schema_saida_sha256 -eq [string]$codexConfig.schema_saida_sha256) `
    'C4 e C6 devem congelar exatamente o mesmo schema de saída'
Assert-True ([string]$codexC6Config.modelo_solicitado -eq [string]$codexConfig.modelo_solicitado) `
    'C4 e C6 devem solicitar o mesmo modelo'
$codexC6LockPath = Join-Path $Repo ([string]$codexC6Config.alertas_sast_lock)
Assert-True ((Get-IaSha256 $codexC6LockPath) -eq [string]$codexC6Config.alertas_sast_lock_sha256) `
    'hash observado do lock de alertas C6 diverge da configuração'
foreach ($campoMetadado in @(
    'versao_cliente','modelo_solicitado','modelo_exibido','modelo_verificacao',
    'sessao_id','tokens_entrada','tokens_saida','tokens_total','resposta_bruta_sha256'
)) {
    Assert-True ($campoMetadado -in @($cursorConfig.metadados_obrigatorios)) `
        "metadado obrigatorio ausente no Cursor: $campoMetadado"
    Assert-True ($campoMetadado -in @($codexConfig.metadados_obrigatorios)) `
        "metadado obrigatorio ausente no Codex: $campoMetadado"
}
Assert-True ('modelo_exibido' -in @($codexConfig.metadados_nulos_permitidos)) `
    'Codex deve documentar que o JSONL pode nao expor o modelo efetivo'
Assert-True ('modelo_exibido' -notin @($cursorConfig.metadados_nulos_permitidos)) `
    'Cursor deve continuar exigindo o modelo exibido no evento de sistema'
$restricoesCursor = $cursorConfig.restricoes | ConvertTo-Json -Depth 10 -Compress
$restricoesCodex = $codexConfig.restricoes | ConvertTo-Json -Depth 10 -Compress
Assert-True ($restricoesCursor -eq $restricoesCodex) `
    'Cursor e Codex devem usar restrições experimentais equivalentes'

$promptBasePath = Join-Path $Repo ([string]$cursorConfig.prompt)
Assert-True ((Get-IaSha256 $promptBasePath) -eq [string]$cursorConfig.prompt_sha256) `
    'hash observado do prompt comum diverge da configuração'
$promptBase = Get-Content -LiteralPath $promptBasePath -Raw -Encoding UTF8
foreach ($trechoObrigatorio in @(
    'Inclua um achado somente quando',
    'ALERTAS SAST, QUANDO PRESENTES',
    'TAXONOMIA E SEVERIDADE',
    'Cada item deve conter exatamente estas propriedades'
)) {
    Assert-True $promptBase.Contains($trechoObrigatorio) `
        "seção obrigatória ausente do prompt comum: $trechoObrigatorio"
}

$payloadTeste = '{"schema_version":"1.0","tipo":"payload-codigo-estatico","arquivos":[]}'
$alertasTeste = '{"schema_version":"1.0","tipo":"alertas-sast-v1","alertas":[]}'
$promptIsolado = New-IaPrompt -Base $promptBase -PayloadJson $payloadTeste -AlertasJson $null
$promptHibrido = New-IaPrompt -Base $promptBase -PayloadJson $payloadTeste -AlertasJson $alertasTeste
Assert-True ($promptIsolado.Contains('PAYLOAD_CODIGO_JSON_INICIO') -and
    $promptIsolado.Contains('PAYLOAD_CODIGO_JSON_FIM')) `
    'prompt efetivo deve delimitar o payload não confiável'
Assert-True (-not $promptIsolado.Contains('ALERTAS_SAST_JSON_INICIO')) `
    'prompt isolado não deve conter seção híbrida'
Assert-True ($promptHibrido.Contains('ALERTAS_SAST_JSON_INICIO') -and
    $promptHibrido.Contains('ALERTAS_SAST_JSON_FIM')) `
    'prompt híbrido deve delimitar os alertas não confiáveis'

# Regressão para Windows PowerShell 5.1: strings produzidas por Get-Content
# carregam propriedades ETS e tornam ConvertTo-Json -Depth 10 extremamente
# lento. O payload deve conter System.String limpa e serializar corretamente.
$alvoInfoTeste = Get-IaAlvo 'ALVO-0001'
$payloadReal = New-IaPayloadCodigo $alvoInfoTeste
$primeiroConteudo = $payloadReal['arquivos'][0]['conteudo_utf8']
Assert-True ($primeiroConteudo -is [string]) `
    'conteúdo de código do payload deve ser string'
Assert-True ($null -eq $primeiroConteudo.PSObject.Properties['PSPath']) `
    'conteúdo de código do payload não deve carregar metadados ETS de arquivo'
$relogioPayload = [Diagnostics.Stopwatch]::StartNew()
$payloadRealJson = ConvertTo-Json -InputObject $payloadReal -Depth 10 -Compress
$relogioPayload.Stop()
Assert-True ($relogioPayload.Elapsed.TotalSeconds -lt 5) `
    'serialização do payload excedeu 5 segundos'
$payloadRealLido = $payloadRealJson | ConvertFrom-Json -ErrorAction Stop
Assert-True (@($payloadRealLido.arquivos).Count -eq @($payloadReal['arquivos']).Count) `
    'serialização alterou a quantidade de arquivos do payload'
Assert-True ([string]$payloadRealLido.arquivos[0].conteudo_utf8 -ceq $primeiroConteudo) `
    'serialização alterou o conteúdo do primeiro arquivo do payload'

# Garante que o transporte por stdin preserve UTF-8 no Windows PowerShell 5.1.
$powershellLocal = Join-Path $PSHOME 'powershell.exe'
$scriptFilho = @'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$recebido = [Console]::In.ReadToEnd()
if ($recebido -ceq 'ação, validação e configuração') {
    [Console]::Out.Write('utf8-ok')
    exit 0
}
[Console]::Error.Write('stdin divergente')
exit 9
'@
$processoUtf8 = Invoke-IaProcesso -Executavel $powershellLocal `
    -Argumentos @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',$scriptFilho) `
    -Diretorio $Repo -EntradaPadrao 'ação, validação e configuração' `
    -TimeoutSegundos 10 -IntervaloProgressoSegundos 2 -Rotulo 'teste-stdin-utf8'
Assert-True $processoUtf8.terminou 'processo local de teste UTF-8 excedeu o timeout'
Assert-True ([int]$processoUtf8.codigo_saida -eq 0) `
    "processo local recusou stdin UTF-8: $($processoUtf8.stderr)"
Assert-True ([string]$processoUtf8.stdout -ceq 'utf8-ok') `
    'stdout UTF-8 do processo local divergiu'

$entrada = Join-Path $Repo 'alvos/corpus-v1/ALVO-0001'
$vazio = Test-IaRelatorio -Resposta '[]' -EntradaRaiz $entrada
Assert-True $vazio.valido 'relatório vazio válido foi recusado'

$achado = [ordered]@{
    arquivo = 'app.py'
    linha_inicial = 1
    linha_final = 1
    cwe = 'CWE-502'
    severidade = 'baixa'
    descricao = 'achado sintético para validar o contrato'
    recomendacao = $null
}
$valido = Test-IaRelatorio -Resposta (ConvertTo-Json -InputObject @($achado) -Compress) `
    -EntradaRaiz $entrada
Assert-True $valido.valido 'relatório sintético válido foi recusado'

$foraDoArquivo = [ordered]@{}
foreach ($chave in $achado.Keys) { $foraDoArquivo[$chave] = $achado[$chave] }
$linhasApp = [IO.File]::ReadAllLines(
    (Join-Path $entrada 'app.py'), [Text.UTF8Encoding]::new($false)
).Length
$foraDoArquivo['linha_inicial'] = $linhasApp + 1
$foraDoArquivo['linha_final'] = $linhasApp + 1
$linhaRejeitada = Test-IaRelatorio `
    -Resposta (ConvertTo-Json -InputObject @($foraDoArquivo) -Compress) `
    -EntradaRaiz $entrada
Assert-True (-not $linhaRejeitada.valido) `
    'linha que excede o tamanho do arquivo foi aceita'
Assert-True ([string]$linhaRejeitada.erro -like '*excede o arquivo*') `
    'falha de limite de linha nao foi identificada explicitamente'

$objetoRaiz = Test-IaRelatorio -Resposta ($achado | ConvertTo-Json -Compress) `
    -EntradaRaiz $entrada
Assert-True (-not $objetoRaiz.valido) 'objeto na raiz foi aceito no lugar de array'

$invalido = [ordered]@{}
foreach ($chave in $achado.Keys) { $invalido[$chave] = $achado[$chave] }
$invalido['arquivo'] = '../oracle/resposta.py'
$rejeitado = Test-IaRelatorio -Resposta (ConvertTo-Json -InputObject @($invalido) -Compress) `
    -EntradaRaiz $entrada
Assert-True (-not $rejeitado.valido) 'caminho que escapa do alvo foi aceito'

$casos = @(
    @('scripts/executar-c3-cursor.ps1','C3','cursor'),
    @('scripts/executar-c4-codex.ps1','C4','codex')
)
foreach ($caso in $casos) {
    $saida = @(& (Join-Path $Repo $caso[0]) -Alvo ALVO-0001 -SomentePlanejar 2>&1)
    $plano = ($saida -join "`n") | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$plano.condicao -eq $caso[1]) "condição divergente em $($caso[0])"
    Assert-True ([string]$plano.ferramenta -eq $caso[2]) "ferramenta divergente em $($caso[0])"
    Assert-True ([bool]$plano.prompt_por_stdin) 'prompt deve ser enviado por stdin'
    Assert-True ([int]$plano.timeout_segundos -eq 3600) `
        'timeout padrão de agentes deve ser 3600 segundos'
    Assert-True ([int]$plano.progresso_intervalo_segundos -eq 10) `
        'intervalo padrão de progresso deve ser 10 segundos'
    Assert-True ([string]$plano.saida -like 'resultados/ia/piloto/*') `
        'plano piloto deve usar namespace separado da coleta'
    if ($caso[2] -eq 'cursor') {
        Assert-True ('--mode=ask' -in @($plano.argumentos)) 'Cursor deve usar modo ask'
        Assert-True ('enabled' -in @($plano.argumentos)) 'sandbox do Cursor deve estar habilitado'
    }
    else {
        Assert-True ('read-only' -in @($plano.argumentos)) 'Codex deve usar sandbox somente leitura'
        Assert-True ('--output-schema' -notin @($plano.argumentos)) `
            'Codex não deve aplicar schema nativo ausente no Cursor; a validação deve ser local e comum'
    }
}

$planoLoteTexto = & (Join-Path $Repo 'scripts/executar-c4-codex-lote.ps1') `
    -Finalidade coleta -Repeticoes 1 -Alvos @('ALVO-0001','ALVO-0002') `
    -Modelo 'modelo-sintetico-teste-executores' `
    -SomentePlanejar
$planoLote = ($planoLoteTexto -join "`n") | ConvertFrom-Json -ErrorAction Stop
Assert-True ([int]$planoLote.alvos -eq 2) 'lote C4 deve respeitar seleção de alvos'
Assert-True ([int]$planoLote.tarefas_total -eq 2) `
    'lote C4 de uma repetição e dois alvos deve conter duas tarefas'
Assert-True ([int]$planoLote.chamadas_planejadas -eq 2) `
    'lote C4 novo deve planejar duas chamadas'
Assert-True (@($planoLote.ordem | ForEach-Object { $_.alvo }) -join ',' -eq `
    'ALVO-0001,ALVO-0002') 'lote C4 deve ter ordem determinística por alvo'

$testeNome = 'ALVO-0001-alertas-sast-teste-executores.json'
$testePath = Join-Path $Repo "execucoes/ia/alertas/$testeNome"
$raizAlertas = [IO.Path]::GetFullPath((Join-Path $Repo 'execucoes/ia/alertas')).TrimEnd('\','/')
$testeFull = [IO.Path]::GetFullPath($testePath)
$testeLoteDir = Join-Path $raizAlertas "teste-lote-$PID"
Assert-True ($testeFull.StartsWith($raizAlertas + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase)) 'caminho de teste fora da raiz permitida'
Assert-True (-not (Test-Path -LiteralPath $testeFull)) 'artefato de teste já existe'
Assert-True (-not (Test-Path -LiteralPath $testeLoteDir)) 'diretório de teste de lote já existe'
try {
    $geracao = @(& (Join-Path $Repo 'scripts/gerar-alertas-sast.ps1') `
        -Alvo ALVO-0001 -Destino $testeFull 2>&1)
    $recibo = ($geracao -join "`n") | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([int]$recibo.quantidade_alertas -gt 0) 'nenhum alerta foi gerado'
    $alertas = Get-Content -LiteralPath $testeFull -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$alertas.tipo -eq 'alertas-sast-v1') 'tipo de alertas divergente'
    Assert-True (@($alertas.fontes).Count -eq 2) 'alertas devem preservar C1 e C2'

    foreach ($caso in @(
        @('scripts/executar-c5-cursor-sast.ps1','C5','cursor'),
        @('scripts/executar-c6-codex-sast.ps1','C6','codex')
    )) {
        $saida = @(& (Join-Path $Repo $caso[0]) -Alvo ALVO-0001 `
            -AlertasSast $testeFull -SomentePlanejar 2>&1)
        $plano = ($saida -join "`n") | ConvertFrom-Json -ErrorAction Stop
        Assert-True ([string]$plano.condicao -eq $caso[1]) "condição divergente em $($caso[0])"
        Assert-True ([string]$plano.ferramenta -eq $caso[2]) "ferramenta divergente em $($caso[0])"
        Assert-True ([bool]$plano.hibrido) 'plano C5/C6 deve ser híbrido'
        Assert-True ([int]$plano.timeout_segundos -eq 3600) `
            'timeout padrão híbrido deve ser 3600 segundos'
        Assert-True ([int]$plano.progresso_intervalo_segundos -eq 10) `
            'intervalo padrão híbrido de progresso deve ser 10 segundos'
    }

    foreach ($alvoLote in @('ALVO-0001','ALVO-0002')) {
        $destinoLote = Join-Path $testeLoteDir "$alvoLote-alertas-sast.json"
        $geracaoLote = @(& (Join-Path $Repo 'scripts/gerar-alertas-sast.ps1') `
            -Alvo $alvoLote -Destino $destinoLote 2>&1)
        [void](($geracaoLote -join "`n") | ConvertFrom-Json -ErrorAction Stop)
    }
    $planoC6Texto = & (Join-Path $Repo 'scripts/executar-c6-codex-sast-lote.ps1') `
        -Finalidade coleta -Repeticoes 1 -Alvos @('ALVO-0001','ALVO-0002') `
        -AlertasDiretorio $testeLoteDir -Modelo 'modelo-sintetico-teste-executores' `
        -SomentePlanejar
    $planoC6 = ($planoC6Texto -join "`n") | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$planoC6.condicao -eq 'C6') 'lote híbrido deve declarar C6'
    Assert-True ([bool]$planoC6.hibrido) 'lote C6 deve declarar entrada híbrida'
    Assert-True ([int]$planoC6.alvos -eq 2) 'lote C6 deve respeitar seleção de alvos'
    Assert-True ([int]$planoC6.tarefas_total -eq 2) `
        'lote C6 de uma repetição e dois alvos deve conter duas tarefas'
    Assert-True ([int]$planoC6.chamadas_planejadas -eq 2) `
        'lote C6 novo deve planejar duas chamadas'
    Assert-True (@($planoC6.ordem | Where-Object {
        [string]$_.alertas_sast_sha256 -notmatch '^[0-9a-f]{64}$'
    }).Count -eq 0) 'lote C6 deve congelar o hash dos alertas por tarefa'
}
finally {
    if (Test-Path -LiteralPath $testeFull) { Remove-Item -LiteralPath $testeFull -Force }
    if (Test-Path -LiteralPath $testeLoteDir) {
        Get-ChildItem -LiteralPath $testeLoteDir -File | Remove-Item -Force
        Remove-Item -LiteralPath $testeLoteDir -Force
    }
}

[ordered]@{
    schema_version = '1.0'
    resultado = 'aprovado'
    cenarios = @('C3','C4','C5','C6')
    ferramentas = @('cursor','codex')
    chamadas_externas = 0
} | ConvertTo-Json -Compress
