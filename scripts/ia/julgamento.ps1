Set-StrictMode -Version Latest

# Biblioteca da avaliação qualitativa por rubrica. Carregada por ponto
# (". julgamento.ps1") pelos scripts de execução e de teste. Usa somente
# recursos do Windows PowerShell 5.1 e não depende de Python.
. (Join-Path $PSScriptRoot 'comum.ps1')

$script:JulgCriterios = @(
    'correcao_tecnica','localizacao','acionabilidade',
    'clareza_problema','clareza_risco','clareza_contexto',
    'clareza_concretude','clareza_concisao'
)

function Test-JulgTipo {
    param($Valor, [string]$Tipo)
    switch ($Tipo) {
        'object' {
            return ($null -ne $Valor -and
                $Valor.GetType().FullName -eq 'System.Management.Automation.PSCustomObject')
        }
        'array' { return ($Valor -is [System.Array]) }
        'string' { return ($Valor -is [string]) }
        'integer' { return ($Valor -is [int] -or $Valor -is [long]) }
        'number' {
            if ($Valor -is [int] -or $Valor -is [long]) { return $true }
            if ($Valor -is [double]) {
                return (-not [double]::IsNaN($Valor) -and -not [double]::IsInfinity($Valor))
            }
            return ($Valor -is [decimal])
        }
        'boolean' { return ($Valor -is [bool]) }
        'null' { return ($null -eq $Valor) }
        default { return $false }
    }
}

# Interpreta o subconjunto de JSON Schema usado em schema-julgamento.json.
# Devolve a primeira violação encontrada ou $null.
function Test-JulgSchema {
    param($Valor, $Spec, [string]$Caminho = '$')

    $tipoSpec = Get-IaValor $Spec 'type'
    [object[]]$tipos = if ($null -eq $tipoSpec) { @() } else { @($tipoSpec) }
    if ($tipos.Count -gt 0) {
        $compativel = $false
        foreach ($tipo in $tipos) {
            if (Test-JulgTipo $Valor ([string]$tipo)) { $compativel = $true; break }
        }
        if (-not $compativel) { return "${Caminho}: tipo incompatível com $($tipos -join '|')" }
    }

    $enum = Get-IaValor $Spec 'enum'
    if ($null -ne $enum) {
        $encontrado = $false
        foreach ($permitido in @($enum)) {
            if ($Valor -is [string] -and $Valor -ceq [string]$permitido) { $encontrado = $true; break }
        }
        if (-not $encontrado) { return "${Caminho}: valor fora do enum" }
    }

    if (Test-JulgTipo $Valor 'object') {
        $obrigatorios = Get-IaValor $Spec 'required'
        $propriedades = Get-IaValor $Spec 'properties'
        $presentes = @($Valor.PSObject.Properties.Name)
        if ($null -ne $obrigatorios) {
            $ausentes = @(@($obrigatorios) | Where-Object { $_ -cnotin $presentes })
            if ($ausentes.Count -gt 0) { return "${Caminho}: campos ausentes $($ausentes -join ',')" }
        }
        [string[]]$nomesSpec = if ($null -eq $propriedades) { @() } else { @($propriedades.PSObject.Properties.Name) }
        if ((Get-IaValor $Spec 'additionalProperties') -eq $false) {
            $extras = @($presentes | Where-Object { $_ -cnotin $nomesSpec })
            if ($extras.Count -gt 0) { return "${Caminho}: campos inesperados $($extras -join ',')" }
        }
        foreach ($nome in $presentes) {
            if ($nome -cin $nomesSpec) {
                $erro = Test-JulgSchema $Valor.$nome $propriedades.$nome "$Caminho.$nome"
                if ($erro) { return $erro }
            }
        }
    }
    elseif ($Valor -is [System.Array]) {
        $itemSpec = Get-IaValor $Spec 'items'
        if ($null -ne $itemSpec) {
            for ($i = 0; $i -lt $Valor.Count; $i++) {
                $erro = Test-JulgSchema $Valor[$i] $itemSpec "$Caminho[$i]"
                if ($erro) { return $erro }
            }
        }
    }
    elseif ($Valor -is [string]) {
        $padrao = Get-IaValor $Spec 'pattern'
        if ($null -ne $padrao -and -not [regex]::IsMatch($Valor, [string]$padrao)) {
            return "${Caminho}: formato inválido"
        }
    }
    elseif ($null -ne $Valor -and (Test-JulgTipo $Valor 'number')) {
        $minimo = Get-IaValor $Spec 'minimum'
        $maximo = Get-IaValor $Spec 'maximum'
        if (($null -ne $minimo -and [double]$Valor -lt [double]$minimo) -or
            ($null -ne $maximo -and [double]$Valor -gt [double]$maximo)) {
            return "${Caminho}: fora da escala"
        }
    }
    return $null
}

# 25 * [(T-1)/4 + (L-1)/4 + (A-1)/4 + soma(clareza)/5]; $null se faltar nota.
function Get-JulgScoreDerivado {
    param($Criterios)
    $notas = [Collections.Generic.List[double]]::new()
    foreach ($campo in $script:JulgCriterios) {
        $nota = $Criterios.$campo.nota
        if ($null -eq $nota) { return $null }
        $notas.Add([double]$nota)
    }
    $ordinais = (($notas[0] - 1) / 4) + (($notas[1] - 1) / 4) + (($notas[2] - 1) / 4)
    $clareza = 0.0
    foreach ($i in 3..7) { $clareza += $notas[$i] }
    return [Math]::Round(25 * ($ordinais + $clareza / 5), 6)
}

function Get-JulgMateriaisFornecidos {
    param($Entrada)
    $conhecidos = @{}
    $origem = Get-IaValor $Entrada 'referencia_origem'
    if ($null -ne $origem -and (Get-IaValor $origem 'caminho')) {
        $conhecidos[([string]$origem.caminho).Replace('\', '/')] = ([string]$origem.sha256).ToLowerInvariant()
    }
    $arquivoRelato = ([string](Get-IaValor $Entrada.relatorio 'arquivo')).Replace('\', '/')
    foreach ($item in @(Get-IaValor $Entrada 'codigo')) {
        if ($null -eq $item) { continue }
        $caminho = ([string]$item.caminho).Replace('\', '/')
        $hash = if ($item.sha256) { ([string]$item.sha256).ToLowerInvariant() } else { $null }
        $conhecidos[$caminho] = $hash
        if ($arquivoRelato -and $caminho.EndsWith('/' + $arquivoRelato)) {
            $conhecidos[$arquivoRelato] = $hash
        }
    }
    return $conhecidos
}

# Confere o material citado com o que foi efetivamente entregue ao julgador.
# Devolve @{ erro = <texto|$null>; avisos = @(...) }.
function Test-JulgMateriais {
    param($Registro, $Entrada)
    $conhecidos = Get-JulgMateriaisFornecidos $Entrada
    $hashes = @{}
    foreach ($valor in $conhecidos.Values) { if ($null -ne $valor) { $hashes[[string]$valor] = $true } }
    $avisos = [Collections.Generic.List[string]]::new()
    $origem = Get-IaValor $Entrada 'referencia_origem'
    $hashOrigem = if ($null -ne $origem -and $origem.sha256) { ([string]$origem.sha256).ToLowerInvariant() } else { $null }

    foreach ($item in @($Registro.material_consultado)) {
        $caminho = ([string]$item.caminho).Trim().Replace('\', '/')
        $hash = if ($null -ne $item.sha256) { ([string]$item.sha256).ToLowerInvariant() } else { $null }
        if ($null -ne $hash -and -not $hashes.ContainsKey($hash)) {
            return @{ erro = "hash de material não fornecido nesta entrada: $caminho"; avisos = @($avisos) }
        }
        if ($conhecidos.ContainsKey($caminho)) {
            $esperado = $conhecidos[$caminho]
            if ($null -ne $hash -and $hash -ne $esperado) {
                return @{ erro = "hash não pertence ao caminho declarado: $caminho"; avisos = @($avisos) }
            }
            if ($null -eq $hash -and $null -ne $esperado) {
                $avisos.Add("hash omitido na resposta, mas preservado na entrada: $caminho")
            }
            continue
        }
        $minusculo = $caminho.ToLowerInvariant()
        $espaco = $minusculo.Replace('material-cego/', 'material-cego.')
        $prefixos = @('material-cego.relatorio','material-cego.referencia','material-cego.codigo',
            'relato','referencia','codigo')
        $virtual = $false
        foreach ($prefixo in $prefixos) { if ($espaco.StartsWith($prefixo)) { $virtual = $true; break } }
        if (-not $virtual -or $espaco.Contains('/') -or
            $espaco -match '\.(py|json|md|html|yml|yaml|xml|txt)$') {
            return @{ erro = "material/caminho não fornecido nesta entrada: $caminho"; avisos = @($avisos) }
        }
        if ($minusculo.Contains('relato') -and $null -ne $hash) {
            return @{ erro = 'relato virtual não possui hash próprio fornecido'; avisos = @($avisos) }
        }
        if ($minusculo.Contains('referencia') -and $null -ne $hash -and
            ($null -eq $hashOrigem -or $hash -ne $hashOrigem)) {
            return @{ erro = 'hash da referência virtual incompatível com a origem'; avisos = @($avisos) }
        }
        $avisos.Add("âncora virtual da mensagem: $caminho")
    }
    return @{ erro = $null; avisos = @($avisos) }
}

# Valida um julgamento já convertido de JSON. Nunca altera notas nem infere
# valores ausentes: apenas aceita ou rejeita.
function Test-JulgRegistro {
    param(
        [Parameter(Mandatory = $true)]$Registro,
        [Parameter(Mandatory = $true)]$Schema,
        [Parameter(Mandatory = $true)]$Entrada,
        [Parameter(Mandatory = $true)][string]$IdEsperado
    )
    $falha = {
        param([string]$Mensagem)
        [pscustomobject]@{ valido = $false; erro = $Mensagem; avisos = @() }
    }

    $erroSchema = Test-JulgSchema $Registro $Schema
    if ($erroSchema) { return (& $falha $erroSchema) }
    if ([string]$Registro.relatorio_id -cne $IdEsperado) {
        return (& $falha "ID recebido $($Registro.relatorio_id), esperado $IdEsperado")
    }

    $relatorio = $Entrada.relatorio
    $abstencoes = [Collections.Generic.List[string]]::new()
    foreach ($campo in $script:JulgCriterios) {
        $criterio = $Registro.criterios.$campo
        if (-not ([string]$criterio.justificativa).Trim()) { return (& $falha "${campo}: justificativa vazia") }
        $evidencias = @($criterio.evidencias)
        if ($criterio.status -ceq 'abstencao') {
            if ($null -ne $criterio.nota) { return (& $falha "${campo}: abstenção deve ter nota null") }
            $abstencoes.Add($campo)
        }
        else {
            if ($null -eq $criterio.nota) { return (& $falha "${campo}: avaliado exige nota") }
            if ($evidencias.Count -eq 0) { return (& $falha "${campo}: evidência obrigatória") }
        }
        foreach ($evidencia in $evidencias) {
            if (-not ([string]$evidencia.fonte).Trim()) { return (& $falha "${campo}: fonte/trecho vazio") }
            if (-not ([string]$evidencia.trecho).Trim()) {
                # Único caso em que um trecho vazio é um fato verificável: o
                # campo recomendação do relato é vazio e a descrição, citada
                # literalmente, comprova que também não traz solução.
                $ausenciaComprovada = $false
                if ($campo -eq 'acionabilidade' -and
                    $evidencia.fonte -ceq 'relatorio.recomendacao' -and
                    [string]$relatorio.recomendacao -eq '' -and
                    [string]$relatorio.relatorio_id -ceq [string]$Registro.relatorio_id) {
                    $descricao = [string]$relatorio.descricao
                    foreach ($outra in $evidencias) {
                        if ($outra.fonte -cin @('relatorio.descricao','material-cego.relatorio') -and
                            ([string]$outra.trecho).Trim() -and
                            $descricao.Contains([string]$outra.trecho)) { $ausenciaComprovada = $true }
                    }
                }
                if (-not $ausenciaComprovada) { return (& $falha "${campo}: fonte/trecho vazio") }
            }
        }
    }

    $declaradas = @($Registro.abstencoes)
    if ($declaradas.Count -ne @($declaradas | Sort-Object -Unique).Count -or
        (@($declaradas | Sort-Object) -join '|') -cne (@($abstencoes | Sort-Object) -join '|')) {
        return (& $falha 'abstenções não correspondem aos critérios')
    }

    $materiais = @($Registro.material_consultado)
    if ($materiais.Count -eq 0) { return (& $falha 'material consultado obrigatório') }
    foreach ($material in $materiais) {
        if (-not ([string]$material.caminho).Trim() -or -not ([string]$material.escopo).Trim()) {
            return (& $falha 'material vazio')
        }
        if ($null -ne $material.sha256 -and [string]$material.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
            return (& $falha 'sha256 do material deve ter 64 hexadecimais')
        }
    }
    $verificacaoMateriais = Test-JulgMateriais $Registro $Entrada
    if ($verificacaoMateriais.erro) { return (& $falha ([string]$verificacaoMateriais.erro)) }

    $esperado = Get-JulgScoreDerivado $Registro.criterios
    if ($null -eq $esperado) {
        if ($null -ne $Registro.score_total) { return (& $falha 'score deve ser null havendo abstenção') }
    }
    elseif ($null -eq $Registro.score_total -or
        [Math]::Abs([double]$Registro.score_total - $esperado) -gt 1e-5) {
        return (& $falha "score $($Registro.score_total) diverge do derivado $esperado")
    }
    return [pscustomobject]@{
        valido = $true
        erro = $null
        avisos = @($verificacaoMateriais.avisos)
    }
}

# Extrai o único objeto JSON da mensagem final. Aceita somente o objeto puro ou
# envolvido por uma única cerca de código; não procura objetos dentro de prosa.
function Get-JulgJsonDaResposta {
    param([AllowEmptyString()][string]$Texto)
    $limpo = $Texto.Trim()
    $cerca = [regex]::Match($limpo, '^```[A-Za-z]*[ \t]*\r?\n(?<c>[\s\S]*?)\r?\n```$')
    if ($cerca.Success) { $limpo = $cerca.Groups['c'].Value.Trim() }
    if (-not ($limpo.StartsWith('{') -and $limpo.EndsWith('}'))) {
        return [pscustomobject]@{ valido = $false; erro = 'a resposta não é um único objeto JSON'; texto = $null }
    }
    return [pscustomobject]@{ valido = $true; erro = $null; texto = $limpo }
}

function New-JulgPrompt {
    param(
        [Parameter(Mandatory = $true)][string]$RubricaBase,
        [Parameter(Mandatory = $true)][string]$SchemaTexto,
        [Parameter(Mandatory = $true)][string]$EntradaTexto,
        [Parameter(Mandatory = $true)][string]$RelatorioId
    )
    $schemaCompacto = ($SchemaTexto | ConvertFrom-Json | ConvertTo-Json -Depth 30 -Compress)
    $partes = @(
        $RubricaBase.TrimEnd(),
        '',
        'NÃO use qualquer ferramenta, shell, rede, MCP ou arquivo externo. Examine somente',
        'o material abaixo; não execute código. Justificativas e evidências devem ser',
        'concisas e específicas.',
        '',
        'FORMATO DE SAÍDA',
        "Responda com um único objeto JSON, sem texto antes ou depois e sem cerca de",
        "código, que satisfaça exatamente o JSON Schema abaixo. Propriedades adicionais",
        "são proibidas; as notas são números inteiros; nota null só com status abstencao.",
        "O relatorio_id deve ser exatamente $RelatorioId. O score_total deve seguir a",
        'fórmula acima, sem arredondar abaixo de seis casas decimais (o pipeline o',
        'recalcula a partir das notas; confira com cuidado, mas não altere notas por isso).',
        'Toda evidência exige fonte e trecho não vazios. Única exceção: quando o campo',
        'recomendacao do relato está vazio (qualquer nota de acionabilidade), cita-se a',
        'fonte "relatorio.recomendacao" com trecho vazio, sempre acompanhada de uma',
        'evidência "relatorio.descricao" com trecho literal e não vazio da descrição.',
        'Em material_consultado, use o caminho e o sha256 exatos dos arquivos de código e',
        'da origem da referência fornecidos; para o relato e para a referência inline,',
        'use "material-cego.relatorio" e "material-cego.referencia" com sha256 null.',
        '',
        'SCHEMA_JSON_INICIO',
        $schemaCompacto,
        'SCHEMA_JSON_FIM',
        '',
        '<material-cego>',
        $EntradaTexto.TrimEnd(),
        '</material-cego>'
    )
    return ($partes -join "`n") + "`n"
}

# Interpreta o stream-json do Cursor Agent para uma chamada de julgamento.
function ConvertFrom-JulgEventosCursor {
    param([AllowEmptyString()][string]$Stdout)
    $eventos = @(ConvertFrom-IaJsonl $Stdout)
    $sessao = $null; $modeloExibido = $null; $resposta = $null
    $entrada = $null; $saida = $null; $total = $null
    $erroFerramenta = $null
    $violacoes = [Collections.Generic.List[string]]::new()
    foreach ($evento in $eventos) {
        $tipo = [string](Get-IaValor $evento 'type')
        if ($tipo -eq 'system') {
            $s = Get-IaValor $evento 'session_id'
            $m = Get-IaValor $evento 'model'
            if ($null -ne $s) { $sessao = [string]$s }
            if ($null -ne $m) { $modeloExibido = [string]$m }
        }
        elseif ($tipo -eq 'tool_call') {
            $chamada = Get-IaValor $evento 'tool_call'
            if ($null -eq $chamada) { $violacoes.Add('tool_call') }
            else { foreach ($nome in @($chamada.PSObject.Properties.Name)) { $violacoes.Add([string]$nome) } }
        }
        elseif ($tipo -eq 'result') {
            $texto = Get-IaValor $evento 'result'
            if ($null -ne $texto) { $resposta = [string]$texto }
            $s = Get-IaValor $evento 'session_id'
            if ($null -ne $s) { $sessao = [string]$s }
            if ((Get-IaValor $evento 'is_error') -eq $true) {
                $erroFerramenta = if ($null -ne $texto) { [string]$texto } else { 'result com is_error=true' }
            }
            $uso = Get-IaValor $evento 'usage'
            if ($null -ne $uso) {
                $tokens = ConvertFrom-IaUsoCursor $uso
                $entrada = $tokens.entrada; $saida = $tokens.saida; $total = $tokens.total
            }
        }
    }
    if ($null -eq $resposta) { throw 'JSONL do Cursor não contém evento result terminal' }
    return [pscustomobject]@{
        resposta = $resposta
        sessao_id = $sessao
        modelo_exibido = $modeloExibido
        tokens_entrada = $entrada
        tokens_saida = $saida
        tokens_total = $total
        erro_ferramenta = $erroFerramenta
        violacoes = [object[]]@($violacoes | Sort-Object -Unique)
    }
}
