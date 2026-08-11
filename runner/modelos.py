"""Modelos versionados e validação estrita dos artefatos do experimento.

Os modelos deste módulo não acessam rede, disco ou processos. A validação é
deliberadamente fechada: campos ausentes ou desconhecidos são recusados, os
valores indisponíveis permanecem ``None`` e nenhuma informação é inferida.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


class ErroModelo(ValueError):
    """Indica que um achado ou manifesto não satisfaz o contrato v1."""


SCHEMA_VERSION = "1.0"
CONDICOES = frozenset({"C1", "C2", "C3", "C4", "C5", "C6"})
ESTADOS_EXECUCAO = frozenset(
    {"pendente", "em_execucao", "concluida", "falha"}
)
FERRAMENTA_POR_CONDICAO = {
    "C1": "bandit",
    "C2": "semgrep",
    "C3": "cursor",
    "C4": "codex",
    "C5": "cursor",
    "C6": "codex",
}
SEVERIDADES_NORMALIZADAS = frozenset({"baixa", "media", "alta", "critica"})
CONFIANCAS_NORMALIZADAS = frozenset({"baixa", "media", "alta"})
FINALIDADES = frozenset({"coleta", "piloto", "fumaca"})
TIPOS_FALHA = frozenset(
    {
        "proveniencia",
        "preflight",
        "timeout",
        "codigo_saida",
        "formato",
        "interrompida",
        "contaminada",
        "indisponibilidade",
        "interna",
    }
)

_IDENTIFICADOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_CWE_RE = re.compile(r"^CWE-[1-9][0-9]*$")
_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


@dataclass(frozen=True, slots=True)
class Achado:
    """Achado normalizado v1, sempre ligado à saída bruta encerrada."""

    schema_version: str
    condicao: str
    ferramenta: str
    alvo: str
    repeticao: int
    execucao_id: str
    arquivo: str | None
    linha_inicial: int | None
    linha_final: int | None
    regra: str | None
    cwe_original: str | tuple[str, ...] | None
    cwe: str | None
    severidade_original: str | None
    severidade: str | None
    confianca_original: str | None
    confianca: str | None
    descricao: str | None
    evidencia: str | None
    recomendacao: str | None
    texto_original: str | None
    saida_bruta_sha256: str

    CAMPOS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "condicao",
            "ferramenta",
            "alvo",
            "repeticao",
            "execucao_id",
            "arquivo",
            "linha_inicial",
            "linha_final",
            "regra",
            "cwe_original",
            "cwe",
            "severidade_original",
            "severidade",
            "confianca_original",
            "confianca",
            "descricao",
            "evidencia",
            "recomendacao",
            "texto_original",
            "saida_bruta_sha256",
        }
    )

    def __post_init__(self) -> None:
        _validar_versao(self.schema_version)
        _validar_condicao(self.condicao)
        _validar_ferramenta_e_repeticao(
            self.condicao, self.ferramenta, self.repeticao
        )
        _validar_identificador(self.alvo, "alvo")
        _validar_identificador(self.execucao_id, "execucao_id")
        _validar_caminho_relativo_opcional(self.arquivo, "arquivo")
        _validar_linha_opcional(self.linha_inicial, "linha_inicial")
        _validar_linha_opcional(self.linha_final, "linha_final")
        if self.linha_final is not None and self.linha_inicial is None:
            raise ErroModelo("linha_final exige linha_inicial")
        if self.arquivo is None and (
            self.linha_inicial is not None or self.linha_final is not None
        ):
            raise ErroModelo("linhas exigem arquivo")
        if (
            self.linha_inicial is not None
            and self.linha_final is not None
            and self.linha_final < self.linha_inicial
        ):
            raise ErroModelo("linha_final não pode anteceder linha_inicial")

        for campo in (
            "regra",
            "severidade_original",
            "confianca_original",
            "descricao",
            "evidencia",
            "recomendacao",
            "texto_original",
        ):
            _validar_texto_opcional(getattr(self, campo), campo)
        cwe_original = _validar_cwe_original(self.cwe_original)
        object.__setattr__(self, "cwe_original", cwe_original)
        if self.cwe is not None:
            if not isinstance(self.cwe, str) or not _CWE_RE.fullmatch(self.cwe):
                raise ErroModelo("cwe deve usar o formato CWE-N ou ser null")
        _validar_enum_opcional(
            self.severidade,
            SEVERIDADES_NORMALIZADAS,
            "severidade",
        )
        _validar_enum_opcional(
            self.confianca,
            CONFIANCAS_NORMALIZADAS,
            "confianca",
        )
        _validar_sha256(self.saida_bruta_sha256, "saida_bruta_sha256")

    @classmethod
    def from_dict(cls, documento: Mapping[str, Any]) -> "Achado":
        objeto = _exigir_objeto(documento, "achado")
        _exigir_chaves(objeto, cls.CAMPOS, "achado")
        return cls(**{campo: objeto[campo] for campo in cls.CAMPOS})

    @classmethod
    def from_json(cls, documento: str) -> "Achado":
        return cls.from_dict(_carregar_json_estrito(documento, "achado"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "condicao": self.condicao,
            "ferramenta": self.ferramenta,
            "alvo": self.alvo,
            "repeticao": self.repeticao,
            "execucao_id": self.execucao_id,
            "arquivo": self.arquivo,
            "linha_inicial": self.linha_inicial,
            "linha_final": self.linha_final,
            "regra": self.regra,
            "cwe_original": (
                list(self.cwe_original)
                if isinstance(self.cwe_original, tuple)
                else self.cwe_original
            ),
            "cwe": self.cwe,
            "severidade_original": self.severidade_original,
            "severidade": self.severidade,
            "confianca_original": self.confianca_original,
            "confianca": self.confianca,
            "descricao": self.descricao,
            "evidencia": self.evidencia,
            "recomendacao": self.recomendacao,
            "texto_original": self.texto_original,
            "saida_bruta_sha256": self.saida_bruta_sha256,
        }

    def to_json(self) -> str:
        return _serializar_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class ManifestoExecucao:
    """Snapshot validado de uma tarefa ou tentativa de execução."""

    schema_version: str
    execucao_id: str
    condicao: str
    ferramenta: str
    bloco: str | None
    alvo: str
    repeticao: int
    entrada_commit: str | None
    entrada_sha256: str
    comando: tuple[str, ...]
    imagem: str
    imagem_digest: str
    finalidade: str
    inicio_utc: str | None
    termino_utc: str | None
    duracao_monotonica_segundos: float | None
    codigo_saida: int | None
    estado: str
    falha_tipo: str | None
    falha_mensagem: str | None
    tentativa: int
    artefatos_sha256: tuple[tuple[str, str], ...]

    CAMPOS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "execucao_id",
            "condicao",
            "ferramenta",
            "bloco",
            "alvo",
            "repeticao",
            "entrada_commit",
            "entrada_sha256",
            "comando",
            "imagem",
            "imagem_digest",
            "finalidade",
            "inicio_utc",
            "termino_utc",
            "duracao_monotonica_segundos",
            "codigo_saida",
            "estado",
            "falha_tipo",
            "falha_mensagem",
            "tentativa",
            "artefatos_sha256",
        }
    )

    def __post_init__(self) -> None:
        _validar_versao(self.schema_version)
        _validar_identificador(self.execucao_id, "execucao_id")
        _validar_condicao(self.condicao)
        _validar_ferramenta_e_repeticao(
            self.condicao, self.ferramenta, self.repeticao
        )
        _validar_texto_opcional(self.bloco, "bloco")
        if self.condicao in {"C1", "C2"} and self.bloco is not None:
            raise ErroModelo("bloco deve ser null em C1/C2")
        if self.condicao not in {"C1", "C2"} and self.bloco not in {
            "principal",
            "complementar",
        }:
            raise ErroModelo("bloco deve ser principal ou complementar em C3-C6")
        _validar_identificador(self.alvo, "alvo")
        if self.entrada_commit is not None:
            if not isinstance(self.entrada_commit, str) or not _COMMIT_RE.fullmatch(
                self.entrada_commit
            ):
                raise ErroModelo("entrada_commit deve ser commit Git completo ou null")
        _validar_sha256(self.entrada_sha256, "entrada_sha256")

        comando = _validar_comando(self.comando)
        object.__setattr__(self, "comando", comando)
        _validar_texto(self.imagem, "imagem")
        if not isinstance(self.imagem_digest, str) or not _DIGEST_RE.fullmatch(
            self.imagem_digest
        ):
            raise ErroModelo("imagem_digest deve ser digest SHA-256 completo")
        if not isinstance(self.finalidade, str) or self.finalidade not in FINALIDADES:
            raise ErroModelo(f"finalidade deve ser uma de {sorted(FINALIDADES)}")

        inicio = _validar_timestamp_utc_opcional(self.inicio_utc, "inicio_utc")
        termino = _validar_timestamp_utc_opcional(self.termino_utc, "termino_utc")
        if termino is not None and inicio is None:
            raise ErroModelo("termino_utc exige inicio_utc")
        if inicio is not None and termino is not None and termino < inicio:
            raise ErroModelo("termino_utc não pode anteceder inicio_utc")

        _validar_duracao_opcional(self.duracao_monotonica_segundos)
        _validar_inteiro_opcional(self.codigo_saida, "codigo_saida")
        if not isinstance(self.estado, str) or self.estado not in ESTADOS_EXECUCAO:
            raise ErroModelo(
                f"estado deve ser um de {sorted(ESTADOS_EXECUCAO)}"
            )
        if self.falha_tipo is not None and (
            not isinstance(self.falha_tipo, str) or self.falha_tipo not in TIPOS_FALHA
        ):
            raise ErroModelo(f"falha_tipo deve ser um de {sorted(TIPOS_FALHA)} ou null")
        _validar_texto_opcional(self.falha_mensagem, "falha_mensagem")
        _validar_inteiro_positivo(self.tentativa, "tentativa")
        artefatos = _validar_artefatos(self.artefatos_sha256)
        object.__setattr__(self, "artefatos_sha256", artefatos)
        self._validar_estado()

    def _validar_estado(self) -> None:
        if self.estado == "pendente":
            operacionais = (
                self.inicio_utc,
                self.termino_utc,
                self.duracao_monotonica_segundos,
                self.codigo_saida,
            )
            if (
                any(valor is not None for valor in operacionais)
                or self.artefatos_sha256
                or self.falha_tipo is not None
                or self.falha_mensagem is not None
            ):
                raise ErroModelo("estado pendente não pode conter resultado de execução")
            return

        if self.estado == "em_execucao":
            if (
                self.inicio_utc is None
                or self.termino_utc is not None
                or self.duracao_monotonica_segundos is not None
                or self.codigo_saida is not None
                or self.falha_tipo is not None
                or self.falha_mensagem is not None
            ):
                raise ErroModelo(
                    "estado em_execucao exige início e proíbe término, duração e código"
                )
            return

        if (
            self.inicio_utc is None
            or self.termino_utc is None
            or self.duracao_monotonica_segundos is None
        ):
            raise ErroModelo("estado terminal exige início, término e duração")
        if self.estado == "concluida" and self.codigo_saida is None:
            raise ErroModelo("estado concluida exige codigo_saida")
        if self.estado == "concluida":
            if not self.artefatos_sha256:
                raise ErroModelo("estado concluida exige ao menos um artefato preservado")
            if self.falha_tipo is not None or self.falha_mensagem is not None:
                raise ErroModelo("falha_tipo e falha_mensagem devem ser null em concluida")
        if self.estado == "falha" and self.falha_tipo is None:
            raise ErroModelo("estado falha exige falha_tipo")

    @classmethod
    def from_dict(cls, documento: Mapping[str, Any]) -> "ManifestoExecucao":
        objeto = _exigir_objeto(documento, "manifesto de execução")
        _exigir_chaves(objeto, cls.CAMPOS, "manifesto de execução")
        return cls(**{campo: objeto[campo] for campo in cls.CAMPOS})

    @classmethod
    def from_json(cls, documento: str) -> "ManifestoExecucao":
        return cls.from_dict(
            _carregar_json_estrito(documento, "manifesto de execução")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execucao_id": self.execucao_id,
            "condicao": self.condicao,
            "ferramenta": self.ferramenta,
            "bloco": self.bloco,
            "alvo": self.alvo,
            "repeticao": self.repeticao,
            "entrada_commit": self.entrada_commit,
            "entrada_sha256": self.entrada_sha256,
            "comando": list(self.comando),
            "imagem": self.imagem,
            "imagem_digest": self.imagem_digest,
            "finalidade": self.finalidade,
            "inicio_utc": self.inicio_utc,
            "termino_utc": self.termino_utc,
            "duracao_monotonica_segundos": self.duracao_monotonica_segundos,
            "codigo_saida": self.codigo_saida,
            "estado": self.estado,
            "falha_tipo": self.falha_tipo,
            "falha_mensagem": self.falha_mensagem,
            "tentativa": self.tentativa,
            "artefatos_sha256": dict(self.artefatos_sha256),
        }

    def to_json(self) -> str:
        return _serializar_json(self.to_dict())


def _validar_versao(valor: Any) -> None:
    if valor != SCHEMA_VERSION:
        raise ErroModelo(f"schema_version deve ser {SCHEMA_VERSION}")


def _validar_condicao(valor: Any) -> None:
    if not isinstance(valor, str) or valor not in CONDICOES:
        raise ErroModelo(f"condicao deve ser uma de {sorted(CONDICOES)}")


def _validar_ferramenta_e_repeticao(
    condicao: str, ferramenta: Any, repeticao: Any
) -> None:
    esperada = FERRAMENTA_POR_CONDICAO[condicao]
    if ferramenta != esperada:
        raise ErroModelo(
            f"ferramenta de {condicao} deve ser {esperada}"
        )
    _validar_inteiro_positivo(repeticao, "repeticao")
    if condicao in {"C1", "C2"} and repeticao != 1:
        raise ErroModelo("repeticao de C1/C2 deve ser 1")
    if condicao not in {"C1", "C2"} and repeticao > 3:
        raise ErroModelo("repeticao de C3-C6 deve estar entre 1 e 3")


def _validar_identificador(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _IDENTIFICADOR_RE.fullmatch(valor):
        raise ErroModelo(f"{campo} deve ser identificador opaco e seguro")


def _validar_texto(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not valor.strip() or "\x00" in valor:
        raise ErroModelo(f"{campo} deve ser texto não vazio e sem NUL")


def _validar_texto_opcional(valor: Any, campo: str) -> None:
    if valor is not None and (not isinstance(valor, str) or "\x00" in valor):
        raise ErroModelo(f"{campo} deve ser string ou null")


def _validar_enum_opcional(
    valor: Any, permitidos: frozenset[str], campo: str
) -> None:
    if valor is not None and (
        not isinstance(valor, str) or valor not in permitidos
    ):
        raise ErroModelo(f"{campo} deve ser um de {sorted(permitidos)} ou null")


def _validar_cwe_original(
    valor: Any,
) -> str | tuple[str, ...] | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        if not valor or "\x00" in valor:
            raise ErroModelo("cwe_original deve ser texto, lista de textos ou null")
        return valor
    if not isinstance(valor, (list, tuple)) or not valor:
        raise ErroModelo("cwe_original deve ser texto, lista não vazia ou null")
    itens = tuple(valor)
    if any(
        not isinstance(item, str) or not item or "\x00" in item for item in itens
    ):
        raise ErroModelo("cwe_original contém item inválido")
    return itens


def _validar_inteiro_positivo(valor: Any, campo: str) -> None:
    if type(valor) is not int or valor <= 0:
        raise ErroModelo(f"{campo} deve ser inteiro positivo")


def _validar_inteiro_opcional(valor: Any, campo: str) -> None:
    if valor is not None and type(valor) is not int:
        raise ErroModelo(f"{campo} deve ser inteiro ou null")


def _validar_linha_opcional(valor: Any, campo: str) -> None:
    if valor is not None:
        _validar_inteiro_positivo(valor, campo)


def _validar_caminho_relativo_opcional(valor: Any, campo: str) -> None:
    if valor is None:
        return
    _validar_caminho_relativo(valor, campo)


def _validar_caminho_relativo(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not valor:
        raise ErroModelo(f"{campo} deve ser caminho relativo POSIX não vazio")
    if (
        valor.startswith("/")
        or re.match(r"^[A-Za-z]:", valor)
        or "\\" in valor
        or "\x00" in valor
        or any(ord(caractere) < 32 for caractere in valor)
    ):
        raise ErroModelo(f"{campo} deve ser caminho relativo POSIX")
    partes = valor.split("/")
    if any(parte in {"", ".", ".."} for parte in partes):
        raise ErroModelo(f"{campo} contém segmento inseguro")


def _validar_sha256(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _SHA256_RE.fullmatch(valor):
        raise ErroModelo(f"{campo} deve ser SHA-256 completo em minúsculas")


def _validar_comando(valor: Any) -> tuple[str, ...]:
    if not isinstance(valor, (list, tuple)):
        raise ErroModelo("comando deve ser vetor de argumentos")
    itens = tuple(valor)
    if not itens:
        raise ErroModelo("comando não pode ser vazio")
    if any(
        not isinstance(item, str) or not item or "\x00" in item for item in itens
    ):
        raise ErroModelo("comando contém argumento inválido")
    return itens


def _validar_timestamp_utc_opcional(
    valor: Any, campo: str
) -> datetime | None:
    if valor is None:
        return None
    if not isinstance(valor, str) or not _UTC_RE.fullmatch(valor):
        raise ErroModelo(f"{campo} deve ser timestamp UTC canônico terminado em Z")
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ErroModelo(f"{campo} deve ser timestamp UTC válido") from exc


def _validar_duracao_opcional(valor: Any) -> None:
    if valor is None:
        return
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
        or valor < 0
    ):
        raise ErroModelo(
            "duracao_monotonica_segundos deve ser número finito não negativo ou null"
        )


def _validar_artefatos(valor: Any) -> tuple[tuple[str, str], ...]:
    if isinstance(valor, Mapping):
        itens = list(valor.items())
    else:
        try:
            itens = list(valor)
        except (TypeError, ValueError) as exc:
            raise ErroModelo("artefatos_sha256 deve ser objeto") from exc

    normalizados: dict[str, str] = {}
    for item in itens:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ErroModelo("artefatos_sha256 deve ser objeto")
        caminho, sha256 = item
        _validar_caminho_relativo(caminho, "caminho de artefato")
        _validar_sha256(sha256, f"artefatos_sha256[{caminho!r}]")
        if caminho in normalizados:
            raise ErroModelo(f"artefato duplicado: {caminho}")
        normalizados[caminho] = sha256
    return tuple(sorted(normalizados.items()))


def _exigir_objeto(valor: Any, campo: str) -> Mapping[str, Any]:
    if not isinstance(valor, Mapping):
        raise ErroModelo(f"{campo} deve ser objeto JSON")
    return valor


def _exigir_chaves(
    objeto: Mapping[str, Any], esperadas: frozenset[str], campo: str
) -> None:
    atuais = set(objeto)
    if atuais != esperadas:
        ausentes = sorted(esperadas - atuais)
        desconhecidas = sorted(atuais - esperadas)
        raise ErroModelo(
            f"campos inválidos em {campo}; "
            f"ausentes={ausentes}, desconhecidos={desconhecidas}"
        )


def _carregar_json_estrito(documento: str, campo: str) -> Mapping[str, Any]:
    if not isinstance(documento, str):
        raise ErroModelo(f"{campo} deve ser texto JSON")
    try:
        valor = json.loads(
            documento,
            object_pairs_hook=_objeto_sem_chaves_duplicadas,
            parse_constant=_constante_json_invalida,
        )
    except json.JSONDecodeError as exc:
        raise ErroModelo(f"{campo} não contém JSON válido: {exc}") from exc
    return _exigir_objeto(valor, campo)


def _objeto_sem_chaves_duplicadas(
    pares: list[tuple[str, Any]],
) -> dict[str, Any]:
    objeto: dict[str, Any] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroModelo(f"chave JSON duplicada: {chave}")
        objeto[chave] = valor
    return objeto


def _constante_json_invalida(valor: str) -> None:
    raise ErroModelo(f"constante JSON não finita é proibida: {valor}")


def _serializar_json(documento: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            documento,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ErroModelo(f"não foi possível serializar o modelo: {exc}") from exc
