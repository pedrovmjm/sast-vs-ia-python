"""Adaptador puro para a saída JSON do Bandit 1.9.4.

Os valores nativos são preservados separadamente. As únicas classificações
normalizadas são os mapas fechados documentados abaixo e a forma sintática
``issue_cwe.id = N`` → ``CWE-N``; nenhum dado é inferido de regra, mensagem,
código, rede, oracle ou sistema de arquivos.
"""

from __future__ import annotations

import copy
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


# Contrato congelado para os níveis emitidos pelo Bandit 1.9.4. Qualquer valor
# desconhecido continua em *_original e produz normalização nula.
MAPA_SEVERIDADE: Mapping[str, str] = MappingProxyType(
    {"LOW": "baixa", "MEDIUM": "media", "HIGH": "alta"}
)
MAPA_CONFIANCA: Mapping[str, str] = MappingProxyType(
    {"LOW": "baixa", "MEDIUM": "media", "HIGH": "alta"}
)

_AUSENTE = object()


class ResultadoParcialBanditWarning(UserWarning):
    """Sinaliza ``errors`` não vazio sem descartar achados válidos."""

    def __init__(self, erros: list[Any], saida_bruta_sha256: str) -> None:
        self.erros = tuple(copy.deepcopy(erros))
        self.saida_bruta_sha256 = saida_bruta_sha256
        super().__init__(
            "Bandit retornou "
            f"{len(self.erros)} erro(s) parcial(is); bruto "
            f"SHA-256={saida_bruta_sha256}"
        )


def normalizar(
    documento: bytes | str,
    proveniencia: Proveniencia,
) -> list[Achado]:
    """Converte resultados Bandit em achados C1 ligados ao bruto recebido."""

    _validar_proveniencia(proveniencia)
    verificar_hash_bruto(documento, proveniencia.saida_bruta_sha256)
    raiz = carregar_json_estrito(documento, contexto="saída Bandit")
    if not isinstance(raiz, Mapping):
        raise ErroAdaptador("saída Bandit deve ser objeto JSON")

    resultados = raiz.get("results", _AUSENTE)
    if not isinstance(resultados, list):
        raise ErroAdaptador("saída Bandit exige results como lista")
    erros = raiz.get("errors", _AUSENTE)
    if not isinstance(erros, list):
        raise ErroAdaptador("saída Bandit exige errors como lista")

    achados = [
        _normalizar_resultado(resultado, indice, proveniencia)
        for indice, resultado in enumerate(resultados)
    ]
    if erros:
        warnings.warn(
            ResultadoParcialBanditWarning(
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
    contexto = f"results[{indice}]"
    if not isinstance(resultado, Mapping):
        raise ErroAdaptador(f"{contexto} da saída Bandit deve ser objeto")

    linha_inicial, linha_final = _normalizar_linhas(resultado, contexto)
    cwe_original, cwe = _normalizar_cwe(
        resultado.get("issue_cwe", _AUSENTE),
        f"{contexto}.issue_cwe",
    )
    severidade_original = _texto_opcional(
        resultado.get("issue_severity", _AUSENTE),
        f"{contexto}.issue_severity",
    )
    confianca_original = _texto_opcional(
        resultado.get("issue_confidence", _AUSENTE),
        f"{contexto}.issue_confidence",
    )

    try:
        return Achado(
            schema_version=SCHEMA_VERSION,
            condicao="C1",
            ferramenta="bandit",
            alvo=proveniencia.alvo,
            repeticao=proveniencia.repeticao,
            execucao_id=proveniencia.execucao_id,
            arquivo=normalizar_caminho_entrada(
                _valor_opcional(resultado, "filename")
            ),
            linha_inicial=linha_inicial,
            linha_final=linha_final,
            regra=_texto_opcional(
                resultado.get("test_id", _AUSENTE),
                f"{contexto}.test_id",
            ),
            cwe_original=cwe_original,
            cwe=cwe,
            severidade_original=severidade_original,
            severidade=MAPA_SEVERIDADE.get(severidade_original),
            confianca_original=confianca_original,
            confianca=MAPA_CONFIANCA.get(confianca_original),
            descricao=_texto_opcional(
                resultado.get("issue_text", _AUSENTE),
                f"{contexto}.issue_text",
            ),
            evidencia=_texto_opcional(
                resultado.get("code", _AUSENTE),
                f"{contexto}.code",
            ),
            recomendacao=None,
            texto_original=texto_json_canonico(resultado),
            saida_bruta_sha256=proveniencia.saida_bruta_sha256,
        )
    except ErroModelo as exc:
        raise ErroAdaptador(
            f"{contexto} incompatível com Achado v1: {exc}"
        ) from exc


def _validar_proveniencia(proveniencia: Any) -> None:
    if not isinstance(proveniencia, Proveniencia):
        raise ErroAdaptador("proveniência Bandit deve ser Proveniencia")
    if proveniencia.repeticao != 1:
        raise ErroAdaptador("repeticao de C1/Bandit deve ser 1")
    proveniencia.validar_para("C1")


def _valor_opcional(objeto: Mapping[str, Any], chave: str) -> Any:
    valor = objeto.get(chave, _AUSENTE)
    return None if valor is _AUSENTE else valor


def _texto_opcional(valor: Any, campo: str) -> str | None:
    if valor is _AUSENTE or valor is None:
        return None
    if not isinstance(valor, str) or "\x00" in valor:
        raise ErroAdaptador(f"{campo} deve ser string ou null")
    return valor


def _inteiro_positivo_opcional(valor: Any, campo: str) -> int | None:
    if valor is _AUSENTE or valor is None:
        return None
    if type(valor) is not int or valor <= 0:
        raise ErroAdaptador(f"{campo} deve ser inteiro positivo ou null")
    return valor


def _normalizar_linhas(
    resultado: Mapping[str, Any],
    contexto: str,
) -> tuple[int | None, int | None]:
    linha = _inteiro_positivo_opcional(
        resultado.get("line_number", _AUSENTE),
        f"{contexto}.line_number",
    )
    intervalo = resultado.get("line_range", _AUSENTE)
    if intervalo is _AUSENTE or intervalo is None:
        return linha, None
    if not isinstance(intervalo, list):
        raise ErroAdaptador(f"{contexto}.line_range deve ser lista ou null")
    if not intervalo:
        return linha, None
    if any(type(item) is not int or item <= 0 for item in intervalo):
        raise ErroAdaptador(
            f"{contexto}.line_range deve conter somente inteiros positivos"
        )
    if any(atual > seguinte for atual, seguinte in zip(intervalo, intervalo[1:])):
        raise ErroAdaptador(f"{contexto}.line_range deve estar em ordem crescente")
    if linha is not None and linha not in intervalo:
        raise ErroAdaptador(
            f"{contexto}.line_range deve começar em line_number"
        )
    return intervalo[0], intervalo[-1]


def _normalizar_cwe(
    valor: Any,
    campo: str,
) -> tuple[str | None, str | None]:
    if valor is _AUSENTE or valor is None:
        return None, None
    if not isinstance(valor, Mapping):
        raise ErroAdaptador(f"{campo} deve ser objeto ou null")
    identificador = valor.get("id", _AUSENTE)
    if identificador is _AUSENTE or identificador is None:
        return None, None
    if type(identificador) is not int or identificador <= 0:
        raise ErroAdaptador(f"{campo}.id deve ser inteiro positivo ou null")
    original = str(identificador)
    return original, f"CWE-{original}"


__all__ = [
    "MAPA_CONFIANCA",
    "MAPA_SEVERIDADE",
    "ResultadoParcialBanditWarning",
    "normalizar",
]
