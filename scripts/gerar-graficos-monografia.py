#!/usr/bin/env python3
"""Gera os gráficos da monografia em SVG e PDF a partir das evidências da avaliação.

O SVG é o arquivo principal (edição e pôster); o PDF vetorial é a cópia incluída
pelo pdfLaTeX. Cada gráfico responde a uma pergunta e tem como título a mensagem
sustentada pelos dados, calculada aqui a partir dos próprios valores.
"""

import argparse
import csv
import json
import random
import statistics
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, ScalarFormatter  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CONDICOES = ("C1", "C2", "C3", "C4", "C5", "C6")
NOMES = {"C1": "C1 · Bandit", "C2": "C2 · Semgrep", "C3": "C3 · Cursor", "C4": "C4 · Codex",
         "C5": "C5 · Cursor + SAST", "C6": "C6 · Codex + SAST"}
COR = {"C1": "#F6C26B", "C2": "#E8A33D", "C3": "#8AB4F8", "C4": "#4A86E8",
       "C5": "#93D3A2", "C6": "#3FA35B"}
HACHURA = {"C1": "", "C2": "///", "C3": "", "C4": "///", "C5": "", "C6": "///"}
MARCADOR = {"C1": "s", "C2": "s", "C3": "o", "C4": "o", "C5": "^", "C6": "^"}
TEXTO = "#202124"
CINZA = "#5F6368"
LARGURA = 6.3

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 10,
    "axes.labelsize": 8.5, "axes.edgecolor": "#3C4043", "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True,
    "axes.grid": True, "grid.color": "#DADCE0", "grid.linestyle": "--", "grid.linewidth": 0.6,
    "xtick.color": "#3C4043", "ytick.color": "#3C4043", "xtick.direction": "out",
    "ytick.direction": "out", "legend.frameon": False, "legend.fontsize": 8,
    "hatch.color": "#3C4043", "hatch.linewidth": 0.6, "svg.fonttype": "none",
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
})


CURTOS = {"C1": "C1\nBandit", "C2": "C2\nSemgrep", "C3": "C3\nCursor", "C4": "C4\nCodex",
          "C5": "C5\nCursor\n+ SAST", "C6": "C6\nCodex\n+ SAST"}


def br(valor, casas=1):
    return format(valor, "." + str(casas) + "f").replace(".", ",").replace("-", "−")


def sinal(valor, casas=2):
    return ("+" if valor > 0 else "") + br(valor, casas)


def titulo(figura, mensagem, explicacao, folga=0.12):
    linhas = textwrap.wrap(explicacao, 104)
    altura = figura.get_figheight()
    figura.text(0.0, 1.0, mensagem, fontsize=10.5, fontweight="bold", color=TEXTO,
                ha="left", va="bottom", transform=figura.transFigure)
    figura.text(0.0, 1.0 - 0.04 / altura, "\n".join(linhas), fontsize=8.3, color=CINZA,
                ha="left", va="top", linespacing=1.35, transform=figura.transFigure)
    figura.subplots_adjust(top=1.0 - (0.1 + 0.155 * len(linhas) + folga) / altura)


def virgulas(figura):
    for eixo in figura.axes:
        for eixo_dado, escala in ((eixo.xaxis, eixo.get_xscale()), (eixo.yaxis, eixo.get_yscale())):
            if escala == "log":
                eixo_dado.set_major_formatter(FuncFormatter(
                    lambda v, _: (format(int(v / 1000)) + " mil") if v >= 1000 else format(v, "g").replace(".", ",")))
            elif isinstance(eixo_dado.get_major_formatter(), ScalarFormatter):
                eixo_dado.set_major_formatter(FuncFormatter(
                    lambda v, _: format(v, "g").replace(".", ",").replace("-", "−")))


def rotulos_com_guias(eixo, pontos, posicoes, tamanho=7.8):
    for (x, y, texto), (tx, ty) in zip(pontos, posicoes):
        eixo.annotate(texto, (x, y), xytext=(tx, ty), textcoords="data", fontsize=tamanho,
                      color=TEXTO, va="center",
                      arrowprops={"arrowstyle": "-", "color": "#9AA0A6", "linewidth": 0.7,
                                  "shrinkA": 2, "shrinkB": 5})


def ler_csv(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


class Dados:
    def __init__(self, raiz):
        avaliacao = raiz / "evidencias" / "avaliacao"
        qualitativa = raiz / "evidencias" / "avaliacao-qualitativa"
        self.resumo = json.loads((avaliacao / "resumo.json").read_text(encoding="utf-8"))
        self.metricas = {m["condicao"]: m for m in self.resumo["metricas_condicoes"]}
        self.pareadas = ler_csv(avaliacao / "comparacoes-pareadas.csv")
        self.severidade = ler_csv(avaliacao / "metricas-por-severidade.csv")
        self.notas = ler_csv(qualitativa / "pontuacoes-condicoes.csv")
        self.deltas = ler_csv(qualitativa / "deltas-comuns.csv")
        self.dimensoes = ler_csv(qualitativa / "resumo-dimensoes.csv")

    def media_dimensao(self, condicao, dimensao, recorte="total"):
        return float(next(d["media"] for d in self.dimensoes if d["condicao"] == condicao
                          and d["tipo_recorte"] == recorte and d["dimensao"] == dimensao))


def precisao_recall(dados):
    figura, eixo = plt.subplots(figsize=(LARGURA, 3.6))
    for f3 in (0.2, 0.3, 0.4):
        pontos = [(r / 1000, f3 * (r / 1000) / (10 * r / 1000 - 9 * f3))
                  for r in range(int(900 * f3) + 2, 1000)]
        pontos = [(r, p) for r, p in pontos if 0 < p <= 1]
        eixo.plot([r * 100 for r, _ in pontos], [p * 100 for _, p in pontos], color="#BDC1C6",
                  linestyle=(0, (4, 3)), linewidth=0.8, zorder=1)
        p_rotulo = 0.5
        r_rotulo = 9 * f3 * p_rotulo / (10 * p_rotulo - f3)
        eixo.text(r_rotulo * 100 + 0.5, p_rotulo * 100, "F3 = " + br(f3, 1), fontsize=7,
                  color="#80868B", va="center")
    ordem_ia = sorted(CONDICOES[2:], key=lambda c: -dados.metricas[c]["precision"])
    posicoes = {"C1": (7, 9), "C2": (31, 38)}
    posicoes.update({c: (35, 98 - 8 * i) for i, c in enumerate(ordem_ia)})
    rotulos = []
    for c in CONDICOES:
        m = dados.metricas[c]
        x, y = m["recall"] * 100, m["precision"] * 100
        eixo.errorbar(x, y, xerr=[[x - m["recall_ic95_inferior"] * 100], [m["recall_ic95_superior"] * 100 - x]],
                      yerr=[[y - m["precision_ic95_inferior"] * 100], [m["precision_ic95_superior"] * 100 - y]],
                      fmt="none", ecolor="#3C4043", elinewidth=0.8, capsize=2.5, zorder=2)
        eixo.scatter(x, y, s=70, marker=MARCADOR[c], color=COR[c], edgecolor="#202124",
                     linewidth=0.8, hatch=HACHURA[c], zorder=3)
        rotulos.append((x, y, NOMES[c] + " (" + br(y) + "%; " + br(x) + "%)"))
    rotulos_com_guias(eixo, rotulos, [posicoes[c] for c in CONDICOES])
    eixo.set_xlim(0, 50)
    eixo.set_ylim(0, 100)
    eixo.set_xlabel("Recall (%) — vulnerabilidades encontradas")
    eixo.set_ylabel("Precisão (%) — alertas corretos")
    ia = [dados.metricas[c]["precision"] * 100 for c in CONDICOES[2:]]
    recall_max = max(dados.metricas[c]["recall"] for c in CONDICOES) * 100
    titulo(figura, "Agentes de IA trocam cobertura por precisão",
           "Precisão de " + br(min(ia)) + "% a " + br(max(ia)) + "% nas condições de IA, mas recall "
           "máximo de " + br(recall_max) + "%. Cruzes: IC95% por reamostragem de repositórios; "
           "curvas: F3 constante.")
    return figura


def recall_severidade(dados):
    ordem = (("low", "Baixa"), ("medium", "Média"), ("high", "Alta"), ("critical", "Crítica"))
    valores = {(c, s): statistics.mean(float(r["recall"]) for r in dados.severidade
                                       if r["condicao"] == c and r["severidade"] == s) * 100
               for c in CONDICOES for s, _ in ordem}
    figura, eixo = plt.subplots(figsize=(LARGURA, 2.9))
    for i, (s, _) in enumerate(ordem):
        linha = [valores[(c, s)] for c in CONDICOES]
        eixo.plot([min(linha), max(linha)], [i, i], color="#DADCE0", linewidth=5,
                  solid_capstyle="round", zorder=1)
        for c in CONDICOES:
            eixo.scatter(valores[(c, s)], i, s=46, marker=MARCADOR[c], color=COR[c],
                         edgecolor="#202124", linewidth=0.7, hatch=HACHURA[c], zorder=3)
    eixo.set_yticks(range(len(ordem)), [nome for _, nome in ordem])
    eixo.set_xlim(0, 100)
    eixo.set_xlabel("Recall médio nas repetições (%)")
    eixo.grid(axis="y", visible=False)
    eixo.legend(handles=[plt.Line2D([], [], marker=MARCADOR[c], linestyle="", markersize=6.5,
                                    markerfacecolor=COR[c], markeredgecolor="#202124",
                                    label=NOMES[c]) for c in CONDICOES],
                loc="lower right", ncol=2, fontsize=7.5, handletextpad=0.3, columnspacing=0.8)
    criticas = [valores[(c, "critical")] for c in CONDICOES]
    outras_max = max(valores[(c, s)] for c in CONDICOES for s, _ in ordem[:3])
    mensagem = ("Vulnerabilidades críticas são as mais encontradas"
                if min(criticas) > outras_max else "O recall varia conforme a severidade")
    melhor = max(CONDICOES, key=lambda c: valores[(c, "critical")])
    titulo(figura, mensagem, "Recall por severidade de referência. A faixa cinza liga o menor e o "
           "maior valor entre condições; o máximo em críticas é " + br(valores[(melhor, "critical")])
           + "% (" + melhor + ").")
    return figura


def falsos_positivos(dados):
    figura, eixo = plt.subplots(figsize=(LARGURA, 2.8))
    ordem = list(reversed(CONDICOES))
    for i, c in enumerate(ordem):
        m = dados.metricas[c]
        v = m["fpr"] * 100
        eixo.barh(i, v, height=0.62, color=COR[c], edgecolor="#202124", linewidth=0.7,
                  hatch=HACHURA[c], zorder=2)
        eixo.errorbar(v, i, xerr=[[v - m["fpr_ic95_inferior"] * 100], [m["fpr_ic95_superior"] * 100 - v]],
                      fmt="none", ecolor="#202124", elinewidth=0.9, capsize=3, zorder=3)
        eixo.text(m["fpr_ic95_superior"] * 100 + 1.5, i, br(v) + "%", va="center", fontsize=8,
                  color=TEXTO)
    eixo.set_yticks(range(len(ordem)), [NOMES[c] for c in ordem])
    eixo.set_xlim(0, 105)
    eixo.set_xlabel("Taxa de falsos positivos (%) — FP / (FP + TN)")
    eixo.grid(axis="y", visible=False)
    sast = [dados.metricas[c]["fpr"] * 100 for c in CONDICOES[:2]]
    ia = [dados.metricas[c]["fpr"] * 100 for c in CONDICOES[2:]]
    titulo(figura, "No SAST, a taxa de falsos positivos passa de 80%; nos agentes, fica perto de 25%"
           if min(sast) > 80 and max(ia) < 30 else "Taxa de falsos positivos por condição",
           "Taxa de " + br(min(sast)) + "–" + br(max(sast)) + "% no SAST contra " + br(min(ia)) + "–"
           + br(max(ia)) + "% na IA. FP inclui achados sem correspondência; barras: IC95%.")
    return figura


def comparacoes_pareadas(dados):
    metricas = (("precision", "Precisão"), ("recall", "Recall"), ("f3", "F3"))
    figura, eixo = plt.subplots(figsize=(LARGURA, 2.9))
    linhas = []
    for comparacao, cor in (("C5-C3", COR["C5"]), ("C6-C4", COR["C6"])):
        for campo, nome in metricas:
            r = next(x for x in dados.pareadas if x["comparacao"] == comparacao and x["metrica"] == campo)
            linhas.append((comparacao, nome, cor, float(r["delta"]) * 100,
                           float(r["ic95_inferior"]) * 100, float(r["ic95_superior"]) * 100))
    for i, (comparacao, nome, cor, delta, inf, sup) in enumerate(reversed(linhas)):
        eixo.plot([inf, sup], [i, i], color="#202124", linewidth=1.1, zorder=2)
        for limite in (inf, sup):
            eixo.plot([limite, limite], [i - 0.15, i + 0.15], color="#202124", linewidth=1.1, zorder=2)
        eixo.scatter(delta, i, s=55, marker="D", color=cor, edgecolor="#202124", linewidth=0.8, zorder=3)
        eixo.text(10.6, i, sinal(delta) + "  [" + br(inf, 2) + "; " + br(sup, 2) + "]",
                  va="center", fontsize=7.6, color=TEXTO)
    eixo.axvline(0, color=CINZA, linestyle=(0, (4, 3)), linewidth=0.9, zorder=1)
    eixo.set_yticks(range(len(linhas)),
                    [c.replace("-", " − ") + " · " + n for c, n, *_ in reversed(linhas)])
    eixo.set_xlim(-10, 10)
    eixo.set_xticks([-10, -5, 0, 5, 10])
    eixo.text(10.6, len(linhas) - 0.35, "Δ  [IC95%]", fontsize=7.6, color=CINZA)
    eixo.set_xlabel("Diferença pareada (pontos percentuais): condição híbrida − condição isolada")
    eixo.grid(axis="y", visible=False)
    eixo.axhspan(2.5, 5.5, color="#F1F3F4", zorder=0)
    todos_zero = all(inf <= 0 <= sup for *_, inf, sup in linhas)
    titulo(figura, "Fornecer alertas SAST não mudou a detecção de forma conclusiva"
           if todos_zero else "Diferenças pareadas entre condições híbridas e isoladas",
           "Diferença média e IC95% por reamostragem de repositórios"
           + ("; todos os intervalos incluem zero." if todos_zero else "."))
    figura.subplots_adjust(right=0.8)
    return figura


def estabilidade(dados):
    cores = ("#E8EAED", "#D2E3FC", "#8AB4F8", "#1A73E8")
    figura, eixo = plt.subplots(figsize=(LARGURA, 2.6))
    ordem = ("C6", "C5", "C4", "C3")
    tres = {}
    for i, c in enumerate(ordem):
        esquerda = 0
        for f in range(4):
            item = next(e for e in dados.resumo["estabilidade"] if e["condicao"] == c and e["frequencia"] == f)
            largura = item["proporcao"] * 100
            eixo.barh(i, largura, left=esquerda, height=0.62, color=cores[f], edgecolor="white",
                      linewidth=1.2, zorder=2)
            if largura >= 6:
                eixo.text(esquerda + largura / 2, i, br(largura, 0) + "%", ha="center", va="center",
                          fontsize=7.6, color="white" if f == 3 else TEXTO)
            esquerda += largura
            if f == 3:
                tres[c] = (item["entradas"], largura)
    eixo.set_yticks(range(len(ordem)), [NOMES[c] for c in ordem])
    eixo.set_xlim(0, 100)
    eixo.set_xlabel("Vulnerabilidades do benchmark (%)")
    eixo.grid(visible=False)
    eixo.legend(handles=[Patch(facecolor=cores[f], edgecolor="#BDC1C6", label=str(f) + " de 3")
                         for f in range(4)], title="Detectada em", title_fontsize=7.5,
                loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=4, fontsize=7.5)
    melhor = max(tres, key=lambda c: tres[c][0])
    titulo(figura, "Poucas vulnerabilidades são encontradas nas três repetições",
           "No melhor caso, " + melhor + " detectou " + str(tres[melhor][0]) + " das 697 vulnerabilidades "
           "(" + br(tres[melhor][1], 0) + "%) em todas as execuções.")
    return figura


def priorizacao(dados):
    figura, (esquerdo, direito) = plt.subplots(1, 2, figsize=(LARGURA, 2.9), sharey=True)
    ordem = list(reversed(CONDICOES))
    def media(c, campo):
        return statistics.mean(p[campo] for p in dados.resumo["priorizacao"] if p["condicao"] == c)
    for eixo, campo, rotulo, escala, limite in (
            (esquerdo, "kappa_ponderado_quadratico", "Kappa ponderado", 1, 1),
            (direito, "concordancia_exata_rotulados", "Concordância exata (%)", 100, 100)):
        for i, c in enumerate(ordem):
            v = media(c, campo) * escala
            eixo.barh(i, v, height=0.62, color=COR[c], edgecolor="#202124", linewidth=0.7,
                      hatch=HACHURA[c], zorder=2)
            eixo.text(v + limite * 0.02, i, br(v, 2 if escala == 1 else 1) + ("" if escala == 1 else "%"),
                      va="center", fontsize=7.8)
        eixo.set_xlim(0, limite * 1.15)
        eixo.set_xlabel(rotulo)
        eixo.grid(axis="y", visible=False)
    esquerdo.set_yticks(range(len(ordem)), [NOMES[c] for c in ordem])
    kappa_sast = max(media(c, "kappa_ponderado_quadratico") for c in CONDICOES[:2])
    kappa_ia = min(media(c, "kappa_ponderado_quadratico") for c in CONDICOES[2:])
    titulo(figura, "Agentes de IA indicam a severidade mais perto da referência"
           if kappa_ia > kappa_sast else "Concordância da severidade com a referência",
           "Severidade reportada nos verdadeiros positivos contra a do benchmark; média das repetições.")
    figura.subplots_adjust(wspace=0.12)
    return figura


def distribuicao_score(dados):
    figura, eixo = plt.subplots(figsize=(LARGURA, 3.0))
    aleatorio = random.Random(20261005)
    medianas = {}
    for i, c in enumerate(CONDICOES):
        valores = [float(n["score_total"]) for n in dados.notas if n["condicao"] == c and n["score_total"]]
        medianas[c] = statistics.median(valores)
        eixo.boxplot([valores], positions=[i], widths=0.5, whis=(0, 100),
                     showfliers=False, patch_artist=True,
                     boxprops={"facecolor": COR[c], "edgecolor": "#202124", "linewidth": 0.8,
                               "hatch": HACHURA[c], "alpha": 0.85},
                     medianprops={"color": "#202124", "linewidth": 1.4},
                     whiskerprops={"color": "#202124", "linewidth": 0.8},
                     capprops={"color": "#202124", "linewidth": 0.8}, zorder=2)
        eixo.scatter([i + aleatorio.uniform(-0.17, 0.17) for _ in valores], valores, s=7,
                     color="#202124", alpha=0.45, linewidth=0, zorder=3)
        eixo.text(i, 104, br(medianas[c], 1), ha="center", fontsize=7.8, color=TEXTO)
    eixo.set_xticks(range(len(CONDICOES)), [CURTOS[c] for c in CONDICOES])
    eixo.set_ylim(0, 110)
    eixo.set_ylabel("Score qualitativo (0–100)")
    eixo.grid(axis="x", visible=False)
    titulo(figura, "Relatos dos agentes de IA concentram-se no topo da escala de qualidade",
           "Score de cada um dos 50 relatos verdadeiros-positivos por condição; número acima: mediana.")
    return figura


def mapa(eixo, linhas, colunas, valores, normalizados, cmap, formato):
    eixo.imshow(normalizados, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(len(linhas)):
        for j in range(len(colunas)):
            eixo.text(j, i, formato(valores[i][j]), ha="center", va="center", fontsize=8.5,
                      color="white" if normalizados[i][j] > 0.62 else TEXTO)
    eixo.set_xticks(range(len(colunas)), colunas, fontsize=8.3)
    eixo.set_yticks(range(len(linhas)), linhas)
    eixo.tick_params(length=0)
    eixo.xaxis.tick_top()
    eixo.grid(visible=False)
    for lado in eixo.spines.values():
        lado.set_visible(False)
    eixo.set_xticks([x - 0.5 for x in range(1, len(colunas))], minor=True)
    eixo.set_yticks([y - 0.5 for y in range(1, len(linhas))], minor=True)
    eixo.grid(which="minor", color="white", linestyle="-", linewidth=2)
    eixo.tick_params(which="minor", length=0)


AZUIS = LinearSegmentedColormap.from_list("azuis", ["#F1F3F4", "#AECBFA", "#1967D2"])
VERDES = LinearSegmentedColormap.from_list("verdes", ["#F1F3F4", "#A8DAB5", "#137333"])


def mapa_dimensoes(dados):
    campos = (("correcao_tecnica", "Correção técnica", 5), ("localizacao", "Localização", 5),
              ("acionabilidade", "Acionabilidade", 5), ("clareza_total", "Clareza (0–5)", 5))
    valores = [[dados.media_dimensao(c, campo) for campo, _, _ in campos] for c in CONDICOES]
    normalizados = [[(v / 5) if campo == "clareza_total" else (v - 1) / 4
                     for v, (campo, _, _) in zip(linha, campos)] for linha in valores]
    figura, eixo = plt.subplots(figsize=(LARGURA, 3.4))
    mapa(eixo, [NOMES[c] for c in CONDICOES], [r for _, r, _ in campos], valores, normalizados,
         AZUIS, lambda v: br(v, 2))
    acion = [dados.media_dimensao(c, "acionabilidade") for c in CONDICOES]
    titulo(figura, "A diferença entre SAST e IA vem sobretudo da acionabilidade",
           "Média por dimensão, 50 relatos por condição; escala de 1 a 5, exceto clareza (0 a 5). "
           "Acionabilidade: " + br(acion[0], 2) + " e " + br(acion[1], 2) + " no SAST contra "
           + br(min(acion[2:]), 2) + "–" + br(max(acion[2:]), 2) + " na IA.", folga=0.42)
    return figura


def mapa_clareza(dados):
    itens = (("clareza_problema", "Problema"), ("clareza_risco", "Risco"),
             ("clareza_contexto", "Contexto"), ("clareza_concretude", "Concretude"),
             ("clareza_concisao", "Concisão"))
    valores = [[statistics.mean(float(n[campo]) for n in dados.notas if n["condicao"] == c) * 100
                for campo, _ in itens] for c in CONDICOES]
    figura, eixo = plt.subplots(figsize=(LARGURA, 3.4))
    mapa(eixo, [NOMES[c] for c in CONDICOES], [r for _, r in itens], valores,
         [[v / 100 for v in linha] for linha in valores], VERDES, lambda v: br(v, 0) + "%")
    titulo(figura, "Mensagens SAST raramente explicam o risco da falha",
           "Relatos que atendem a cada item do checklist de clareza, 50 por condição. Risco explícito: "
           + br(valores[0][1], 0) + "% em C1 e " + br(valores[1][1], 0) + "% em C2; 100% nas condições de IA.",
           folga=0.42)
    return figura


def deltas_dimensoes(dados):
    campos = (("correcao_tecnica", "Correção técnica"), ("localizacao", "Localização"),
              ("acionabilidade", "Acionabilidade"), ("clareza_total", "Clareza"))
    figura, eixo = plt.subplots(figsize=(LARGURA, 3.0))
    aleatorio = random.Random(7)
    largura = 0.34
    medias = {}
    for k, comparacao in enumerate(("C5-C3", "C6-C4")):
        cor = COR["C5"] if k == 0 else COR["C6"]
        for j, (campo, _) in enumerate(campos):
            valores = [float(r["delta"]) for r in dados.deltas
                       if r["comparacao"] == comparacao and r["dimensao"] == campo]
            media = statistics.mean(valores)
            medias[(comparacao, campo)] = media
            x = j + (k - 0.5) * largura
            eixo.bar(x, media, width=largura * 0.9, color=cor, edgecolor="#202124", linewidth=0.7,
                     hatch="" if k == 0 else "///", zorder=2)
            eixo.scatter([x + aleatorio.uniform(-0.09, 0.09) for _ in valores],
                         [v + aleatorio.uniform(-0.06, 0.06) for v in valores], s=6, color="#202124",
                         alpha=0.4, linewidth=0, zorder=3)
            eixo.text(x, max(media, 0) + 0.08 if media >= 0 else media - 0.25,
                      sinal(media), ha="center", fontsize=7.4)
    eixo.axhline(0, color="#3C4043", linewidth=0.8, zorder=1)
    eixo.set_xticks(range(len(campos)), [n for _, n in campos])
    eixo.set_ylabel("Diferença por relato (pontos da escala)")
    eixo.set_ylim(-1.6, 3.4)
    eixo.grid(axis="x", visible=False)
    eixo.legend(handles=[Patch(facecolor=COR["C5"], edgecolor="#202124", label="C5 − C3 (Cursor)"),
                         Patch(facecolor=COR["C6"], edgecolor="#202124", hatch="///",
                               label="C6 − C4 (Codex)")], loc="upper right")
    melhor = max(campos, key=lambda c: min(medias[(x, c[0])] for x in ("C5-C3", "C6-C4")))
    titulo(figura, "Com alertas SAST, os agentes apontam melhor a linha vulnerável"
           if melhor[0] == "localizacao" else "Diferenças entre condição híbrida e isolada",
           "Recorte comum: 20 vulnerabilidades avaliadas nas seis condições. Barras: média; pontos: "
           "diferença em cada vulnerabilidade. Descritivo, sem inferência.")
    return figura


def operacional(dados):
    figura, (tempo, tokens) = plt.subplots(1, 2, figsize=(LARGURA, 2.9))
    def caixas(eixo, campo, condicoes, rotulo):
        estatisticas = []
        for c in condicoes:
            d = next(o for o in dados.resumo["operacional"] if o["condicao"] == c)[campo]
            estatisticas.append({"label": c, "whislo": d["minimo"], "q1": d["q1"], "med": d["mediana"],
                                 "q3": d["q3"], "whishi": d["maximo"], "fliers": []})
        partes = eixo.bxp(estatisticas, patch_artist=True, widths=0.55, showfliers=False,
                          medianprops={"color": "#202124", "linewidth": 1.3},
                          whiskerprops={"color": "#202124", "linewidth": 0.8},
                          capprops={"color": "#202124", "linewidth": 0.8})
        for caixa, c in zip(partes["boxes"], condicoes):
            caixa.set(facecolor=COR[c], edgecolor="#202124", linewidth=0.8, hatch=HACHURA[c])
        eixo.set_yscale("log")
        eixo.set_ylabel(rotulo)
        eixo.grid(axis="x", visible=False)
        return {e["label"]: e["med"] for e in estatisticas}
    medianas_tempo = caixas(tempo, "duracao_segundos", CONDICOES, "Tempo por tentativa (s, escala log)")
    medianas_tokens = caixas(tokens, "tokens_total", CONDICOES[2:], "Tokens totais (escala log)")
    tempo.set_title("Tempo", loc="left", fontsize=8.8, color=CINZA)
    tokens.set_title("Tokens (somente IA)", loc="left", fontsize=8.8, color=CINZA)
    outras = [medianas_tempo[c] for c in CONDICOES[1:]]
    tokens_ia = [medianas_tokens[c] for c in CONDICOES[2:]]
    titulo(figura, "O Bandit responde em cerca de 1 s; as demais condições, em dezenas de segundos",
           "Medianas: " + br(medianas_tempo["C1"], 1) + " s no Bandit e " + br(min(outras), 0) + "–"
           + br(max(outras), 0) + " s nas demais; " + br(min(tokens_ia) / 1000, 1) + " mil a "
           + br(max(tokens_ia) / 1000, 1) + " mil tokens nas condições de IA. Tentativas selecionadas.")
    figura.subplots_adjust(wspace=0.32)
    return figura


def sintese(dados):
    figura, eixo = plt.subplots(figsize=(LARGURA, 3.5))
    ordem_ia = sorted(CONDICOES[2:], key=lambda c: -dados.media_dimensao(c, "score_total"))
    posicoes = {"C1": (30, 50), "C2": (36, 68)}
    posicoes.update({c: (27, 100 - 5.5 * i) for i, c in enumerate(ordem_ia)})
    rotulos = []
    for c in CONDICOES:
        m = dados.metricas[c]
        x, y = m["precision"] * 100, dados.media_dimensao(c, "score_total")
        eixo.scatter(x, y, s=m["recall"] * 100 * 9, marker=MARCADOR[c], color=COR[c],
                     edgecolor="#202124", linewidth=0.8, hatch=HACHURA[c], zorder=3)
        rotulos.append((x, y, NOMES[c] + " · score " + br(y) + " · recall " + br(m["recall"] * 100) + "%"))
    rotulos_com_guias(eixo, rotulos, [posicoes[c] for c in CONDICOES], tamanho=7.5)
    eixo.set_xlim(0, 100)
    eixo.set_ylim(40, 102)
    eixo.set_xlabel("Precisão de detecção (%)")
    eixo.set_ylabel("Score qualitativo médio (0–100)")
    recall_max = max(dados.metricas[c]["recall"] for c in CONDICOES) * 100
    titulo(figura, "Mais precisão e melhores relatos, mas cobertura baixa em todas as condições",
           "Cada marcador é uma condição; a área é proporcional ao recall médio, que não passa de "
           + br(recall_max) + "%.")
    return figura


GRAFICOS = {
    "deteccao-precisao-recall": precisao_recall,
    "deteccao-recall-severidade": recall_severidade,
    "deteccao-falsos-positivos": falsos_positivos,
    "hibrido-comparacoes-pareadas": comparacoes_pareadas,
    "estabilidade-repeticoes": estabilidade,
    "priorizacao-severidade": priorizacao,
    "qualidade-distribuicao-score": distribuicao_score,
    "qualidade-dimensoes": mapa_dimensoes,
    "qualidade-clareza": mapa_clareza,
    "hibrido-qualidade-dimensoes": deltas_dimensoes,
    "operacional-tempo-tokens": operacional,
    "sintese-precisao-qualidade": sintese,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=REPO / "monografia" / "figs" / "graficos")
    parser.add_argument("--grafico", choices=tuple(GRAFICOS),
                        help="Regenera somente o gráfico indicado.")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    dados = Dados(REPO)
    selecionados = {args.grafico: GRAFICOS[args.grafico]} if args.grafico else GRAFICOS
    for nome, construir in selecionados.items():
        figura = construir(dados)
        virgulas(figura)
        for extensao in ("svg", "pdf"):
            figura.savefig(args.saida / (nome + "." + extensao), metadata={"Date": None}
                           if extensao == "svg" else {"CreationDate": None})
        plt.close(figura)
    print(json.dumps({"graficos": len(selecionados), "saida": str(args.saida)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
