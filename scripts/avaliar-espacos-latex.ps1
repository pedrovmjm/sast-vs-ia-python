<#
.SYNOPSIS
Lista pontos de espacamento para revisao manual, sem modificar o LaTeX.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/avaliar-espacos-latex.ps1 -Relatorio docs/ESPACAMENTOS-FUNDAMENTACAO.md
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/avaliar-espacos-latex.ps1 -Arquivo monografia/capitulos/introducao.tex
#>
[CmdletBinding()]
param(
    [string]$Arquivo = 'monografia/capitulos/fundamentacao.tex',
    [string]$Relatorio,
    [switch]$IncluirFimLinha
)

$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $Arquivo).Path
if ([IO.Path]::GetExtension($sourcePath) -ne '.tex') {
    throw 'O arquivo de entrada deve ser um .tex.'
}
if ($Relatorio) {
    $reportPath = [IO.Path]::GetFullPath($Relatorio)
    if ([IO.Path]::GetExtension($reportPath) -notin '.md', '.txt') {
        throw 'O relatorio deve ser .md ou .txt; nao e permitido escrever em .tex.'
    }
    if ($reportPath -eq $sourcePath) { throw 'Entrada e relatorio devem ser arquivos diferentes.' }
}

# A mascara mantem os indices originais para informar linha e coluna exatas.
function Hide-LatexLiterals([string]$Line) {
    $masked = $Line
    for ($position = 0; $position -lt $masked.Length; $position++) {
        if ($masked[$position] -ne '%') { continue }
        $slashes = 0
        for ($back = $position - 1; $back -ge 0 -and $masked[$back] -eq '\'; $back--) { $slashes++ }
        if ($slashes % 2 -eq 0) {
            $masked = $masked.Substring(0, $position)
            break
        }
    }
    $maskChar = [string][char]0xE000
    $literalPatterns = @(
        '\\verb\*?(?<delimiter>[^\w\s]).*?\k<delimiter>',
        '(?<!\\)\$\$.*?(?<!\\)\$\$|(?<!\\)\$(?:\\.|[^$\\])*\$',
        '\\\(.*?\\\)|\\\[.*?\\\]'
    )
    foreach ($pattern in $literalPatterns) {
        $masked = [regex]::Replace($masked, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{
            param($match)
            return $maskChar * $match.Length
        })
    }
    $commands = '\\(?:texttt|url|path|href|label|cite[A-Za-z]*|(?:auto|page|eq)?ref)\*?(?:\[[^\]]*\])*\{'
    foreach ($command in [regex]::Matches($masked, $commands)) {
        $start = $command.Index + $command.Length
        $end = $start
        $depth = 1
        while ($end -lt $masked.Length -and $depth -gt 0) {
            if ($masked[$end] -eq '{') { $depth++ }
            if ($masked[$end] -eq '}') { $depth-- }
            $end++
        }
        if ($depth -eq 0) {
            $length = $end - $start - 1
            $masked = $masked.Substring(0, $start) + ($maskChar * $length) + $masked.Substring($end - 1)
        }
    }
    return $masked
}

$rules = @(
    @{ Name = 'Espaco antes de pontuacao'; Pattern = '(?<=\S)[ \t]+(?=[,.;:!?])'; Advice = 'Conferir a remocao do espaco antes do sinal; nao remover a pontuacao.' },
    @{ Name = 'Espaco antes de referencia com til'; Pattern = '(?<=\S)[ \t]+~(?=\\(?:ref|pageref|autoref|eqref)\*?\{)'; Advice = 'O til ja insere espaco inseparavel. Conferir, por exemplo, Secao~\ref{...}.' },
    @{ Name = 'Espacos repetidos no fonte'; Pattern = '(?<=\S)[ \t]{2,}(?=[^\s~,.;:!?)])'; Advice = 'O LaTeX normalmente reduz estes espacos a um so. Conferir tambem se falta pontuacao; nao e necessariamente defeito no PDF.' },
    @{ Name = 'Possivel falta de espaco apos pontuacao'; Pattern = '[,:;!?](?=\p{L})|(?<!\.)\.(?=\p{L})'; Advice = 'Conferir a separacao entre palavras ou frases; abreviaturas e enderecos podem ser excecoes.' },
    @{ Name = 'Espaco na parte interna de parenteses'; Pattern = '\([ \t]+(?=\S)|(?<=\S)[ \t]+\)'; Advice = 'Conferir se o espaco apos abrir ou antes de fechar o parentese e intencional.' }
)
if ($IncluirFimLinha) {
    $rules += @{ Name = 'Espaco no fim da linha'; Pattern = '(?<=\S)[ \t]+$'; Advice = 'Normalmente sem efeito visual; revisar apenas a limpeza do fonte.' }
}

$lines = [IO.File]::ReadAllLines($sourcePath, [Text.Encoding]::UTF8)
$findings = [Collections.Generic.List[object]]::new()
$ignoredEnvironment = $null
for ($lineIndex = 0; $lineIndex -lt $lines.Length; $lineIndex++) {
    $line = $lines[$lineIndex]
    $visible = Hide-LatexLiterals $line
    if ($ignoredEnvironment) {
        if ($visible -match ('\\end\{' + [regex]::Escape($ignoredEnvironment) + '\}')) { $ignoredEnvironment = $null }
        continue
    }
    if ($visible -match '\\begin\{(verbatim\*?|lstlisting|minted|comment|equation\*?|align\*?|displaymath|math)\}') {
        $environment = $Matches[1]
        if ($visible -notmatch ('\\end\{' + [regex]::Escape($environment) + '\}')) { $ignoredEnvironment = $environment }
        continue
    }
    foreach ($rule in $rules) {
        foreach ($match in [regex]::Matches($visible, $rule.Pattern)) {
            $start = [Math]::Max(0, $match.Index - 42)
            $end = [Math]::Min($line.Length, $match.Index + $match.Length + 42)
            $context = $line.Substring($start, $match.Index - $start) + '[' + $line.Substring($match.Index, $match.Length) + ']' + $line.Substring($match.Index + $match.Length, $end - $match.Index - $match.Length)
            $context = $context.Replace(' ', [string][char]0xB7).Replace("`t", '<TAB>')
            $findings.Add([pscustomobject]@{ Line = $lineIndex + 1; Column = $match.Index + 1; Kind = $rule.Name; Advice = $rule.Advice; Context = $context })
        }
    }
}

$report = [Collections.Generic.List[string]]::new()
$report.Add('# Pontos de espacamento para revisao manual')
$report.Add('')
$report.Add('Arquivo: ' + $sourcePath)
$report.Add('')
$report.Add(('Total: {0} apontamentos em {1} linhas.' -f $findings.Count, @($findings.Line | Sort-Object -Unique).Count))
$report.Add('')
$report.Add('O script apenas le o .tex. Os apontamentos sao candidatos a revisao, nao correcoes automaticas. Cada espaco aparece como ' + [char]0xB7 + '; colchetes destacam a ocorrencia. Linha e coluna comecam em 1.')
$report.Add('')
$report.Add('Espacos repetidos no fonte geralmente sao reduzidos pelo LaTeX. Ja o espaco comum antes de ~ e a pontuacao afastada merecem conferir no PDF. Esta analise nao mede justificacao, margens, espaco vertical nem quebras de pagina.')
$report.Add('')
$report.Add('Comentarios, literais comuns e ambientes de codigo/matematica reconhecidos sao ignorados. A analise e heuristica e nao interpreta macros personalizadas nem toda a sintaxe do TeX.')
$report.Add('')
$report.Add('## Tipos encontrados')
$report.Add('')
foreach ($group in ($findings | Group-Object Kind)) { $report.Add(('- {0}: {1}' -f $group.Name, $group.Count)) }
$report.Add('')
$report.Add('## Ocorrencias')
$report.Add('')
foreach ($finding in ($findings | Sort-Object Line, Column, Kind)) {
    $report.Add(('### Linha {0}, coluna {1}: {2}' -f $finding.Line, $finding.Column, $finding.Kind))
    $report.Add('')
    $report.Add($finding.Advice)
    $report.Add('')
    $report.Add('```text')
    $report.Add($finding.Context)
    $report.Add('```')
    $report.Add('')
}
if ($Relatorio) {
    [IO.File]::WriteAllLines($reportPath, $report, [Text.UTF8Encoding]::new($false))
    Write-Output ('{0} apontamentos. Relatorio: {1}' -f $findings.Count, $reportPath)
} else {
    $report
}
