#!/usr/bin/env python3
"""Gera figuras PGFPlots para pdfLaTeX a partir da avaliação, sem dependências."""

import argparse
import csv
import json
import statistics
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CORES = ("blue!75!black", "cyan!65!black", "green!50!black",
         "orange!80!black", "red!65!black", "violet!80!black")


def numero(valor):
    return format(float(valor), ".8f")


def eixo(opcoes, series):
    return ("% Gerado por scripts/gerar-figuras-monografia.py; não editar.\n"
            "\\begin{tikzpicture}\n\\begin{axis}[\n"
            "width=0.96\\textwidth,height=6.4cm,\n"
            "tick label style={font=\\small},label style={font=\\small},\n"
            "legend style={font=\\small,at={(0.5,-0.22)},anchor=north,"
            "legend columns=3,draw=none,"
            "/tikz/every even column/.append style={column sep=8pt}},\n"
            "ymajorgrids=true,grid style={black!12},\n"
            + opcoes + "\n]\n" + "\n".join(series)
            + "\n\\end{axis}\n\\end{tikzpicture}\n")


def metricas(linhas, campos):
    series = []
    for indice, (campo, rotulo) in enumerate(campos):
        pontos = []
        for x, item in enumerate(linhas, 1):
            valor = item[campo] * 100
            menos = valor - item[campo + "_ic95_inferior"] * 100
            mais = item[campo + "_ic95_superior"] * 100 - valor
            pontos.append("(" + numero(x + (indice - (len(campos)-1)/2)*0.13)
                          + "," + numero(valor) + ") += (0," + numero(mais)
                          + ") -= (0," + numero(menos) + ")")
        marca = ("*", "square*", "triangle*")[indice]
        series.append("\\addplot+[only marks,mark=" + marca + ",color="
                      + CORES[indice] + ",error bars/.cd,y dir=both,y explicit] "
                      "coordinates {" + " ".join(pontos) + "};\n"
                      "\\addlegendentry{" + rotulo + "}")
    return eixo("xmin=0.5,xmax=6.5,ymin=0,ymax=100,ylabel={Percentual (\\%)},"
                "xtick={1,2,3,4,5,6},xticklabels={C1,C2,C3,C4,C5,C6}", series)


def estabilidade(linhas):
    series = []
    for freq in range(4):
        pontos = ["(" + str(x) + "," + numero(next(
            item["proporcao"] * 100 for item in linhas
            if item["condicao"] == cond and item["frequencia"] == freq)) + ")"
            for x, cond in enumerate(("C3", "C4", "C5", "C6"), 1)]
        series.append("\\addplot+[fill=" + ("black!25", "orange!40", "cyan!45", "green!55")[freq]
                      + ",draw=black!50] coordinates {" + " ".join(pontos) + "};\n"
                      "\\addlegendentry{" + str(freq) + " de 3}")
    return eixo("ybar stacked,bar width=22pt,xmin=0.5,xmax=4.5,ymin=0,ymax=100,"
                "ylabel={Vulnerabilidades (\\%)},xtick={1,2,3,4},"
                "xticklabels={C3,C4,C5,C6},legend columns=4", series)


def caixas(linhas, campo, rotulo):
    validas = [item for item in linhas if item[campo]["n"]]
    series = []
    for x, item in enumerate(validas, 1):
        dados = item[campo]
        parametros = ",".join(chave + "=" + numero(dados[origem]) for chave, origem in
                              (("lower whisker", "minimo"), ("lower quartile", "q1"),
                               ("median", "mediana"), ("upper quartile", "q3"),
                               ("upper whisker", "maximo")))
        series.append("\\addplot+[boxplot prepared={draw position=" + str(x) + ","
                      + parametros + "},fill=" + CORES[int(item["condicao"][1])-1]
                      + ",fill opacity=0.4,draw=black] coordinates {};")
    return eixo("boxplot/draw direction=y,ymin=0,ylabel={" + rotulo + "},xtick={"
                + ",".join(str(x) for x in range(1, len(validas)+1))
                + "},xticklabels={" + ",".join(item["condicao"] for item in validas)
                + "},xmin=0.5,xmax=" + str(len(validas)+0.5), series)


def grupos(grupos_dados, campos, rotulo, escala=100, maximo=100):
    series = []
    for indice, (campo, legenda) in enumerate(campos):
        series.append("\\addplot+[ybar,fill=" + CORES[indice] + "] coordinates {"
                      + " ".join("(" + str(x) + "," + numero(item[campo]*escala) + ")"
                                 for x, item in enumerate(grupos_dados, 1)) + "};\n"
                      "\\addlegendentry{" + legenda + "}")
    return eixo("ybar,bar width=5pt,ymin=0,ymax=" + str(maximo) + ",ylabel={" + rotulo + "},"
                "xtick={1,2,3,4,5,6},xticklabels={C1,C2,C3,C4,C5,C6},"
                "enlarge x limits=0.1,legend columns=2", series)


def figuras_qualitativas(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        dados = list(csv.DictReader(arquivo))
    condicoes = ("C1", "C2", "C3", "C4", "C5", "C6")
    def media(condicao, recorte, dimensao):
        linha = next(item for item in dados if item["condicao"] == condicao
                     and item["tipo_recorte"] == recorte and item["dimensao"] == dimensao)
        if not linha["media"]:
            raise ValueError("Não há média válida para figura: " + condicao + "/" + dimensao)
        return float(linha["media"])
    scores = [{recorte: media(condicao, recorte, "score_total")
               for recorte in ("total", "comum")} for condicao in condicoes]
    campos = [("correcao_tecnica", "Correção técnica"), ("localizacao", "Localização"),
              ("acionabilidade", "Acionabilidade"), ("clareza_total", "Clareza (0--5)")]
    dimensoes = [{campo: media(condicao, "comum", campo) for campo, _ in campos}
                for condicao in condicoes]
    return {
        "qualidade-score.tex": grupos(scores, [("total", "Amostra completa"), ("comum", "Recorte comum")],
                                      "Score médio (0--100)", escala=1),
        "qualidade-dimensoes.tex": grupos(dimensoes, campos, "Pontuação média", escala=1, maximo=5),
    }


def pareadas(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        dados = list(csv.DictReader(arquivo))
    series = ["\\addplot[black!50,dashed,forget plot] coordinates {(0.5,0) (3.5,0)};"]
    for i, comparacao in enumerate(("C5-C3", "C6-C4")):
        pontos = []
        for x, campo in enumerate(("precision", "recall", "f3"), 1):
            item = next(item for item in dados if item["comparacao"] == comparacao and item["metrica"] == campo)
            valor = float(item["delta"]) * 100
            pontos.append("(" + numero(x + (i-0.5)*0.15) + "," + numero(valor)
                          + ") += (0," + numero(float(item["ic95_superior"])*100-valor)
                          + ") -= (0," + numero(valor-float(item["ic95_inferior"])*100) + ")")
        series.append("\\addplot+[only marks,color=" + CORES[i]
                      + ",error bars/.cd,y dir=both,y explicit] coordinates {"
                      + " ".join(pontos) + "};\n\\addlegendentry{" + comparacao + "}")
    return eixo("xmin=0.5,xmax=3.5,ylabel={Diferença (pontos percentuais)},"
                "xtick={1,2,3},xticklabels={Precisão,Recall,F3}", series)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dados", type=Path, default=REPO / "evidencias" / "avaliacao")
    parser.add_argument("--saida", type=Path, default=REPO / "monografia" / "figs" / "avaliacao")
    args = parser.parse_args()
    resumo = json.loads((args.dados / "resumo.json").read_text(encoding="utf-8"))
    metricas_condicoes = resumo["metricas_condicoes"]
    figuras = {
        "deteccao-precisao-recall-ic95.tex": metricas(metricas_condicoes, [("precision", "Precisão"), ("recall", "Recall")]),
        "deteccao-fscores-ic95.tex": metricas(metricas_condicoes, [("f1", "F1"), ("f2", "F2"), ("f3", "F3")]),
        "taxa-falsos-positivos-ic95.tex": metricas(metricas_condicoes, [("fpr", "Taxa de falsos positivos")]),
        "estabilidade-ia.tex": estabilidade(resumo["estabilidade"]),
        "tempo-execucao.tex": caixas(resumo["operacional"], "duracao_segundos", "Tempo (segundos)"),
        "tokens-ia.tex": caixas(resumo["operacional"], "tokens_total", "Tokens totais informados"),
        "comparacoes-pareadas.tex": pareadas(args.dados / "comparacoes-pareadas.csv"),
    }
    with (args.dados / "metricas-por-severidade.csv").open(encoding="utf-8-sig", newline="") as arquivo:
        severidade = list(csv.DictReader(arquivo))
    campos = [("low", "Baixa"), ("medium", "Média"), ("high", "Alta"), ("critical", "Crítica")]
    linhas = [{campo: statistics.mean(float(item["recall"]) for item in severidade
                                     if item["condicao"] == cond and item["severidade"] == campo)
               for campo, _ in campos} for cond in ("C1", "C2", "C3", "C4", "C5", "C6")]
    figuras["recall-severidade.tex"] = grupos(linhas, campos, "Recall (\\%)")
    campos = [("concordancia_exata_rotulados", "Concordância exata"),
              ("concordancia_uma_categoria_rotulados", "Tolerância de uma categoria")]
    linhas = [{campo: statistics.mean(item[campo] for item in resumo["priorizacao"]
                                     if item["condicao"] == cond)
               for campo, _ in campos} for cond in ("C1", "C2", "C3", "C4", "C5", "C6")]
    figuras["priorizacao.tex"] = grupos(linhas, campos, "Concordância entre TPs (\\%)")
    resumo_qualitativo = args.dados.parent / "avaliacao-qualitativa" / "resumo-dimensoes.csv"
    if resumo_qualitativo.exists():
        figuras.update(figuras_qualitativas(resumo_qualitativo))
    args.saida.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in figuras.items():
        (args.saida / nome).write_text(conteudo, encoding="utf-8")
    print(json.dumps({"figuras": len(figuras), "saida": str(args.saida)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
