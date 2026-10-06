#!/usr/bin/env python3
"""Gera as tabelas LaTeX da pontuação qualitativa a partir do resumo congelado.

Lê evidencias/avaliacao-qualitativa/resumo-qualitativa.json, produzido por
finalizar-rubrica.py --agregar depois do congelamento dos 300 julgamentos e da
abertura da chave, e escreve dois fragmentos `tabular` em
monografia/figs/avaliacao/. Usa somente a biblioteca padrão.
"""

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONDICOES = ("C1", "C2", "C3", "C4", "C5", "C6")
DIMENSOES = (
    ("correcao_tecnica", "Correção"),
    ("localizacao", "Localização"),
    ("acionabilidade", "Acionabilidade"),
    ("clareza_total", "Clareza (0--5)"),
    ("score_total", "Score"),
)
CABECALHO = "% Gerado por scripts/gerar-tabela-qualitativa.py; não editar.\n"


def decimal(valor, casas=2):
    if valor is None:
        return "--"
    texto = format(float(valor), f".{casas}f").replace(".", ",")
    return texto.replace("-", "$-$")


def indexar(linhas, chaves):
    indice = {}
    for linha in linhas:
        chave = tuple(linha[c] for c in chaves)
        if chave in indice:
            raise ValueError(f"linha duplicada no resumo: {chave}")
        indice[chave] = linha
    return indice


def tabela_condicoes(resumo):
    indice = indexar(resumo["resumos"], ("condicao", "tipo_recorte", "dimensao"))
    cabecalho = " & ".join(
        ["\\textbf{Condição}", "\\textbf{Relatos}", "\\textbf{Scores válidos}"]
        + [f"\\textbf{{{rotulo}}}" for _, rotulo in DIMENSOES]
    )
    linhas = [CABECALHO + "\\begin{tabular}{|l|r|r|" + "r|" * len(DIMENSOES) + "}\n\\hline",
              cabecalho + " \\\\\n\\hline"]
    for condicao in CONDICOES:
        score = indice[(condicao, "total", "score_total")]
        celulas = [condicao, str(score["n_total"]), str(score["n_validos"])]
        for campo, _ in DIMENSOES:
            celulas.append(decimal(indice[(condicao, "total", campo)]["media"]))
        linhas.append(" & ".join(celulas) + " \\\\\n\\hline")
    linhas.append("\\end{tabular}\n")
    return "\n".join(linhas)


def tabela_deltas(resumo):
    indice = indexar(resumo["deltas_comuns"], ("comparacao", "dimensao"))
    cabecalho = " & ".join(
        ["\\textbf{Comparação}", "\\textbf{Pares válidos}"]
        + [f"\\textbf{{{rotulo}}}" for _, rotulo in DIMENSOES]
    )
    linhas = [CABECALHO + "\\begin{tabular}{|l|r|" + "r|" * len(DIMENSOES) + "}\n\\hline",
              cabecalho + " \\\\\n\\hline"]
    for comparacao in ("C5-C3", "C6-C4"):
        score = indice[(comparacao, "score_total")]
        celulas = [comparacao.replace("-", "$-$"),
                   f"{score['n_validos']} de {score['n_total']}"]
        for campo, _ in DIMENSOES:
            celulas.append(decimal(indice[(comparacao, campo)]["media"]))
        linhas.append(" & ".join(celulas) + " \\\\\n\\hline")
    linhas.append("\\end{tabular}\n")
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resumo", type=Path,
                        default=REPO / "evidencias" / "avaliacao-qualitativa" / "resumo-qualitativa.json")
    parser.add_argument("--saida", type=Path,
                        default=REPO / "monografia" / "figs" / "avaliacao")
    args = parser.parse_args()
    resumo = json.loads(args.resumo.read_text(encoding="utf-8"))
    if resumo.get("n_relatorios") != 300:
        raise SystemExit("o resumo não corresponde aos 300 relatórios congelados")
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "qualitativa-condicoes.tex").write_text(tabela_condicoes(resumo), encoding="utf-8")
    (args.saida / "qualitativa-deltas.tex").write_text(tabela_deltas(resumo), encoding="utf-8")
    print(json.dumps({"estado": "concluida", "n_relatorios": resumo["n_relatorios"],
                      "n_scores_validos": resumo.get("n_scores_validos")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
