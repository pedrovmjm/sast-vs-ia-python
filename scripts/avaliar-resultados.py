#!/usr/bin/env python3
"""Executa a avaliação quantitativa C1--C6 conforme a metodologia fixada."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_PADRAO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_PADRAO))

from runner.avaliacao.relatorio import executar_avaliacao


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO_PADRAO)
    parser.add_argument("--saida", type=Path, default=None)
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--semente", type=int, default=20260928)
    args = parser.parse_args()
    repo = args.repo.resolve()
    saida = (args.saida or repo / "evidencias" / "avaliacao").resolve()
    resumo = executar_avaliacao(repo, saida, args.bootstrap, args.semente)
    print(
        json.dumps(
            {
                "estado": "concluida",
                "unidades": resumo["unidades_selecionadas"],
                "alvos": resumo["alvos"],
                "saida": str(saida),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
