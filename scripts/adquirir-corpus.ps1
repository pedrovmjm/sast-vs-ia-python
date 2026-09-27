[CmdletBinding()]
param(
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}$")]
    [string]$Imagem = "tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0",

    [string]$RaizDados
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$DadosRoot = $Repo
if (-not [string]::IsNullOrWhiteSpace($RaizDados)) {
    $DadosRoot = if ([IO.Path]::IsPathRooted($RaizDados)) {
        [IO.Path]::GetFullPath($RaizDados)
    }
    else {
        [IO.Path]::GetFullPath((Join-Path $Repo $RaizDados))
    }
    $prefixoRepo = $Repo.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $DadosRoot.StartsWith($prefixoRepo, [StringComparison]::OrdinalIgnoreCase)) {
        throw "RaizDados deve permanecer dentro do repositorio"
    }
}
$BenchmarkRoot = [IO.Path]::GetFullPath((Join-Path $DadosRoot "benchmark"))
$CacheRoot = [IO.Path]::GetFullPath((Join-Path $BenchmarkRoot "corpus-realvuln-v1"))
$AlvosRoot = [IO.Path]::GetFullPath((Join-Path $DadosRoot "alvos"))
$OracleRoot = [IO.Path]::GetFullPath((Join-Path $DadosRoot "oracle"))
$EvidenciasRoot = [IO.Path]::GetFullPath((Join-Path $DadosRoot "evidencias"))
$CorpusLockPath = Join-Path $Repo "config/corpus-realvuln-v1.lock.json"
$PoliticaPath = Join-Path $Repo "config/politica-sanitizacao-v1.json"
$EspelhosLockPath = Join-Path $Repo "config/espelhos-corpus-realvuln-v1.lock.json"
$AlvosFinal = Join-Path $AlvosRoot "corpus-v1"
$OracleFinal = Join-Path $OracleRoot "realvuln-v1"
$EvidenciaFinal = Join-Path $EvidenciasRoot "corpus-realvuln-v1"
$Token = [guid]::NewGuid().ToString("N")
$Trabalho = Join-Path $CacheRoot ".aquisicao-$Token"
$AlvosTemp = Join-Path $AlvosRoot ".corpus-v1-$Token"
$OracleTemp = Join-Path $OracleRoot ".realvuln-v1-$Token"
$EvidenciaTemp = Join-Path $EvidenciasRoot ".corpus-realvuln-v1-$Token"
$RealVulnGit = Join-Path $CacheRoot "realvuln.git"
$ReposCache = Join-Path $CacheRoot "repos"
$ImagemInfo = $null
$Promovidos = [Collections.Generic.List[string]]::new()

function Assert-True {
    param([bool]$Condicao, [string]$Mensagem)
    if (-not $Condicao) { throw $Mensagem }
}

function Assert-Equal {
    param($Esperado, $Observado, [string]$Mensagem)
    if ($Esperado -ne $Observado) {
        throw "$Mensagem; esperado=[$Esperado], observado=[$Observado]"
    }
}

function Assert-DiretorioReal {
    param([string]$Caminho, [string]$Contexto)
    $item = Get-Item -LiteralPath $Caminho -Force -ErrorAction Stop
    Assert-True $item.PSIsContainer "$Contexto deve ser diretório"
    Assert-True (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
        "$Contexto não pode ser reparse point"
}

function Invoke-Git {
    param([string[]]$Argumentos, [string]$Contexto)
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $linhas = @(& git -c core.hooksPath=NUL -c protocol.file.allow=never @Argumentos 2>&1)
        $codigo = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $anterior }
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $($linhas -join ' ')"
    }
    return @($linhas | ForEach-Object { [string]$_ })
}

function Invoke-Docker {
    param([string[]]$Argumentos, [string]$Contexto)
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $linhas = @(& docker @Argumentos 2>&1)
        $codigo = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $anterior }
    if ($codigo -ne 0) {
        throw "$Contexto falhou (código $codigo): $($linhas -join ' ')"
    }
    return @($linhas | ForEach-Object { [string]$_ })
}

function Invoke-DockerCapturado {
    param([string[]]$Argumentos)
    $anterior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $linhas = @(& docker @Argumentos 2>&1)
        $codigo = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $anterior }
    return [ordered]@{
        codigo_saida = $codigo
        saida = @($linhas | ForEach-Object { [string]$_ })
    }
}

function Get-ImagemLocal {
    $linhas = Invoke-Docker @("image", "inspect", "--format", "{{json .}}", $Imagem) `
        "inspeção da imagem"
    $info = ($linhas -join [Environment]::NewLine) | ConvertFrom-Json -ErrorAction Stop
    Assert-True ([string]$info.Id -match "^sha256:[0-9a-f]{64}$") "ID da imagem inválido"
    Assert-Equal "linux" ([string]$info.Os) "SO da imagem"
    Assert-Equal "amd64" ([string]$info.Architecture) "arquitetura da imagem"
    return $info
}

function Get-Sha256 {
    param([string]$Caminho)
    return (Get-FileHash -LiteralPath $Caminho -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-JsonNovo {
    param([string]$Caminho, $Documento)
    Assert-True (-not (Test-Path -LiteralPath $Caminho)) "JSON já existe: $Caminho"
    $json = $Documento | ConvertTo-Json -Depth 20 -Compress
    [IO.File]::WriteAllText($Caminho, $json + "`n", [Text.UTF8Encoding]::new($false))
}

function Remove-ArvorePropria {
    param([string]$Caminho, [string]$RaizPermitida)
    $full = [IO.Path]::GetFullPath($Caminho)
    $raiz = [IO.Path]::GetFullPath($RaizPermitida).TrimEnd("\", "/")
    Assert-True ($full.StartsWith($raiz + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) "cleanup recusou caminho fora da raiz"
    if (-not (Test-Path -LiteralPath $full)) { return }
    $item = Get-Item -LiteralPath $full -Force
    Assert-True (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
        "cleanup recusou reparse point"
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
}

function Assert-BareCache {
    param([string]$Caminho, [string]$Url, [string]$Contexto)
    if (-not (Test-Path -LiteralPath $Caminho)) {
        Invoke-Git @("init", "--bare", $Caminho) "git init $Contexto" | Out-Null
        Invoke-Git @("--git-dir=$Caminho", "remote", "add", "origin", $Url) `
            "origem $Contexto" | Out-Null
    }
    Assert-DiretorioReal $Caminho "$Contexto cache"
    $origem = @(Invoke-Git @("--git-dir=$Caminho", "config", "--get", "remote.origin.url") `
        "URL $Contexto")
    Assert-Equal $Url ([string]$origem[0]).Trim() "URL congelada de $Contexto"
}

function Invoke-ContainerBase {
    param([string[]]$Extra)
    return @(
        "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "10001:10001",
        "--pids-limit", "64", "--memory", "512m", "--memory-swap", "512m",
        "--cpus", "1", "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=32m,uid=10001,gid=10001,mode=1777",
        "--env", "HOME=/tmp/tcc-home", "--env", "PYTHONSAFEPATH=1"
    ) + $Extra
}

function Invoke-ExtracaoTar {
    param([string]$Tar, [string]$RaizSaida, [string]$Nome)
    $argumentos = Invoke-ContainerBase @(
        "--mount", "type=bind,src=$Tar,dst=/entrada/repo.tar,readonly",
        "--mount", "type=bind,src=$RaizSaida,dst=/exportacoes",
        [string]$ImagemInfo.Id, "/usr/local/bin/python", "-P", "-m", "runner.corpus",
        "extrair-tar-git", "--arquivo", "/entrada/repo.tar",
        "--destino", "/exportacoes/$Nome"
    )
    Invoke-Docker $argumentos "extração segura de $Nome" | Out-Null
}

function Invoke-PreparacaoCorpus {
    param([string]$Origem, [string]$DestinoNome, [string]$InventarioNome,
        [string]$RelatorioNome)
    $argumentos = Invoke-ContainerBase @(
        "--mount", "type=bind,src=$Origem,dst=/origem,readonly",
        "--mount", "type=bind,src=$AlvosTemp,dst=/alvos",
        "--mount", "type=bind,src=$EvidenciaTemp,dst=/evidencia",
        "--mount", "type=bind,src=$PoliticaPath,dst=/config/politica.json,readonly",
        [string]$ImagemInfo.Id, "/usr/local/bin/python", "-P", "-m", "runner.preparacao",
        "preparar-corpus", "--origem", "/origem", "--destino", "/alvos/$DestinoNome",
        "--politica", "/config/politica.json", "--inventario",
        "/evidencia/$InventarioNome", "--relatorio", "/evidencia/$RelatorioNome"
    )
    Invoke-Docker $argumentos "sanitização de $DestinoNome" | Out-Null
}

try {
    foreach ($raiz in @($BenchmarkRoot, $AlvosRoot, $OracleRoot, $EvidenciasRoot)) {
        if (-not (Test-Path -LiteralPath $raiz)) {
            New-Item -ItemType Directory -Path $raiz -ErrorAction Stop | Out-Null
        }
        Assert-DiretorioReal $raiz "raiz"
    }
    foreach ($final in @($AlvosFinal, $OracleFinal, $EvidenciaFinal)) {
        Assert-True (-not (Test-Path -LiteralPath $final)) `
            "destino final já existe e não será sobrescrito: $final"
    }
    foreach ($temporario in @($Trabalho, $AlvosTemp, $EvidenciaTemp)) {
        New-Item -ItemType Directory -Path $temporario -ErrorAction Stop | Out-Null
    }
    if (-not (Test-Path -LiteralPath $ReposCache)) {
        New-Item -ItemType Directory -Path $ReposCache -ErrorAction Stop | Out-Null
    }
    Assert-DiretorioReal $ReposCache "cache dos repositórios"

    $ImagemInfo = Get-ImagemLocal
    Invoke-Docker @("compose", "run", "--rm", "controlador", "python", "-c",
        "from runner.corpus import *; c=carregar_json('/workspace/config/corpus-realvuln-v1.lock.json'); validar_lock_corpus(c); validar_politica(carregar_json('/workspace/config/politica-sanitizacao-v1.json')); validar_lock_espelhos(carregar_json('/workspace/config/espelhos-corpus-realvuln-v1.lock.json'), c); print('contratos=ok')") `
        "validação dos contratos" | Out-Null
    $lockHashAntes = Get-Sha256 $CorpusLockPath
    $lock = Get-Content -LiteralPath $CorpusLockPath -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
    $espelhos = Get-Content -LiteralPath $EspelhosLockPath -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
    $politica = Get-Content -LiteralPath $PoliticaPath -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop

    Assert-BareCache $RealVulnGit ([string]$lock.realvuln.url) "RealVuln"
    Invoke-Git @("--git-dir=$RealVulnGit", "fetch", "--depth=1", "origin",
        "refs/tags/v1.0:refs/tags/v1.0") "aquisição RealVuln v1.0" | Out-Null
    $tagLinhas = @(Invoke-Git @("--git-dir=$RealVulnGit", "rev-parse", "refs/tags/v1.0") `
        "objeto da tag")
    $commitLinhas = @(Invoke-Git @("--git-dir=$RealVulnGit", "rev-parse", "refs/tags/v1.0^{}") `
        "commit da tag")
    $tag = ([string]$tagLinhas[0]).Trim()
    $commit = ([string]$commitLinhas[0]).Trim()
    Assert-Equal ([string]$lock.realvuln.tag_object) $tag "objeto da tag RealVuln"
    Assert-Equal ([string]$lock.realvuln.commit) $commit "commit RealVuln"

    $oracleTar = Join-Path $Trabalho "oracle.tar"
    Invoke-Git @("--git-dir=$RealVulnGit", "archive", "--format=tar", "--output=$oracleTar",
        $commit, "benchmark-manifest.json", "validate_gt.py", "ground-truth") `
        "exportação do oracle" | Out-Null
    Invoke-ExtracaoTar $oracleTar $OracleRoot ([IO.Path]::GetFileName($OracleTemp))
    Assert-Equal ([string]$lock.realvuln.manifesto_sha256) `
        (Get-Sha256 (Join-Path $OracleTemp "benchmark-manifest.json")) "hash do manifesto RealVuln"

    $validacaoArgs = Invoke-ContainerBase @(
        "--workdir", "/oracle", "--mount", "type=bind,src=$OracleTemp,dst=/oracle,readonly",
        [string]$ImagemInfo.Id, "/usr/local/bin/python", "-P", "/oracle/validate_gt.py"
    )
    $validacaoOficial = Invoke-DockerCapturado $validacaoArgs
    Write-JsonNovo (Join-Path $EvidenciaTemp "validacao-oficial.json") $validacaoOficial
    Assert-Equal 0 $validacaoOficial.codigo_saida "validador oficial do ground truth"

    $auditArgs = Invoke-ContainerBase @(
        "--mount", "type=bind,src=$OracleTemp,dst=/oracle,readonly",
        "--mount", "type=bind,src=$CorpusLockPath,dst=/config/corpus.json,readonly",
        "--mount", "type=bind,src=$EvidenciaTemp,dst=/evidencia",
        [string]$ImagemInfo.Id, "/usr/local/bin/python", "-P", "-m", "runner.corpus",
        "auditar-ground-truth", "--oracle", "/oracle", "--corpus-lock",
        "/config/corpus.json", "--saida", "/evidencia/ground-truth-resumo.json"
    )
    Invoke-Docker $auditArgs "auditoria autoral do ground truth" | Out-Null

    $resumoAlvos = [Collections.Generic.List[object]]::new()
    foreach ($alvo in $lock.alvos) {
        $alvoId = [string]$alvo.alvo
        $repoId = [string]$alvo.realvuln_id
        $repoUrl = [string]$alvo.url
        $repoCommit = [string]$alvo.commit
        Write-Host "[$alvoId] adquirindo $repoId"
        $gitDir = Join-Path $ReposCache "$alvoId.git"
        Assert-BareCache $gitDir $repoUrl $alvoId
        $tipo = $null
        $urlTransporte = $repoUrl
        $espelhoUsado = $false
        $candidatosEspelho = @($espelhos.espelhos | Where-Object alvo -eq $alvoId)
        $remotosRegistrados = @(Invoke-Git @("--git-dir=$gitDir", "remote") "remotos de $alvoId")
        if ($candidatosEspelho.Count -eq 1 -and $remotosRegistrados -contains "espelho") {
            $urlTransporte = [string]$candidatosEspelho[0].url_espelho
            $urlEspelhoRegistrada = @(Invoke-Git @("--git-dir=$gitDir", "config", "--get",
                "remote.espelho.url") "URL do espelho de $alvoId")
            Assert-Equal $urlTransporte ([string]$urlEspelhoRegistrada[0]).Trim() `
                "URL congelada do espelho de $alvoId"
            $espelhoUsado = $true
        }
        try {
            $tipoLinhas = @(Invoke-Git @("--git-dir=$gitDir", "cat-file", "-t", $repoCommit) `
                "consulta de $alvoId")
            $tipo = ([string]$tipoLinhas[0]).Trim()
        }
        catch {
            try {
                Invoke-Git @("--git-dir=$gitDir", "fetch", "--depth=1", "origin", $repoCommit) `
                    "aquisição do commit $alvoId" | Out-Null
            }
            catch {
                Assert-Equal 1 $candidatosEspelho.Count "espelho necessário ausente para $alvoId"
                $urlTransporte = [string]$candidatosEspelho[0].url_espelho
                $remotos = @(Invoke-Git @("--git-dir=$gitDir", "remote") "remotos de $alvoId")
                if ($remotos -notcontains "espelho") {
                    Invoke-Git @("--git-dir=$gitDir", "remote", "add", "espelho", $urlTransporte) `
                        "registro do espelho de $alvoId" | Out-Null
                }
                $urlEspelhoRegistrada = @(Invoke-Git @("--git-dir=$gitDir", "config", "--get",
                    "remote.espelho.url") "URL do espelho de $alvoId")
                Assert-Equal $urlTransporte ([string]$urlEspelhoRegistrada[0]).Trim() `
                    "URL congelada do espelho de $alvoId"
                Invoke-Git @("--git-dir=$gitDir", "fetch", "--depth=1", "espelho", $repoCommit) `
                    "aquisição pelo espelho de $alvoId" | Out-Null
                $espelhoUsado = $true
            }
            $tipoLinhas = @(Invoke-Git @("--git-dir=$gitDir", "cat-file", "-t", $repoCommit) `
                "tipo do commit $alvoId")
            $tipo = ([string]$tipoLinhas[0]).Trim()
        }
        Assert-Equal "commit" $tipo "objeto adquirido de $alvoId"
        $arvore = @(Invoke-Git @("--git-dir=$gitDir", "ls-tree", "-r", "--full-tree",
            "--format=%(objectmode) %(objecttype) %(objectname) %(path)", $repoCommit) "árvore de $alvoId")
        Assert-True ($arvore.Count -gt 0) "árvore vazia em $alvoId"
        $exclusoesGit = [Collections.Generic.List[object]]::new()
        foreach ($linha in $arvore) {
            Assert-True ($linha -match "^(100644|100755|120000) blob ([0-9a-f]{40}) (.+)$") `
                "entrada Git não suportada em $alvoId`: $linha"
            $modo = [string]$Matches[1]
            $objeto = [string]$Matches[2]
            $relativo = [string]$Matches[3]
            Assert-True (-not [string]::IsNullOrWhiteSpace($relativo)) "caminho vazio em $alvoId"
            Assert-True (-not $relativo.StartsWith("/")) "caminho absoluto em $alvoId"
            Assert-True (-not $relativo.Contains("\")) "separador ambíguo em $alvoId"
            Assert-True (-not (($relativo -split "/") -contains "..")) "travessia em $alvoId"
            Assert-True ($relativo -notmatch "[\x00-\x1f]") "controle em caminho de $alvoId"
            if ($modo -eq "120000") {
                Assert-True (@($politica.caminhos_excluidos) -contains $relativo.ToLowerInvariant()) `
                    "link Git não previsto pela política em $alvoId`: $relativo"
                $destinoLink = @(
                    Invoke-Git @("--git-dir=$gitDir", "show", "$repoCommit`:$relativo") `
                        "conteúdo do link $alvoId"
                ) -join "`n"
                $exclusoesGit.Add([ordered]@{
                    caminho = $relativo
                    modo_git = $modo
                    objeto_git = $objeto
                    destino_link = $destinoLink
                    acao = "omitido_sem_seguir"
                })
            }
        }

        $tar = Join-Path $Trabalho "$alvoId.tar"
        $archiveArgs = @("--git-dir=$gitDir", "archive", "--format=tar", "--output=$tar",
            $repoCommit, ".")
        foreach ($exclusao in $exclusoesGit) {
            $archiveArgs += ":(exclude)$([string]$exclusao.caminho)"
        }
        Invoke-Git $archiveArgs "archive de $alvoId" | Out-Null
        $exportNome = "export-$alvoId"
        Invoke-ExtracaoTar $tar $Trabalho $exportNome
        $exportacao = Join-Path $Trabalho $exportNome

        $inventario = "$alvoId-inventario.json"
        $relatorio = "$alvoId-sanitizacao.json"
        $inventarioReg = "$alvoId-inventario-regenerado.json"
        $relatorioReg = "$alvoId-sanitizacao-regenerada.json"
        Invoke-PreparacaoCorpus $exportacao $alvoId $inventario $relatorio
        Invoke-PreparacaoCorpus $exportacao "$alvoId-REGENERADO" $inventarioReg $relatorioReg
        Assert-Equal (Get-Sha256 (Join-Path $EvidenciaTemp $inventario)) `
            (Get-Sha256 (Join-Path $EvidenciaTemp $inventarioReg)) "inventário regenerado $alvoId"
        Assert-Equal (Get-Sha256 (Join-Path $EvidenciaTemp $relatorio)) `
            (Get-Sha256 (Join-Path $EvidenciaTemp $relatorioReg)) "sanitização regenerada $alvoId"
        Remove-ArvorePropria (Join-Path $AlvosTemp "$alvoId-REGENERADO") $AlvosTemp
        Remove-Item -LiteralPath (Join-Path $EvidenciaTemp $inventarioReg) -Force
        Remove-Item -LiteralPath (Join-Path $EvidenciaTemp $relatorioReg) -Force
        $docInventario = Get-Content -LiteralPath (Join-Path $EvidenciaTemp $inventario) `
            -Raw -Encoding UTF8 | ConvertFrom-Json
        $resumoAlvos.Add([ordered]@{
            alvo = $alvoId
            realvuln_id = $repoId
            url = $repoUrl
            commit = $repoCommit
            url_transporte = $urlTransporte
            espelho_usado = $espelhoUsado
            exclusoes_git = @($exclusoesGit)
            entrada_sha256 = [string]$docInventario.entrada_sha256
            arquivos = [int]$docInventario.arquivos
            tamanho_total_bytes = [long]$docInventario.tamanho_total_bytes
            inventario_sha256 = Get-Sha256 (Join-Path $EvidenciaTemp $inventario)
            sanitizacao_sha256 = Get-Sha256 (Join-Path $EvidenciaTemp $relatorio)
        })
        Remove-ArvorePropria $exportacao $Trabalho
        Remove-Item -LiteralPath $tar -Force
    }

    Assert-Equal $lockHashAntes (Get-Sha256 $CorpusLockPath) "lock alterado durante aquisição"
    $resumo = [ordered]@{
        schema_version = "1.0"
        realvuln_tag = [string]$lock.realvuln.tag
        realvuln_tag_object = $tag
        realvuln_commit = $commit
        corpus_lock_sha256 = $lockHashAntes
        politica_sha256 = Get-Sha256 $PoliticaPath
        espelhos_lock_sha256 = Get-Sha256 $EspelhosLockPath
        imagem_id = [string]$ImagemInfo.Id
        quantidade_alvos = $resumoAlvos.Count
        ground_truth = [ordered]@{
            repositorios = 26
            entradas = 817
            vulnerabilidades = 697
            armadilhas_fp = 120
        }
        alvos = @($resumoAlvos)
    }
    Assert-Equal 26 $resumoAlvos.Count "quantidade final de alvos"
    Write-JsonNovo (Join-Path $EvidenciaTemp "resumo.json") $resumo

    Move-Item -LiteralPath $OracleTemp -Destination $OracleFinal -ErrorAction Stop
    $Promovidos.Add($OracleFinal)
    Move-Item -LiteralPath $AlvosTemp -Destination $AlvosFinal -ErrorAction Stop
    $Promovidos.Add($AlvosFinal)
    Move-Item -LiteralPath $EvidenciaTemp -Destination $EvidenciaFinal -ErrorAction Stop
    $Promovidos.Add($EvidenciaFinal)
    Write-Host "Corpus RealVuln v1 preparado: 26 alvos, 817 entradas de ground truth."
}
catch {
    foreach ($promovido in @($Promovidos)) {
        if ($promovido.StartsWith($AlvosRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $promovido $AlvosRoot
        }
        elseif ($promovido.StartsWith($OracleRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $promovido $OracleRoot
        }
        elseif ($promovido.StartsWith($EvidenciasRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $promovido $EvidenciasRoot
        }
    }
    throw
}
finally {
    foreach ($item in @($Trabalho, $AlvosTemp, $OracleTemp, $EvidenciaTemp)) {
        if ($item.StartsWith($BenchmarkRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $item $BenchmarkRoot
        }
        elseif ($item.StartsWith($AlvosRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $item $AlvosRoot
        }
        elseif ($item.StartsWith($OracleRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $item $OracleRoot
        }
        elseif ($item.StartsWith($EvidenciasRoot, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-ArvorePropria $item $EvidenciasRoot
        }
    }
}
