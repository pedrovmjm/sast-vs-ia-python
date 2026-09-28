[CmdletBinding()]
param(
    [switch]$Verificar,
    [string]$Saida = "evidencias/publicacao/auditoria-acesso-cursor-v1.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$repoPrefixo = $repo.TrimEnd("\", "/") + [IO.Path]::DirectorySeparatorChar
$saidaFull = [IO.Path]::GetFullPath((Join-Path $repo $Saida))
if (-not $saidaFull.StartsWith($repoPrefixo, [StringComparison]::OrdinalIgnoreCase)) {
    throw "A saida deve permanecer dentro do repositorio"
}

function Assert-True {
    param([bool]$Condicao, [string]$Mensagem)
    if (-not $Condicao) { throw $Mensagem }
}

function Get-Sha256 {
    param([string]$Caminho)
    return (Get-FileHash -LiteralPath $Caminho -Algorithm SHA256).Hash.ToLowerInvariant()
}

$cenarios = [Collections.Generic.List[object]]::new()
foreach ($condicao in @("C3", "C5")) {
    foreach ($fase in @("piloto", "coleta")) {
        $resultadosRaiz = Join-Path $repo "resultados/ia/$fase"
        $execucoesRaiz = Join-Path $repo "execucoes/ia/$fase"
        $eventos = @(Get-ChildItem -LiteralPath $resultadosRaiz -Directory -ErrorAction Stop |
            Where-Object { $_.Name -like "$condicao-*" } |
            Get-ChildItem -Recurse -Filter "eventos.jsonl" -File)
        $manifestos = @(Get-ChildItem -LiteralPath $resultadosRaiz -Directory -ErrorAction Stop |
            Where-Object { $_.Name -like "$condicao-*" } |
            Get-ChildItem -Recurse -Filter "manifesto.json" -File)
        $respostas = @(Get-ChildItem -LiteralPath $resultadosRaiz -Directory -ErrorAction Stop |
            Where-Object { $_.Name -like "$condicao-*" } |
            Get-ChildItem -Recurse -Filter "resposta.json" -File)

        $tipos = @{}
        $permissionModes = @{}
        $toolCalls = 0
        $toolBlocks = 0
        $systemCwds = 0
        $cwdsInvalidos = 0
        $eventosBytes = [long]0
        $eventosInventario = [Collections.Generic.List[object]]::new()
        foreach ($arquivo in $eventos) {
            $eventosBytes += [long]$arquivo.Length
            $eventoSha256 = Get-Sha256 $arquivo.FullName
            $manifestoPath = Join-Path $arquivo.DirectoryName "manifesto.json"
            Assert-True (Test-Path -LiteralPath $manifestoPath -PathType Leaf) `
                "Manifesto ausente para $($arquivo.FullName)"
            $manifestoEvento = Get-Content -Raw -LiteralPath $manifestoPath -Encoding UTF8 |
                ConvertFrom-Json -ErrorAction Stop
            Assert-True (
                [string]$manifestoEvento.artefatos_sha256.'eventos.jsonl' -eq $eventoSha256
            ) "SHA-256 de eventos diverge do manifesto: $($arquivo.FullName)"
            $relativo = $arquivo.FullName.Substring($repo.Length).TrimStart("\", "/").Replace("\", "/")
            $partes = $relativo.Split("/")
            $esperado = "execucoes/ia/" + ($partes[2..($partes.Length - 2)] -join "/")
            $tiposArquivo = @{}
            $callsArquivo = 0
            foreach ($linha in Get-Content -LiteralPath $arquivo.FullName -Encoding UTF8) {
                if ([string]::IsNullOrWhiteSpace($linha)) { continue }
                $evento = $linha | ConvertFrom-Json -ErrorAction Stop
                $tipo = [string]$evento.type
                if (-not $tipos.ContainsKey($tipo)) { $tipos[$tipo] = 0 }
                if (-not $tiposArquivo.ContainsKey($tipo)) { $tiposArquivo[$tipo] = 0 }
                $tipos[$tipo]++
                $tiposArquivo[$tipo]++
                if ($tipo -eq "tool_call") {
                    $toolCalls++
                    $callsArquivo++
                }
                $messageProp = $evento.PSObject.Properties["message"]
                $contentProp = if ($null -eq $messageProp) {
                    $null
                } else {
                    $messageProp.Value.PSObject.Properties["content"]
                }
                if ($null -ne $contentProp) {
                    foreach ($bloco in @($contentProp.Value)) {
                        if ([string]$bloco.type -in @("tool_use", "tool_result")) {
                            $toolBlocks++
                            $callsArquivo++
                        }
                    }
                }
                if ($tipo -eq "system" -and $null -ne $evento.cwd) {
                    $systemCwds++
                    $cwd = ([string]$evento.cwd).Replace("\", "/")
                    if (-not $cwd.EndsWith($esperado, [StringComparison]::OrdinalIgnoreCase)) {
                        $cwdsInvalidos++
                    }
                    $permissionMode = [string]$evento.permissionMode
                    if (-not $permissionModes.ContainsKey($permissionMode)) {
                        $permissionModes[$permissionMode] = 0
                    }
                    $permissionModes[$permissionMode]++
                }
            }
            $eventosInventario.Add([pscustomobject][ordered]@{
                caminho = $relativo
                tamanho_bytes = [long]$arquivo.Length
                sha256 = $eventoSha256
                tool_calls = $callsArquivo
            })
        }

        $concluidos = 0
        $falhas = 0
        $sandboxDesabilitado = 0
        foreach ($arquivo in $manifestos) {
            $manifesto = Get-Content -Raw -LiteralPath $arquivo.FullName -Encoding UTF8 |
                ConvertFrom-Json -ErrorAction Stop
            if ([string]$manifesto.estado -eq "concluida") { $concluidos++ } else { $falhas++ }
            $comando = @($manifesto.comando)
            for ($i = 0; $i -lt $comando.Count - 1; $i++) {
                if ([string]$comando[$i] -eq "--sandbox" -and
                    [string]$comando[$i + 1] -eq "disabled") {
                    $sandboxDesabilitado++
                    break
                }
            }
        }

        $cliFiles = @(Get-ChildItem -LiteralPath $execucoesRaiz -Directory -ErrorAction Stop |
            Where-Object { $_.Name -like "$condicao-*" } |
            Get-ChildItem -Recurse -Filter "cli.json" -File -Force)
        $cliValidos = 0
        foreach ($arquivo in $cliFiles) {
            $cli = Get-Content -Raw -LiteralPath $arquivo.FullName -Encoding UTF8 |
                ConvertFrom-Json -ErrorAction Stop
            $allow = @($cli.permissions.allow)
            $deny = @($cli.permissions.deny)
            if ($allow.Count -eq 1 -and [string]$allow[0] -eq "Read(**)" -and
                $deny.Count -eq 2 -and "Write(**)" -in $deny -and "Shell(*)" -in $deny) {
                $cliValidos++
            }
        }

        $arquivosWorkspace = @(Get-ChildItem -LiteralPath $execucoesRaiz -Directory -ErrorAction Stop |
            Where-Object { $_.Name -like "$condicao-*" } |
            Get-ChildItem -Recurse -File -Force)
        $inesperados = @($arquivosWorkspace | Where-Object {
            $_.Name -notin @("cli.json", "sandbox.json", "schema-relatorio-ia-v1.json")
        })

        Assert-True ($eventos.Count -eq $manifestos.Count) `
            "$condicao/${fase}: quantidade de eventos e manifestos diverge"
        Assert-True ($respostas.Count -eq $concluidos) `
            "$condicao/${fase}: respostas validas e conclusoes divergem"
        Assert-True ($toolCalls -eq 0) "$condicao/${fase}: tool_call observado"
        Assert-True ($toolBlocks -eq 0) "$condicao/${fase}: bloco de ferramenta observado"
        Assert-True ($cwdsInvalidos -eq 0) "$condicao/${fase}: cwd fora da area isolada"
        Assert-True ($cliFiles.Count -eq $manifestos.Count) `
            "$condicao/${fase}: cli.json ausente em alguma tentativa"
        Assert-True ($cliValidos -eq $cliFiles.Count) `
            "$condicao/${fase}: permissao cli.json divergente"
        Assert-True ($inesperados.Count -eq 0) `
            "$condicao/${fase}: arquivo inesperado na area de execucao"

        $tiposOrdenados = [ordered]@{}
        foreach ($chave in @($tipos.Keys | Sort-Object)) {
            $tiposOrdenados[$chave] = [int]$tipos[$chave]
        }
        $permissionModesOrdenados = [ordered]@{}
        foreach ($chave in @($permissionModes.Keys | Sort-Object)) {
            $permissionModesOrdenados[$chave] = [int]$permissionModes[$chave]
        }
        $cenarios.Add([pscustomobject][ordered]@{
            condicao = $condicao
            fase = $fase
            tentativas = $manifestos.Count
            concluidas = $concluidos
            falhas_preservadas = $falhas
            respostas_json_validas = $respostas.Count
            arquivos_eventos = $eventos.Count
            bytes_eventos = $eventosBytes
            tipos_evento = $tiposOrdenados
            permission_modes_evento_system = $permissionModesOrdenados
            tool_calls = $toolCalls
            tool_use_ou_result_blocks = $toolBlocks
            eventos_system_com_cwd = $systemCwds
            cwd_fora_da_area_da_tentativa = $cwdsInvalidos
            cli_json_validados = $cliValidos
            workspaces_com_arquivos_inesperados = $inesperados.Count
            tentativas_com_sandbox_nativo_desabilitado = $sandboxDesabilitado
            eventos_inventario = $eventosInventario
        })
    }
}

$documento = [ordered]@{
    schema_version = "1.0"
    tipo = "auditoria-acesso-cursor"
    conclusao = $(
        "Read(**) concedia capacidade de leitura relativa ao workspace, mas nao " +
        "evidencia uma leitura. Nenhuma chamada tool_call foi observada em C3 ou C5."
    )
    escopo = @("C3/piloto", "C3/coleta", "C5/piloto", "C5/coleta")
    fonte_integral_necessaria = $(
        "A verificacao completa requer os eventos locais; eventos que incorporam codigo " +
        "de alvos nao redistribuiveis permanecem fora do Git publico. Seus SHA-256 " +
        "continuam registrados nos manifestos e neste inventario derivado."
    )
    criterios = [ordered]@{
        tool_call_permitido_observado = 0
        tool_use_ou_result_block_observado = 0
        cwd = "termina na area execucoes/ia/<fase>/<execucao>/<tentativa>"
        arquivos_workspace = @(
            ".cursor/cli.json",
            ".cursor/sandbox.json somente quando criado",
            "schema-relatorio-ia-v1.json"
        )
        cli_allow = @("Read(**)")
        cli_deny = @("Write(**)", "Shell(*)")
    }
    cenarios = $cenarios
}

$jsonCompacto = $documento | ConvertTo-Json -Depth 12 -Compress
if ($Verificar) {
    Assert-True (Test-Path -LiteralPath $saidaFull -PathType Leaf) "Auditoria ausente: $Saida"
    $gravado = Get-Content -Raw -LiteralPath $saidaFull -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop | ConvertTo-Json -Depth 12 -Compress
    Assert-True ($gravado -ceq $jsonCompacto) "Auditoria Cursor diverge dos artefatos locais"
    Write-Output "Auditoria Cursor aprovada: 0 tool_call em $($cenarios.Count) cenarios"
    exit 0
}

$diretorioSaida = Split-Path -Parent $saidaFull
if (-not (Test-Path -LiteralPath $diretorioSaida)) {
    New-Item -ItemType Directory -Path $diretorioSaida -ErrorAction Stop | Out-Null
}
$json = $documento | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText($saidaFull, $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Auditoria Cursor gravada: $Saida"
