[CmdletBinding()]
param(
    # Relatos específicos (REL-NNNN). Sem este parâmetro, usa todos os da amostra.
    [ValidatePattern('^REL-[0-9]{4}$')]
    [string[]]$Ids,

    # Fatia da amostra ordenada por identificador: começa em -Inicio (1..300).
    [ValidateRange(1,100000)]
    [int]$Inicio = 1,

    [ValidateRange(1,100000)]
    [int]$Limite = 100000,

    [ValidateNotNullOrEmpty()]
    [string]$Modelo = 'composer-2.5-fast',

    [ValidateNotNullOrEmpty()]
    [string]$PadraoModeloExibido = 'Composer\s*2\.5\s*Fast',

    [ValidateNotNullOrEmpty()]
    [string]$ExecutavelCursor = 'agent',

    [ValidateRange(1,86400)]
    [int]$TimeoutSegundos = 900,

    # Tentativas máximas por relato em uma mesma chamada do script.
    [ValidateRange(1,10)]
    [int]$TentativasPorRelato = 2,

    # Relatos processados simultaneamente (cada um em sua própria sessão do agente).
    [ValidateRange(1,30)]
    [int]$Paralelo = 1,

    # Interrompe o lote após N falhas seguidas (cota, autenticação, rede).
    [ValidateRange(1,100)]
    [int]$FalhasConsecutivasMax = 5,

    [string]$EntradasDiretorio,
    [string]$SaidaDiretorio,
    [string]$Rubrica,
    [string]$Schema,

    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao,
    [switch]$PararEmFalha,

    # Não chama o modelo: seleciona a maior tentativa válida de cada relato e
    # copia para respostas-selecionadas/, somente se os 300 estiverem completos.
    [switch]$Consolidar
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ia/julgamento.ps1')

$repo = $script:IaRepo
$privado = Join-Path $repo 'build/avaliacao-qualitativa-processo'
foreach ($par in @(
    @{ nome = 'EntradasDiretorio'; padrao = (Join-Path $privado 'entradas') },
    @{ nome = 'SaidaDiretorio'; padrao = (Join-Path $privado 'execucoes-cursor') },
    @{ nome = 'Rubrica'; padrao = (Join-Path $repo 'config/avaliacao-qualitativa/prompt-rubrica-v1.md') },
    @{ nome = 'Schema'; padrao = (Join-Path $repo 'config/avaliacao-qualitativa/schema-julgamento.json') }
)) {
    $atual = (Get-Variable -Name $par.nome).Value
    if ([string]::IsNullOrWhiteSpace($atual)) { $atual = $par.padrao }
    elseif (-not [IO.Path]::IsPathRooted($atual)) { $atual = Join-Path $repo $atual }
    Set-Variable -Name $par.nome -Value ([IO.Path]::GetFullPath($atual))
}
$executor = Join-Path $PSScriptRoot 'ia/julgar-relato-cursor.ps1'
$amostraCsv = Join-Path $repo 'evidencias/avaliacao/amostra-qualitativa-cega.csv'

function Write-LoteProgresso {
    param([Parameter(Mandatory = $true)][string]$Mensagem)
    $timestamp = [DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss')
    [Console]::Error.WriteLine("[JULGAMENTO $timestamp] $Mensagem")
}

function Get-CursorFixado {
    $resolvido = @(Get-Command $ExecutavelCursor -CommandType Application,ExternalScript `
        -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($resolvido.Count -eq 0) { throw "Cursor Agent nativo não encontrado no PATH: $ExecutavelCursor" }
    $origem = [string]$resolvido[0].Source
    if (-not $origem) { $origem = [string]$resolvido[0].Path }
    $extensao = [IO.Path]::GetExtension($origem).ToLowerInvariant()
    if ($extensao -in @('.cmd','.bat')) {
        $companheiro = [IO.Path]::ChangeExtension($origem, '.ps1')
        if (-not (Test-Path -LiteralPath $companheiro -PathType Leaf)) {
            throw "launcher $extensao do Cursor não possui wrapper PowerShell: $origem"
        }
        $origem = $companheiro; $extensao = '.ps1'
    }
    if ($extensao -eq '.ps1') {
        $windowsPowerShell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
        $linhas = @(& $windowsPowerShell -NoLogo -NoProfile -NonInteractive `
            -ExecutionPolicy Bypass -File $origem --version 2>&1)
        if ($LASTEXITCODE -ne 0 -or $linhas.Count -eq 0) {
            throw "não foi possível obter a versão do Cursor: $($linhas -join ' ')"
        }
        return [pscustomobject]@{ versao = ([string]$linhas[-1]).Trim(); executavel = $origem }
    }
    $linhas = @(& $origem --version 2>&1)
    if ($LASTEXITCODE -ne 0 -or $linhas.Count -eq 0) {
        throw "não foi possível obter a versão do Cursor: $($linhas -join ' ')"
    }
    return [pscustomobject]@{ versao = ([string]$linhas[-1]).Trim(); executavel = $origem }
}

$schemaDoc = Read-IaJson $Schema
$assinaturaAtual = [ordered]@{
    schema_sha256 = Get-IaSha256 $Schema
    rubrica_sha256 = Get-IaSha256 $Rubrica
}

# Lê as tentativas de um relato e identifica a maior que continua íntegra:
# manifesto concluído, hashes conferem e a resposta ainda passa na validação.
function Get-EstadoRelato {
    param([Parameter(Mandatory = $true)][string]$Id)
    $raiz = Join-Path $SaidaDiretorio $Id
    $entradaPath = Join-Path $EntradasDiretorio "$Id.json"
    $entradaHash = Get-IaSha256 $entradaPath
    $entrada = Read-IaJson $entradaPath
    $maior = 0
    $melhor = $null
    if (Test-Path -LiteralPath $raiz -PathType Container) {
        foreach ($pasta in @(Get-ChildItem -LiteralPath $raiz -Directory | Sort-Object Name)) {
            if ($pasta.Name -notmatch '^tentativa-([0-9]{3,})$') { continue }
            $numero = [int]$Matches[1]
            if ($numero -gt $maior) { $maior = $numero }
            $manifestoPath = Join-Path $pasta.FullName 'manifesto.json'
            $respostaPath = Join-Path $pasta.FullName 'resposta.json'
            if (-not (Test-Path -LiteralPath $manifestoPath -PathType Leaf) -or
                -not (Test-Path -LiteralPath $respostaPath -PathType Leaf)) { continue }
            try {
                $manifesto = Read-IaJson $manifestoPath
                if ([string]$manifesto.estado -ne 'concluida' -or -not [bool]$manifesto.resposta_valida -or
                    [string]$manifesto.relatorio_id -cne $Id -or
                    [string]$manifesto.modelo_solicitado -ne $Modelo -or
                    [string]$manifesto.entrada_sha256 -ne $entradaHash -or
                    [string]$manifesto.schema_sha256 -ne $assinaturaAtual.schema_sha256 -or
                    [string]$manifesto.rubrica_sha256 -ne $assinaturaAtual.rubrica_sha256 -or
                    [string]$manifesto.resposta_sha256 -ne (Get-IaSha256 $respostaPath) -or
                    @($manifesto.violacoes).Count -ne 0) { continue }
                $registro = Read-IaJson $respostaPath
                $validacao = Test-JulgRegistro -Registro $registro -Schema $schemaDoc `
                    -Entrada $entrada -IdEsperado $Id
                if (-not $validacao.valido) { continue }
                $melhor = [pscustomobject]@{
                    tentativa = $numero
                    pasta = $pasta.FullName
                    manifesto = $manifesto
                    resposta_path = $respostaPath
                }
            }
            catch { continue }
        }
    }
    return [pscustomobject]@{
        id = $Id
        sucesso = $melhor
        proxima_tentativa = $maior + 1
    }
}

# Seleção dos relatos -------------------------------------------------------
Assert-Ia (Test-Path -LiteralPath $EntradasDiretorio -PathType Container) `
    "diretório de entradas ausente: $EntradasDiretorio"
$idsAmostra = @(Import-Csv -LiteralPath $amostraCsv -Encoding UTF8 |
    ForEach-Object { [string]$_.relatorio_id } | Sort-Object -Unique)
Assert-Ia ($idsAmostra.Count -eq 300) "a amostra deve conter 300 relatórios; encontrados $($idsAmostra.Count)"
$idsEntradas = @(Get-ChildItem -LiteralPath $EntradasDiretorio -Filter 'REL-*.json' -File |
    ForEach-Object { $_.BaseName } | Sort-Object)
Assert-Ia (($idsEntradas -join ',') -ceq ($idsAmostra -join ',')) `
    'as entradas preparadas diferem dos 300 relatórios da amostra'

if ($Consolidar) {
    $destino = Join-Path $privado 'respostas-selecionadas'
    $selecionadas = [Collections.Generic.List[object]]::new()
    $faltantes = [Collections.Generic.List[string]]::new()
    foreach ($id in $idsAmostra) {
        $estado = Get-EstadoRelato $id
        if ($null -eq $estado.sucesso) { $faltantes.Add($id); continue }
        $selecionadas.Add([ordered]@{
            relatorio_id = $id
            tentativa = $estado.sucesso.tentativa
            resposta_sha256 = [string]$estado.sucesso.manifesto.resposta_sha256
            sessao_id = [string]$estado.sucesso.manifesto.sessao_id
            modelo_exibido = [string]$estado.sucesso.manifesto.modelo_exibido
            versao_cliente = [string]$estado.sucesso.manifesto.versao_cliente
            duracao_segundos = $estado.sucesso.manifesto.duracao_segundos
            tokens_entrada = $estado.sucesso.manifesto.tokens_entrada
            tokens_saida = $estado.sucesso.manifesto.tokens_saida
            tokens_total = $estado.sucesso.manifesto.tokens_total
            manifesto = $estado.sucesso.pasta.Substring($repo.Length).TrimStart('\','/').Replace('\','/') + '/manifesto.json'
            _origem = $estado.sucesso.resposta_path
        })
    }
    Assert-Ia ($faltantes.Count -eq 0) `
        "seleção incompleta: $($selecionadas.Count)/300 válidos; faltam $($faltantes.Count) (ex.: $(@($faltantes | Select-Object -First 8) -join ', '))"
    $sessoes = @($selecionadas | ForEach-Object { $_.sessao_id } | Sort-Object -Unique)
    Assert-Ia ($sessoes.Count -eq 300) 'sessão repetida entre relatos'
    New-Item -ItemType Directory -Force -Path $destino | Out-Null
    foreach ($item in $selecionadas) {
        $alvo = Join-Path $destino "$($item.relatorio_id).json"
        if (Test-Path -LiteralPath $alvo -PathType Leaf) {
            Assert-Ia ((Get-IaSha256 $alvo) -eq $item.resposta_sha256) `
                "canônico já existente com conteúdo diferente: $($item.relatorio_id)"
        }
    }
    foreach ($item in $selecionadas) {
        $alvo = Join-Path $destino "$($item.relatorio_id).json"
        if (-not (Test-Path -LiteralPath $alvo -PathType Leaf)) {
            $temporario = "$alvo.part"
            Copy-Item -LiteralPath $item._origem -Destination $temporario -ErrorAction Stop
            Assert-Ia ((Get-IaSha256 $temporario) -eq $item.resposta_sha256) `
                "resposta alterada durante a cópia: $($item.relatorio_id)"
            Move-Item -LiteralPath $temporario -Destination $alvo -ErrorAction Stop
        }
    }
    $relatorioSelecao = [ordered]@{
        schema_version = '1.0'
        tipo = 'selecao-julgamentos-cursor-v1'
        regra = 'Maior tentativa concluída e íntegra por relato; o valor das notas não participa.'
        timestamp_utc = Get-IaTimestampUtc
        modelo_solicitado = $Modelo
        n_esperados = 300
        n_validos = $selecionadas.Count
        schema_sha256 = $assinaturaAtual.schema_sha256
        rubrica_sha256 = $assinaturaAtual.rubrica_sha256
        versoes_cliente = @($selecionadas | ForEach-Object { $_.versao_cliente } | Sort-Object -Unique)
        modelos_exibidos = @($selecionadas | ForEach-Object { $_.modelo_exibido } | Sort-Object -Unique)
        chave = 'Não lida por este script.'
        selecionadas = @($selecionadas | ForEach-Object {
            $copia = [ordered]@{}
            foreach ($chave in $_.Keys) { if ($chave -ne '_origem') { $copia[$chave] = $_[$chave] } }
            $copia
        })
    }
    $selecaoPath = Join-Path $privado 'selecao-respostas-cursor.json'
    [IO.File]::WriteAllText($selecaoPath, (($relatorioSelecao | ConvertTo-Json -Depth 8) + "`n"), $script:IaUtf8)
    Write-LoteProgresso "300 respostas copiadas para $destino; seleção em $selecaoPath"
    Write-Output 'Próximo passo (chave ainda fechada): python3 build/avaliacao-qualitativa-processo/finalizar-rubrica.py --congelar'
    return
}

if ($null -ne $Ids -and $Ids.Count -gt 0) {
    $selecionados = @($Ids | Sort-Object -Unique)
    foreach ($id in $selecionados) {
        if ($id -notin $idsAmostra) { throw "relato fora da amostra: $id" }
    }
}
else {
    $selecionados = @($idsAmostra | Select-Object -Skip ($Inicio - 1) -First $Limite)
}
if ($selecionados.Count -eq 0) { throw 'nenhum relato selecionado' }
if (-not $SomentePlanejar -and -not $ConfirmarExecucao) {
    throw 'lote externo exige -ConfirmarExecucao; use -SomentePlanejar antes de consumir tokens'
}

$cursorFixado = if ($SomentePlanejar) {
    [pscustomobject]@{ versao = $null; executavel = $ExecutavelCursor }
} else { Get-CursorFixado }

$tarefas = [Collections.Generic.List[object]]::new()
foreach ($id in $selecionados) {
    $estado = Get-EstadoRelato $id
    $tarefas.Add([pscustomobject]@{
        id = $id
        concluida = ($null -ne $estado.sucesso)
        tentativa_sucesso = if ($null -eq $estado.sucesso) { $null } else { $estado.sucesso.tentativa }
        proxima_tentativa = [int]$estado.proxima_tentativa
    })
}
$pendentes = @($tarefas | Where-Object { -not $_.concluida })

if ($SomentePlanejar) {
    if ($pendentes.Count -gt 0) {
        $primeiro = $pendentes[0]
        $planoTexto = & $executor -RelatorioId $primeiro.id -Tentativa $primeiro.proxima_tentativa `
            -Modelo $Modelo -PadraoModeloExibido $PadraoModeloExibido `
            -EntradasDiretorio $EntradasDiretorio -SaidaDiretorio $SaidaDiretorio `
            -Rubrica $Rubrica -Schema $Schema -ExecutavelCursor $ExecutavelCursor `
            -TimeoutSegundos $TimeoutSegundos -SomentePlanejar
        [void](($planoTexto -join "`n") | ConvertFrom-Json -ErrorAction Stop)
    }
    [ordered]@{
        schema_version = '1.0'
        tipo = 'plano-lote-julgamento-rubrica'
        ferramenta = 'cursor'
        modelo = $Modelo
        saida = $SaidaDiretorio
        rubrica_sha256 = $assinaturaAtual.rubrica_sha256
        schema_sha256 = $assinaturaAtual.schema_sha256
        relatos = $tarefas.Count
        concluidos = $tarefas.Count - $pendentes.Count
        chamadas_planejadas = $pendentes.Count
        ordem = @($tarefas | ForEach-Object {
            [ordered]@{
                relatorio_id = $_.id
                tentativa = $_.proxima_tentativa
                acao = if ($_.concluida) { 'pular_concluido' } else { 'executar' }
            }
        })
    } | ConvertTo-Json -Depth 6 -Compress
    return
}

Write-LoteProgresso "$($tarefas.Count) relatos; $($pendentes.Count) pendentes; Cursor $($cursorFixado.versao); modelo $Modelo"
$resultados = [Collections.Generic.List[object]]::new()
$falhasSeguidas = 0
$interrompido = $null
$indice = 0
if ($Paralelo -gt 1) {
    Write-LoteProgresso "execução paralela: até $Paralelo relatos simultâneos"
    $bloco = {
        param($Executor, $Id, $TentativaInicial, $Tentativas, $Modelo, $Padrao, $Entradas, $Saida, $Rubrica, $Schema, $Cursor, $Timeout)
        $ErrorActionPreference = 'Stop'
        $tentativa = $TentativaInicial
        $falhas = 0
        $ok = $false
        $falha = $null
        for ($n = 1; $n -le $Tentativas; $n++) {
            try {
                $retorno = @(& $Executor -RelatorioId $Id -Tentativa $tentativa `
                    -Modelo $Modelo -PadraoModeloExibido $Padrao `
                    -EntradasDiretorio $Entradas -SaidaDiretorio $Saida `
                    -Rubrica $Rubrica -Schema $Schema -ExecutavelCursor $Cursor `
                    -TimeoutSegundos $Timeout -ConfirmarExecucao)
                $manifesto = ($retorno -join "`n") | ConvertFrom-Json -ErrorAction Stop
                $ok = [string]$manifesto.estado -eq 'concluida' -and [bool]$manifesto.resposta_valida
                $falha = if ($ok) { $null } else { "$($manifesto.falha_tipo): $($manifesto.falha_mensagem)" }
            }
            catch {
                $ok = $false
                $falha = "falha_lote: $($_.Exception.Message)"
            }
            $tentativa++
            if ($ok) { break }
            $falhas++
        }
        [pscustomobject]@{
            relatorio_id = $Id; ok = $ok; falhas = $falhas
            tentativa_final = $tentativa - 1; falha = $falha
        }
    }
    $fila = [Collections.Generic.Queue[object]]::new()
    foreach ($tarefa in $tarefas) {
        if ($tarefa.concluida) {
            $resultados.Add([pscustomobject]@{
                relatorio_id = $tarefa.id; tentativa = $tarefa.tentativa_sucesso
                resultado = 'pulado_concluido'; falha = $null
            })
        }
        else { $fila.Enqueue($tarefa) }
    }
    $totalFila = $fila.Count
    $terminados = 0
    $ativos = [Collections.Generic.List[object]]::new()
    try {
        while ($fila.Count -gt 0 -or $ativos.Count -gt 0) {
            while (-not $interrompido -and $fila.Count -gt 0 -and $ativos.Count -lt $Paralelo) {
                $tarefa = $fila.Dequeue()
                $job = Start-Job -ScriptBlock $bloco -ArgumentList @(
                    $executor, $tarefa.id, [int]$tarefa.proxima_tentativa, $TentativasPorRelato,
                    $Modelo, $PadraoModeloExibido, $EntradasDiretorio, $SaidaDiretorio,
                    $Rubrica, $Schema, $cursorFixado.executavel, $TimeoutSegundos)
                $ativos.Add([pscustomobject]@{ job = $job; id = $tarefa.id; inicio = [DateTime]::Now })
                Write-LoteProgresso "$($tarefa.id)/tentativa-$('{0:D3}' -f [int]$tarefa.proxima_tentativa): enviado (ativos=$($ativos.Count))"
                Start-Sleep -Seconds 1
            }
            if ($ativos.Count -eq 0) { break }
            [void](Wait-Job -Job @($ativos | ForEach-Object { $_.job }) -Any -Timeout 5)
            $prontos = @($ativos | Where-Object { $_.job.State -notin @('Running','NotStarted') })
            foreach ($item in $prontos) {
                $ativos.Remove($item) | Out-Null
                $terminados++
                $r = $null
                try {
                    $r = @(Receive-Job -Job $item.job -ErrorAction Stop |
                        Where-Object { $null -ne $_ -and $null -ne $_.PSObject.Properties['relatorio_id'] }) |
                        Select-Object -Last 1
                }
                catch { $r = $null }
                if ($null -eq $r) {
                    $motivo = 'job sem resultado'
                    if ($item.job.State -eq 'Failed' -and $item.job.ChildJobs.Count -gt 0 -and
                        $null -ne $item.job.ChildJobs[0].JobStateInfo.Reason) {
                        $motivo = $item.job.ChildJobs[0].JobStateInfo.Reason.Message
                    }
                    $r = [pscustomobject]@{
                        relatorio_id = $item.id; ok = $false; falhas = 1
                        tentativa_final = 0; falha = "falha_lote: $motivo"
                    }
                }
                Remove-Job -Job $item.job -Force
                $segundos = [int]([DateTime]::Now - $item.inicio).TotalSeconds
                if ([bool]$r.ok) {
                    $falhasSeguidas = 0
                    Write-LoteProgresso "[$terminados/$totalFila] $($item.id): concluído em $segundos s (ativos=$($ativos.Count))"
                }
                else {
                    $falhasSeguidas += [int]$r.falhas
                    Write-LoteProgresso "[$terminados/$totalFila] $($item.id): falha ($($r.falha)) após $segundos s"
                    if (-not $interrompido) {
                        if ($falhasSeguidas -ge $FalhasConsecutivasMax) {
                            $interrompido = "$falhasSeguidas falhas consecutivas; lote interrompido para evitar consumo inútil"
                        }
                        elseif ($PararEmFalha) { $interrompido = 'parada solicitada por -PararEmFalha' }
                        if ($interrompido) { Write-LoteProgresso "$interrompido; aguardando os $($ativos.Count) em andamento" }
                    }
                }
                $resultados.Add([pscustomobject]@{
                    relatorio_id = $item.id; tentativa = [int]$r.tentativa_final
                    resultado = if ([bool]$r.ok) { 'concluido' } else { 'falha' }
                    falha = $r.falha
                })
            }
        }
    }
    finally {
        foreach ($item in @($ativos)) {
            Stop-Job -Job $item.job -ErrorAction SilentlyContinue
            Remove-Job -Job $item.job -Force -ErrorAction SilentlyContinue
        }
    }
}
else {
foreach ($tarefa in $tarefas) {
    $indice++
    if ($tarefa.concluida) {
        Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.id): já concluído; pulando"
        $resultados.Add([pscustomobject]@{
            relatorio_id = $tarefa.id; tentativa = $tarefa.tentativa_sucesso
            resultado = 'pulado_concluido'; falha = $null
        })
        continue
    }
    $tentativa = $tarefa.proxima_tentativa
    $final = $null
    for ($n = 1; $n -le $TentativasPorRelato; $n++) {
        Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.id)/tentativa-$('{0:D3}' -f $tentativa): iniciando"
        try {
            $saida = @(& $executor -RelatorioId $tarefa.id -Tentativa $tentativa `
                -Modelo $Modelo -PadraoModeloExibido $PadraoModeloExibido `
                -EntradasDiretorio $EntradasDiretorio -SaidaDiretorio $SaidaDiretorio `
                -Rubrica $Rubrica -Schema $Schema `
                -ExecutavelCursor $cursorFixado.executavel `
                -TimeoutSegundos $TimeoutSegundos -ConfirmarExecucao)
            $manifesto = ($saida -join "`n") | ConvertFrom-Json -ErrorAction Stop
            $ok = [string]$manifesto.estado -eq 'concluida' -and [bool]$manifesto.resposta_valida
            $falha = if ($ok) { $null } else { "$($manifesto.falha_tipo): $($manifesto.falha_mensagem)" }
        }
        catch {
            $ok = $false
            $falha = "falha_lote: $($_.Exception.Message)"
        }
        $tentativa++
        if ($ok) { $falhasSeguidas = 0; $final = [pscustomobject]@{ resultado = 'concluido'; falha = $null }; break }
        $falhasSeguidas++
        $final = [pscustomobject]@{ resultado = 'falha'; falha = $falha }
        Write-LoteProgresso "[$indice/$($tarefas.Count)] $($tarefa.id): falha ($falha)"
        if ($falhasSeguidas -ge $FalhasConsecutivasMax) {
            $interrompido = "$falhasSeguidas falhas consecutivas; lote interrompido para evitar consumo inútil"
            break
        }
    }
    $resultados.Add([pscustomobject]@{
        relatorio_id = $tarefa.id; tentativa = $tentativa - 1
        resultado = $final.resultado; falha = $final.falha
    })
    if ($interrompido) { Write-LoteProgresso $interrompido; break }
    if ($final.resultado -eq 'falha' -and $PararEmFalha) { break }
}
}

$resumo = [ordered]@{
    schema_version = '1.0'
    tipo = 'resumo-lote-julgamento-rubrica'
    ferramenta = 'cursor'
    modelo_solicitado = $Modelo
    versao_cursor = $cursorFixado.versao
    rubrica_sha256 = $assinaturaAtual.rubrica_sha256
    schema_sha256 = $assinaturaAtual.schema_sha256
    relatos_planejados = $tarefas.Count
    processados = $resultados.Count
    concluidos = @($resultados | Where-Object { $_.resultado -eq 'concluido' }).Count
    pulados = @($resultados | Where-Object { $_.resultado -eq 'pulado_concluido' }).Count
    falhas = @($resultados | Where-Object { $_.resultado -eq 'falha' }).Count
    interrompido = $interrompido
    resultados = @($resultados)
}
$loteId = 'LOTE-{0}' -f [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$loteDir = Join-Path (Join-Path $SaidaDiretorio 'lotes') $loteId
New-Item -ItemType Directory -Path $loteDir -ErrorAction Stop | Out-Null
$resumoPath = Join-Path $loteDir 'resumo.json'
$resumoJson = $resumo | ConvertTo-Json -Depth 8 -Compress
[IO.File]::WriteAllText($resumoPath, $resumoJson + "`n", $script:IaUtf8)
Write-LoteProgresso "lote encerrado; resumo=$resumoPath"
$resumoJson
