#!/usr/bin/env python3
"""Audita a completude e resume as três repetições C3--C6.

O script não pontua contra o oracle. Ele só valida cobertura, estados e
metadados observáveis; a pontuação será uma etapa posterior separada.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


CONDICOES = ("C3", "C4", "C5", "C6")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", type=Path, default=Path("resultados/ia"))
    parser.add_argument("--csv", type=Path, default=Path("evidencias/ia/resumo-repeticoes.csv"))
    args = parser.parse_args()
    manifestos = sorted(args.raiz.rglob("manifesto.json")) if args.raiz.exists() else []
    linhas = []
    for caminho in manifestos:
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
        if manifesto.get("condicao") not in CONDICOES:
            continue
        obrigatorios = ("condicao", "alvo", "repeticao", "estado", "produto", "sessao_id")
        ausentes = [campo for campo in obrigatorios if campo not in manifesto]
        if ausentes:
            raise SystemExit(f"manifesto incompleto {caminho}: {ausentes}")
        linhas.append({
            "condicao": manifesto["condicao"], "alvo": manifesto["alvo"],
            "repeticao": manifesto["repeticao"], "estado": manifesto["estado"],
            "produto": manifesto["produto"], "duracao_segundos": manifesto.get("duracao_segundos"),
            "tokens_total": manifesto.get("tokens_total"), "resposta_valida": manifesto.get("resposta_valida"),
        })
    esperados = len(CONDICOES) * 26 * 3
    if len(linhas) != esperados:
        raise SystemExit(f"esperados {esperados} manifestos C3-C6; encontrados {len(linhas)}")
    chaves = [(linha["condicao"], linha["alvo"], linha["repeticao"]) for linha in linhas]
    if len(set(chaves)) != esperados:
        raise SystemExit("há chaves duplicadas ou repetições ausentes")
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader(); escritor.writerows(linhas)
    print(json.dumps({"manifestos": len(linhas), "estados": Counter(l["estado"] for l in linhas), "csv": str(args.csv)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
