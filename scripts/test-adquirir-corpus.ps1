[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "adquirir-corpus.ps1"
$texto = Get-Content -LiteralPath $scriptPath -Raw -Encoding UTF8
[void][scriptblock]::Create($texto)

$falhas = [Collections.Generic.List[string]]::new()
function Assert-Contem {
    param([string]$Trecho, [string]$Nome)
    if (-not $texto.Contains($Trecho)) { $falhas.Add("AUSENTE $Nome") }
    else { Write-Host "PASS $Nome" }
}
function Assert-NaoContem {
    param([string]$Trecho, [string]$Nome)
    if ($texto.Contains($Trecho)) { $falhas.Add("PROIBIDO $Nome") }
    else { Write-Host "PASS $Nome" }
}

Assert-NaoContem '"checkout"' "não usa checkout"
Assert-NaoContem '"submodule"' "não inicializa submódulo"
Assert-Contem '"archive"' "exporta por git archive"
Assert-Contem '"--network", "none"' "desliga rede nos contêineres de dados"
Assert-Contem '"--read-only"' "usa rootfs somente leitura"
Assert-Contem '"--cap-drop", "ALL"' "remove capabilities"
Assert-Contem '"no-new-privileges"' "bloqueia novos privilégios"
Assert-Contem '"--user", "10001:10001"' "usa usuário não-root"
Assert-Contem '"--pull", "never"' "usa imagem local por ID"
Assert-Contem '"/oracle/validate_gt.py"' "executa validador oficial"
Assert-Contem '"auditar-ground-truth"' "executa auditoria autoral"
Assert-Contem '"$alvoId-REGENERADO"' "regenera cada alvo"
Assert-Contem '"$alvoId-inventario-regenerado.json"' "compara inventario regenerado"
Assert-Contem '"$alvoId-sanitizacao-regenerada.json"' "compara relatorio regenerado"

$origem = $texto.IndexOf('"--depth=1", "origin", $repoCommit', [StringComparison]::Ordinal)
$espelho = $texto.IndexOf('"--depth=1", "espelho", $repoCommit', [StringComparison]::Ordinal)
if ($origem -lt 0 -or $espelho -le $origem) { $falhas.Add("ORDEM fallback de espelho") }
else { Write-Host "PASS espelho somente após falha da origem" }

if ($falhas.Count -gt 0) {
    $falhas | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host "15 teste(s) de aquisição passaram; 0 falharam."
