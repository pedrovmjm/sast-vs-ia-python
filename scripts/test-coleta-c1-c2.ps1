[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Script = Join-Path $PSScriptRoot "executar-coleta-c1-c2.ps1"
$FilaRuntime = Join-Path $Repo "execucoes/fila-c1-c2.json"
$existiaAntes = Test-Path -LiteralPath $FilaRuntime

$linhas = @(& $Script -SomentePlanejar 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "plano seco falhou: $($linhas -join ' ')"
}
try {
    $plano = ($linhas -join "`n") | ConvertFrom-Json -ErrorAction Stop
}
catch { throw "plano seco não retornou JSON válido" }

if ([string]$plano.tipo -ne "plano-seco-coleta-c1-c2") {
    throw "tipo do plano seco diverge"
}
if ([int]$plano.quantidade -ne 52 -or @($plano.tarefas).Count -ne 52) {
    throw "plano seco deve conter exatamente 52 tarefas"
}
$ids = @($plano.tarefas | ForEach-Object { [string]$_.execucao_id })
if (@($ids | Sort-Object -Unique).Count -ne 52) {
    throw "plano seco contém execução duplicada"
}
foreach ($condicao in @("C1", "C2")) {
    if (@($plano.tarefas | Where-Object { $_.condicao -eq $condicao }).Count -ne 26) {
        throw "plano seco deve conter 26 tarefas $condicao"
    }
}
if ((Test-Path -LiteralPath $FilaRuntime) -ne $existiaAntes) {
    throw "plano seco alterou a existência da fila runtime"
}

[ordered]@{
    schema_version = "1.0"
    resultado = "aprovado"
    tarefas = 52
    c1 = 26
    c2 = 26
    criou_fila = $false
} | ConvertTo-Json -Compress
