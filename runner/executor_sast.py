"""Executor interno das condições SAST.

Este módulo roda *dentro* do contêiner endurecido. Ele nunca chama Docker e
nunca importa código do alvo: somente inicia o binário fixado da condição,
preserva seus artefatos e então invoca o adaptador puro correspondente.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import signal
import stat
import subprocess
import sys
import time
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runner.adaptadores.bandit import normalizar as normalizar_bandit
from runner.adaptadores.comum import ErroAdaptador, Proveniencia
from runner.adaptadores.semgrep import normalizar as normalizar_semgrep
from runner.aquisicao import (
    ErroProveniencia,
    calcular_sha256_arquivo,
    calcular_sha256_arvore,
    carregar_json,
    validar_manifesto,
    verificar_bundle_regras,
)
from runner.modelos import ManifestoExecucao, SCHEMA_VERSION


class ErroExecucao(RuntimeError):
    """Indica violação do contrato operacional do executor."""


class ErroContaminacao(ErroExecucao):
    """Indica que a entrada mudou durante a tentativa."""


@dataclass(frozen=True, slots=True)
class ResultadoProcesso:
    codigo_saida: int | None
    timeout: bool


@dataclass(frozen=True, slots=True)
class ConfiguracaoExecucao:
    condicao: str
    execucao_id: str
    alvo: str
    entrada_commit: str | None
    entrada_sha256: str
    finalidade: str
    tentativa: int
    imagem: str
    imagem_digest: str
    timeout_segundos: int
    entrada_dir: Path = Path("/entrada")
    saida_dir: Path = Path("/saida")
    regras_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.condicao not in {"C1", "C2"}:
            raise ErroExecucao("executor SAST aceita somente C1 ou C2")
        try:
            Proveniencia(
                alvo=self.alvo,
                repeticao=1,
                execucao_id=self.execucao_id,
                saida_bruta_sha256="0" * 64,
            ).validar_para(self.condicao)
        except ErroAdaptador as exc:
            raise ErroExecucao(f"proveniência da execução é inválida: {exc}") from exc
        if self.entrada_commit is not None and not re.fullmatch(
            r"[0-9a-f]{40}", self.entrada_commit
        ):
            raise ErroExecucao("entrada_commit deve ser commit SHA-1 completo ou null")
        if not isinstance(self.entrada_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.entrada_sha256
        ):
            raise ErroExecucao("entrada_sha256 deve ser SHA-256 completo")
        if self.finalidade not in {"fumaca", "piloto", "coleta"}:
            raise ErroExecucao("finalidade inválida")
        if type(self.tentativa) is not int or self.tentativa <= 0:
            raise ErroExecucao("tentativa deve ser inteiro positivo")
        if not isinstance(self.imagem, str) or not self.imagem.strip():
            raise ErroExecucao("imagem é obrigatória")
        if not isinstance(self.imagem_digest, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", self.imagem_digest
        ):
            raise ErroExecucao("imagem_digest deve ser ID SHA-256 completo")
        if (
            type(self.timeout_segundos) is not int
            or self.timeout_segundos <= 0
            or self.timeout_segundos > 86_400
        ):
            raise ErroExecucao("timeout_segundos deve estar entre 1 e 86400")

        entrada = _path_real(self.entrada_dir, "entrada_dir")
        saida = _path_real(self.saida_dir, "saida_dir")
        regras = (
            _path_real(self.regras_dir, "regras_dir")
            if self.regras_dir is not None
            else None
        )
        if entrada == saida or _eh_ancestral(entrada, saida) or _eh_ancestral(saida, entrada):
            raise ErroExecucao("entrada e saída não podem se sobrepor")
        if self.condicao == "C1" and regras is not None:
            raise ErroExecucao("C1 não aceita diretório de regras Semgrep")
        if self.condicao == "C2" and regras is None:
            raise ErroExecucao("C2 exige diretório de regras Semgrep")
        if regras is not None and (
            regras in {entrada, saida}
            or _eh_ancestral(regras, entrada)
            or _eh_ancestral(entrada, regras)
            or _eh_ancestral(regras, saida)
            or _eh_ancestral(saida, regras)
        ):
            raise ErroExecucao("regras, entrada e saída não podem se sobrepor")

        object.__setattr__(self, "entrada_dir", entrada)
        object.__setattr__(self, "saida_dir", saida)
        object.__setattr__(self, "regras_dir", regras)

    def to_dict(self) -> dict[str, Any]:
        return {
            "condicao": self.condicao,
            "execucao_id": self.execucao_id,
            "alvo": self.alvo,
            "entrada_commit": self.entrada_commit,
            "entrada_sha256": self.entrada_sha256,
            "finalidade": self.finalidade,
            "tentativa": self.tentativa,
            "imagem": self.imagem,
            "imagem_digest": self.imagem_digest,
            "timeout_segundos": self.timeout_segundos,
            "entrada_dir": self.entrada_dir,
            "saida_dir": self.saida_dir,
            "regras_dir": self.regras_dir,
        }


def comando_scanner(
    configuracao: ConfiguracaoExecucao,
) -> tuple[tuple[str, ...], frozenset[int]]:
    """Retorna o vetor imutável da condição e seus códigos esperados."""

    bruto_part = configuracao.saida_dir / "bruto.json.part"
    if configuracao.condicao == "C1":
        return (
            (
                "/usr/local/bin/bandit",
                "--recursive",
                str(configuracao.entrada_dir),
                "--format",
                "json",
                "--output",
                str(bruto_part),
            ),
            frozenset({0, 1}),
        )
    assert configuracao.regras_dir is not None
    return (
        (
            "/usr/local/bin/semgrep",
            "scan",
            "--config",
            str(configuracao.regras_dir / "python"),
            "--json",
            "--metrics=off",
            "--jobs",
            "1",
            "--output",
            str(bruto_part),
            str(configuracao.entrada_dir),
        ),
        frozenset({0}),
    )


def executar_sast(
    configuracao: ConfiguracaoExecucao,
    *,
    executar_processo: Callable[
        [Sequence[str], Any, Any, int], ResultadoProcesso
    ] = None,
    validar_ambiente: Callable[[ConfiguracaoExecucao], None] = None,
    verificar_regras: Callable[[ConfiguracaoExecucao], str | None] = None,
    obter_versoes: Callable[[ConfiguracaoExecucao], Mapping[str, Any]] = None,
    normalizadores: Mapping[str, Callable[[bytes, Proveniencia], list[Any]]] | None = None,
    agora_utc: Callable[[], str] = None,
    monotonic_ns: Callable[[], int] = None,
) -> ManifestoExecucao:
    """Executa uma tentativa completa e sempre fecha seu manifesto terminal."""

    executar_processo = executar_processo or _executar_processo
    validar_ambiente = validar_ambiente or _validar_ambiente
    verificar_regras = verificar_regras or _verificar_regras
    obter_versoes = obter_versoes or _obter_versoes
    agora_utc = agora_utc or _agora_utc
    monotonic_ns = monotonic_ns or time.monotonic_ns
    normalizadores = normalizadores or {
        "C1": normalizar_bandit,
        "C2": normalizar_semgrep,
    }

    _validar_saida_vazia(configuracao.saida_dir)
    comando, codigos_esperados = comando_scanner(configuracao)
    manifesto_pendente = ManifestoExecucao(
        schema_version=SCHEMA_VERSION,
        execucao_id=configuracao.execucao_id,
        condicao=configuracao.condicao,
        ferramenta="bandit" if configuracao.condicao == "C1" else "semgrep",
        bloco=None,
        alvo=configuracao.alvo,
        repeticao=1,
        entrada_commit=configuracao.entrada_commit,
        entrada_sha256=configuracao.entrada_sha256,
        comando=comando,
        imagem=configuracao.imagem,
        imagem_digest=configuracao.imagem_digest,
        finalidade=configuracao.finalidade,
        inicio_utc=None,
        termino_utc=None,
        duracao_monotonica_segundos=None,
        codigo_saida=None,
        estado="pendente",
        falha_tipo=None,
        falha_mensagem=None,
        tentativa=configuracao.tentativa,
        artefatos_sha256={},
    )
    _escrever_bytes_atomico(
        configuracao.saida_dir / "manifesto.pendente.json",
        manifesto_pendente.to_json().encode("utf-8"),
    )
    inicio_utc = agora_utc()
    inicio_ns = monotonic_ns()
    manifesto_inicial = ManifestoExecucao(
        schema_version=SCHEMA_VERSION,
        execucao_id=configuracao.execucao_id,
        condicao=configuracao.condicao,
        ferramenta="bandit" if configuracao.condicao == "C1" else "semgrep",
        bloco=None,
        alvo=configuracao.alvo,
        repeticao=1,
        entrada_commit=configuracao.entrada_commit,
        entrada_sha256=configuracao.entrada_sha256,
        comando=comando,
        imagem=configuracao.imagem,
        imagem_digest=configuracao.imagem_digest,
        finalidade=configuracao.finalidade,
        inicio_utc=inicio_utc,
        termino_utc=None,
        duracao_monotonica_segundos=None,
        codigo_saida=None,
        estado="em_execucao",
        falha_tipo=None,
        falha_mensagem=None,
        tentativa=configuracao.tentativa,
        artefatos_sha256={},
    )
    _escrever_bytes_atomico(
        configuracao.saida_dir / "manifesto.em_execucao.json",
        manifesto_inicial.to_json().encode("utf-8"),
    )

    estado = "falha"
    falha_tipo: str | None = "interna"
    falha_mensagem: str | None = "execução não iniciada"
    codigo_saida: int | None = None
    etapa = "preflight"

    try:
        validar_ambiente(configuracao)
        observado_antes = calcular_sha256_arvore(configuracao.entrada_dir)
        if observado_antes != configuracao.entrada_sha256:
            raise ErroProveniencia(
                "SHA-256 canônico da entrada diverge antes da execução"
            )
        regra_sha256 = None
        if configuracao.condicao == "C2":
            regra_sha256 = verificar_regras(configuracao)
        if configuracao.condicao == "C2" and (
            not isinstance(regra_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", regra_sha256)
        ):
            raise ErroProveniencia(
                "verificador das regras retornou SHA-256 inválido"
            )
        versoes = dict(obter_versoes(configuracao))
        _validar_versoes(versoes)
        if regra_sha256 is not None:
            versoes["regras_semgrep_sha256"] = regra_sha256
        _escrever_json_atomico(configuracao.saida_dir / "versoes.json", versoes)
        artefatos_pre_scanner = _hashes_artefatos(
            configuracao.saida_dir,
            (
                "manifesto.pendente.json",
                "manifesto.em_execucao.json",
                "versoes.json",
            ),
        )

        etapa = "execucao"
        processo_inicio_utc = agora_utc()
        processo_inicio_ns = monotonic_ns()
        stdout_part = configuracao.saida_dir / "stdout.bin.part"
        stderr_part = configuracao.saida_dir / "stderr.bin.part"
        with stdout_part.open("xb") as stdout, stderr_part.open("xb") as stderr:
            resultado = executar_processo(
                comando,
                stdout,
                stderr,
                configuracao.timeout_segundos,
            )
            _sincronizar(stdout)
            _sincronizar(stderr)
        codigo_saida = resultado.codigo_saida
        processo_termino_ns = monotonic_ns()
        processo_termino_utc = agora_utc()
        _finalizar_partes(configuracao.saida_dir)

        processo_duracao = (
            processo_termino_ns - processo_inicio_ns
        ) / 1_000_000_000
        if not math.isfinite(processo_duracao) or processo_duracao < 0:
            raise ErroExecucao("relógio do scanner produziu duração inválida")
        _escrever_json_atomico(
            configuracao.saida_dir / "processo.json",
            {
                "codigo_saida": codigo_saida,
                "comando": list(comando),
                "codigos_saida_esperados": sorted(codigos_esperados),
                "duracao_monotonica_segundos": processo_duracao,
                "inicio_utc": processo_inicio_utc,
                "termino_utc": processo_termino_utc,
                "timeout": resultado.timeout,
                "timeout_segundos": configuracao.timeout_segundos,
            },
        )
        try:
            _verificar_hashes_artefatos(
                configuracao.saida_dir, artefatos_pre_scanner
            )
        except (ErroExecucao, ErroProveniencia, OSError) as exc:
            raise ErroContaminacao(
                f"scanner alterou metadado preexistente: {exc}"
            ) from exc
        try:
            observado_depois = calcular_sha256_arvore(configuracao.entrada_dir)
        except ErroProveniencia as exc:
            raise ErroContaminacao(
                f"entrada ficou inválida depois da execução: {exc}"
            ) from exc
        if observado_depois != configuracao.entrada_sha256:
            raise ErroContaminacao(
                "SHA-256 canônico da entrada diverge depois da execução"
            )
        if configuracao.condicao == "C2":
            try:
                regra_sha256_depois = verificar_regras(configuracao)
            except (ErroProveniencia, ErroExecucao) as exc:
                raise ErroContaminacao(
                    f"regras ficaram inválidas depois da execução: {exc}"
                ) from exc
            if regra_sha256_depois != regra_sha256:
                raise ErroContaminacao(
                    "SHA-256 das regras diverge depois da execução"
                )

        bruto_path = configuracao.saida_dir / "bruto.json"
        if resultado.timeout:
            falha_tipo = "timeout"
            falha_mensagem = (
                f"scanner excedeu timeout de {configuracao.timeout_segundos} segundos"
            )
        elif codigo_saida not in codigos_esperados:
            falha_tipo = "codigo_saida"
            falha_mensagem = f"scanner encerrou com código inesperado {codigo_saida}"
        elif not bruto_path.is_file() or bruto_path.is_symlink():
            falha_tipo = "formato"
            falha_mensagem = "scanner não produziu arquivo bruto regular"
        else:
            etapa = "normalizacao"
            bruto = bruto_path.read_bytes()
            proveniencia = Proveniencia(
                alvo=configuracao.alvo,
                repeticao=1,
                execucao_id=configuracao.execucao_id,
                saida_bruta_sha256=hashlib.sha256(bruto).hexdigest(),
            )
            normalizador = normalizadores.get(configuracao.condicao)
            if normalizador is None:
                raise ErroExecucao("normalizador da condição não foi configurado")
            with warnings.catch_warnings(record=True) as avisos_emitidos:
                warnings.simplefilter("always")
                achados = normalizador(bruto, proveniencia)
            normalizado = [achado.to_dict() for achado in achados]
            _escrever_json_atomico(
                configuracao.saida_dir / "normalizado.json", normalizado
            )
            if avisos_emitidos:
                _escrever_json_atomico(
                    configuracao.saida_dir / "avisos.json",
                    [_aviso_para_dict(aviso) for aviso in avisos_emitidos],
                )
            _exigir_artefatos_conclusao(configuracao.saida_dir)
            estado = "concluida"
            falha_tipo = None
            falha_mensagem = None
    except ErroAdaptador as exc:
        falha_tipo = "formato"
        falha_mensagem = str(exc)
    except ErroContaminacao as exc:
        falha_tipo = "contaminada"
        falha_mensagem = str(exc)
    except ErroProveniencia as exc:
        falha_tipo = "proveniencia"
        falha_mensagem = str(exc)
    except ErroExecucao as exc:
        falha_tipo = "preflight" if etapa == "preflight" else "interna"
        falha_mensagem = str(exc)
    except (OSError, ValueError, TypeError) as exc:
        falha_tipo = "interna"
        falha_mensagem = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        falha_tipo = "interna"
        falha_mensagem = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            _finalizar_partes(configuracao.saida_dir)
        except ErroExecucao as exc:
            estado = "falha"
            falha_tipo = "interna"
            falha_mensagem = str(exc)

    termino_utc = agora_utc()
    termino_ns = monotonic_ns()
    duracao = (termino_ns - inicio_ns) / 1_000_000_000
    if not math.isfinite(duracao) or duracao < 0:
        raise ErroExecucao("relógio monotônico produziu duração inválida")
    try:
        artefatos = _coletar_artefatos(configuracao.saida_dir)
    except (ErroExecucao, ErroProveniencia, OSError) as exc:
        estado = "falha"
        falha_tipo = "interna"
        falha_mensagem = str(exc)
        artefatos = _coletar_artefatos(
            configuracao.saida_dir, rejeitar_inesperados=False
        )
    manifesto_terminal = ManifestoExecucao(
        schema_version=SCHEMA_VERSION,
        execucao_id=configuracao.execucao_id,
        condicao=configuracao.condicao,
        ferramenta="bandit" if configuracao.condicao == "C1" else "semgrep",
        bloco=None,
        alvo=configuracao.alvo,
        repeticao=1,
        entrada_commit=configuracao.entrada_commit,
        entrada_sha256=configuracao.entrada_sha256,
        comando=comando,
        imagem=configuracao.imagem,
        imagem_digest=configuracao.imagem_digest,
        finalidade=configuracao.finalidade,
        inicio_utc=inicio_utc,
        termino_utc=termino_utc,
        duracao_monotonica_segundos=duracao,
        codigo_saida=codigo_saida,
        estado=estado,
        falha_tipo=falha_tipo,
        falha_mensagem=falha_mensagem,
        tentativa=configuracao.tentativa,
        artefatos_sha256=artefatos,
    )
    _escrever_bytes_atomico(
        configuracao.saida_dir / "manifesto.json",
        manifesto_terminal.to_json().encode("utf-8"),
    )
    return manifesto_terminal


def _executar_processo(
    comando: Sequence[str],
    stdout: Any,
    stderr: Any,
    limite: int,
    *,
    popen_factory: Callable[..., Any] = subprocess.Popen,
) -> ResultadoProcesso:
    """Executa vetor sem shell e encerra todo o grupo em timeout."""

    ambiente = {
        "HOME": "/tmp/tcc-home",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "SEMGREP_ENABLE_VERSION_CHECK": "0",
        "SEMGREP_SEND_METRICS": "off",
        "TMPDIR": "/tmp",
    }
    processo = popen_factory(
        list(comando),
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        cwd="/tmp",
        env=ambiente,
        start_new_session=True,
        close_fds=True,
    )
    try:
        codigo = processo.wait(timeout=limite)
        return ResultadoProcesso(codigo_saida=codigo, timeout=False)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(processo.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(processo.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            processo.wait()
        return ResultadoProcesso(codigo_saida=None, timeout=True)


def _validar_ambiente(configuracao: ConfiguracaoExecucao) -> None:
    """Falha fechada se o runtime não tiver os controles compensatórios."""

    if configuracao.entrada_dir != Path("/entrada").resolve(strict=False):
        raise ErroExecucao("entrada interna deve ser exatamente /entrada")
    if configuracao.saida_dir != Path("/saida").resolve(strict=False):
        raise ErroExecucao("saída interna deve ser exatamente /saida")
    esperado_regras = Path("/opt/regras-semgrep").resolve(strict=False)
    if configuracao.condicao == "C2" and configuracao.regras_dir != esperado_regras:
        raise ErroExecucao("regras C2 devem estar em /opt/regras-semgrep")
    if os.getuid() != 10001 or os.getgid() != 10001:
        raise ErroExecucao("executor deve usar uid/gid 10001")
    if Path.cwd() != Path("/opt/tcc"):
        raise ErroExecucao("workdir do executor deve ser /opt/tcc")
    if os.environ.get("PYTHONSAFEPATH") != "1":
        raise ErroExecucao("PYTHONSAFEPATH=1 é obrigatório")
    if str(configuracao.entrada_dir) in sys.path:
        raise ErroExecucao("entrada não pode integrar sys.path")
    if Path("/var/run/docker.sock").exists():
        raise ErroExecucao("docker.sock não pode existir no contêiner")

    status = Path("/proc/self/status").read_text(encoding="utf-8")
    cap_eff = re.search(r"(?m)^CapEff:\s*([0-9a-fA-F]+)$", status)
    no_new = re.search(r"(?m)^NoNewPrivs:\s*(\d+)$", status)
    if cap_eff is None or int(cap_eff.group(1), 16) != 0:
        raise ErroExecucao("capabilities efetivas devem ser zero")
    if no_new is None or int(no_new.group(1)) != 1:
        raise ErroExecucao("no-new-privileges deve estar ativo")
    interfaces = _listar_interfaces_rede(Path("/sys/class/net"))
    if interfaces != {"lo"}:
        raise ErroExecucao(f"rede não isolada; interfaces={sorted(interfaces)}")

    mounts = _ler_mounts()
    _exigir_mount(mounts, Path("/"), "ro")
    _exigir_mount(mounts, Path("/tmp"), "rw")
    _exigir_mount(mounts, configuracao.entrada_dir, "ro")
    _exigir_mount(mounts, configuracao.saida_dir, "rw")
    if configuracao.condicao == "C2":
        assert configuracao.regras_dir is not None
        _exigir_mount(mounts, configuracao.regras_dir, "ro")
    elif esperado_regras.exists():
        raise ErroExecucao("C1 não pode receber regras Semgrep")


def _verificar_regras(configuracao: ConfiguracaoExecucao) -> str:
    assert configuracao.regras_dir is not None
    manifesto = carregar_json("/opt/tcc/config/fontes.lock.json")
    validar_manifesto(manifesto)
    fonte = manifesto["sources"]["semgrep_rules"]
    return verificar_bundle_regras(configuracao.regras_dir, fonte)


def _obter_versoes(configuracao: ConfiguracaoExecucao) -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "bandit": importlib.metadata.version("bandit"),
        "semgrep": importlib.metadata.version("semgrep"),
    }


def _validar_versoes(versoes: Mapping[str, Any]) -> None:
    esperadas = {"python": "3.12.13", "bandit": "1.9.4", "semgrep": "1.172.0"}
    for nome, esperada in esperadas.items():
        if versoes.get(nome) != esperada:
            raise ErroExecucao(
                f"versão de {nome} diverge: esperada={esperada}, observada={versoes.get(nome)}"
            )


def _validar_saida_vazia(saida: Path) -> None:
    if saida.is_symlink() or not saida.is_dir():
        raise ErroExecucao("saída deve ser diretório real existente")
    try:
        if any(saida.iterdir()):
            raise ErroExecucao("saída deve ser nova e vazia")
    except OSError as exc:
        raise ErroExecucao(f"não foi possível inspecionar saída: {exc}") from exc


def _finalizar_partes(saida: Path) -> None:
    for nome in ("stdout.bin", "stderr.bin", "bruto.json"):
        parcial = saida / f"{nome}.part"
        final = saida / nome
        if not parcial.exists() and not parcial.is_symlink():
            continue
        _exigir_arquivo_regular(parcial)
        if final.exists() or final.is_symlink():
            raise ErroExecucao(f"artefato final já existe: {final.name}")
        with parcial.open("rb") as arquivo:
            os.fsync(arquivo.fileno())
        os.replace(parcial, final)
        _sincronizar_diretorio(saida)


def _coletar_artefatos(
    saida: Path, *, rejeitar_inesperados: bool = True
) -> dict[str, str]:
    permitidos = {
        "manifesto.pendente.json",
        "manifesto.em_execucao.json",
        "versoes.json",
        "processo.json",
        "stdout.bin",
        "stderr.bin",
        "bruto.json",
        "normalizado.json",
        "avisos.json",
    }
    artefatos: dict[str, str] = {}
    for item in saida.iterdir():
        if item.name == "manifesto.json":
            continue
        if item.name not in permitidos:
            if rejeitar_inesperados:
                raise ErroExecucao(f"artefato inesperado na saída: {item.name}")
            continue
        try:
            _exigir_arquivo_regular(item)
            artefatos[item.name] = calcular_sha256_arquivo(item)
        except (ErroExecucao, ErroProveniencia, OSError):
            if rejeitar_inesperados:
                raise
    return artefatos


def _hashes_artefatos(saida: Path, nomes: Sequence[str]) -> dict[str, str]:
    return {nome: calcular_sha256_arquivo(saida / nome) for nome in nomes}


def _verificar_hashes_artefatos(
    saida: Path, esperados: Mapping[str, str]
) -> None:
    observados = _hashes_artefatos(saida, tuple(esperados))
    if observados != dict(esperados):
        raise ErroExecucao("hash de metadado preexistente diverge")


def _exigir_artefatos_conclusao(saida: Path) -> None:
    obrigatorios = (
        "manifesto.pendente.json",
        "manifesto.em_execucao.json",
        "versoes.json",
        "processo.json",
        "stdout.bin",
        "stderr.bin",
        "bruto.json",
        "normalizado.json",
    )
    for nome in obrigatorios:
        _exigir_arquivo_regular(saida / nome)


def _exigir_arquivo_regular(path: Path) -> None:
    try:
        modo = path.lstat().st_mode
    except OSError as exc:
        raise ErroExecucao(f"não foi possível inspecionar artefato {path}: {exc}") from exc
    if stat.S_ISLNK(modo) or not stat.S_ISREG(modo):
        raise ErroExecucao(f"artefato deve ser arquivo regular: {path.name}")


def _aviso_para_dict(aviso: warnings.WarningMessage) -> dict[str, Any]:
    mensagem = aviso.message
    documento: dict[str, Any] = {
        "categoria": type(mensagem).__name__,
        "mensagem": str(mensagem),
    }
    if hasattr(mensagem, "erros"):
        documento["erros"] = list(getattr(mensagem, "erros"))
    if hasattr(mensagem, "saida_bruta_sha256"):
        documento["saida_bruta_sha256"] = getattr(
            mensagem, "saida_bruta_sha256"
        )
    return documento


def _escrever_json_atomico(destino: Path, documento: Any) -> None:
    try:
        conteudo = json.dumps(
            documento,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ErroExecucao(f"documento não é JSON determinístico: {exc}") from exc
    _escrever_bytes_atomico(destino, conteudo)


def _escrever_bytes_atomico(destino: Path, conteudo: bytes) -> None:
    if not isinstance(conteudo, bytes):
        raise ErroExecucao("escrita atômica exige bytes")
    if destino.exists() or destino.is_symlink():
        raise ErroExecucao(f"destino já existe e não será sobrescrito: {destino.name}")
    temporario = destino.with_name(destino.name + ".tmp")
    if temporario.exists() or temporario.is_symlink():
        raise ErroExecucao(f"temporário já existe: {temporario.name}")
    try:
        with temporario.open("xb") as arquivo:
            arquivo.write(conteudo)
            _sincronizar(arquivo)
        os.replace(temporario, destino)
        _sincronizar_diretorio(destino.parent)
    except OSError as exc:
        try:
            if temporario.exists() and not temporario.is_symlink():
                temporario.unlink()
        except OSError:
            pass
        raise ErroExecucao(f"falha na escrita atômica de {destino.name}: {exc}") from exc


def _sincronizar(arquivo: Any) -> None:
    arquivo.flush()
    os.fsync(arquivo.fileno())


def _sincronizar_diretorio(path: Path) -> None:
    descritor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descritor)
    finally:
        os.close(descritor)


def _agora_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _path_real(valor: Any, campo: str) -> Path:
    if not isinstance(valor, (str, os.PathLike)):
        raise ErroExecucao(f"{campo} deve ser caminho")
    path = Path(valor)
    if not path.is_absolute():
        raise ErroExecucao(f"{campo} deve ser absoluto")
    return path.resolve(strict=False)


def _eh_ancestral(ancestral: Path, descendente: Path) -> bool:
    return ancestral != descendente and ancestral in descendente.parents


def _ler_mounts() -> dict[Path, frozenset[str]]:
    mounts: dict[Path, frozenset[str]] = {}
    texto = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    for linha in texto.splitlines():
        antes, _, _depois = linha.partition(" - ")
        campos = antes.split()
        if len(campos) < 6:
            continue
        mountpoint = campos[4].replace("\\040", " ").replace("\\134", "\\")
        mounts[Path(mountpoint)] = frozenset(campos[5].split(","))
    return mounts


def _listar_interfaces_rede(sysfs: Path) -> set[str]:
    return {item.name for item in sysfs.iterdir() if item.is_dir()}


def _exigir_mount(
    mounts: Mapping[Path, frozenset[str]], path: Path, modo: str
) -> None:
    opcoes = mounts.get(path)
    if opcoes is None or modo not in opcoes:
        raise ErroExecucao(f"mount {path} deve existir em modo {modo}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executor interno SAST C1/C2")
    parser.add_argument("--condicao", required=True, choices=("C1", "C2"))
    parser.add_argument("--execucao-id", required=True)
    parser.add_argument("--alvo", required=True)
    parser.add_argument("--entrada-commit")
    parser.add_argument("--entrada-sha256", required=True)
    parser.add_argument("--finalidade", required=True, choices=("fumaca", "piloto", "coleta"))
    parser.add_argument("--tentativa", required=True, type=int)
    parser.add_argument("--imagem", required=True)
    parser.add_argument("--imagem-digest", required=True)
    parser.add_argument("--timeout-segundos", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    configuracao = ConfiguracaoExecucao(
        condicao=args.condicao,
        execucao_id=args.execucao_id,
        alvo=args.alvo,
        entrada_commit=args.entrada_commit,
        entrada_sha256=args.entrada_sha256,
        finalidade=args.finalidade,
        tentativa=args.tentativa,
        imagem=args.imagem,
        imagem_digest=args.imagem_digest,
        timeout_segundos=args.timeout_segundos,
        regras_dir=Path("/opt/regras-semgrep") if args.condicao == "C2" else None,
    )
    manifesto = executar_sast(configuracao)
    print(manifesto.to_json())
    return 0 if manifesto.estado == "concluida" else 2


if __name__ == "__main__":
    raise SystemExit(main())
