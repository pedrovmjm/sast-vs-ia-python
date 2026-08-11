#!/usr/bin/env python3
"""Gera dados e gráficos descritivos da linha de base C1/C2.

Não calcula TP/FP/FN: esses valores dependem do avaliador/oracle e pertencem
à etapa posterior de adjudicação. O script usa somente manifestos e achados
normalizados já preservados em resultados/.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def carregar(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tentativas_validas(execucao: Path):
    candidatas = []
    for tentativa in execucao.glob("tentativa-*"):
        manifesto = tentativa / "manifesto.json"
        normalizado = tentativa / "normalizado.json"
        if manifesto.is_file() and normalizado.is_file():
            documento = carregar(manifesto)
            if documento.get("finalidade") == "coleta":
                candidatas.append((int(documento["tentativa"]), tentativa, documento))
    return sorted(candidatas, key=lambda item: item[0])


def coletar(repo: Path):
    linhas = []
    for execucao in sorted((repo / "resultados").glob("C[12]-ALVO-*-R01")):
        tentativas = tentativas_validas(execucao)
        if not tentativas:
            continue
        tentativa, diretorio, manifesto = tentativas[-1]
        normalizado = carregar(diretorio / "normalizado.json")
        achados = normalizado if isinstance(normalizado, list) else normalizado.get("value", [])
        if not isinstance(achados, list):
            raise ValueError(f"normalizado.value inválido: {diretorio}")
        linhas.append(
            {
                "execucao_id": manifesto["execucao_id"],
                "alvo": manifesto["alvo"],
                "condicao": manifesto["condicao"],
                "ferramenta": manifesto["ferramenta"],
                "tentativa": tentativa,
                "estado": manifesto["estado"],
                "duracao_segundos": manifesto["duracao_monotonica_segundos"],
                "achados": len(achados),
                "arquivos_com_achado": len({a["arquivo"] for a in achados}),
                "cwes_distintas": len({a["cwe"] for a in achados if a.get("cwe")}),
            }
        )
    if len(linhas) != 52:
        raise ValueError(f"esperadas 52 execuções C1/C2; encontradas {len(linhas)}")
    return linhas


def escrever_csv(linhas, destino: Path):
    campos = list(linhas[0])
    with destino.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def svg_text(texto: str, x: float, y: float, tamanho: int = 14) -> str:
    seguro = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{tamanho}">{seguro}</text>'


def escrever_graficos(linhas, destino: Path):
    por_condicao = defaultdict(list)
    for linha in linhas:
        por_condicao[linha["condicao"]].append(linha)
    labels = ["C1 — Bandit", "C2 — Semgrep"]
    chaves = ["C1", "C2"]
    cores = ["#355C7D", "#C06C84"]

    totais = [sum(item["achados"] for item in por_condicao[chave]) for chave in chaves]
    escala = max(totais) or 1
    elementos = [svg_text("Achados observados por condição SAST", 70, 28, 18),
                 svg_text("Achados normalizados", 12, 210, 13)]
    for indice, (label, total, cor) in enumerate(zip(labels, totais, cores)):
        x = 120 + indice * 190
        altura = 145 * total / escala
        elementos.append(f'<rect x="{x}" y="{180-altura:.1f}" width="90" height="{altura:.1f}" fill="{cor}"/>')
        elementos.append(svg_text(str(total), x + 35, 170 - altura, 14))
        elementos.append(svg_text(label, x - 15, 205, 13))
    (destino / "sast-achados-por-condicao.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="520" height="230" viewBox="0 0 520 230">'
        + ''.join(elementos) + '<line x1="70" y1="180" x2="480" y2="180" stroke="#333"/></svg>\n',
        encoding="utf-8")

    duracoes = [[item["duracao_segundos"] for item in por_condicao[chave]] for chave in chaves]
    maximo = max(max(valores) for valores in duracoes) or 1
    elementos = [svg_text("Distribuição do tempo de execução por condição SAST", 45, 28, 18),
                 svg_text("Duração (s)", 12, 210, 13)]
    for indice, (label, valores, cor) in enumerate(zip(labels, duracoes, cores)):
        valores = sorted(valores)
        x = 120 + indice * 190
        minimo, mediana, maximo_local = valores[0], valores[len(valores)//2], valores[-1]
        y_min = 180 - 145 * minimo / maximo
        y_med = 180 - 145 * mediana / maximo
        y_max = 180 - 145 * maximo_local / maximo
        elementos.extend([f'<line x1="{x+45}" y1="{y_max:.1f}" x2="{x+45}" y2="{y_min:.1f}" stroke="{cor}" stroke-width="3"/>',
                          f'<rect x="{x+15}" y="{y_med-10:.1f}" width="60" height="20" fill="{cor}" opacity=".75"/>',
                          svg_text(label, x - 15, 205, 13)])
    (destino / "sast-tempo-por-condicao.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="520" height="230" viewBox="0 0 520 230">'
        + ''.join(elementos) + '<line x1="70" y1="180" x2="480" y2="180" stroke="#333"/></svg>\n',
        encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()
    repo = args.repo.resolve()
    saida = (args.saida or repo / "evidencias" / "graficos-sast").resolve()
    saida.mkdir(parents=True, exist_ok=True)
    linhas = coletar(repo)
    escrever_csv(linhas, saida / "sast-resumo.csv")
    escrever_graficos(linhas, saida)
    resumo = Counter(linha["condicao"] for linha in linhas)
    print(json.dumps({"execucoes": len(linhas), "por_condicao": resumo, "saida": str(saida)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
