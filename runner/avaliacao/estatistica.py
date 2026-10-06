"""Agregações e inferência previstas no protocolo de avaliação."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict
from typing import Any, Callable, Iterable

from .dados import CONDICOES, CONDICOES_IA, ExecucaoAvaliada


NOMES_METRICAS = ("precision", "recall", "f1", "f2", "f3", "fpr")
ORDEM_SEVERIDADE = {"low": 0, "baixa": 0, "medium": 1, "media": 1, "high": 2, "alta": 2, "critical": 3, "critica": 3}


def divisao(numerador: float, denominador: float) -> float:
    return numerador / denominador if denominador else 0.0


def metricas_contagens(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    precisao = divisao(tp, tp + fp)
    recall = divisao(tp, tp + fn)
    return {
        "precision": precisao,
        "recall": recall,
        "f1": divisao(2 * precisao * recall, precisao + recall),
        "f2": divisao(5 * precisao * recall, 4 * precisao + recall),
        "f3": divisao(10 * precisao * recall, 9 * precisao + recall),
        "fpr": divisao(fp, fp + tn),
    }


def percentil(valores: Iterable[float], proporcao: float) -> float:
    ordenados = sorted(valores)
    if not ordenados:
        return math.nan
    if len(ordenados) == 1:
        return float(ordenados[0])
    posicao = (len(ordenados) - 1) * proporcao
    inferior = math.floor(posicao)
    superior = math.ceil(posicao)
    if inferior == superior:
        return float(ordenados[inferior])
    peso = posicao - inferior
    return float(ordenados[inferior] * (1 - peso) + ordenados[superior] * peso)


def resumo_distribuicao(valores: Iterable[float]) -> dict[str, float | int | None]:
    itens = [float(valor) for valor in valores if valor is not None and math.isfinite(float(valor))]
    if not itens:
        return {"n": 0, "minimo": None, "q1": None, "mediana": None, "q3": None, "maximo": None}
    return {
        "n": len(itens),
        "minimo": min(itens),
        "q1": percentil(itens, 0.25),
        "mediana": percentil(itens, 0.5),
        "q3": percentil(itens, 0.75),
        "maximo": max(itens),
    }


def _somar_contagens(itens: Iterable[ExecucaoAvaliada]) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    for item in itens:
        tp += item.scorecard.tp
        fp += item.scorecard.fp
        fn += item.scorecard.fn
        tn += item.scorecard.tn
    return tp, fp, fn, tn


def metricas_por_repeticao(avaliadas: list[ExecucaoAvaliada]) -> list[dict[str, Any]]:
    grupos: dict[tuple[str, int], list[ExecucaoAvaliada]] = defaultdict(list)
    for item in avaliadas:
        grupos[(item.execucao.condicao, item.execucao.repeticao)].append(item)
    linhas: list[dict[str, Any]] = []
    for (condicao, repeticao), itens in sorted(grupos.items()):
        tp, fp, fn, tn = _somar_contagens(itens)
        linhas.append(
            {
                "condicao": condicao,
                "repeticao": repeticao,
                "repositorios": len(itens),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                **metricas_contagens(tp, fp, fn, tn),
            }
        )
    return linhas


def metricas_por_repositorio(avaliadas: list[ExecucaoAvaliada]) -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []
    for item in avaliadas:
        card = item.scorecard
        linhas.append(
            {
                "condicao": item.execucao.condicao,
                "alvo": item.execucao.alvo,
                "repeticao": item.execucao.repeticao,
                "tentativa": item.execucao.tentativa,
                "tp": card.tp,
                "fp": card.fp,
                "fn": card.fn,
                "tn": card.tn,
                **metricas_contagens(card.tp, card.fp, card.fn, card.tn),
            }
        )
    return linhas


def _indices_bootstrap(quantidade_alvos: int, iteracoes: int, semente: int) -> list[list[int]]:
    gerador = random.Random(semente)
    return [
        [gerador.randrange(quantidade_alvos) for _ in range(quantidade_alvos)]
        for _ in range(iteracoes)
    ]


def _contagens_amostra(
    mapa: dict[tuple[str, int, str], tuple[int, int, int, int]],
    condicao: str,
    repeticao: int,
    alvos: list[str],
    indices: list[int] | None = None,
) -> tuple[int, int, int, int]:
    selecionados = alvos if indices is None else [alvos[indice] for indice in indices]
    contagens = [mapa[(condicao, repeticao, alvo)] for alvo in selecionados]
    return tuple(sum(item[posicao] for item in contagens) for posicao in range(4))  # type: ignore[return-value]


def resumo_condicoes_bootstrap(
    avaliadas: list[ExecucaoAvaliada], iteracoes: int, semente: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """IC percentil de 95% por bootstrap no nível do repositório.

    Para C3--C6, a estatística de cada amostra é a média das três métricas
    microcontadas separadamente por repetição. Não há união nem voto entre
    repetições.
    """
    alvos = sorted({item.execucao.alvo for item in avaliadas})
    mapa = {
        (item.execucao.condicao, item.execucao.repeticao, item.execucao.alvo): (
            item.scorecard.tp,
            item.scorecard.fp,
            item.scorecard.fn,
            item.scorecard.tn,
        )
        for item in avaliadas
    }
    amostras = _indices_bootstrap(len(alvos), iteracoes, semente)
    resumo: list[dict[str, Any]] = []
    distribuicoes: dict[tuple[str, str], list[float]] = {}

    for condicao in CONDICOES:
        repeticoes = [1] if condicao not in CONDICOES_IA else [1, 2, 3]
        por_repeticao = []
        contagens_repeticao = []
        for repeticao in repeticoes:
            contagens = _contagens_amostra(mapa, condicao, repeticao, alvos)
            contagens_repeticao.append(contagens)
            por_repeticao.append(metricas_contagens(*contagens))

        linha: dict[str, Any] = {
            "condicao": condicao,
            "repeticoes": len(repeticoes),
            "tp_media": statistics.fmean(item[0] for item in contagens_repeticao),
            "fp_media": statistics.fmean(item[1] for item in contagens_repeticao),
            "fn_media": statistics.fmean(item[2] for item in contagens_repeticao),
            "tn_media": statistics.fmean(item[3] for item in contagens_repeticao),
        }
        for metrica in NOMES_METRICAS:
            pontuais = [item[metrica] for item in por_repeticao]
            valor = statistics.fmean(pontuais)
            desvio = statistics.stdev(pontuais) if len(pontuais) > 1 else 0.0
            amplitude = max(pontuais) - min(pontuais)
            valores_bootstrap: list[float] = []
            for indices in amostras:
                valores_repeticao = [
                    metricas_contagens(
                        *_contagens_amostra(mapa, condicao, repeticao, alvos, indices)
                    )[metrica]
                    for repeticao in repeticoes
                ]
                valores_bootstrap.append(statistics.fmean(valores_repeticao))
            distribuicoes[(condicao, metrica)] = valores_bootstrap
            linha[metrica] = valor
            linha[f"{metrica}_ic95_inferior"] = percentil(valores_bootstrap, 0.025)
            linha[f"{metrica}_ic95_superior"] = percentil(valores_bootstrap, 0.975)
            linha[f"{metrica}_desvio_repeticoes"] = desvio
            linha[f"{metrica}_amplitude_repeticoes"] = amplitude
        resumo.append(linha)

    comparacoes: list[dict[str, Any]] = []
    for base, hibrida in (("C3", "C5"), ("C4", "C6")):
        for metrica in NOMES_METRICAS:
            base_ponto = next(item[metrica] for item in resumo if item["condicao"] == base)
            hibrida_ponto = next(item[metrica] for item in resumo if item["condicao"] == hibrida)
            deltas = [
                valor_hibrido - valor_base
                for valor_base, valor_hibrido in zip(
                    distribuicoes[(base, metrica)], distribuicoes[(hibrida, metrica)]
                )
            ]
            comparacoes.append(
                {
                    "comparacao": f"{hibrida}-{base}",
                    "base": base,
                    "hibrida": hibrida,
                    "metrica": metrica,
                    "delta": hibrida_ponto - base_ponto,
                    "ic95_inferior": percentil(deltas, 0.025),
                    "ic95_superior": percentil(deltas, 0.975),
                    "probabilidade_delta_positivo_bootstrap": divisao(
                        sum(delta > 0 for delta in deltas), len(deltas)
                    ),
                }
            )
    return resumo, comparacoes


def estabilidade(avaliadas: list[ExecucaoAvaliada]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    por_execucao = {
        (item.execucao.condicao, item.execucao.alvo, item.execucao.repeticao): {
            resultado.ground_truth_id
            for resultado in item.correspondencias
            if resultado.classification == "TP" and resultado.ground_truth_id
        }
        for item in avaliadas
        if item.execucao.condicao in CONDICOES_IA
    }
    gt_por_alvo: dict[str, list[dict[str, Any]]] = {}
    for item in avaliadas:
        gt_por_alvo.setdefault(
            item.execucao.alvo,
            [entrada for entrada in item.ground_truth["findings"] if entrada["is_vulnerable"]],
        )

    entradas: list[dict[str, Any]] = []
    totais: list[dict[str, Any]] = []
    for condicao in CONDICOES_IA:
        frequencias: Counter[int] = Counter()
        for alvo, vulnerabilidades in sorted(gt_por_alvo.items()):
            for entrada in vulnerabilidades:
                deteccoes = sum(
                    entrada["id"] in por_execucao[(condicao, alvo, repeticao)]
                    for repeticao in (1, 2, 3)
                )
                frequencias[deteccoes] += 1
                entradas.append(
                    {
                        "condicao": condicao,
                        "alvo": alvo,
                        "ground_truth_id": entrada["id"],
                        "cwe": entrada["primary_cwe"],
                        "severidade": entrada["severity"],
                        "deteccoes_em_3": deteccoes,
                    }
                )
        for frequencia in range(4):
            totais.append(
                {
                    "condicao": condicao,
                    "frequencia": frequencia,
                    "entradas": frequencias[frequencia],
                    "proporcao": divisao(frequencias[frequencia], sum(frequencias.values())),
                }
            )
    return entradas, totais


def operacional(avaliadas: list[ExecucaoAvaliada]) -> list[dict[str, Any]]:
    por_condicao: dict[str, list[ExecucaoAvaliada]] = defaultdict(list)
    for item in avaliadas:
        por_condicao[item.execucao.condicao].append(item)
    linhas: list[dict[str, Any]] = []
    for condicao in CONDICOES:
        itens = por_condicao[condicao]
        duracoes = []
        tokens_entrada = []
        tokens_saida = []
        tokens_total = []
        for item in itens:
            manifesto = item.execucao.manifesto
            duracao = manifesto.get("duracao_monotonica_segundos", manifesto.get("duracao_segundos"))
            if isinstance(duracao, (int, float)):
                duracoes.append(float(duracao))
            for chave, destino in (
                ("tokens_entrada", tokens_entrada),
                ("tokens_saida", tokens_saida),
                ("tokens_total", tokens_total),
            ):
                valor = manifesto.get(chave)
                if isinstance(valor, (int, float)):
                    destino.append(float(valor))
        linhas.append(
            {
                "condicao": condicao,
                "duracao_segundos": resumo_distribuicao(duracoes),
                "tokens_entrada": resumo_distribuicao(tokens_entrada),
                "tokens_saida": resumo_distribuicao(tokens_saida),
                "tokens_total": resumo_distribuicao(tokens_total),
            }
        )
    return linhas


def kappa_ponderado_quadratico(pares: list[tuple[int, int]], categorias: int = 4) -> float | None:
    if not pares:
        return None
    matriz = [[0 for _ in range(categorias)] for _ in range(categorias)]
    for observado, esperado in pares:
        matriz[observado][esperado] += 1
    total = len(pares)
    linhas = [sum(linha) for linha in matriz]
    colunas = [sum(matriz[i][j] for i in range(categorias)) for j in range(categorias)]
    denominador_peso = (categorias - 1) ** 2
    desacordo_observado = 0.0
    desacordo_esperado = 0.0
    for i in range(categorias):
        for j in range(categorias):
            peso = ((i - j) ** 2) / denominador_peso
            desacordo_observado += peso * matriz[i][j] / total
            desacordo_esperado += peso * (linhas[i] * colunas[j]) / (total * total)
    if desacordo_esperado == 0:
        return 1.0 if desacordo_observado == 0 else None
    return 1.0 - desacordo_observado / desacordo_esperado


def priorizacao(avaliadas: list[ExecucaoAvaliada]) -> list[dict[str, Any]]:
    grupos: dict[tuple[str, int], list[ExecucaoAvaliada]] = defaultdict(list)
    for item in avaliadas:
        grupos[(item.execucao.condicao, item.execucao.repeticao)].append(item)
    linhas: list[dict[str, Any]] = []
    for (condicao, repeticao), itens in sorted(grupos.items()):
        total_tp = rotulados = exatos = tolerantes = 0
        pares: list[tuple[int, int]] = []
        for item in itens:
            for resultado in item.correspondencias:
                if resultado.classification != "TP" or not resultado.scanner_finding or not resultado.ground_truth_entry:
                    continue
                total_tp += 1
                observado = ORDEM_SEVERIDADE.get(str(resultado.scanner_finding.severity).lower())
                referencia = ORDEM_SEVERIDADE.get(str(resultado.ground_truth_entry.get("severity")).lower())
                if observado is None or referencia is None:
                    continue
                rotulados += 1
                exatos += observado == referencia
                tolerantes += abs(observado - referencia) <= 1
                pares.append((observado, referencia))
        linhas.append(
            {
                "condicao": condicao,
                "repeticao": repeticao,
                "verdadeiros_positivos": total_tp,
                "com_severidade": rotulados,
                "cobertura": divisao(rotulados, total_tp),
                "concordancia_exata_rotulados": divisao(exatos, rotulados),
                "concordancia_uma_categoria_rotulados": divisao(tolerantes, rotulados),
                "concordancia_exata_todos_tp": divisao(exatos, total_tp),
                "concordancia_uma_categoria_todos_tp": divisao(tolerantes, total_tp),
                "kappa_ponderado_quadratico": kappa_ponderado_quadratico(pares),
            }
        )
    return linhas


def detalhamentos(
    avaliadas: list[ExecucaoAvaliada],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    familias: dict[tuple[str, int, str, str], Counter[str]] = defaultdict(Counter)
    severidades: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    correspondencias: list[dict[str, Any]] = []

    for item in avaliadas:
        execucao = item.execucao
        brutos = {
            achado.finding_id: bruto
            for achado, bruto in zip(execucao.achados, execucao.achados_brutos)
        }
        for resultado in item.correspondencias:
            gt = resultado.ground_truth_entry
            if gt:
                cwe = str(gt.get("primary_cwe", "desconhecido"))
                severidade = str(gt.get("severity", "desconhecida"))
                familias[(execucao.condicao, execucao.repeticao, cwe, str(gt.get("expected_category", "sem_categoria")))][resultado.classification] += 1
                severidades[(execucao.condicao, execucao.repeticao, severidade)][resultado.classification] += 1
            achado = resultado.scanner_finding
            if achado is None:
                continue
            bruto = brutos.get(achado.finding_id, {})
            correspondencias.append(
                {
                    "condicao": execucao.condicao,
                    "alvo": execucao.alvo,
                    "repeticao": execucao.repeticao,
                    "tentativa": execucao.tentativa,
                    "achado_id": achado.finding_id,
                    "classificacao": resultado.classification,
                    "ground_truth_id": resultado.ground_truth_id,
                    "arquivo_reportado": achado.file,
                    "linha_reportada": achado.line,
                    "cwe_reportado": achado.cwe,
                    "severidade_reportada": achado.severity,
                    "cwe_referencia": gt.get("primary_cwe") if gt else None,
                    "severidade_referencia": gt.get("severity") if gt else None,
                    "categoria_referencia": gt.get("expected_category") if gt else None,
                    "descricao": bruto.get("descricao"),
                    "recomendacao": bruto.get("recomendacao"),
                }
            )

    linhas_cwe: list[dict[str, Any]] = []
    for (condicao, repeticao, cwe, categoria), contagens in sorted(familias.items()):
        tp, fp, fn, tn = (contagens[chave] for chave in ("TP", "FP", "FN", "TN"))
        linhas_cwe.append(
            {
                "condicao": condicao,
                "repeticao": repeticao,
                "cwe": cwe,
                "categoria": categoria,
                "tp": tp,
                "fp_armadilhas_associadas": fp,
                "fn": fn,
                "tn": tn,
                "recall": divisao(tp, tp + fn),
                "fpr_armadilhas": divisao(fp, fp + tn),
            }
        )

    linhas_severidade: list[dict[str, Any]] = []
    for (condicao, repeticao, severidade), contagens in sorted(severidades.items()):
        tp, fp, fn, tn = (contagens[chave] for chave in ("TP", "FP", "FN", "TN"))
        linhas_severidade.append(
            {
                "condicao": condicao,
                "repeticao": repeticao,
                "severidade": severidade,
                "tp": tp,
                "fp_armadilhas_associadas": fp,
                "fn": fn,
                "tn": tn,
                "recall": divisao(tp, tp + fn),
                "fpr_armadilhas": divisao(fp, fp + tn),
            }
        )
    return correspondencias, linhas_cwe, linhas_severidade
