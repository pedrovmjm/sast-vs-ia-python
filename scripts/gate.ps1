[CmdletBinding()]
param(
    [ValidateSet("quick", "full", "build")]
    [string]$Gate = "quick"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DockerStep {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ("docker " + ($Arguments -join " "))
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha no comando Docker (código $LASTEXITCODE): $($Arguments -join ' ')"
    }
}

Invoke-DockerStep -Arguments @("compose", "config", "--quiet")

if ($Gate -in @("full", "build")) {
    Invoke-DockerStep -Arguments @("compose", "build", "controlador")
}

if ($Gate -eq "build") {
    Invoke-DockerStep -Arguments @(
        "compose", "run", "--rm", "controlador",
        "python", "-m", "compileall", "-q", "runner", "tests"
    )
}

Invoke-DockerStep -Arguments @(
    "compose", "run", "--rm", "controlador",
    "python", "-m", "unittest", "discover", "-v",
    "-s", "tests", "-p", "test_*.py"
)

if ($Gate -eq "build") {
    Invoke-DockerStep -Arguments @(
        "compose", "run", "--rm", "controlador",
        "python", "tests/runtime_probe.py"
    )
    Invoke-DockerStep -Arguments @(
        "compose", "run", "--rm", "controlador",
        "python", "-m", "pip", "check"
    )
    Invoke-DockerStep -Arguments @(
        "compose", "run", "--rm", "controlador", "python", "--version"
    )
    Invoke-DockerStep -Arguments @(
        "compose", "run", "--rm", "controlador", "bandit", "--version"
    )
    Invoke-DockerStep -Arguments @(
        "compose", "run", "--rm", "controlador", "semgrep", "--version"
    )

    $embeddedCheck = "from runner.aquisicao import verificar_fontes; verificar_fontes('/opt/tcc/config/fontes.lock.json'); print('embedded_preflight=ok')"
    Invoke-DockerStep -Arguments @(
        "run", "--rm", "--platform", "linux/amd64", "--network", "none",
        "--read-only", "--cap-drop", "ALL", "--security-opt",
        "no-new-privileges", "tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0",
        "python", "-c", $embeddedCheck
    )
}
