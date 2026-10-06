"""Gráficos SVG vetoriais a partir dos artefatos da avaliação."""

from __future__ import annotations

import csv
import html
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


CORES = {
    "C1": "#4477AA",
    "C2": "#66CCEE",
    "C3": "#228833",
    "C4": "#CCBB44",
    "C5": "#EE6677",
    "C6": "#AA3377",
}
CONDICOES = tuple(CORES)


def _texto(texto: Any, x: float, y: float, tamanho: int = 13, ancora: str = "start", peso: str = "normal") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{ancora}" '
        f'font-family="Arial, sans-serif" font-size="{tamanho}" font-weight="{peso}" '
        f'fill="#222">{html.escape(str(texto))}</text>'
    )


def _svg(largura: int, altura: int, elementos: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img">'
        '<rect width="100%" height="100%" fill="white"/>'
        + "".join(elementos)
        + "</svg>\n"
    )


def _marcador(x: float, y: float, indice: int, cor: str) -> str:
    tipo = indice % 3
    if tipo == 0:
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{cor}" stroke="white" stroke-width="1"/>'
    if tipo == 1:
        return f'<rect x="{x-5:.1f}" y="{y-5:.1f}" width="10" height="10" fill="{cor}" stroke="white" stroke-width="1"/>'
    pontos = f"{x:.1f},{y-6:.1f} {x-6:.1f},{y+5:.1f} {x+6:.1f},{y+5:.1f}"
    return f'<polygon points="{pontos}" fill="{cor}" stroke="white" stroke-width="1"/>'


def _eixos_percentuais(elementos: list[str], x0: float, y0: float, largura: float, altura: float) -> None:
    for indice in range(6):
        valor = indice / 5
        y = y0 + altura - valor * altura
        elementos.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+largura}" y2="{y:.1f}" stroke="#dddddd"/>')
        elementos.append(_texto(f"{valor*100:.0f}%", x0 - 10, y + 4, 11, "end"))
    elementos.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0+altura}" stroke="#444"/>')
    elementos.append(f'<line x1="{x0}" y1="{y0+altura}" x2="{x0+largura}" y2="{y0+altura}" stroke="#444"/>')


def grafico_metricas(
    resumo: list[dict[str, Any]], metricas: list[tuple[str, str]], titulo: str
) -> str:
    largura, altura = 960, 500
    x0, y0, area_largura, area_altura = 80, 70, 830, 330
    elementos = [_texto(titulo, largura / 2, 30, 19, "middle", "bold")]
    _eixos_percentuais(elementos, x0, y0, area_largura, area_altura)
    passo = area_largura / len(CONDICOES)
    deslocamentos = [
        (indice - (len(metricas) - 1) / 2) * 18
        for indice in range(len(metricas))
    ]
    for indice_condicao, condicao in enumerate(CONDICOES):
        item = next(registro for registro in resumo if registro["condicao"] == condicao)
        centro = x0 + passo * (indice_condicao + 0.5)
        elementos.append(_texto(condicao, centro, y0 + area_altura + 25, 13, "middle", "bold"))
        for indice_metrica, (chave, _rotulo) in enumerate(metricas):
            x = centro + deslocamentos[indice_metrica]
            valor = float(item[chave])
            inferior = float(item[f"{chave}_ic95_inferior"])
            superior = float(item[f"{chave}_ic95_superior"])
            y = y0 + area_altura * (1 - valor)
            y_inf = y0 + area_altura * (1 - inferior)
            y_sup = y0 + area_altura * (1 - superior)
            cor = CORES[condicao]
            elementos.extend(
                (
                    f'<line x1="{x:.1f}" y1="{y_sup:.1f}" x2="{x:.1f}" y2="{y_inf:.1f}" stroke="{cor}" stroke-width="2"/>',
                    f'<line x1="{x-5:.1f}" y1="{y_sup:.1f}" x2="{x+5:.1f}" y2="{y_sup:.1f}" stroke="{cor}" stroke-width="2"/>',
                    f'<line x1="{x-5:.1f}" y1="{y_inf:.1f}" x2="{x+5:.1f}" y2="{y_inf:.1f}" stroke="{cor}" stroke-width="2"/>',
                    _marcador(x, y, indice_metrica, cor),
                )
            )
    legenda_x = 260
    for indice, (_chave, rotulo) in enumerate(metricas):
        x = legenda_x + indice * 180
        elementos.append(_marcador(x, 455, indice, "#555"))
        elementos.append(_texto(rotulo, x + 12, 460, 12))
    elementos.append(_texto("Ponto: estimativa; haste: IC95% por bootstrap de repositórios.", largura / 2, 485, 11, "middle"))
    return _svg(largura, altura, elementos)


def grafico_estabilidade(linhas: list[dict[str, Any]]) -> str:
    largura, altura = 850, 470
    x0, y0, area_largura, area_altura = 80, 65, 700, 310
    elementos = [_texto("Estabilidade da detecção nas três repetições de IA", largura / 2, 30, 19, "middle", "bold")]
    _eixos_percentuais(elementos, x0, y0, area_largura, area_altura)
    cores_freq = ("#D73027", "#FC8D59", "#91CF60", "#1A9850")
    condicoes = ("C3", "C4", "C5", "C6")
    largura_barra = 90
    passo = area_largura / len(condicoes)
    for indice, condicao in enumerate(condicoes):
        x = x0 + passo * (indice + 0.5) - largura_barra / 2
        acumulado = 0.0
        for frequencia in range(4):
            linha = next(item for item in linhas if item["condicao"] == condicao and int(item["frequencia"]) == frequencia)
            proporcao = float(linha["proporcao"])
            h = proporcao * area_altura
            y = y0 + area_altura - (acumulado + proporcao) * area_altura
            elementos.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{largura_barra}" height="{h:.1f}" fill="{cores_freq[frequencia]}"/>')
            if h >= 23:
                elementos.append(_texto(f"{proporcao*100:.1f}%", x + largura_barra / 2, y + h / 2 + 4, 11, "middle"))
            acumulado += proporcao
        elementos.append(_texto(condicao, x + largura_barra / 2, y0 + area_altura + 25, 13, "middle", "bold"))
    for frequencia in range(4):
        x = 175 + frequencia * 155
        elementos.append(f'<rect x="{x}" y="420" width="14" height="14" fill="{cores_freq[frequencia]}"/>')
        elementos.append(_texto(f"{frequencia}/3 detecções", x + 20, 432, 11))
    return _svg(largura, altura, elementos)


def grafico_box_resumo(
    operacional: list[dict[str, Any]], grupo: str, titulo: str, condicoes: tuple[str, ...]
) -> str:
    largura, altura = 900, 470
    x0, y0, area_largura, area_altura = 85, 65, 750, 310
    valores = [
        float(item[grupo]["maximo"])
        for item in operacional
        if item["condicao"] in condicoes and item[grupo]["maximo"] is not None
    ]
    maximo = max(valores) if valores else 1.0
    elementos = [_texto(titulo, largura / 2, 30, 19, "middle", "bold")]
    for indice in range(6):
        valor = maximo * indice / 5
        y = y0 + area_altura - area_altura * indice / 5
        elementos.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0+area_largura}" y2="{y:.1f}" stroke="#ddd"/>')
        elementos.append(_texto(f"{valor:,.0f}".replace(",", "."), x0 - 10, y + 4, 11, "end"))
    passo = area_largura / len(condicoes)
    for indice, condicao in enumerate(condicoes):
        item = next(registro for registro in operacional if registro["condicao"] == condicao)[grupo]
        centro = x0 + passo * (indice + 0.5)
        minimo, q1, mediana, q3, max_local = (float(item[chave]) for chave in ("minimo", "q1", "mediana", "q3", "maximo"))
        y_val = lambda valor: y0 + area_altura * (1 - valor / maximo)
        elementos.extend(
            (
                f'<line x1="{centro:.1f}" y1="{y_val(max_local):.1f}" x2="{centro:.1f}" y2="{y_val(minimo):.1f}" stroke="{CORES[condicao]}" stroke-width="2"/>',
                f'<rect x="{centro-28:.1f}" y="{y_val(q3):.1f}" width="56" height="{max(1, y_val(q1)-y_val(q3)):.1f}" fill="{CORES[condicao]}" fill-opacity=".65" stroke="{CORES[condicao]}"/>',
                f'<line x1="{centro-28:.1f}" y1="{y_val(mediana):.1f}" x2="{centro+28:.1f}" y2="{y_val(mediana):.1f}" stroke="#111" stroke-width="2"/>',
                f'<line x1="{centro-12:.1f}" y1="{y_val(max_local):.1f}" x2="{centro+12:.1f}" y2="{y_val(max_local):.1f}" stroke="{CORES[condicao]}"/>',
                f'<line x1="{centro-12:.1f}" y1="{y_val(minimo):.1f}" x2="{centro+12:.1f}" y2="{y_val(minimo):.1f}" stroke="{CORES[condicao]}"/>',
            )
        )
        elementos.append(_texto(condicao, centro, y0 + area_altura + 25, 13, "middle", "bold"))
    elementos.append(_texto("Caixa: Q1–Q3; linha: mediana; hastes: mínimo–máximo.", largura / 2, 445, 11, "middle"))
    return _svg(largura, altura, elementos)


def _cor_calor(valor: float) -> str:
    valor = max(0.0, min(1.0, valor))
    inicio = (247, 252, 245)
    fim = (35, 139, 69)
    rgb = tuple(round(inicio[i] + (fim[i] - inicio[i]) * valor) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def grafico_recall_severidade(caminho_csv: Path) -> str:
    grupos: dict[tuple[str, str], list[float]] = defaultdict(list)
    with caminho_csv.open(encoding="utf-8-sig", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            grupos[(linha["condicao"], linha["severidade"])].append(float(linha["recall"]))
    severidades = ("low", "medium", "high", "critical")
    rotulos = {"low": "Baixa", "medium": "Média", "high": "Alta", "critical": "Crítica"}
    largura, altura = 820, 460
    x0, y0, celula_w, celula_h = 150, 75, 100, 55
    elementos = [_texto("Recall médio por severidade do ground truth", largura / 2, 30, 19, "middle", "bold")]
    for coluna, severidade in enumerate(severidades):
        elementos.append(_texto(rotulos[severidade], x0 + coluna * celula_w + celula_w / 2, 60, 12, "middle", "bold"))
    for linha_indice, condicao in enumerate(CONDICOES):
        y = y0 + linha_indice * celula_h
        elementos.append(_texto(condicao, x0 - 18, y + 34, 13, "end", "bold"))
        for coluna, severidade in enumerate(severidades):
            valores = grupos.get((condicao, severidade), [])
            valor = statistics.fmean(valores) if valores else 0.0
            x = x0 + coluna * celula_w
            elementos.append(f'<rect x="{x}" y="{y}" width="{celula_w}" height="{celula_h}" fill="{_cor_calor(valor)}" stroke="white"/>')
            elementos.append(_texto(f"{valor*100:.1f}%", x + celula_w / 2, y + 34, 12, "middle"))
    elementos.append(_texto("C3–C6: média das três repetições; C1–C2: execução única.", largura / 2, 430, 11, "middle"))
    return _svg(largura, altura, elementos)


def grafico_priorizacao(linhas: list[dict[str, Any]]) -> str:
    grupos: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in linhas:
        grupos[item["condicao"]].append(item)
    resumo = []
    for condicao in CONDICOES:
        itens = grupos[condicao]
        resumo.append(
            {
                "condicao": condicao,
                "cobertura": statistics.fmean(float(item["cobertura"]) for item in itens),
                "exata": statistics.fmean(float(item["concordancia_exata_rotulados"]) for item in itens),
                "tolerante": statistics.fmean(float(item["concordancia_uma_categoria_rotulados"]) for item in itens),
            }
        )
    falso_resumo = []
    for item in resumo:
        falso_resumo.append(
            {
                "condicao": item["condicao"],
                "cobertura": item["cobertura"],
                "cobertura_ic95_inferior": item["cobertura"],
                "cobertura_ic95_superior": item["cobertura"],
                "exata": item["exata"],
                "exata_ic95_inferior": item["exata"],
                "exata_ic95_superior": item["exata"],
                "tolerante": item["tolerante"],
                "tolerante_ic95_inferior": item["tolerante"],
                "tolerante_ic95_superior": item["tolerante"],
            }
        )
    return grafico_metricas(
        falso_resumo,
        [("cobertura", "Cobertura"), ("exata", "Concordância exata"), ("tolerante", "Tolerância ±1")],
        "Cobertura e concordância da priorização",
    ).replace("Ponto: estimativa; haste: IC95% por bootstrap de repositórios.", "C3–C6: média das três repetições; concordância calculada entre TPs rotulados.")


def gerar_graficos(dados: Path, saida: Path) -> list[Path]:
    resumo = json.loads((dados / "resumo.json").read_text(encoding="utf-8"))
    saida.mkdir(parents=True, exist_ok=True)
    artefatos = {
        "deteccao-fscores-ic95.svg": grafico_metricas(
            resumo["metricas_condicoes"], [("f1", "F1"), ("f2", "F2"), ("f3", "F3")], "F-scores por condição"
        ),
        "deteccao-precisao-recall-ic95.svg": grafico_metricas(
            resumo["metricas_condicoes"], [("precision", "Precisão"), ("recall", "Recall")], "Precisão e recall por condição"
        ),
        "taxa-falsos-positivos-ic95.svg": grafico_metricas(
            resumo["metricas_condicoes"], [("fpr", "Taxa de falsos positivos")], "Taxa de falsos positivos por condição"
        ),
        "estabilidade-ia.svg": grafico_estabilidade(resumo["estabilidade"]),
        "tempo-execucao.svg": grafico_box_resumo(
            resumo["operacional"], "duracao_segundos", "Tempo de execução por unidade (segundos)", CONDICOES
        ),
        "tokens-ia.svg": grafico_box_resumo(
            resumo["operacional"], "tokens_total", "Tokens totais informados por execução de IA", ("C3", "C4", "C5", "C6")
        ),
        "recall-severidade.svg": grafico_recall_severidade(dados / "metricas-por-severidade.csv"),
        "priorizacao.svg": grafico_priorizacao(resumo["priorizacao"]),
    }
    caminhos = []
    for nome, conteudo in artefatos.items():
        caminho = saida / nome
        caminho.write_text(conteudo, encoding="utf-8")
        caminhos.append(caminho)
    return caminhos
