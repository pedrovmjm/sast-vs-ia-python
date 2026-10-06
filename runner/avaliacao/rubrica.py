"""Análise da rubrica qualitativa e da concordância entre avaliadores."""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .estatistica import kappa_ponderado_quadratico, resumo_distribuicao


CAMPOS_ORDINAIS = (
    "correcao_tecnica_1a5",
    "localizacao_1a5",
    "acionabilidade_1a5",
)
CAMPOS_BINARIOS = (
    "clareza_problema_0ou1",
    "clareza_risco_0ou1",
    "clareza_contexto_0ou1",
    "clareza_concretude_0ou1",
    "clareza_concisao_0ou1",
)
VOGAIS = set("aeiouáàâãéêíóôõúü")


def carregar_csv(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def _inteiro(linha: dict[str, str], campo: str, minimo: int, maximo: int) -> int:
    try:
        valor = int(linha[campo])
    except (KeyError, TypeError, ValueError) as erro:
        raise ValueError(f"{linha.get('relatorio_id', '?')}: {campo} não preenchido") from erro
    if not minimo <= valor <= maximo:
        raise ValueError(f"{linha.get('relatorio_id', '?')}: {campo} fora de {minimo}..{maximo}")
    return valor


def _indexar(linhas: list[dict[str, str]], nome: str) -> dict[str, dict[str, str]]:
    indice: dict[str, dict[str, str]] = {}
    for linha in linhas:
        identificador = linha.get("relatorio_id", "")
        if not identificador or identificador in indice:
            raise ValueError(f"relatorio_id ausente ou duplicado em {nome}: {identificador!r}")
        indice[identificador] = linha
    return indice


def _limpar_para_legibilidade(texto: str) -> str:
    texto = re.sub(r"`[^`]*`", " ", texto)
    texto = re.sub(r"\b(?:[A-Za-z]:)?[^\s,;:()]+[\\/][^\s,;:()]+", " ", texto)
    texto = re.sub(r"\bCWE-[0-9]+\b", " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\b[A-Za-zÀ-ÖØ-öø-ÿ]+(?:_[A-Za-z0-9À-ÖØ-öø-ÿ]+)+\b", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _silabas_palavra(palavra: str) -> int:
    palavra = palavra.lower()
    grupos = 0
    anterior_vogal = False
    for caractere in palavra:
        atual_vogal = caractere in VOGAIS
        if atual_vogal and not anterior_vogal:
            grupos += 1
        anterior_vogal = atual_vogal
    return max(1, grupos)


def flesch_portugues(texto: str) -> dict[str, float | int | str | None]:
    """Índice de Martins et al. com silabificação heurística determinística."""
    limpo = _limpar_para_legibilidade(texto)
    palavras = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", limpo)
    if not palavras:
        return {"texto_limpo": limpo, "sentencas": 0, "palavras": 0, "silabas": 0, "indice": None}
    sentencas = max(1, len(re.findall(r"[.!?]+", limpo)))
    silabas = sum(_silabas_palavra(palavra) for palavra in palavras)
    indice = 248.835 - 1.015 * (len(palavras) / sentencas) - 84.6 * (silabas / len(palavras))
    return {
        "texto_limpo": limpo,
        "sentencas": sentencas,
        "palavras": len(palavras),
        "silabas": silabas,
        "indice": indice,
    }


def kappa_nao_ponderado(pares: list[tuple[int, int]], categorias: tuple[int, ...] = (0, 1)) -> float | None:
    if not pares:
        return None
    total = len(pares)
    concordancia = sum(a == b for a, b in pares) / total
    marginal_a = Counter(a for a, _ in pares)
    marginal_b = Counter(b for _, b in pares)
    esperada = sum((marginal_a[c] / total) * (marginal_b[c] / total) for c in categorias)
    if esperada == 1:
        return 1.0 if concordancia == 1 else None
    return (concordancia - esperada) / (1 - esperada)


def analisar_rubrica(
    principal_path: Path,
    segundo_path: Path,
    chave_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    principal = _indexar(carregar_csv(principal_path), "avaliador principal")
    segundo = _indexar(carregar_csv(segundo_path), "segundo avaliador")
    chave = _indexar(carregar_csv(chave_path), "chave")
    if set(principal) != set(chave):
        raise ValueError("o formulário principal e a chave não contêm os mesmos relatórios")
    if not set(segundo).issubset(principal):
        raise ValueError("o formulário do segundo avaliador contém relatórios fora da amostra")
    if len(segundo) < (len(principal) + 4) // 5:
        raise ValueError("o segundo avaliador deve cobrir pelo menos 20% da amostra")

    valores: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    flesch_linhas: list[dict[str, Any]] = []
    for relatorio_id, linha in principal.items():
        segredo = chave[relatorio_id]
        condicao = segredo["condicao"]
        recorte = segredo["tipo_recorte"]
        for campo in CAMPOS_ORDINAIS:
            valores[(condicao, recorte, campo)].append(_inteiro(linha, campo, 1, 5))
        clareza = []
        for campo in CAMPOS_BINARIOS:
            valor = _inteiro(linha, campo, 0, 1)
            clareza.append(valor)
            valores[(condicao, recorte, campo)].append(valor)
        valores[(condicao, recorte, "clareza_total_0a5")].append(sum(clareza))
        legibilidade = flesch_portugues(f"{linha.get('descricao', '')}. {linha.get('recomendacao', '')}")
        flesch_linhas.append(
            {
                "relatorio_id": relatorio_id,
                "condicao": condicao,
                "tipo_recorte": recorte,
                "sentencas": legibilidade["sentencas"],
                "palavras": legibilidade["palavras"],
                "silabas": legibilidade["silabas"],
                "flesch_ptbr": legibilidade["indice"],
            }
        )

    resumo_linhas: list[dict[str, Any]] = []
    for (condicao, recorte, dimensao), itens in sorted(valores.items()):
        resumo = resumo_distribuicao(itens)
        resumo_linhas.append(
            {
                "condicao": condicao,
                "tipo_recorte": recorte,
                "dimensao": dimensao,
                **resumo,
                "media": statistics.fmean(itens),
            }
        )

    concordancia_linhas: list[dict[str, Any]] = []
    for campo in CAMPOS_ORDINAIS:
        pares = [
            (_inteiro(principal[item], campo, 1, 5), _inteiro(segundo[item], campo, 1, 5))
            for item in sorted(segundo)
        ]
        concordancia_linhas.append(
            {
                "dimensao": campo,
                "tipo": "ordinal",
                "n": len(pares),
                "concordancia_percentual": sum(a == b for a, b in pares) / len(pares),
                "kappa": kappa_ponderado_quadratico([(a - 1, b - 1) for a, b in pares], categorias=5),
                "ponderacao": "quadratica",
            }
        )
    for campo in CAMPOS_BINARIOS:
        pares = [
            (_inteiro(principal[item], campo, 0, 1), _inteiro(segundo[item], campo, 0, 1))
            for item in sorted(segundo)
        ]
        concordancia_linhas.append(
            {
                "dimensao": campo,
                "tipo": "binaria",
                "n": len(pares),
                "concordancia_percentual": sum(a == b for a, b in pares) / len(pares),
                "kappa": kappa_nao_ponderado(pares),
                "ponderacao": "nenhuma",
            }
        )

    resumo = {
        "schema_version": "1.0",
        "relatorios_principal": len(principal),
        "relatorios_segundo_avaliador": len(segundo),
        "proporcao_segundo_avaliador": len(segundo) / len(principal),
        "flesch": {
            "formula": "248.835 - 1.015*(palavras/sentencas) - 84.6*(silabas/palavras)",
            "pre_processamento": "remove código entre crases, caminhos, CWE e identificadores com sublinhado",
            "silabificacao": "número de grupos contíguos de vogais, mínimo um por palavra",
            "papel": "medida secundária de facilidade sintática; não substitui a rubrica",
        },
    }
    return resumo_linhas, concordancia_linhas, flesch_linhas, resumo


def escrever_analise_rubrica(
    principal: Path, segundo: Path, chave: Path, saida: Path
) -> dict[str, Any]:
    resumo_linhas, concordancia, flesch, resumo = analisar_rubrica(principal, segundo, chave)
    saida.mkdir(parents=True, exist_ok=True)
    for nome, linhas in (
        ("rubrica-resumo.csv", resumo_linhas),
        ("concordancia-avaliadores.csv", concordancia),
        ("legibilidade-flesch.csv", flesch),
    ):
        with (saida / nome).open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(
                arquivo, fieldnames=list(linhas[0]), lineterminator="\n"
            )
            escritor.writeheader()
            escritor.writerows(linhas)
    (saida / "resumo-rubrica.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumo
