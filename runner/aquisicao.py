"""Validação local da proveniência antes de qualquer aquisição.

Este módulo é deliberadamente puro: não abre rede, não executa processos e não
importa código pertencente ao benchmark. A aquisição será adicionada em uma
tarefa posterior, reutilizando estas invariantes como precondição.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class ErroProveniencia(ValueError):
    """Indica que uma fonte ou uma exceção não satisfaz o contrato aprovado."""


SCHEMA_VERSION = "1.0"
REALVULN_URL = "https://github.com/kolega-ai/Real-Vuln-Benchmark.git"
REALVULN_TAG_OBJECT = "aa9f7321c8c53fe417b8faa517f1c4308b69b389"
REALVULN_COMMIT = "d98e9fc91273702c9547663b6906d1fc494d4fcc"
REALVULN_ABBREVIATED_IDENTIFIERS = {
    "ground_truth_content_hash": "sha256:a57347fbdf2a",
    "default_prompt_version": "sha256:3481f1432c23",
}
SEMGREP_RULES_URL = "https://github.com/semgrep/semgrep-rules.git"
SEMGREP_RULES_COMMIT = "40b8c63f75dc7c22c8a77482d73bfb864b146f7e"
SEMGREP_RULES_BUNDLE_SHA256 = (
    "29eb41850a07fee98955446524423ddd9e9f5040cbf7e301788b791386ee8309"
)
HOST_TOOLS = ("git", "wsl", "docker_desktop", "docker_engine")
HOST_POLICY_LOCKS = {
    "git": {
        "recommended": "2.55.0.windows.3",
        "source": "https://github.com/git-for-windows/git/releases",
    },
    "wsl": {
        "recommended": "2.1.5",
        "source": "https://learn.microsoft.com/windows/wsl/install",
    },
    "docker_desktop": {
        "recommended": "4.86.0",
        "source": "https://docs.docker.com/desktop/release-notes/",
    },
    "docker_engine": {
        "recommended": "29.7.2",
        "source": "https://docs.docker.com/desktop/release-notes/",
    },
}
WAIVED_HOST_VERSIONS = {
    "git": "2.46.2.windows.1",
    "wsl": "2.0.14.0",
    "docker_desktop": "4.38.0",
    "docker_engine": "27.5.1",
}
WAIVER_ALLOWED_ACTIONS = (
    "preflight",
    "acquire-git-sources",
    "docker-build",
    "sast-smoke",
)
WAIVER_APPROVAL_COMMIT = "81561a2c6eb0473ab5a1a5cdffdf787a586965b7"
PYTHON_REFERENCE = "python:3.12.13-slim-bookworm"
PYTHON_INDEX_DIGEST = (
    "sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2"
)
PYTHON_MANIFEST_DIGEST = (
    "sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af"
)
PYTHON_SOURCE_URL = "https://github.com/docker-library/python"
PYTHON_SOURCE_REVISION = "3362634339580d3232e65a66dd5a36c47ae7ff14"
PACKAGE_LOCKS = {
    "bandit": {
        "version": "1.9.4",
        "project_url": "https://pypi.org/project/bandit/1.9.4/",
        "source_url": "https://github.com/PyCQA/bandit",
        "source_commit": "92ae8b82fb422a639f0ed8d99e96cea769594e08",
        "wheel_sha256": "f89ffa663767f5a0585ea075f01020207e966a9c0f2b9ef56a57c7963a3f6f8e",
    },
    "semgrep": {
        "version": "1.172.0",
        "project_url": "https://pypi.org/project/semgrep/1.172.0/",
        "source_url": "https://github.com/semgrep/semgrep",
        "source_commit": "651f37efa397bf066e1cf627414eeabe40b07e27",
        "wheel_sha256": "d8b94af4266a575287ad2cd844573743ab4fe58f6bfb6d9229327807937eade3",
    },
}
LICENSE_LOCKS = {
    "RealVuln": ["MIT em LICENSE", "Apache-2.0 em pyproject.toml"],
    "Python": ["PSF-2.0", "licenças dos componentes Debian"],
    "bandit": ["Apache-2.0"],
    "semgrep": ["LGPL-2.1-or-later"],
    "regras Semgrep": ["Semgrep Rules License v1.0"],
}
PYTHON_PACKAGES_LOCK = {
    "type": "python-requirements-lock",
    "python_version": "3.12.13",
    "platform": "linux/amd64",
    "resolver": "pip 25.0.1",
    "index_url": "https://pypi.org/simple",
    "artifact_host": "files.pythonhosted.org",
    "only_binary": True,
    "input_path": "docker/requirements.in",
    "input_sha256": "a9a929621d5bc5913ad0370bcbd673b3615150361e1d5d862e727cf0b9fbd199",
    "lock_path": "docker/requirements.lock",
    "lock_sha256": "6acd3885d28a89476b01dac76b8b8c450f287847b1a6c7505191df30471020a4",
    "package_count": 69,
    "wheel_count": 69,
    "license_review": "pending-before-image-distribution",
}
REQUIRED_WAIVER_CONTROLS = frozenset(
    {
        "validar_origem_commit_sha256",
        "nao_executar_codigo_alvo",
        "container_sem_rede",
        "alvo_somente_leitura",
        "usuario_nao_root",
        "capabilities_removidas",
        "no_new_privileges",
    }
)

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+(?:\.windows\.\d+)?$")
_PYTHON_REF_RE = re.compile(r"^python:\d+\.\d+\.\d+-slim-bookworm$")


def carregar_json(caminho: str | Path) -> dict[str, Any]:
    """Carrega um documento JSON local sem efeitos externos."""

    path = Path(caminho)
    try:
        with path.open("r", encoding="utf-8") as arquivo:
            documento = json.load(
                arquivo,
                object_pairs_hook=_objeto_sem_chaves_duplicadas,
                parse_constant=_constante_json_invalida,
            )
    except (OSError, json.JSONDecodeError) as exc:
        raise ErroProveniencia(f"não foi possível ler JSON válido de {path}: {exc}") from exc

    if not isinstance(documento, dict):
        raise ErroProveniencia(f"o documento {path} deve ser um objeto JSON")
    return documento


def validar_manifesto(manifesto: Mapping[str, Any]) -> Mapping[str, Any]:
    """Valida estrutura, pinos e origens do lock sem acessar a rede."""

    _exigir_objeto(manifesto, "manifesto")
    _exigir_chaves(
        manifesto,
        {"schema_version", "validated_at", "host_policy", "sources"},
        "manifesto",
    )
    if manifesto.get("schema_version") != SCHEMA_VERSION:
        raise ErroProveniencia("schema_version do manifesto não é suportada")
    _validar_data(manifesto.get("validated_at"), "validated_at")

    politica = _exigir_objeto(manifesto.get("host_policy"), "host_policy")
    _exigir_chaves(politica, set(HOST_TOOLS), "host_policy")
    for ferramenta in HOST_TOOLS:
        item = _exigir_objeto(politica.get(ferramenta), f"host_policy.{ferramenta}")
        _exigir_chaves(item, {"recommended", "source"}, f"host_policy.{ferramenta}")
        if dict(item) != HOST_POLICY_LOCKS[ferramenta]:
            raise ErroProveniencia(
                f"política aprovada do host diverge para {ferramenta}"
            )
        _parse_versao(item.get("recommended"), f"host_policy.{ferramenta}.recommended")
        _validar_https(item.get("source"), f"host_policy.{ferramenta}.source")

    fontes = _exigir_objeto(manifesto.get("sources"), "sources")
    esperadas = {
        "realvuln",
        "python_image",
        "bandit",
        "semgrep",
        "python_packages",
        "semgrep_rules",
    }
    if set(fontes) != esperadas:
        raise ErroProveniencia("o conjunto de fontes não corresponde ao design aprovado")

    _validar_realvuln(_exigir_objeto(fontes["realvuln"], "sources.realvuln"))
    _validar_python(_exigir_objeto(fontes["python_image"], "sources.python_image"))
    _validar_pypi(
        _exigir_objeto(fontes["bandit"], "sources.bandit"),
        nome="bandit",
    )
    _validar_pypi(
        _exigir_objeto(fontes["semgrep"], "sources.semgrep"),
        nome="semgrep",
    )
    _validar_python_packages(
        _exigir_objeto(fontes["python_packages"], "sources.python_packages")
    )
    _validar_regras(_exigir_objeto(fontes["semgrep_rules"], "sources.semgrep_rules"))
    return manifesto


def calcular_sha256_arquivo(caminho: str | Path) -> str:
    """Calcula SHA-256 de arquivo regular, sem seguir links."""

    path = Path(caminho)
    if path.is_symlink() or _eh_juncao(path) or not path.is_file():
        raise ErroProveniencia(f"arquivo regular obrigatório para SHA-256: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                digest.update(bloco)
    except OSError as exc:
        raise ErroProveniencia(f"não foi possível calcular SHA-256 de {path}: {exc}") from exc
    return digest.hexdigest()


def calcular_sha256_arvore(caminho: str | Path) -> str:
    """Produz hash canônico de caminhos, tamanhos e conteúdos de uma árvore."""

    raiz = Path(caminho)
    if raiz.is_symlink() or _eh_juncao(raiz) or not raiz.is_dir():
        raise ErroProveniencia(f"raiz do bundle deve ser diretório real: {raiz}")

    entradas: list[tuple[bytes, int, str]] = []
    pendentes = [raiz]
    try:
        while pendentes:
            diretorio = pendentes.pop()
            with os.scandir(diretorio) as itens:
                for item in itens:
                    path = Path(item.path)
                    if item.is_symlink() or _eh_juncao(path):
                        raise ErroProveniencia(f"link ou junção proibido no bundle: {path}")
                    if item.is_dir(follow_symlinks=False):
                        pendentes.append(path)
                    elif item.is_file(follow_symlinks=False):
                        relativo = path.relative_to(raiz).as_posix()
                        relativo_bytes = relativo.encode("utf-8")
                        if b"\0" in relativo_bytes:
                            raise ErroProveniencia("caminho do bundle contém byte NUL")
                        entradas.append(
                            (relativo_bytes, path.stat().st_size, calcular_sha256_arquivo(path))
                        )
                    else:
                        raise ErroProveniencia(f"entrada especial proibida no bundle: {path}")
    except OSError as exc:
        raise ErroProveniencia(f"não foi possível percorrer o bundle {raiz}: {exc}") from exc

    if not entradas:
        raise ErroProveniencia("bundle de regras está vazio")
    digest = hashlib.sha256(b"tree-sha256-v1\0")
    for relativo, tamanho, conteudo_sha256 in sorted(entradas, key=lambda item: item[0]):
        digest.update(relativo)
        digest.update(b"\0")
        digest.update(str(tamanho).encode("ascii"))
        digest.update(b"\0")
        digest.update(conteudo_sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def verificar_bundle_regras(
    raiz_repositorio: str | Path, fonte: Mapping[str, Any]
) -> str:
    """Compara a árvore local selecionada ao hash fixado no lock."""

    paths = fonte.get("paths")
    if paths != ["python"]:
        raise ErroProveniencia("paths do bundle de regras devem ser exatamente ['python']")
    esperado = fonte.get("bundle_sha256")
    _validar_sha256(esperado, "semgrep_rules.bundle_sha256")
    observado = calcular_sha256_arvore(Path(raiz_repositorio) / "python")
    if observado != esperado:
        raise ErroProveniencia(
            f"SHA-256 do bundle de regras diverge: esperado {esperado}, observado {observado}"
        )
    return observado


def verificar_lock_dependencias(
    raiz_projeto: str | Path, fonte: Mapping[str, Any]
) -> dict[str, Any]:
    """Confere os arquivos do lock Python e suas contagens sem instalar pacotes."""

    _validar_python_packages(fonte)
    raiz = Path(raiz_projeto)
    input_path = raiz / fonte["input_path"]
    lock_path = raiz / fonte["lock_path"]
    input_sha256 = calcular_sha256_arquivo(input_path)
    lock_sha256 = calcular_sha256_arquivo(lock_path)
    if input_sha256 != fonte["input_sha256"]:
        raise ErroProveniencia(
            f"requirements.in diverge: esperado {fonte['input_sha256']}, observado {input_sha256}"
        )
    if lock_sha256 != fonte["lock_sha256"]:
        raise ErroProveniencia(
            f"requirements.lock diverge: esperado {fonte['lock_sha256']}, observado {lock_sha256}"
        )

    try:
        texto = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErroProveniencia(f"não foi possível ler {lock_path}: {exc}") from exc
    pacotes = re.findall(r"(?m)^([A-Za-z0-9_.-]+)==([^\s\\]+)\s*\\$", texto)
    hashes = re.findall(r"(?m)^\s+--hash=sha256:([0-9a-f]{64})$", texto)
    nomes = {nome.lower().replace("_", "-").replace(".", "-") for nome, _ in pacotes}
    if len(pacotes) != fonte["package_count"] or len(nomes) != len(pacotes):
        raise ErroProveniencia("contagem ou unicidade dos pacotes no lock diverge")
    if len(hashes) != fonte["wheel_count"] or len(set(hashes)) != len(hashes):
        raise ErroProveniencia("contagem ou unicidade dos wheels no lock diverge")
    return {
        "input_sha256": input_sha256,
        "lock_sha256": lock_sha256,
        "package_count": len(pacotes),
        "wheel_count": len(hashes),
    }


def verificar_fontes(
    caminho_manifesto: str | Path,
    *,
    observadas: Mapping[str, str] | None = None,
    caminho_excecao: str | Path | None = None,
    acao: str = "preflight",
) -> dict[str, Any]:
    """Valida arquivos locais e retorna relatório; nunca baixa nem executa processos."""

    manifesto = carregar_json(caminho_manifesto)
    validar_manifesto(manifesto)
    caminho_manifesto = Path(caminho_manifesto)
    raiz_projeto = caminho_manifesto.resolve().parent.parent
    lock_python = verificar_lock_dependencias(
        raiz_projeto, manifesto["sources"]["python_packages"]
    )
    avisos: list[str] = []
    waiver_sha256: str | None = None
    if observadas is not None:
        excecao = carregar_json(caminho_excecao) if caminho_excecao is not None else None
        avisos = verificar_versoes_host(
            observadas, manifesto["host_policy"], excecao, acao=acao
        )
        if caminho_excecao is not None:
            waiver_sha256 = calcular_sha256_arquivo(caminho_excecao)
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": calcular_sha256_arquivo(caminho_manifesto),
        "waiver_sha256": waiver_sha256,
        "requirements_lock_sha256": lock_python["lock_sha256"],
        "warnings": avisos,
    }


def verificar_versoes_host(
    observadas: Mapping[str, str],
    politica: Mapping[str, Any],
    excecao: Mapping[str, Any] | None = None,
    *,
    acao: str = "preflight",
) -> list[str]:
    """Compara versões e aplica somente a exceção auditável AD-005."""

    _exigir_objeto(observadas, "versões observadas")
    _exigir_objeto(politica, "política do host")
    abaixo: list[tuple[str, str, str]] = []

    for ferramenta in HOST_TOOLS:
        observada = observadas.get(ferramenta)
        regra = _exigir_objeto(politica.get(ferramenta), f"host_policy.{ferramenta}")
        recomendada = regra.get("recommended")
        if _parse_versao(observada, ferramenta) < _parse_versao(
            recomendada, f"host_policy.{ferramenta}.recommended"
        ):
            abaixo.append((ferramenta, str(observada), str(recomendada)))

    if not abaixo:
        return []
    if excecao is None:
        nomes = ", ".join(item[0] for item in abaixo)
        raise ErroProveniencia(
            f"versões abaixo da recomendação ({nomes}) exigem exceção explícita"
        )

    _validar_excecao(excecao, observadas, acao)
    return [
        f"{ferramenta} {observada} abaixo de {recomendada}; risco aceito em AD-005"
        for ferramenta, observada, recomendada in abaixo
    ]


def _validar_excecao(
    excecao: Mapping[str, Any], observadas: Mapping[str, str], acao: str
) -> None:
    _exigir_objeto(excecao, "exceção")
    _exigir_chaves(
        excecao,
        {
            "schema_version",
            "status",
            "decision",
            "accepted_at",
            "accepted_by",
            "scope",
            "reason",
            "versions",
            "allowed_actions",
            "required_controls",
            "approval",
        },
        "exceção",
    )
    if excecao.get("schema_version") != SCHEMA_VERSION:
        raise ErroProveniencia("schema_version da exceção não é suportada")
    if excecao.get("status") != "accepted" or excecao.get("decision") != "AD-005":
        raise ErroProveniencia("exceção não está aceita pela decisão AD-005")
    if excecao.get("scope") != "ambiente-e-primeira-execucao-sast":
        raise ErroProveniencia("escopo da exceção não corresponde a esta feature")

    aceita_em = _validar_data(excecao.get("accepted_at"), "accepted_at")
    if aceita_em > date.today():
        raise ErroProveniencia("data de aceitação da exceção está no futuro")
    if not isinstance(excecao.get("accepted_by"), str) or not excecao["accepted_by"].strip():
        raise ErroProveniencia("accepted_by da exceção é obrigatório")
    if not isinstance(excecao.get("reason"), str) or not excecao["reason"].strip():
        raise ErroProveniencia("reason da exceção é obrigatório")

    versoes_aceitas = _exigir_objeto(excecao.get("versions"), "exceção.versions")
    _exigir_chaves(versoes_aceitas, set(HOST_TOOLS), "exceção.versions")
    if dict(versoes_aceitas) != WAIVED_HOST_VERSIONS:
        raise ErroProveniencia("exceção não corresponde às versões aprovadas em AD-005")
    if dict(versoes_aceitas) != dict(observadas):
        raise ErroProveniencia("exceção não corresponde às versões observadas")

    acoes = excecao.get("allowed_actions")
    if not isinstance(acoes, list) or tuple(acoes) != WAIVER_ALLOWED_ACTIONS:
        raise ErroProveniencia("conjunto de ações da exceção diverge de AD-005")
    if acao not in acoes:
        raise ErroProveniencia(f"ação {acao!r} não é autorizada pela exceção")

    controles = excecao.get("required_controls")
    if not isinstance(controles, list) or set(controles) != REQUIRED_WAIVER_CONTROLS:
        raise ErroProveniencia("controles compensatórios da exceção estão incompletos")

    aprovacao = _exigir_objeto(excecao.get("approval"), "exceção.approval")
    _exigir_chaves(aprovacao, {"reference", "git_commit"}, "exceção.approval")
    if aprovacao.get("reference") != ".specs/project/STATE.md#AD-005":
        raise ErroProveniencia("referência de aprovação da exceção é inválida")
    _validar_commit(aprovacao.get("git_commit"), "exceção.approval.git_commit")
    if aprovacao.get("git_commit") != WAIVER_APPROVAL_COMMIT:
        raise ErroProveniencia("commit de aprovação da exceção diverge de AD-005")


def _validar_realvuln(fonte: Mapping[str, Any]) -> None:
    _exigir_chaves(
        fonte,
        {
            "type",
            "url",
            "tag",
            "tag_object",
            "commit",
            "upstream_abbreviated_identifiers",
            "license_observed",
        },
        "sources.realvuln",
    )
    if fonte.get("type") != "git":
        raise ErroProveniencia("tipo da fonte RealVuln é inválido")
    if fonte.get("url") != REALVULN_URL:
        raise ErroProveniencia("origem oficial do RealVuln não corresponde ao lock")
    if fonte.get("tag") != "v1.0":
        raise ErroProveniencia("tag RealVuln deve ser v1.0")
    if fonte.get("tag_object") != REALVULN_TAG_OBJECT:
        raise ErroProveniencia("objeto da tag RealVuln diverge da origem validada")
    if fonte.get("commit") != REALVULN_COMMIT:
        raise ErroProveniencia("commit RealVuln diverge da especificação aprovada")
    _validar_commit(fonte.get("commit"), "RealVuln.commit")
    abreviados = _exigir_objeto(
        fonte.get("upstream_abbreviated_identifiers"),
        "RealVuln.upstream_abbreviated_identifiers",
    )
    _exigir_chaves(
        abreviados,
        {"ground_truth_content_hash", "default_prompt_version"},
        "RealVuln.upstream_abbreviated_identifiers",
    )
    for nome, valor in abreviados.items():
        if not isinstance(valor, str) or not re.fullmatch(r"sha256:[0-9a-f]{12}", valor):
            raise ErroProveniencia(f"identificador upstream abreviado inválido: {nome}")
    if dict(abreviados) != REALVULN_ABBREVIATED_IDENTIFIERS:
        raise ErroProveniencia("identificador upstream do RealVuln diverge do manifesto v1.0")
    _validar_licencas(fonte, "RealVuln")


def _validar_python(fonte: Mapping[str, Any]) -> None:
    _exigir_chaves(
        fonte,
        {
            "type",
            "registry",
            "reference",
            "index_digest",
            "platform",
            "manifest_digest",
            "source_url",
            "source_revision",
            "license_observed",
        },
        "sources.python_image",
    )
    if fonte.get("type") != "oci" or fonte.get("registry") != "docker.io/library/python":
        raise ErroProveniencia("origem OCI do Python não é a oficial fixada")
    referencia = fonte.get("reference")
    if not isinstance(referencia, str) or "latest" in referencia.lower():
        raise ErroProveniencia("referência flutuante da imagem Python é proibida")
    if not _PYTHON_REF_RE.fullmatch(referencia):
        raise ErroProveniencia("referência da imagem Python não usa versão completa")
    if referencia != PYTHON_REFERENCE:
        raise ErroProveniencia("referência da imagem Python diverge do design aprovado")
    _validar_digest(fonte.get("index_digest"), "python_image.index_digest")
    _validar_digest(fonte.get("manifest_digest"), "python_image.manifest_digest")
    if fonte.get("index_digest") != PYTHON_INDEX_DIGEST:
        raise ErroProveniencia("digest do índice Python diverge da fonte validada")
    if fonte.get("manifest_digest") != PYTHON_MANIFEST_DIGEST:
        raise ErroProveniencia("digest amd64 do Python diverge da fonte validada")
    if fonte.get("platform") != "linux/amd64":
        raise ErroProveniencia("plataforma da imagem Python deve ser linux/amd64")
    _validar_url_exata(fonte.get("source_url"), PYTHON_SOURCE_URL, "origem do Python")
    _validar_commit(fonte.get("source_revision"), "python_image.source_revision")
    if fonte.get("source_revision") != PYTHON_SOURCE_REVISION:
        raise ErroProveniencia("revisão do Dockerfile Python diverge da fonte validada")
    _validar_licencas(fonte, "Python")


def _validar_pypi(fonte: Mapping[str, Any], *, nome: str) -> None:
    campos = {
        "type",
        "project_url",
        "source_url",
        "version",
        "wheel_sha256",
        "source_commit",
        "license_observed",
    }
    campos.add("wheel" if nome == "bandit" else "wheel_platform")
    _exigir_chaves(fonte, campos, f"sources.{nome}")
    if fonte.get("type") != "pypi":
        raise ErroProveniencia(f"tipo da fonte {nome} é inválido")
    esperado = PACKAGE_LOCKS[nome]
    _validar_url_exata(
        fonte.get("project_url"), esperado["project_url"], f"origem PyPI de {nome}"
    )
    _validar_url_exata(
        fonte.get("source_url"), esperado["source_url"], f"origem do código de {nome}"
    )
    _parse_versao(fonte.get("version"), f"{nome}.version")
    if fonte.get("version") != esperado["version"]:
        raise ErroProveniencia(f"versão de {nome} diverge do lock aprovado")
    _validar_sha256(fonte.get("wheel_sha256"), f"{nome}.wheel_sha256")
    if fonte.get("wheel_sha256") != esperado["wheel_sha256"]:
        raise ErroProveniencia(f"SHA-256 do wheel de {nome} diverge da fonte validada")
    _validar_commit(fonte.get("source_commit"), f"{nome}.source_commit")
    if fonte.get("source_commit") != esperado["source_commit"]:
        raise ErroProveniencia(f"commit de {nome} diverge da fonte validada")
    _validar_licencas(fonte, nome)


def _validar_python_packages(fonte: Mapping[str, Any]) -> None:
    _exigir_chaves(fonte, set(PYTHON_PACKAGES_LOCK), "sources.python_packages")
    _validar_url_exata(
        fonte.get("index_url"),
        PYTHON_PACKAGES_LOCK["index_url"],
        "índice do lock Python",
    )
    _validar_sha256(fonte.get("input_sha256"), "python_packages.input_sha256")
    _validar_sha256(fonte.get("lock_sha256"), "python_packages.lock_sha256")
    if dict(fonte) != PYTHON_PACKAGES_LOCK:
        if fonte.get("lock_sha256") != PYTHON_PACKAGES_LOCK["lock_sha256"]:
            raise ErroProveniencia("SHA-256 do requirements.lock diverge da resolução validada")
        raise ErroProveniencia("metadados do lock Python divergem da resolução validada")


def _validar_regras(fonte: Mapping[str, Any]) -> None:
    _exigir_chaves(
        fonte,
        {
            "type",
            "url",
            "commit",
            "paths",
            "bundle_sha256",
            "license_observed",
            "redistribute",
        },
        "sources.semgrep_rules",
    )
    if fonte.get("type") != "git" or fonte.get("url") != SEMGREP_RULES_URL:
        raise ErroProveniencia("origem das regras Semgrep não corresponde ao lock")
    _validar_commit(fonte.get("commit"), "semgrep_rules.commit")
    if fonte.get("commit") != SEMGREP_RULES_COMMIT:
        raise ErroProveniencia("commit das regras Semgrep diverge da fonte validada")
    if fonte.get("paths") != ["python"]:
        raise ErroProveniencia("paths do bundle Semgrep devem ser exatamente ['python']")
    _validar_sha256(fonte.get("bundle_sha256"), "semgrep_rules.bundle_sha256")
    if fonte.get("bundle_sha256") != SEMGREP_RULES_BUNDLE_SHA256:
        raise ErroProveniencia("SHA-256 do bundle Semgrep diverge da aquisição validada")
    if fonte.get("redistribute") is not False:
        raise ErroProveniencia("regras Semgrep não podem ser marcadas para redistribuição")
    _validar_licencas(fonte, "regras Semgrep")


def _validar_https(valor: Any, campo: str) -> str:
    if not isinstance(valor, str):
        raise ErroProveniencia(f"{campo} deve ser URL HTTPS")
    partes = urlsplit(valor)
    try:
        porta = partes.port
    except ValueError as exc:
        raise ErroProveniencia(f"{campo} contém porta inválida") from exc
    if (
        partes.scheme != "https"
        or not partes.hostname
        or partes.username
        or partes.password
        or porta not in (None, 443)
        or partes.query
        or partes.fragment
        or "\\" in valor
        or "%2f" in valor.lower()
        or "/./" in partes.path
        or "/../" in partes.path
    ):
        raise ErroProveniencia(f"{campo} deve ser URL HTTPS simples")
    return partes.hostname.lower()


def _validar_url_exata(valor: Any, esperada: str, campo: str) -> None:
    _validar_https(valor, campo)
    if valor != esperada:
        raise ErroProveniencia(f"{campo}: origem não corresponde à URL oficial exata")


def _validar_commit(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _COMMIT_RE.fullmatch(valor):
        raise ErroProveniencia(f"{campo} deve ser commit Git completo")


def _validar_sha256(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _SHA256_RE.fullmatch(valor):
        raise ErroProveniencia(f"{campo} deve ser SHA-256 completo")


def _validar_digest(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _DIGEST_RE.fullmatch(valor):
        raise ErroProveniencia(f"{campo} deve ser digest SHA-256 completo")


def _validar_licencas(fonte: Mapping[str, Any], nome: str) -> None:
    licencas = fonte.get("license_observed")
    if not isinstance(licencas, list) or not licencas:
        raise ErroProveniencia(f"licença observada de {nome} é obrigatória")
    if any(not isinstance(item, str) or not item.strip() for item in licencas):
        raise ErroProveniencia(f"licença observada de {nome} contém valor inválido")
    if licencas != LICENSE_LOCKS[nome]:
        raise ErroProveniencia(f"licença observada de {nome} diverge da fonte validada")


def _parse_versao(valor: Any, campo: str) -> tuple[int, ...]:
    if not isinstance(valor, str) or not _VERSION_RE.fullmatch(valor):
        raise ErroProveniencia(f"{campo} deve conter versão completa")
    numeros = tuple(int(parte) for parte in re.findall(r"\d+", valor))
    if len(numeros) < 2:
        raise ErroProveniencia(f"{campo} deve conter versão completa")
    return numeros


def _validar_data(valor: Any, campo: str) -> date:
    if not isinstance(valor, str):
        raise ErroProveniencia(f"{campo} deve ser uma data ISO")
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ErroProveniencia(f"{campo} deve ser uma data ISO") from exc


def _exigir_objeto(valor: Any, campo: str) -> Mapping[str, Any]:
    if not isinstance(valor, Mapping):
        raise ErroProveniencia(f"{campo} deve ser um objeto")
    return valor


def _exigir_chaves(
    objeto: Mapping[str, Any], esperadas: set[str], campo: str
) -> None:
    atuais = set(objeto)
    if atuais != esperadas:
        ausentes = sorted(esperadas - atuais)
        desconhecidas = sorted(atuais - esperadas)
        raise ErroProveniencia(
            f"campos inválidos em {campo}; ausentes={ausentes}, desconhecidos={desconhecidas}"
        )


def _objeto_sem_chaves_duplicadas(
    pares: list[tuple[str, Any]],
) -> dict[str, Any]:
    objeto: dict[str, Any] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroProveniencia(f"chave JSON duplicada: {chave}")
        objeto[chave] = valor
    return objeto


def _constante_json_invalida(valor: str) -> None:
    raise ErroProveniencia(f"constante JSON não finita é proibida: {valor}")


def _eh_juncao(path: Path) -> bool:
    detector = getattr(path, "is_junction", None)
    return bool(detector()) if detector is not None else False
