#!/usr/bin/env python3
"""Analisa formulários preenchidos da rubrica e a concordância interavaliador."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_PADRAO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_PADRAO))

from runner.avaliacao.rubrica import escrever_analise_rubrica


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    padrao = REPO_PADRAO / "evidencias" / "avaliacao"
    parser.add_argument("--principal", type=Path, default=padrao / "amostra-qualitativa-cega.csv")
    parser.add_argument("--segundo", type=Path, default=padrao / "amostra-segundo-avaliador.csv")
    parser.add_argument("--chave", type=Path, default=padrao / "chave-amostra-qualitativa.csv")
    parser.add_argument("--saida", type=Path, default=padrao / "rubrica")
    args = parser.parse_args()
    resumo = escrever_analise_rubrica(
        args.principal.resolve(), args.segundo.resolve(), args.chave.resolve(), args.saida.resolve()
    )
    print(json.dumps({"estado": "concluida", **resumo}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
