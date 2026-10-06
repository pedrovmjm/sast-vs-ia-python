"""Sorteio pré-especificado e cegamento da amostra qualitativa."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any

from .dados import CONDICOES, ExecucaoAvaliada


def _tp_primeira_repeticao(avaliadas: list[ExecucaoAvaliada]) -> dict[str, list[dict[str, Any]]]:
    por_condicao: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in avaliadas:
        if item.execucao.repeticao != 1:
            continue
        brutos = {
            achado.finding_id: bruto
            for achado, bruto in zip(item.execucao.achados, item.execucao.achados_brutos)
        }
        for resultado in item.correspondencias:
            if resultado.classification != "TP" or not resultado.scanner_finding or not resultado.ground_truth_entry:
                continue
            achado = resultado.scanner_finding
            bruto = brutos[achado.finding_id]
            gt = resultado.ground_truth_entry
            por_condicao[item.execucao.condicao].append(
                {
                    "condicao": item.execucao.condicao,
                    "alvo": item.execucao.alvo,
                    "ground_truth_id": resultado.ground_truth_id,
                    "achado_id": achado.finding_id,
                    "arquivo": achado.file,
                    "linha": achado.line,
                    "cwe_reportado": achado.cwe,
                    "severidade_reportada": achado.severity,
                    "descricao": bruto.get("descricao") or "",
                    "recomendacao": bruto.get("recomendacao") or "",
                    "cwe_referencia": gt.get("primary_cwe"),
                    "severidade_referencia": gt.get("severity"),
                }
            )
    return por_condicao


def _amostrar_estratificado(
    candidatos: list[dict[str, Any]], quantidade: int, gerador: random.Random
) -> list[dict[str, Any]]:
    estratos: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidatos:
        estratos[(str(item["cwe_referencia"]), str(item["severidade_referencia"]))].append(item)
    for itens in estratos.values():
        gerador.shuffle(itens)
    chaves = sorted(estratos)
    gerador.shuffle(chaves)
    selecionados: list[dict[str, Any]] = []
    while len(selecionados) < quantidade and chaves:
        proximas: list[tuple[str, str]] = []
        for chave in chaves:
            if estratos[chave] and len(selecionados) < quantidade:
                selecionados.append(estratos[chave].pop())
            if estratos[chave]:
                proximas.append(chave)
        chaves = proximas
    return selecionados


def preparar_amostra(
    avaliadas: list[ExecucaoAvaliada], semente: int, limite_comum: int = 20, limite_condicao: int = 50
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    por_condicao = _tp_primeira_repeticao(avaliadas)
    if set(por_condicao) != set(CONDICOES):
        raise ValueError("faltam condições na primeira repetição para a amostra qualitativa")
    ids_por_condicao = {
        condicao: {str(item["ground_truth_id"]) for item in itens}
        for condicao, itens in por_condicao.items()
    }
    comuns = set.intersection(*(ids_por_condicao[condicao] for condicao in CONDICOES))
    gerador = random.Random(semente)
    comuns_ordenados = sorted(comuns)
    gerador.shuffle(comuns_ordenados)
    ids_comuns = comuns_ordenados[:limite_comum]
    grupo_comum = {gt_id: f"COMUM-{indice:03d}" for indice, gt_id in enumerate(ids_comuns, start=1)}

    selecionados: list[dict[str, Any]] = []
    for condicao in CONDICOES:
        por_id = {str(item["ground_truth_id"]): item for item in por_condicao[condicao]}
        comuns_condicao = []
        for gt_id in ids_comuns:
            item = dict(por_id[gt_id])
            item["tipo_recorte"] = "comum"
            item["grupo_comum"] = grupo_comum[gt_id]
            comuns_condicao.append(item)
        restantes = [
            item for item in por_condicao[condicao] if str(item["ground_truth_id"]) not in grupo_comum
        ]
        faltantes = max(0, min(limite_condicao, len(por_condicao[condicao])) - len(comuns_condicao))
        complemento = _amostrar_estratificado(restantes, faltantes, gerador)
        for item_original in complemento:
            item = dict(item_original)
            item["tipo_recorte"] = "estratificado"
            item["grupo_comum"] = ""
            comuns_condicao.append(item)
        selecionados.extend(comuns_condicao)

    gerador.shuffle(selecionados)
    cegos: list[dict[str, Any]] = []
    chave: list[dict[str, Any]] = []
    for indice, item in enumerate(selecionados, start=1):
        relatorio_id = f"REL-{indice:04d}"
        cegos.append(
            {
                "relatorio_id": relatorio_id,
                "tipo_recorte": item["tipo_recorte"],
                "grupo_comum": item["grupo_comum"],
                "alvo": item["alvo"],
                "ground_truth_id": item["ground_truth_id"],
                "cwe_referencia": item["cwe_referencia"],
                "severidade_referencia": item["severidade_referencia"],
                "arquivo_reportado": item["arquivo"],
                "linha_reportada": item["linha"],
                "cwe_reportado": item["cwe_reportado"],
                "severidade_reportada": item["severidade_reportada"],
                "descricao": item["descricao"],
                "recomendacao": item["recomendacao"],
                "correcao_tecnica_1a5": "",
                "localizacao_1a5": "",
                "acionabilidade_1a5": "",
                "clareza_problema_0ou1": "",
                "clareza_risco_0ou1": "",
                "clareza_contexto_0ou1": "",
                "clareza_concretude_0ou1": "",
                "clareza_concisao_0ou1": "",
                "observacoes_avaliador": "",
            }
        )
        chave.append(
            {
                "relatorio_id": relatorio_id,
                "condicao": item["condicao"],
                "achado_id": item["achado_id"],
                "alvo": item["alvo"],
                "ground_truth_id": item["ground_truth_id"],
                "tipo_recorte": item["tipo_recorte"],
                "grupo_comum": item["grupo_comum"],
            }
        )

    # Segundo avaliador: no mínimo 20%, estratificado por condição e CWE.
    chave_por_id = {item["relatorio_id"]: item for item in chave}
    cegos_por_id = {item["relatorio_id"]: item for item in cegos}
    candidatos_segundo = []
    for item in cegos:
        segredo = chave_por_id[item["relatorio_id"]]
        candidatos_segundo.append(
            {
                **item,
                "_condicao": segredo["condicao"],
            }
        )
    quantidade_segundo = math.ceil(len(cegos) * 0.20)
    segundo_selecionado = _amostrar_estratificado(
        [
            {
                **item,
                "cwe_referencia": item["cwe_referencia"],
                "severidade_referencia": item["_condicao"],
            }
            for item in candidatos_segundo
        ],
        quantidade_segundo,
        gerador,
    )
    segundo_ids = {item["relatorio_id"] for item in segundo_selecionado}
    segundo = [cegos_por_id[relatorio_id] for relatorio_id in sorted(segundo_ids)]

    resumo = {
        "semente": semente,
        "execucao_principal": 1,
        "limite_recorte_comum": limite_comum,
        "entradas_detectadas_por_todas": len(comuns),
        "entradas_comuns_sorteadas": len(ids_comuns),
        "limite_por_condicao": limite_condicao,
        "relatorios_por_condicao": {
            condicao: sum(item["condicao"] == condicao for item in chave) for condicao in CONDICOES
        },
        "relatorios_total": len(cegos),
        "segundo_avaliador_total": len(segundo),
        "segundo_avaliador_proporcao": len(segundo) / len(cegos) if cegos else 0.0,
    }
    return cegos, chave, segundo, resumo
