#!/usr/bin/env python3
"""Gera gráficos SVG publicáveis a partir dos resultados da avaliação."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_PADRAO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_PADRAO))

from runner.avaliacao.graficos import gerar_graficos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dados", type=Path, default=REPO_PADRAO / "evidencias" / "avaliacao")
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()
    dados = args.dados.resolve()
    saida = (args.saida or dados / "graficos").resolve()
    caminhos = gerar_graficos(dados, saida)
    print(json.dumps({"estado": "concluida", "graficos": len(caminhos), "saida": str(saida)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
