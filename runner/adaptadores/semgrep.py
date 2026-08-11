"""Adaptador puro para a saída JSON do Semgrep Community Edition 1.172.0.

O módulo não lê arquivos, não executa processos e não consulta rede, registry ou
oracle. O chamador continua responsável por persistir os bytes brutos antes de
invocar :func:`normalizar`; o SHA-256 explícito liga cada achado a esse bruto.
"""

from __future__ import annotations

import copy
import re
import warnings
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from runner.adaptadores.comum import (
    ErroAdaptador,
    Proveniencia,
    carregar_json_estrito,
    normalizar_caminho_entrada,
    texto_json_canonico,
    verificar_hash_bruto,
)
from runner.modelos import Achado, ErroModelo, SCHEMA_VERSION


VERSAO_SEMGREP = "1.172.0"

MAPA_SEVERIDADE: Mapping[str, str] = MappingProxyType(
    {"INFO": "baixa", "WARNING": "media", "ERROR": "alta"}
)
_CWE_RE = re.compile(r"\bCWE-([1-9][0-9]*)\b", re.IGNORECASE)
_AUSENTE = object()


class ResultadoParcialSemgrepWarning(UserWarning):
    """Sinaliza ``errors`` do Semgrep sem descartar achados válidos.

    ``erros`` é uma cópia da lista estruturada presente no bruto. O hash permite
    ao executor localizar o documento original, que não é reescrito pelo
    adaptador.
    """

    def __init__(self, erros: list[Any], saida_bruta_sha256: str) -> None:
        self.erros = tuple(copy.deepcopy(erros))
        self.saida_bruta_sha256 = saida_bruta_sha256
        super().__init__(
            "Semgrep retornou "
            f"{len(self.erros)} erro(s) parcial(is); bruto "
            f"SHA-256={saida_bruta_sha256}"
        )


def normalizar(
    documento: bytes | str,
    proveniencia: Proveniencia,
) -> list[Achado]:
    """Converte um documento Semgrep 1.172.0 em achados C2.

    O JSON é analisado estritamente pelo módulo comum. Campos opcionais ausentes
    se tornam ``None`` e nenhuma informação é obtida fora do próprio documento.
    Uma lista ``errors`` não vazia emite :class:`ResultadoParcialSemgrepWarning`
    depois que todos os achados válidos forem construídos.
    """

    _validar_proveniencia(proveniencia)
    verificar_hash_bruto(documento, proveniencia.saida_bruta_sha256)
    raiz = carregar_json_estrito(documento, contexto="saída Semgrep")
    if not isinstance(raiz, Mapping):
        raise ErroAdaptador("saída Semgrep deve ser objeto JSON")
    if raiz.get("version", _AUSENTE) != VERSAO_SEMGREP:
        raise ErroAdaptador(
            f"saída Semgrep deve declarar version={VERSAO_SEMGREP}"
        )

    resultados = raiz.get("results", _AUSENTE)
    erros = raiz.get("errors", _AUSENTE)
    if not isinstance(resultados, list):
        raise ErroAdaptador("saída Semgrep exige results como lista")
    if not isinstance(erros, list):
        raise ErroAdaptador("saída Semgrep exige errors como lista")

    achados = [
        _normalizar_resultado(resultado, indice, proveniencia)
        for indice, resultado in enumerate(resultados)
    ]
    if erros:
        warnings.warn(
            ResultadoParcialSemgrepWarning(
                erros,
                proveniencia.saida_bruta_sha256,
            ),
            stacklevel=2,
        )
    return achados


def _normalizar_resultado(
    resultado: Any,
    indice: int,
    proveniencia: Proveniencia,
) -> Achado:
    if not isinstance(resultado, Mapping):
        raise ErroAdaptador(
            f"results[{indice}] da saída Semgrep deve ser objeto"
        )

    extra = _objeto_opcional(resultado.get("extra", _AUSENTE), f"results[{indice}].extra")
    metadata = _objeto_opcional(
        extra.get("metadata", _AUSENTE),
        f"results[{indice}].extra.metadata",
    )
    cwe_original, cwe = _normalizar_cwe(
        metadata.get("cwe", _AUSENTE),
        f"results[{indice}].extra.metadata.cwe",
    )
    severidade_original = _texto_opcional(
        extra.get("severity", _AUSENTE),
        f"results[{indice}].extra.severity",
    )

    try:
        return Achado(
            schema_version=SCHEMA_VERSION,
            condicao="C2",
            ferramenta="semgrep",
            alvo=proveniencia.alvo,
            repeticao=proveniencia.repeticao,
            execucao_id=proveniencia.execucao_id,
            arquivo=normalizar_caminho_entrada(
                _nulo_se_ausente(resultado.get("path", _AUSENTE))
            ),
            linha_inicial=_linha(
                resultado.get("start", _AUSENTE),
                f"results[{indice}].start",
            ),
            linha_final=_linha(
                resultado.get("end", _AUSENTE),
                f"results[{indice}].end",
            ),
            regra=_texto_opcional(
                resultado.get("check_id", _AUSENTE),
                f"results[{indice}].check_id",
            ),
            cwe_original=cwe_original,
            cwe=cwe,
            severidade_original=severidade_original,
            severidade=(
                MAPA_SEVERIDADE.get(severidade_original.upper())
                if severidade_original is not None
                else None
            ),
            confianca_original=_texto_opcional(
                metadata.get("confidence", _AUSENTE),
                f"results[{indice}].extra.metadata.confidence",
            ),
            confianca=None,
            descricao=_texto_opcional(
                extra.get("message", _AUSENTE),
                f"results[{indice}].extra.message",
            ),
            evidencia=_texto_opcional(
                extra.get("lines", _AUSENTE),
                f"results[{indice}].extra.lines",
            ),
            recomendacao=_texto_opcional(
                extra.get("fix", _AUSENTE),
                f"results[{indice}].extra.fix",
            ),
            texto_original=texto_json_canonico(resultado),
            saida_bruta_sha256=proveniencia.saida_bruta_sha256,
        )
    except ErroModelo as exc:
        raise ErroAdaptador(
            f"results[{indice}] incompatível com Achado v1: {exc}"
        ) from exc


def _validar_proveniencia(proveniencia: Any) -> None:
    if not isinstance(proveniencia, Proveniencia):
        raise ErroAdaptador("proveniência Semgrep deve ser Proveniencia")
    proveniencia.validar_para("C2")


def _objeto_opcional(valor: Any, campo: str) -> Mapping[str, Any]:
    if valor is _AUSENTE or valor is None:
        return {}
    if not isinstance(valor, Mapping):
        raise ErroAdaptador(f"{campo} deve ser objeto ou null")
    return valor


def _texto_opcional(valor: Any, campo: str) -> str | None:
    if valor is _AUSENTE or valor is None:
        return None
    if not isinstance(valor, str) or "\x00" in valor:
        raise ErroAdaptador(f"{campo} deve ser string ou null")
    return valor


def _linha(valor: Any, campo: str) -> int | None:
    if valor is _AUSENTE or valor is None:
        return None
    if not isinstance(valor, Mapping):
        raise ErroAdaptador(f"{campo} deve ser objeto ou null")
    linha = valor.get("line", _AUSENTE)
    if linha is _AUSENTE or linha is None:
        return None
    if type(linha) is not int or linha <= 0:
        raise ErroAdaptador(f"{campo}.line deve ser inteiro positivo ou null")
    return linha


def _nulo_se_ausente(valor: Any) -> Any:
    return None if valor is _AUSENTE else valor


def _normalizar_cwe(
    valor: Any,
    campo: str,
) -> tuple[str | list[str] | None, str | None]:
    if valor is _AUSENTE or valor is None:
        return None, None
    if isinstance(valor, str):
        if not valor or "\x00" in valor:
            raise ErroAdaptador(f"{campo} contém CWE inválida")
        original: str | list[str] = valor
        candidatos = (valor,)
    elif isinstance(valor, list):
        if not valor:
            return None, None
        if any(
            not isinstance(item, str) or not item or "\x00" in item
            for item in valor
        ):
            raise ErroAdaptador(f"{campo} deve conter somente strings não vazias")
        original = list(valor)
        candidatos = tuple(valor)
    else:
        raise ErroAdaptador(f"{campo} deve ser string, lista de strings ou null")

    for candidato in candidatos:
        correspondencia = _CWE_RE.search(candidato)
        if correspondencia is not None:
            return original, f"CWE-{correspondencia.group(1)}"
    return original, None


__all__ = [
    "MAPA_SEVERIDADE",
    "ResultadoParcialSemgrepWarning",
    "VERSAO_SEMGREP",
    "normalizar",
]
