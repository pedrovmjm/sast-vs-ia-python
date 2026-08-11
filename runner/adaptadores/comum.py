"""Primitivas puras e reutilizáveis pelos adaptadores de saída JSON.

Este módulo não acessa disco, rede ou processos. O hash é calculado sobre os
bytes recebidos; quando a entrada é texto, sua representação UTF-8 é o bruto
de referência.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any


class ErroAdaptador(ValueError):
    """Indica entrada bruta ou proveniência incompatível com o contrato."""


_IDENTIFICADOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONDICAO_RE = re.compile(r"^C[1-6]$")
_UNIDADE_WINDOWS_RE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True, slots=True)
class Proveniencia:
    """Identidade mínima da execução que produziu uma saída bruta."""

    alvo: str
    repeticao: int
    execucao_id: str
    saida_bruta_sha256: str

    def __post_init__(self) -> None:
        _validar_identificador(self.alvo, "alvo")
        if type(self.repeticao) is not int or self.repeticao <= 0:
            raise ErroAdaptador("repeticao deve ser inteiro positivo")
        _validar_identificador(self.execucao_id, "execucao_id")
        if (
            not isinstance(self.saida_bruta_sha256, str)
            or not _SHA256_RE.fullmatch(self.saida_bruta_sha256)
        ):
            raise ErroAdaptador(
                "saida_bruta_sha256 deve ser SHA-256 completo em minúsculas"
            )

    def validar_para(self, condicao: str) -> None:
        """Confirma que o ID liga condição, alvo e repetição declarados."""

        if not isinstance(condicao, str) or not _CONDICAO_RE.fullmatch(condicao):
            raise ErroAdaptador("condicao deve estar entre C1 e C6")
        esperado = f"{condicao}-{self.alvo}-R{self.repeticao:02d}"
        if self.execucao_id != esperado:
            raise ErroAdaptador(
                f"execucao_id de {condicao} deve ser exatamente {esperado}"
            )


def verificar_hash_bruto(documento: bytes | str, esperado: str) -> str:
    """Recalcula e valida o SHA-256 dos bytes efetivamente recebidos."""

    if not isinstance(esperado, str) or not _SHA256_RE.fullmatch(esperado):
        raise ErroAdaptador("hash esperado deve ser SHA-256 completo em minúsculas")
    bruto = _documento_em_bytes(documento)
    calculado = hashlib.sha256(bruto).hexdigest()
    if calculado != esperado:
        raise ErroAdaptador(
            "SHA-256 do bruto diverge da proveniência: "
            f"esperado={esperado}, calculado={calculado}"
        )
    return calculado


def carregar_json_estrito(documento: bytes | str, *, contexto: str) -> Any:
    """Decodifica JSON UTF-8 sem chaves duplicadas nem números não finitos."""

    texto = _documento_em_texto(documento)
    try:
        return json.loads(
            texto,
            object_pairs_hook=_objeto_sem_chaves_duplicadas,
            parse_constant=_constante_nao_finita,
            parse_float=_numero_finito,
        )
    except ErroAdaptador:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ErroAdaptador(f"{contexto} não contém JSON estrito válido: {exc}") from exc


def texto_json_canonico(valor: Any) -> str:
    """Serializa um valor JSON de forma determinística e sem NaN/Infinity."""

    try:
        return json.dumps(
            valor,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise ErroAdaptador(f"valor não pode ser serializado como JSON canônico: {exc}") from exc


def normalizar_caminho_entrada(valor: Any) -> str | None:
    """Converte caminho de ferramenta em caminho POSIX relativo à entrada."""

    if valor is None:
        return None
    if not isinstance(valor, str) or not valor:
        raise ErroAdaptador("arquivo deve ser caminho não vazio ou null")

    caminho = valor.replace("\\", "/")
    if caminho.startswith("/entrada/"):
        caminho = caminho[len("/entrada/") :]
    else:
        while caminho.startswith("./"):
            caminho = caminho[2:]

    if (
        not caminho
        or caminho.startswith("/")
        or _UNIDADE_WINDOWS_RE.match(caminho)
        or "\x00" in caminho
        or any(ord(caractere) < 32 for caractere in caminho)
    ):
        raise ErroAdaptador(
            "arquivo deve ficar sob /entrada e resultar em caminho POSIX relativo"
        )
    if any(parte in {"", ".", ".."} for parte in caminho.split("/")):
        raise ErroAdaptador("arquivo contém segmento vazio, atual ou ascendente")
    return caminho


def _validar_identificador(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _IDENTIFICADOR_RE.fullmatch(valor):
        raise ErroAdaptador(f"{campo} deve ser identificador opaco e seguro")


def _documento_em_bytes(documento: bytes | str) -> bytes:
    if isinstance(documento, bytes):
        return documento
    if isinstance(documento, str):
        try:
            return documento.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ErroAdaptador("texto bruto não pode ser codificado em UTF-8") from exc
    raise ErroAdaptador("documento deve ser bytes ou texto JSON")


def _documento_em_texto(documento: bytes | str) -> str:
    if isinstance(documento, str):
        try:
            documento.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ErroAdaptador("texto bruto não representa UTF-8 válido") from exc
        return documento
    if isinstance(documento, bytes):
        try:
            return documento.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ErroAdaptador("saída bruta não contém UTF-8 válido") from exc
    raise ErroAdaptador("documento deve ser bytes ou texto JSON")


def _objeto_sem_chaves_duplicadas(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    objeto: dict[str, Any] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroAdaptador(f"chave JSON duplicada: {chave}")
        objeto[chave] = valor
    return objeto


def _constante_nao_finita(valor: str) -> None:
    raise ErroAdaptador(f"constante JSON não finita é proibida: {valor}")


def _numero_finito(valor: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ErroAdaptador(f"número JSON não finito é proibido: {valor}")
    return numero
