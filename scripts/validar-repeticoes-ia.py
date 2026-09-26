#!/usr/bin/env python3
"""Audita a completude e resume as três repetições C3--C6.

O script não pontua contra o oracle. Ele só valida cobertura, estados e
metadados observáveis; a pontuação será uma etapa posterior separada.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CONDICOES = ("C3", "C4", "C5", "C6")
CAMPOS_ACHADO = {
    "arquivo", "linha_inicial", "linha_final", "cwe", "severidade",
    "descricao", "recomendacao",
}


def validar_resposta(caminho: Path, alvo_raiz: Path) -> tuple[bool, str | None]:
    """Revalida uma resposta bruta sem alterar a tentativa preservada."""
    try:
        if not caminho.is_file():
            return False, "resposta-bruta.txt ausente"
        documento: Any = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, f"resposta JSON invalida: {exc}"
    if not isinstance(documento, list):
        return False, "a raiz do relatorio deve ser um array"

    try:
        raiz_resolvida = alvo_raiz.resolve()
    except OSError as exc:
        return False, f"nao foi possivel resolver a raiz do alvo: {exc}"
    for indice, item in enumerate(documento):
        if not isinstance(item, dict) or set(item) != CAMPOS_ACHADO:
            return False, f"achado {indice}: campos divergem do schema"
        relativo = item["arquivo"]
        if (
            not isinstance(relativo, str)
            or not relativo
            or "\\" in relativo
            or relativo.startswith("/")
            or any(parte in ("", ".", "..") for parte in relativo.split("/"))
            or not relativo.lower().endswith(".py")
        ):
            return False, f"achado {indice}: caminho de arquivo invalido"
        try:
            arquivo = (raiz_resolvida / Path(*relativo.split("/"))).resolve()
            arquivo.relative_to(raiz_resolvida)
        except ValueError:
            return False, f"achado {indice}: caminho escapa do alvo"
        except OSError as exc:
            return False, f"achado {indice}: nao foi possivel resolver o arquivo: {exc}"
        try:
            if not arquivo.is_file():
                return False, f"achado {indice}: arquivo nao existe no alvo"
            quantidade_linhas = len(arquivo.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError) as exc:
            return False, f"achado {indice}: nao foi possivel ler o arquivo: {exc}"
        for campo in ("linha_inicial", "linha_final"):
            valor = item[campo]
            if valor is not None and (
                isinstance(valor, bool)
                or not isinstance(valor, int)
                or valor < 1
                or valor > quantidade_linhas
            ):
                return False, f"achado {indice}: {campo} fora do arquivo"
        inicio, fim = item["linha_inicial"], item["linha_final"]
        if inicio is not None and fim is not None and fim < inicio:
            return False, f"achado {indice}: intervalo de linhas invertido"
        cwe = item["cwe"]
        if cwe is not None and (
            not isinstance(cwe, str) or re.fullmatch(r"CWE-[0-9]+", cwe) is None
        ):
            return False, f"achado {indice}: CWE invalida"
        if item["severidade"] not in (None, "baixa", "media", "alta", "critica"):
            return False, f"achado {indice}: severidade invalida"
        descricao = item["descricao"]
        if not isinstance(descricao, str) or not descricao.strip():
            return False, f"achado {indice}: descricao invalida"
        recomendacao = item["recomendacao"]
        if recomendacao is not None and not isinstance(recomendacao, str):
            return False, f"achado {indice}: recomendacao invalida"
    return True, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", type=Path, default=Path("resultados/ia"))
    parser.add_argument("--alvos-raiz", type=Path, default=Path("alvos/corpus-v1"))
    parser.add_argument(
        "--condicoes", nargs="+", choices=CONDICOES, default=list(CONDICOES)
    )
    parser.add_argument("--csv", type=Path, default=Path("evidencias/ia/resumo-repeticoes.csv"))
    args = parser.parse_args()
    manifestos = sorted(args.raiz.rglob("manifesto.json")) if args.raiz.exists() else []
    tentativas = []
    for caminho in manifestos:
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        if manifesto.get("condicao") not in args.condicoes:
            continue
        if manifesto.get("finalidade") != "coleta":
            continue
        obrigatorios = (
            "condicao", "alvo", "repeticao", "tentativa", "finalidade",
            "estado", "produto", "sessao_id", "resposta_valida",
        )
        ausentes = [campo for campo in obrigatorios if campo not in manifesto]
        if ausentes:
            raise SystemExit(f"manifesto incompleto {caminho}: {ausentes}")
        resposta_atualmente_valida, erro_revalidacao = validar_resposta(
            caminho.parent / "resposta-bruta.txt",
            args.alvos_raiz / manifesto["alvo"],
        )
        tentativas.append({
            "condicao": manifesto["condicao"], "alvo": manifesto["alvo"],
            "repeticao": manifesto["repeticao"], "tentativa": manifesto["tentativa"],
            "estado": manifesto["estado"],
            "produto": manifesto["produto"], "duracao_segundos": manifesto.get("duracao_segundos"),
            "tokens_total": manifesto.get("tokens_total"), "resposta_valida": manifesto.get("resposta_valida"),
            "resposta_atualmente_valida": resposta_atualmente_valida,
            "erro_revalidacao": erro_revalidacao,
            "caminho_manifesto": str(caminho),
        })

    esperados = len(args.condicoes) * 26 * 3
    chaves_esperadas = {
        (condicao, f"ALVO-{alvo:04d}", repeticao)
        for condicao in args.condicoes
        for alvo in range(1, 27)
        for repeticao in range(1, 4)
    }
    por_chave = defaultdict(list)
    for tentativa in tentativas:
        chave = (tentativa["condicao"], tentativa["alvo"], tentativa["repeticao"])
        por_chave[chave].append(tentativa)
    extras = sorted(set(por_chave) - chaves_esperadas)
    ausentes = sorted(chaves_esperadas - set(por_chave))
    if extras or ausentes:
        raise SystemExit(
            f"cobertura divergente: ausentes={len(ausentes)}, extras={len(extras)}"
        )

    linhas = []
    for chave in sorted(chaves_esperadas):
        observadas = sorted(por_chave[chave], key=lambda item: item["tentativa"])
        sucessos = [
            item for item in observadas
            if item["estado"] == "concluida"
            and item["resposta_valida"] is True
            and item["resposta_atualmente_valida"] is True
        ]
        if len(sucessos) != 1:
            raise SystemExit(
                f"{chave} deve ter exatamente uma tentativa valida; encontradas {len(sucessos)}"
            )
        selecionada = dict(sucessos[0])
        selecionada["tentativas_observadas"] = len(observadas)
        selecionada["falhas_anteriores"] = sum(
            1 for item in observadas if item["tentativa"] < selecionada["tentativa"]
        )
        linhas.append(selecionada)

    if len(linhas) != esperados:
        raise SystemExit(f"esperadas {esperados} unidades validas; encontradas {len(linhas)}")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader(); escritor.writerows(linhas)
    print(json.dumps({
        "unidades_validas": len(linhas),
        "tentativas_observadas": len(tentativas),
        "estados_tentativas": Counter(t["estado"] for t in tentativas),
        "csv": str(args.csv),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
