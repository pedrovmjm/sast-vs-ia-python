[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^ALVO-[0-9]{4}$')][string]$Alvo,
    [ValidateRange(1,3)][int]$Repeticao = 1,
    [ValidateRange(1,2147483647)][int]$Tentativa = 1,
    [ValidateSet('piloto','coleta')][string]$Finalidade = 'piloto',
    [string]$Modelo = 'gpt-5.6-luna-medium',
    [ValidateSet('WSL','Nativo')][string]$ModoCursor = 'Nativo',
    [string]$DistribuicaoWsl,
    [string]$ExecutavelCursor = 'agent',
    [ValidateRange(1,86400)][int]$TimeoutSegundos = 3600,
    [switch]$SomentePlanejar,
    [switch]$ConfirmarExecucao
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$adaptador = Join-Path $PSScriptRoot 'ia/executar-cursor.ps1'
& $adaptador -Condicao C3 -Alvo $Alvo -Repeticao $Repeticao -Tentativa $Tentativa `
    -Finalidade $Finalidade -Modelo $Modelo -ModoCursor $ModoCursor `
    -DistribuicaoWsl $DistribuicaoWsl -ExecutavelCursor $ExecutavelCursor `
    -TimeoutSegundos $TimeoutSegundos -SomentePlanejar:$SomentePlanejar `
    -ConfirmarExecucao:$ConfirmarExecucao
