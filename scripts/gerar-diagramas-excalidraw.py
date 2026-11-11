#!/usr/bin/env python3
"""Gera os diagramas da monografia no formato .excalidraw, sem dependências.

Cada arquivo pode ser aberto e editado em https://excalidraw.com e exportado
como PNG (escala 3x, fundo branco) para monografia/figs/excalidraw/<nome>.png.
"""

import argparse
import base64
import csv
import hashlib
import json
import random
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ICONES = Path(__file__).resolve().parent / "icones-material"

# Paleta tonal do Material Design (tons 50, 100, 200/300 e 600-800). Cada cor tem um
# papel fixo em todas as figuras: SAST, agentes de IA, híbrido, avaliação/ground truth,
# avaliador LLM e dados neutros.
SUAVE = {"sast": "#FEF7E0", "ia": "#E8F0FE", "hibrido": "#E6F4EA", "avaliacao": "#FCE8E6",
         "dados": "#F3E8FD", "neutro": "#F8F9FA", "branco": "#FFFFFF", "risco": "#FCE8E6"}
FORTE = {"sast": "#FEEFC3", "ia": "#D2E3FC", "hibrido": "#CEEAD6", "avaliacao": "#FAD2CF",
         "dados": "#E9D2FD", "neutro": "#F1F3F4", "branco": "#FFFFFF", "risco": "#FAD2CF"}
BORDA_ZONA = {"sast": "#FDD663", "ia": "#AECBFA", "hibrido": "#A8DAB5", "avaliacao": "#F6AEA9",
              "dados": "#D7AEFB", "neutro": "#DADCE0", "branco": "#DADCE0", "risco": "#F6AEA9"}
BORDA_NO = {"sast": "#F9AB00", "ia": "#8AB4F8", "hibrido": "#81C995", "avaliacao": "#F28B82",
            "dados": "#C58AF9", "neutro": "#BDC1C6", "branco": "#DADCE0", "risco": "#F28B82"}
ACENTO = {"sast": "#B06000", "ia": "#1967D2", "hibrido": "#137333", "avaliacao": "#C5221F",
          "dados": "#8430CE", "neutro": "#5F6368", "branco": "#5F6368", "risco": "#C5221F"}
DESTAQUE = {"sast": "#F9AB00", "ia": "#1A73E8", "hibrido": "#1E8E3E", "avaliacao": "#D93025",
            "dados": "#9334E6", "neutro": "#5F6368", "branco": "#5F6368", "risco": "#D93025"}
TEXTO = "#202124"
CINZA = "#5F6368"
FONTE = 2
RAIO_NO = 10
RAIO_ZONA = 16


class Diagrama:
    def __init__(self, semente):
        self.elementos = []
        self.caixas = {}
        self.arquivos = {}
        self.aleatorio = random.Random(semente)
        self.contador = 0

    def icone(self, x, y, nome, cor=CINZA, tamanho=22, grupo=None):
        svg = (ICONES / (nome + ".svg")).read_text(encoding="utf-8")
        svg = svg.replace("<svg ", '<svg fill="' + cor + '" ', 1)
        id_arquivo = hashlib.sha1(svg.encode("utf-8")).hexdigest()
        self.arquivos[id_arquivo] = {
            "mimeType": "image/svg+xml", "id": id_arquivo, "created": 1,
            "dataURL": "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()}
        return self._base("image", x, y, tamanho, tamanho, strokeColor="transparent",
                          status="saved", fileId=id_arquivo, scale=[1, 1], crop=None,
                          groupIds=[grupo] if grupo else [])

    def _id(self, prefixo):
        self.contador += 1
        return prefixo + "-" + str(self.contador)

    def _base(self, tipo, x, y, largura, altura, **extra):
        elemento = {
            "id": self._id(tipo), "type": tipo, "x": x, "y": y,
            "width": largura, "height": altura, "angle": 0, "strokeColor": TEXTO,
            "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
            "strokeStyle": "solid", "roughness": 0, "opacity": 100, "groupIds": [],
            "frameId": None, "roundness": None, "strokeSharpness": "sharp",
            "seed": self.aleatorio.randint(1, 2**31 - 1), "version": 1,
            "versionNonce": self.aleatorio.randint(1, 2**31 - 1), "isDeleted": False,
            "boundElements": [], "updated": 1, "link": None, "locked": False,
        }
        elemento.update(extra)
        self.elementos.append(elemento)
        return elemento

    def _texto(self, texto, x, y, largura, altura, tamanho, container=None,
               alinhamento="center", vertical="middle", cor=TEXTO):
        return self._base(
            "text", x, y, largura, altura, strokeColor=cor, text=texto,
            originalText=texto, fontSize=tamanho, fontFamily=FONTE,
            textAlign=alinhamento, verticalAlign=vertical, containerId=container,
            lineHeight=1.25, autoResize=True, baseline=round(altura - tamanho * 0.32))

    @staticmethod
    def _quebrar(texto, largura, tamanho):
        limite = max(6, int(largura / (tamanho * 0.5)))
        linhas = []
        for paragrafo in texto.split("\n"):
            linhas.extend(textwrap.wrap(paragrafo, limite) or [""])
        return linhas

    def _forma(self, tipo, x, y, largura, altura, fundo, borda, espessura=1,
               tracejado=False, arredondado=True, raio=RAIO_NO):
        if tipo == "rectangle":
            roundness = {"type": 3, "value": raio} if arredondado else None
        else:
            roundness = {"type": 2}
        return self._base(
            tipo, x, y, largura, altura, backgroundColor=fundo, strokeColor=borda,
            strokeWidth=espessura, strokeStyle="dashed" if tracejado else "solid",
            roundness=roundness, strokeSharpness="round" if arredondado else "sharp")

    def caixa(self, nome, x, y, texto, largura=210, altura=60, cor="neutro",
              tipo="rectangle", tamanho=16, tracejado=False, alinhamento="center",
              suave=False, cor_texto=None, ajustar=True, destaque=False, icone=None):
        if icone:
            return self._caixa_com_icone(nome, x, y, texto, largura, altura, cor, tamanho,
                                         tracejado, suave, cor_texto, ajustar, destaque, icone)
        linhas = self._quebrar(texto, largura - 24, tamanho)
        folga = 2.0 if tipo in ("diamond", "ellipse") else 1
        if ajustar:
            altura = max(altura, round(len(linhas) * tamanho * 1.25 * folga + 22))
        if destaque:
            fundo, borda, cor_texto = DESTAQUE[cor], DESTAQUE[cor], cor_texto or "#FFFFFF"
        else:
            fundo = (SUAVE if suave else FORTE)[cor]
            borda = BORDA_NO[cor]
            cor_texto = cor_texto or TEXTO
        forma = self._forma(tipo, x, y, largura, altura, fundo, borda, tracejado=tracejado,
                            espessura=1.5 if tracejado else 1)
        conteudo = "\n".join(linhas)
        altura_texto = len(linhas) * tamanho * 1.25
        largura_texto = max(len(linha) for linha in linhas) * tamanho * 0.5
        rotulo = self._texto(conteudo, x + (largura - largura_texto) / 2,
                             y + (altura - altura_texto) / 2, largura_texto,
                             altura_texto, tamanho, container=forma["id"],
                             alinhamento=alinhamento, cor=cor_texto)
        forma["boundElements"].append({"type": "text", "id": rotulo["id"]})
        if nome:
            self.caixas[nome] = forma
        return forma

    def _caixa_com_icone(self, nome, x, y, texto, largura, altura, cor, tamanho, tracejado,
                         suave, cor_texto, ajustar, destaque, icone):
        lado = round(tamanho * 1.35)
        linhas = self._quebrar(texto, largura - 30 - lado, tamanho)
        altura_texto = len(linhas) * tamanho * 1.25
        if ajustar:
            altura = max(altura, round(altura_texto + 22))
        if destaque:
            fundo, borda, cor_texto, cor_icone = DESTAQUE[cor], DESTAQUE[cor], cor_texto or "#FFFFFF", "#FFFFFF"
        else:
            fundo, borda = (SUAVE if suave else FORTE)[cor], BORDA_NO[cor]
            cor_texto, cor_icone = cor_texto or TEXTO, ACENTO[cor]
        grupo = self._id("grupo")
        forma = self._forma("rectangle", x, y, largura, altura, fundo, borda, tracejado=tracejado,
                            espessura=1.5 if tracejado else 1)
        forma["groupIds"] = [grupo]
        largura_texto = max(len(l) for l in linhas) * tamanho * 0.5
        bloco = lado + 8 + largura_texto
        inicio = x + max(12, (largura - bloco) / 2)
        self.icone(inicio, y + (altura - lado) / 2, icone, cor_icone, lado, grupo)
        self._texto("\n".join(linhas), inicio + lado + 8, y + (altura - altura_texto) / 2,
                    largura_texto, altura_texto, tamanho, alinhamento="left",
                    vertical="top", cor=cor_texto)["groupIds"] = [grupo]
        if nome:
            self.caixas[nome] = forma
        return forma

    def faixa(self, nome, x, y, largura, altura, titulo, cor, tamanho=20,
              subtitulo=None, tracejado=False, icone=None):
        forma = self._forma("rectangle", x, y, largura, altura, SUAVE[cor], BORDA_ZONA[cor],
                            espessura=1.5 if tracejado else 1, tracejado=tracejado,
                            raio=RAIO_ZONA)
        if nome:
            self.caixas[nome] = forma
        if titulo:
            deslocamento = 0
            if icone:
                lado = round(tamanho * 1.2)
                self.icone(x + 16, y + 12 + (tamanho * 1.25 - lado) / 2, icone, ACENTO[cor], lado)
                deslocamento = lado + 8
            self.texto(x + 18 + deslocamento, y + 12, titulo, tamanho, ACENTO[cor])
        if subtitulo:
            self.texto(x + 18, y + 14 + tamanho * 1.3, subtitulo, 14, CINZA, largura - 36)
        return forma

    def texto(self, x, y, texto, tamanho=16, cor=TEXTO, largura=None, alinhamento="left"):
        linhas = self._quebrar(texto, largura, tamanho) if largura else texto.split("\n")
        conteudo = "\n".join(linhas)
        altura = len(linhas) * tamanho * 1.25
        largura_real = max(len(l) for l in linhas) * tamanho * 0.5
        if alinhamento == "center" and largura:
            x = x + (largura - largura_real) / 2
        self._texto(conteudo, x, y, largura_real, altura, tamanho,
                    alinhamento=alinhamento, vertical="top", cor=cor)
        return y + altura

    def selo(self, x, y, texto, cor="neutro", diametro=36):
        return self.caixa(None, x, y, texto, diametro, diametro, cor, tipo="ellipse", tamanho=16,
                          ajustar=False, destaque=True)

    def retangulo(self, x, y, largura, altura, fundo, borda="transparent", arredondado=True,
                  raio=6):
        return self._forma("rectangle", x, y, largura, altura, fundo, borda, espessura=1,
                           arredondado=arredondado, raio=raio)

    def cilindro(self, nome, x, y, largura, altura, texto, cor="neutro", tamanho=15):
        tampa = 24
        grupo = self._id("grupo")
        elementos = [
            self._forma("ellipse", x, y + altura - tampa, largura, tampa, FORTE[cor], BORDA_NO[cor]),
            self._forma("rectangle", x, y + tampa / 2, largura, altura - tampa, FORTE[cor],
                        "transparent", arredondado=False),
            self.linha([(x, y + tampa / 2), (x, y + altura - tampa / 2)], BORDA_NO[cor], False, 1),
            self.linha([(x + largura, y + tampa / 2), (x + largura, y + altura - tampa / 2)],
                       BORDA_NO[cor], False, 1),
            self._forma("ellipse", x, y, largura, tampa, SUAVE[cor], BORDA_NO[cor]),
        ]
        linhas = self._quebrar(texto, largura - 20, tamanho)
        altura_texto = len(linhas) * tamanho * 1.25
        self.texto(x + 10, y + tampa + (altura - tampa * 1.5 - altura_texto) / 2, "\n".join(linhas),
                   tamanho, TEXTO, largura - 20, "center")
        elementos.append(self.elementos[-1])
        for elemento in elementos:
            elemento["groupIds"] = [grupo]
        if nome:
            self.caixas[nome] = {"id": elementos[1]["id"], "x": x, "y": y, "width": largura,
                                 "height": altura, "boundElements": elementos[1]["boundElements"]}
        return elementos[1]

    def linha(self, pontos, cor=CINZA, tracejado=True, espessura=2):
        x0, y0 = pontos[0]
        relativos = [[px - x0, py - y0] for px, py in pontos]
        xs = [p[0] for p in relativos]
        ys = [p[1] for p in relativos]
        return self._base("line", x0, y0, max(xs) - min(xs), max(ys) - min(ys),
                          strokeColor=cor, strokeWidth=espessura,
                          strokeStyle="dashed" if tracejado else "solid",
                          points=relativos, lastCommittedPoint=None,
                          startArrowhead=None, endArrowhead=None, startBinding=None,
                          endBinding=None)

    def ponto(self, nome, lado):
        caixa = self.caixas[nome]
        x, y, l, a = caixa["x"], caixa["y"], caixa["width"], caixa["height"]
        return {"esquerda": (x, y + a / 2), "direita": (x + l, y + a / 2),
                "topo": (x + l / 2, y), "base": (x + l / 2, y + a)}[lado]

    def seta(self, origem, destino, lados=None, via=(), texto=None, tracejado=False,
             cor=CINZA, inicio=None, fim=None, espessura=1.5, curva=False):
        if lados is None and origem and destino:
            co = self.caixas[origem]
            cd = self.caixas[destino]
            dx = (cd["x"] + cd["width"] / 2) - (co["x"] + co["width"] / 2)
            dy = (cd["y"] + cd["height"] / 2) - (co["y"] + co["height"] / 2)
            if abs(dx) >= abs(dy):
                lados = ("direita", "esquerda") if dx > 0 else ("esquerda", "direita")
            else:
                lados = ("base", "topo") if dy > 0 else ("topo", "base")
        inicio = inicio or self.ponto(origem, lados[0])
        fim = fim or self.ponto(destino, lados[1])
        absolutos = [inicio, *via, fim]
        pontos = [[px - inicio[0], py - inicio[1]] for px, py in absolutos]
        xs = [p[0] for p in pontos]
        ys = [p[1] for p in pontos]
        ligacao = lambda nome: ({"elementId": self.caixas[nome]["id"], "focus": 0, "gap": 4}
                                if nome else None)
        seta = self._base(
            "arrow", inicio[0], inicio[1], max(xs) - min(xs), max(ys) - min(ys),
            strokeColor=cor, strokeWidth=espessura,
            strokeStyle="dashed" if tracejado else "solid", points=pontos,
            roundness={"type": 2} if curva else None,
            lastCommittedPoint=None, startArrowhead=None, endArrowhead="triangle",
            startBinding=ligacao(origem), endBinding=ligacao(destino), elbowed=False)
        for nome in (origem, destino):
            if nome:
                self.caixas[nome]["boundElements"].append({"type": "arrow", "id": seta["id"]})
        if texto:
            meio = len(absolutos) // 2
            a, b = absolutos[meio - 1], absolutos[meio]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            linhas = texto.split("\n")
            largura = max(len(l) for l in linhas) * 14 * 0.5
            altura = len(linhas) * 14 * 1.25
            rotulo = self._texto(texto, mx - largura / 2, my - altura / 2, largura,
                                 altura, 14, container=seta["id"], cor=cor)
            seta["boundElements"].append({"type": "text", "id": rotulo["id"]})
        return seta

    def documento(self):
        return {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
                "elements": self.elementos,
                "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None},
                "files": self.arquivos}


def evolucao_agentes():
    d = Diagrama(11)
    cartoes = [
        ("neutro", "Autocomplete", "Primeiras versões do GitHub Copilot",
         [("Contexto", "texto já digitado no arquivo aberto"),
          ("Iniciativa", "desenvolvedor aceita cada sugestão"),
          ("Ações", "sugerir a próxima linha ou bloco")]),
        ("neutro", "Assistente conversacional", "Chat integrado ao ambiente",
         [("Contexto", "instrução e trechos selecionados"),
          ("Iniciativa", "desenvolvedor, a cada interação"),
          ("Ações", "gerar blocos e propor alterações")]),
        ("ia", "Agente de codificação", "Cursor e OpenAI Codex",
         [("Contexto", "repositório explorado pelo próprio agente"),
          ("Iniciativa", "agente decompõe a tarefa e itera"),
          ("Ações", "ler e escrever arquivos, terminal, testes e analisadores")]),
    ]
    azul = DESTAQUE["ia"]
    claro = "#D2E3FC"
    cinza = "#E8EAED"
    for i, (cor, titulo, exemplo, itens) in enumerate(cartoes):
        x = 20 + i * 420
        d.faixa("cartao" + str(i), x, 20, 370, 510, titulo, cor, tamanho=22, subtitulo=exemplo)
        d.caixa(None, x + 314, 26, "", 44, 44, "branco", tipo="ellipse", ajustar=False)
        d.icone(x + 324, 36, ("keyboard", "chat", "smart_toy")[i],
                ACENTO["ia"] if i == 2 else CINZA, 24)
        base_y = 110
        if i == 0:
            d.retangulo(x + 115, base_y, 140, 120, "#FFFFFF", BORDA_ZONA["neutro"])
            for k in range(6):
                d.retangulo(x + 128, base_y + 14 + k * 17, 110 - (k % 3) * 18, 8,
                            azul if k == 3 else cinza, raio=3)
            d.texto(x + 262, base_y + 64, "← sugestão", 13, ACENTO["ia"])
        elif i == 1:
            d.retangulo(x + 40, base_y, 140, 120, "#FFFFFF", BORDA_ZONA["neutro"])
            for k in range(6):
                d.retangulo(x + 53, base_y + 14 + k * 17, 110 - (k % 3) * 18, 8,
                            azul if k in (1, 2, 3, 4) else cinza, raio=3)
            d.caixa(None, x + 205, base_y + 20, "“refatore esta função”", 140, 60, "ia", tamanho=13)
        else:
            for k, (dx, dy) in enumerate(((30, 0), (95, 20), (160, 40))):
                d.retangulo(x + dx, base_y + dy, 100, 80, "#FFFFFF", BORDA_ZONA["ia"])
                for j in range(3):
                    d.retangulo(x + dx + 12, base_y + dy + 14 + j * 17, 70 - j * 12, 7,
                                azul if j == 0 else claro, raio=3)
            for k, (rotulo, icone) in enumerate((("terminal", "terminal"), ("testes", "science"),
                                                 ("SAST", "search"))):
                d.caixa(None, x + 262, base_y + 6 + k * 44, rotulo, 98, 34, "branco", tamanho=12,
                        icone=icone, ajustar=False)
            d.caixa(None, x + 22, 480, "avaliado neste trabalho", 210, 30, "ia", tamanho=13,
                    destaque=True, ajustar=False, icone="star")
        y = 270
        for rotulo, valor in itens:
            d.texto(x + 22, y, rotulo, 15, ACENTO[cor])
            y = d.texto(x + 22, y + 21, valor, 16, TEXTO, 326) + 18
    for i in range(2):
        d.seta("cartao" + str(i), "cartao" + str(i + 1), espessura=2)
    d.seta(None, None, inicio=(40, 565), fim=(1220, 565), cor="#BDC1C6", espessura=2)
    d.texto(40, 580, "autonomia e alcance do contexto crescentes", 16, CINZA, 1180, "center")
    return d


def anatomia_agente():
    d = Diagrama(12)
    d.faixa("ambiente", 0, 0, 900, 650, "Ambiente", "neutro")
    for i, (texto, icone) in enumerate((("Repositório", "folder"), ("Terminal", "terminal"),
                                        ("Testes", "science"), ("Analisadores", "search"))):
        d.caixa("amb" + str(i), 40 + i * 205, 50, texto, 190, 40, "branco", tamanho=15,
                icone=icone)
    d.faixa("camada", 40, 115, 820, 480, "Camada operacional (agent harness)", "ia",
            tracejado=True)
    d.caixas["camada"]["backgroundColor"] = "#FFFFFF"
    for i, texto in enumerate(("Estado da tarefa", "Seleção de contexto", "Permissões",
                               "Critério de parada", "Ferramentas")):
        d.caixa("cam" + str(i), 60 + i * 158, 160, texto, 148, 40, "branco", tamanho=14)
    d.faixa("agente", 90, 235, 720, 330, "Agente: ciclo ReAct", "ia")
    d.caixa("raciocinio", 205, 295, "Raciocínio", 170, 56, "ia", tamanho=17, icone="psychology")
    d.caixa("acao", 580, 295, "Ação", 170, 56, "ia", tamanho=17, icone="settings")
    d.caixa("observacao", 365, 470, "Observação", 170, 56, "ia", tamanho=17, icone="visibility")
    d.caixa("llm", 380, 368, "LLM", 140, 70, "ia", tipo="ellipse", tamanho=20, destaque=True)
    d.seta("raciocinio", "acao", cor=ACENTO["ia"], espessura=2, via=((477, 285),), curva=True,
           inicio=(375, 310), fim=(580, 310))
    d.seta("acao", "observacao", lados=("base", "direita"), cor=ACENTO["ia"], espessura=2,
           via=((640, 440),), curva=True)
    d.seta("observacao", "raciocinio", lados=("esquerda", "base"), cor=ACENTO["ia"], espessura=2,
           via=((300, 440),), curva=True)
    d.seta("cam1", "raciocinio", lados=("base", "topo"), tracejado=True)
    d.seta("acao", "cam4", lados=("topo", "base"), tracejado=True)
    d.seta("cam4", "amb3", lados=("topo", "base"), tracejado=True)
    notas = [
        ("neutro", "LLM isolado", "Somente o núcleo: recebe uma entrada fixa e produz texto, sem explorar o repositório."),
        ("ia", "Ferramenta-agente", "Cursor e Codex: núcleo, ciclo e camada operacional. O resultado reflete a configuração completa."),
        ("avaliacao", "Neste estudo", "Código entregue no prompt; escrita, shell e analisadores bloqueados nas sessões de IA."),
    ]
    for i, (cor, titulo, texto) in enumerate(notas):
        d.faixa(None, 940, 50 + i * 200, 330, 150, titulo, cor, tamanho=19)
        d.texto(958, 90 + i * 200, texto, 16, TEXTO, 295)
    return d


def padroes_hibridos():
    d = Diagrama(13)
    faixas = [
        ("Filtragem a jusante", "Ameen et al. (2026); Iranmanesh et al. (2025); Agrawal et al. (2025)",
         [("Código", 120, "neutro", "description"), ("SAST", 130, "sast", "search"),
          ("Alertas", 130, "sast", "warning"), ("LLM revisa, filtra e explica", 260, "ia", "smart_toy"),
          ("Achados triados", 170, "hibrido", None)]),
        ("Ampliação a montante", "Li et al. (2025): IRIS com CodeQL",
         [("Código", 120, "neutro", "description"),
          ("LLM infere sources, sinks e sanitizadores", 310, "ia", "smart_toy"),
          ("Especificação de taint", 200, "neutro", None), ("Motor SAST", 160, "sast", "search"),
          ("Alertas", 130, "sast", "warning")]),
        ("Realimentação em laço", "Alrashedy et al. (2025); Lee et al. (2026)",
         [("LLM gera ou corrige o código", 270, "ia", "smart_toy"),
          ("Código", 120, "neutro", "description"), ("SAST analisa", 160, "sast", "search"),
          ("Código final, sem alertas", 220, "hibrido", None)]),
    ]
    for i, (titulo, fonte, etapas) in enumerate(faixas):
        y, altura = ((0, 180), (200, 145), (365, 180))[i]
        d.faixa(None, 0, y, 1240, altura, titulo, "branco" if i else "hibrido", tamanho=21,
                tracejado=bool(i))
        d.texto(700, y + 16, fonte, 13, CINZA, 520)
        x = 30
        nomes = []
        for j, (texto, largura, cor, icone) in enumerate(etapas):
            nome = "p" + str(i) + "-" + str(j)
            d.caixa(nome, x, y + 62, texto, largura, 58, cor, tamanho=15, icone=icone)
            nomes.append(nome)
            x += largura + 50
        for a, b in zip(nomes, nomes[1:]):
            d.seta(a, b)
        if i == 0:
            d.caixa(None, 470, y + 130, "Este trabalho (C5, C6): alertas SAST como contexto do agente",
                    540, 34, "hibrido", tamanho=14, destaque=True, ajustar=False, icone="star")
        if i == 2:
            sast = d.caixas[nomes[2]]
            llm = d.caixas[nomes[0]]
            sx = sast["x"] + sast["width"] / 2
            lx = llm["x"] + llm["width"] / 2
            d.seta(nomes[2], nomes[0], lados=("base", "base"),
                   via=(((sx + lx) / 2, y + 168),), tracejado=True, cor=ACENTO["ia"], curva=True)
            d.texto((sx + lx) / 2 - 90, y + 140, "alertas realimentam o LLM", 14, ACENTO["ia"])
    return d


def desenho_experimental():
    d = Diagrama(14)
    d.cilindro("corpus", 20, 170, 210, 170, "RealVuln v1.0\n26 repositórios Python", "neutro",
               tamanho=16)
    y = 360
    for linha in ("697 vulnerabilidades", "120 armadilhas de FP", "revisões fixadas por hash",
                  "alvos anônimos ALVO-NNNN"):
        y = d.texto(30, y, "• " + linha, 14, CINZA, 230) + 4
    faixas = [
        ("sast", "SAST", "Docker sem rede · 1 execução por alvo · 52 execuções", 0, 200,
         [("c1", "C1 · Bandit 1.9.4"), ("c2", "C2 · Semgrep CE 1.172.0")]),
        ("ia", "IA isolada", "GPT-5.6 Luna nos dois produtos · 3 repetições · 156 execuções", 220, 180,
         [("c3", "C3 · Cursor"), ("c4", "C4 · OpenAI Codex")]),
        ("hibrido", "Híbrida", "mesmos alertas para os dois · 3 repetições · 156 execuções", 420, 180,
         [("c5", "C5 · Cursor + alertas SAST"), ("c6", "C6 · Codex + alertas SAST")]),
    ]
    for cor, titulo, nota, y0, altura, condicoes in faixas:
        d.faixa("faixa-" + cor, 300, y0, 760, altura, titulo, cor, tamanho=21)
        d.texto(420, y0 + 18, nota, 14, CINZA)
        for k, (nome, texto) in enumerate(condicoes):
            d.caixa(nome, 330, y0 + 60 + k * 62, texto, 280, 50, cor, tamanho=16)
        d.seta("corpus", "faixa-" + cor, lados=("direita", "esquerda"),
               fim=(300, y0 + altura / 2))
    d.caixa("alertas", 760, 85, "União normalizada: 1.416 alertas, 1.410 após deduplicação",
            270, 70, "sast", tamanho=15)
    d.seta("c1", "alertas", fim=(760, 105))
    d.seta("c2", "alertas", fim=(760, 135))
    d.texto(650, 300, "código no prompt,\nsem alertas", 14, CINZA)
    d.seta("alertas", "c5", lados=("base", "direita"), via=((895, 505),), tracejado=True,
           cor=ACENTO["hibrido"])
    d.seta("alertas", "c6", lados=("base", "direita"), via=((895, 567),), tracejado=True,
           cor=ACENTO["hibrido"])
    d.linha([(1090, -10), (1090, 610)], cor=BORDA_NO["avaliacao"])
    d.icone(1100, -16, "lock", ACENTO["avaliacao"], 18)
    d.texto(1122, -14, "ground truth somente após a coleta", 14, ACENTO["avaliacao"])
    d.cilindro("oracle", 1480, 80, 170, 130, "Ground truth\n817 entradas", "avaliacao", tamanho=15)
    d.faixa("quanti", 1120, 30, 320, 250, "Avaliação quantitativa", "avaliacao", tamanho=19)
    y = 72
    for linha in ("avaliador oficial do RealVuln", "caminho, CWE aceitável e ±10 linhas",
                  "TP, FP, FN e TN por entrada", "IC95%: 10.000 reamostragens por repositório"):
        y = d.texto(1138, y, "• " + linha, 15, TEXTO, 285) + 6
    d.faixa("quali", 1120, 330, 320, 250, "Avaliação qualitativa", "avaliacao", tamanho=19)
    y = 372
    for linha in ("300 relatos TP, 50 por condição", "ordem opaca, sem indicar a condição",
                  "rubrica: correção, localização, acionabilidade e clareza",
                  "avaliador LLM de outra família"):
        y = d.texto(1138, y, "• " + linha, 15, TEXTO, 285) + 6
    for cor, y_inicio, y_fim in (("sast", 100, 90), ("ia", 310, 160), ("hibrido", 510, 240)):
        d.seta("faixa-" + cor, "quanti", inicio=(1060, y_inicio), fim=(1120, y_fim))
    d.seta("quanti", "quali", texto="TP da 1ª repetição")
    d.seta("oracle", "quanti", lados=("esquerda", "direita"), tracejado=True,
           cor=ACENTO["avaliacao"], fim=(1440, 145))
    d.texto(300, 625, "364 execuções válidas · 433 tentativas preservadas · ordem fixa dos alvos por repetição",
            16, CINZA)
    return d


def questoes_medidas():
    d = Diagrama(18)
    colunas = (("Questão", 0, 230), ("O que é medido", 300, 430), ("Dados utilizados", 800, 380))
    for titulo, x, largura in colunas:
        d.texto(x, 0, titulo, 17, CINZA, largura, "center")
    linhas = [
        ("q1", "neutro", "QP1\nDetecção",
         "Precisão, recall, F1, F2, F3 e taxa de FP, com IC95% por bootstrap",
         "C1–C6 sobre as 817 entradas do RealVuln"),
        ("q2", "neutro", "QP2\nQualidade dos relatos",
         "Rubrica de 1 a 5 (correção, localização, acionabilidade) e checklist de clareza (0 a 5)",
         "300 relatos verdadeiros-positivos da 1ª repetição, 50 por condição"),
        ("q3", "hibrido", "QP3\nEfeito do híbrido",
         "Diferenças pareadas C5 − C3 e C6 − C4 na detecção; contrastes descritivos na qualidade",
         "Mesmos projetos sorteados para a condição híbrida e a isolada"),
        ("q4", "neutro", "QP4\nEstabilidade e priorização",
         "Detecção em 0, 1, 2 ou 3 repetições; concordância de severidade e Kappa ponderado",
         "Três repetições de C3–C6; severidade de referência do RealVuln"),
        ("q5", "branco", "Complementar\noperacional", "Tempo de execução e tokens informados",
         "Registros de cada tentativa"),
    ]
    y = 40
    for nome, cor, questao, medida, dados in linhas:
        tracejado = nome == "q5"
        d.caixa(nome, 0, y, questao, 230, 84, cor, tamanho=16, tracejado=tracejado)
        d.caixa(nome + "m", 300, y, medida, 430, 84, "branco", tamanho=16, tracejado=tracejado)
        d.caixa(nome + "d", 800, y, dados, 380, 84, "dados", tamanho=16, suave=True,
                tracejado=tracejado)
        d.seta(nome, nome + "m")
        d.seta(nome + "m", nome + "d")
        y += 104
    return d


def correspondencia():
    d = Diagrama(19)
    d.caixa("achado", 40, 0, "Achado normalizado\narquivo, linha e CWE", 260, 60, "neutro", tamanho=16,
            icone="description")
    perguntas = [("arquivo", "Mesmo arquivo de uma entrada livre?"),
                 ("cwe", "CWE no conjunto aceitável da entrada?"),
                 ("linha", "Linha na faixa rotulada ±10 linhas?"),
                 ("tipo", "A entrada é uma vulnerabilidade?")]
    for k, (nome, texto) in enumerate(perguntas):
        d.caixa(nome, 0, 100 + k * 150, texto, 340, 110, "branco", tipo="diamond", tamanho=15,
                ajustar=False)
    d.caixa("tp", 95, 720, "TP", 150, 50, "hibrido", tamanho=18, destaque=True, ajustar=False)
    d.texto(20, 782, "a entrada é consumida e não pode\nser usada por outro achado", 14, CINZA, 300,
            "center")
    d.caixa("fp", 450, 270, "FP\nsem correspondência", 220, 70, "avaliacao", tamanho=16)
    d.caixa("fparm", 450, 570, "FP\narmadilha sinalizada", 220, 70, "avaliacao", tamanho=16)
    d.seta("achado", "arquivo")
    for a, b in (("arquivo", "cwe"), ("cwe", "linha"), ("linha", "tipo"), ("tipo", "tp")):
        d.seta(a, b, texto="sim")
    d.seta("cwe", "fp", texto="não", cor=ACENTO["avaliacao"])
    d.seta("tipo", "fparm", texto="não", cor=ACENTO["avaliacao"])
    d.seta("arquivo", "fp", lados=("direita", "topo"), via=((560, 155),), texto="não",
           cor=ACENTO["avaliacao"])
    d.seta("linha", "fp", lados=("direita", "base"), via=((560, 455),), texto="não",
           cor=ACENTO["avaliacao"])
    d.faixa(None, 760, 220, 470, 330, "Após processar todos os achados", "neutro", tamanho=18)
    d.texto(780, 262, "entradas do ground truth que nenhum achado consumiu", 15, CINZA, 430)
    d.caixa("fn", 790, 330, "FN\nvulnerabilidade não detectada", 190, 90, "avaliacao", tamanho=16)
    d.caixa("tn", 1010, 330, "TN\narmadilha corretamente ignorada", 190, 90, "hibrido", tamanho=16)
    d.texto(780, 450, "Uma vulnerabilidade sem alerta correspondente reduz o recall; uma armadilha "
            "ignorada conta a favor na taxa de FP.", 14, CINZA, 430)
    return d


def bootstrap():
    d = Diagrama(20)
    sorteados = {1: 1, 2: 1, 5: 2, 8: 1, 13: 1, 17: 2, 22: 1}
    for bloco, (x0, titulo, nota) in enumerate(((0, "26 projetos", "cada projeto leva todas as\nsuas entradas e repetições"),
                                                (330, "Reamostragem b", "26 sorteios com reposição:\nprojetos repetidos ou ausentes"))):
        d.texto(x0, 0, titulo, 18, TEXTO, 230, "center")
        for i in range(26):
            cor = "ia" if bloco and i in sorteados else "neutro"
            x, y = x0 + 20 + (i % 6) * 33, 36 + (i // 6) * 33
            d.retangulo(x, y, 26, 26, FORTE[cor], BORDA_NO[cor], raio=3)
        d.texto(x0, 210, nota, 14, CINZA, 230, "center")
    d.seta(None, None, inicio=(235, 105), fim=(330, 105), texto="sortear")
    d.caixa("calc", 660, 60, "Somar TP, FP, FN e TN; calcular a métrica em cada repetição e tomar a média",
            300, 90, "neutro", tamanho=15)
    d.seta(None, "calc", inicio=(570, 105), fim=(656, 105))
    base, x0, largura = 470, 690, 22
    alturas = (8, 20, 42, 70, 95, 108, 98, 72, 45, 22, 10)
    for k, h in enumerate(alturas):
        cor = "neutro" if k in (0, len(alturas) - 1) else "ia"
        d.retangulo(x0 + k * largura, base - h, largura, h, FORTE[cor], BORDA_NO[cor], arredondado=False)
    d.linha([(x0 - 10, base), (x0 + 11 * largura + 10, base)], CINZA, False, 1)
    for x, rotulo in ((x0 + largura, "P2,5"), (x0 + 10 * largura, "P97,5")):
        d.linha([(x, base + 8), (x, base - 135)], ACENTO["avaliacao"], True, 1.5)
        d.texto(x - 20, base - 158, rotulo, 14, ACENTO["avaliacao"])
    d.texto(x0 - 20, base + 14, "IC95% da métrica", 16, TEXTO, 280, "center")
    d.seta("calc", None, inicio=(810, 154), fim=(810, 300), texto="repetir\n10.000 vezes")
    d.faixa("par", 0, 320, 560, 220, "Comparação pareada", "hibrido", tamanho=18)
    d.texto(18, 360, "Na mesma reamostragem b, calcula-se a métrica da condição híbrida e da "
            "isolada e a diferença Δ = C5 − C3 (ou C6 − C4).", 15, TEXTO, 520)
    d.texto(18, 435, "O IC95% de Δ inclui zero?\nSim: direção não estabelecida.\n"
            "Não: diferença na direção do sinal.", 15, TEXTO, 520)
    d.seta("calc", "par", inicio=(680, 154), fim=(500, 320), via=((680, 292), (500, 292)))
    return d


def fluxo_qualitativo():
    d = Diagrama(21)
    etapas = [("tp", "Relatos TP\nda 1ª repetição de cada condição", "neutro"),
              ("comum", "Recorte comum\n20 entradas detectadas por C1–C6", "hibrido"),
              ("estrato", "Complemento\nsorteio estratificado por CWE e severidade", "hibrido"),
              ("amostra", "Amostra\n50 relatos por condição, 300 no total", "dados")]
    for k, (nome, texto, cor) in enumerate(etapas):
        d.caixa(nome, k * 300, 0, texto, 240, 90, cor, tamanho=16)
    for a, b in zip(etapas, etapas[1:]):
        d.seta(a[0], b[0])
    d.caixa("cego", 900, 160, "Cegamento\nidentificadores opacos; chave de condições fechada", 240, 106,
            "avaliacao", tamanho=16, icone="lock")
    d.caixa("juiz", 600, 160, "Avaliador LLM\nsessão nova por relato; notas com evidência", 240, 106,
            "ia", tamanho=16, icone="smart_toy")
    d.caixa("valido", 330, 158, "Registro válido?", 200, 110, "branco", tipo="diamond", tamanho=16,
            ajustar=False)
    d.caixa("congela", 0, 160, "Notas congeladas\npor SHA-256", 240, 90, "dados", tamanho=16)
    d.seta("amostra", "cego")
    d.seta("cego", "juiz")
    d.seta("juiz", "valido")
    d.seta("valido", "congela", texto="sim")
    d.seta("valido", "juiz", lados=("base", "base"), via=((430, 300), (720, 300)),
           cor=ACENTO["avaliacao"], tracejado=True)
    d.texto(440, 306, "não: repetir em nova sessão, sem correção manual", 14, ACENTO["avaliacao"])
    d.caixa("chave", 0, 360, "Abertura da chave\nnotas atribuídas às condições C1–C6", 240, 90,
            "neutro", tamanho=16)
    d.seta("congela", "chave")
    d.faixa("leitura", 300, 350, 840, 110, "Duas leituras", "branco", tamanho=17)
    d.texto(320, 385, "Recorte comum: mesmas vulnerabilidades em todas as condições.\n"
            "Amostra completa: utilidade típica dos relatos de cada condição.", 15, TEXTO)
    d.seta("chave", "leitura")
    return d


def protocolo():
    d = Diagrama(22)
    fases = [
        ("Preparação", "neutro", [("Fixar RealVuln e hashes", "neutro"),
                                  ("Validar e baixar os 26 projetos", "neutro"),
                                  ("Sanitizar e criar alvos opacos", "neutro"),
                                  ("Imagem Docker e adaptadores", "neutro"),
                                  ("Piloto: fixar o GPT-5.6 Luna", "neutro")]),
        ("Coleta", "ia", [("Fila em ordem fixa (não aleatorizada)", "risco"),
                          ("C1 e C2 em contêineres", "sast"),
                          ("Normalizar e unir os alertas", "sast"),
                          ("C3 e C4, três sessões", "ia"),
                          ("C5 e C6 com alertas, três sessões", "hibrido"),
                          ("Bloco complementar (não executado)", "risco")]),
        ("Avaliação", "avaliacao", [("Esquema comum e avaliador oficial", "avaliacao"),
                                    ("Métricas, IC95% e pareamento", "avaliacao"),
                                    ("Rubrica cega e notas congeladas", "avaliacao")]),
        ("Relato", "hibrido", [("Resultados por condição, projeto, CWE e severidade", "hibrido")]),
    ]
    numero = 1
    ultimos = []
    for i, (titulo, cor_fase, passos) in enumerate(fases):
        x = i * 320
        d.faixa(None, x, 0, 290, 640, titulo, cor_fase, tamanho=20)
        nomes = []
        for k, (texto, cor) in enumerate(passos):
            nome = "p" + str(numero)
            y = 60 + k * 95
            d.caixa(nome, x + 52, y, texto, 220, 70, cor, tamanho=15, ajustar=False,
                    tracejado=cor == "risco", suave=cor == "risco")
            d.selo(x + 12, y + 17, str(numero), "avaliacao" if cor == "risco" else cor_fase)
            nomes.append(nome)
            numero += 1
        for a, b in zip(nomes, nomes[1:]):
            d.seta(a, b)
        ultimos.append((nomes[0], nomes[-1]))
    for (_, fim), (inicio, _) in zip(ultimos, ultimos[1:]):
        x_saida, y_saida = d.ponto(fim, "direita")
        x_topo = d.ponto(inicio, "topo")[0]
        d.seta(fim, inicio, lados=("direita", "topo"),
               via=((x_saida + 24, y_saida), (x_saida + 24, 48), (x_topo, 48)))
    d.linha([(625, -20), (625, 660)], cor=BORDA_NO["avaliacao"])
    d.icone(635, -26, "lock", ACENTO["avaliacao"], 18)
    d.texto(657, -24, "ground truth aberto somente a partir do passo 12", 14, ACENTO["avaliacao"])
    d.caixa(None, 980, 200, "Passos 6 e 11: não cumpridos como planejado", 240, 70, "risco",
            tamanho=15, tracejado=True, suave=True, icone="warning")
    return d


def isolamento():
    d = Diagrama(15)
    colunas = [
        ("sast", "C1–C2 · Docker", "contêiner efêmero por tentativa",
         ["rede desativada", "raiz somente leitura; entrada montada como leitura",
          "usuário 10001, sem capabilities, no-new-privileges", "2 CPUs · 3 GB · 256 processos",
          "limite de 900 s por scanner", "docker.sock não montado"], []),
        ("ia", "C3 e C5 · Cursor", "sessão nova em pasta exclusiva",
         ["modo de consulta (--mode=ask)", "nega Write(**) e Shell(*)",
          "código entregue pela entrada padrão", "eventos proibidos invalidam a tentativa",
          "auditoria: zero chamadas de ferramenta"], ["sandbox nativo indisponível no Windows"]),
        ("ia", "C4 e C6 · Codex", "codex-cli 0.154.0",
         ["sandbox somente leitura", "sessão efêmera", "política de aprovação never",
          "configurações e regras externas ignoradas", "código entregue pela entrada padrão"],
         ["modelo servido não exposto no JSONL"]),
        ("dados", "Avaliador LLM", "Composer 2.5 Fast, um relato por sessão",
         ["nega Read(**), Write(**) e Shell(*)", "rubrica, esquema e material pela entrada padrão",
          "sem a chave de condições", "modelo exibido conferido a cada sessão"], []),
    ]
    for i, (cor, titulo, subtitulo, itens, riscos) in enumerate(colunas):
        x = i * 320
        d.faixa(None, x, 0, 300, 500, titulo, cor, tamanho=20, subtitulo=subtitulo, icone="lock")
        y = 90
        for item in itens:
            caixa = d.caixa(None, x + 18, y, item, 264, 40, "branco", tamanho=14)
            caixa["strokeColor"] = BORDA_ZONA[cor]
            y += caixa["height"] + 10
        for item in riscos:
            caixa = d.caixa(None, x + 18, y, item, 264, 40, "risco", tamanho=14, icone="warning")
            y += caixa["height"] + 10
    d.linha([(0, 530), (1260, 530)], cor=BORDA_NO["avaliacao"])
    d.texto(10, 538, "barreira de cegamento", 14, ACENTO["avaliacao"])
    d.cilindro(None, 0, 565, 170, 110, "oracle/", "avaliacao", tamanho=17)
    d.texto(200, 585, "ground truth, manifesto e validador oficial do RealVuln", 18, TEXTO)
    d.texto(200, 615, "fora de todas as áreas de trabalho · consultado somente após o fechamento da coleta",
            15, CINZA)
    return d


def custodia():
    d = Diagrama(16)
    d.faixa(None, 0, 0, 540, 640, "resultados/ia/coleta/C3-ALVO-0007-R02/", "neutro", tamanho=17,
            icone="folder")
    d.faixa(None, 20, 55, 500, 90, "tentativa-001 · falha de formato", "avaliacao", tamanho=17)
    d.texto(38, 92, "linha_final além do fim de sqli/views.py (162 > 160); pasta preservada",
            14, CINZA, 460)
    d.faixa("t2", 20, 165, 500, 455, "tentativa-002 · concluída", "hibrido", tamanho=17)
    d.texto(300, 172, "em C5 e C6, também os alertas", 12, CINZA)
    arquivos = ["prompt.txt", "payload-codigo.json", "eventos.jsonl", "stderr.txt",
                "resposta-bruta.txt", "resposta.json"]
    for k, nome in enumerate(arquivos):
        x = 40 + (k % 2) * 240
        y = 215 + (k // 2) * 52
        d.caixa(None, x, y, nome, 220, 40, "branco", tamanho=14, icone="description")
    d.caixa("manifesto", 40, 470, "manifesto.json: SHA-256 de cada artefato, horários, duração, "
            "versão do cliente, modelo solicitado e exibido, tokens e estado", 460, 120, "hibrido",
            tamanho=15, destaque=True)
    d.seta(None, "manifesto", inicio=(270, 372), fim=(270, 466), espessura=2)
    d.texto(285, 405, "SHA-256 de cada arquivo", 14, CINZA)
    etapas = [
        ("e1", "Validação do contrato: esquema, caminhos, linhas e eventos proibidos", "neutro"),
        ("e2", "Seleção da maior tentativa válida, antes de abrir o oracle", "hibrido"),
        ("e3", "Auditoria de fechamento: 364 unidades e 433 tentativas", "neutro"),
        ("e4", "evidencias/: inventários ligados aos registros por hash", "dados"),
        ("e5", "Pontuação com o oracle no modo estrito", "avaliacao"),
    ]
    for k, (nome, texto, cor) in enumerate(etapas):
        y = 30 + k * 120
        d.caixas["s" + nome] = d.selo(640, y + 17, str(k + 1), cor)
        d.caixa(nome, 690, y, texto, 400, 70, cor, tamanho=15)
    for a, b in zip(etapas, etapas[1:]):
        d.seta(a[0], b[0])
    d.seta("manifesto", "se1", lados=("direita", "esquerda"), via=((590, 530), (590, 65)))
    d.texto(1100, 40, "inválida:\nnova tentativa-NNN", 14, ACENTO["avaliacao"])
    return d


def exemplo_relatos():
    d = Diagrama(17)
    amostra = {r["relatorio_id"]: r for r in csv.DictReader(
        (REPO / "evidencias/avaliacao/amostra-qualitativa-cega.csv").open(encoding="utf-8-sig"))}
    notas = {r["relatorio_id"]: r for r in csv.DictReader(
        (REPO / "evidencias/avaliacao-qualitativa/pontuacoes-condicoes.csv").open(encoding="utf-8-sig"))}
    grupo = {n["condicao"]: rid for rid, n in notas.items() if n["grupo_comum"] == "COMUM-003"}
    severidades = {"baixa": "baixa", "media": "média", "alta": "alta", "critica": "crítica"}
    d.caixa(None, 0, 0, "Mesma vulnerabilidade do recorte comum: CWE-89 (injeção de SQL) em "
            "sqli.py, linha 16", 1160, 54, "neutro", tamanho=18)
    lados = (("C1", "C1 · Bandit", "sast"), ("C3", "C3 · Cursor com GPT-5.6 Luna", "ia"))
    def altura_texto(texto):
        return len(Diagrama._quebrar(texto, 515, 15)) * 15 * 1.25
    fim_textos = max(177 + altura_texto("“" + amostra[grupo[c]]["descricao"] + "”") + 14 + 22
                     + altura_texto(amostra[grupo[c]]["recomendacao"] or "(ausente)")
                     for c, _, _ in lados)
    inicio_barras = round(fim_textos + 35)
    altura_cartao = inicio_barras + 4 * 36 + 70 - 80
    for i, (condicao, titulo, cor) in enumerate(lados):
        rid = grupo[condicao]
        relato, nota = amostra[rid], notas[rid]
        x = i * 600
        d.faixa(None, x, 80, 560, altura_cartao, titulo, cor, tamanho=21)
        d.texto(x + 20, 118, relato["cwe_reportado"] + " · severidade "
                + severidades.get(relato["severidade_reportada"], relato["severidade_reportada"])
                + " · " + relato["arquivo_reportado"] + ":" + relato["linha_reportada"], 14, CINZA)
        d.texto(x + 20, 155, "Descrição", 15, ACENTO[cor])
        y = d.texto(x + 20, 177, "“" + relato["descricao"] + "”", 15, TEXTO, 515) + 14
        d.texto(x + 20, y, "Recomendação", 15, ACENTO[cor])
        recomendacao = relato["recomendacao"] or "(ausente)"
        d.texto(x + 20, y + 22, "“" + recomendacao + "”" if relato["recomendacao"] else recomendacao,
                15, TEXTO if relato["recomendacao"] else CINZA, 515)
        y = inicio_barras
        for rotulo, campo, maximo in (("Correção técnica", "correcao_tecnica", 5),
                                      ("Localização", "localizacao", 5),
                                      ("Acionabilidade", "acionabilidade", 5),
                                      ("Clareza", "clareza_total", 5)):
            valor = int(nota[campo])
            d.texto(x + 20, y + 2, rotulo, 15, TEXTO)
            d.retangulo(x + 180, y, 260, 22, "#F1F3F4")
            d.retangulo(x + 180, y, 260 * valor / maximo, 22, DESTAQUE[cor])
            d.texto(x + 452, y + 2, str(valor) + "/" + str(maximo), 15, TEXTO)
            y += 36
        score = format(float(nota["score_total"]), ".2f").rstrip("0").rstrip(".").replace(".", ",")
        d.texto(x + 20, y + 10, "Score", 17, ACENTO[cor])
        d.texto(x + 180, y + 2, score, 30, DESTAQUE[cor] if cor == "ia" else ACENTO[cor])
    d.texto(0, altura_cartao + 100, "Notas atribuídas pelo avaliador LLM; textos reproduzidos sem "
            "edição a partir da amostra cega.", 14, CINZA)
    return d


DIAGRAMAS = {
    "fundamentacao-evolucao-agentes": evolucao_agentes,
    "fundamentacao-anatomia-agente": anatomia_agente,
    "fundamentacao-padroes-hibridos": padroes_hibridos,
    "metodologia-desenho-experimental": desenho_experimental,
    "metodologia-questoes-medidas": questoes_medidas,
    "metodologia-correspondencia": correspondencia,
    "metodologia-bootstrap": bootstrap,
    "metodologia-fluxo-qualitativo": fluxo_qualitativo,
    "metodologia-protocolo": protocolo,
    "desenvolvimento-isolamento": isolamento,
    "desenvolvimento-custodia": custodia,
    "avaliacao-exemplo-relatos": exemplo_relatos,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=REPO / "monografia" / "figs" / "excalidraw")
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    for nome, construir in DIAGRAMAS.items():
        conteudo = json.dumps(construir().documento(), ensure_ascii=False, indent=2)
        (args.saida / (nome + ".excalidraw")).write_text(conteudo + "\n", encoding="utf-8")
    print(json.dumps({"diagramas": len(DIAGRAMAS), "saida": str(args.saida)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
