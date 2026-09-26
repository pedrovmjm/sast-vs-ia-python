[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^ALVO-[0-9]{4}$')][string]$Alvo,
    [ValidateRange(1,3)][int]$Repeticao = 1,
    [ValidateRange(1,2147483647)][int]$Tentativa = 1,
    [ValidateSet('piloto','coleta')][string]$Finalidade = 'piloto',
    [string]$Modelo = 'gpt-5.6-luna',
    [string]$ExecutavelCodex = 'codex',
    [ValidateRange(1,86400)][int]$TimeoutSegundos = 3600,
    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$adaptador = Join-Path $PSScriptRoot 'ia/executar-codex.ps1'
& $adaptador -Condicao C4 -Alvo $Alvo -Repeticao $Repeticao -Tentativa $Tentativa `
    -Finalidade $Finalidade -Modelo $Modelo -ExecutavelCodex $ExecutavelCodex `
    -TimeoutSegundos $TimeoutSegundos -SomentePlanejar:$SomentePlanejar `
    -ConfirmarExecucao:$ConfirmarExecucao
