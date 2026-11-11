"""Amplia as fontes dos três diagramas, preservando os elementos do original.

Gera variantes editáveis; não sobrescreve as cenas originais.
"""
import importlib.util
import json
import os
import csv
from functools import lru_cache
from pathlib import Path
from PIL import ImageFont

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('diagramas', BASE / 'gerar-diagramas-excalidraw.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

FONTE = 'C:/Windows/Fonts/arial.ttf' if os.name == 'nt' else '/mnt/c/Windows/Fonts/arial.ttf'


@lru_cache(None)
def fonte(tamanho):
    return ImageFont.truetype(FONTE, round(tamanho * 4))


def medir(texto, tamanho):
    return fonte(tamanho).getlength(texto) / 4


class Diagrama(g.Diagrama):
    @staticmethod
    def _quebrar(texto, largura, tamanho):
        linhas = []
        for paragrafo in texto.split('\n'):
            linha = ''
            for palavra in paragrafo.split():
                candidato = (linha + ' ' + palavra).strip()
                if linha and medir(candidato, tamanho) > largura - 2:
                    linhas.append(linha)
                    linha = palavra
                else:
                    linha = candidato
            linhas.append(linha)
        return linhas

    def _texto(self, texto, x, y, largura, altura, tamanho, container=None,
               alinhamento='center', vertical='middle', cor=g.TEXTO):
        real = max(medir(linha, tamanho) for linha in texto.split('\n'))
        if alinhamento == 'center':
            x += (largura - real) / 2
        return super()._texto(texto, x, y, real, altura, tamanho, container,
                              alinhamento, vertical, cor)

    def texto(self, x, y, texto, tamanho=19, cor=g.TEXTO, largura=None, alinhamento='left'):
        linhas = self._quebrar(texto, largura, tamanho) if largura else texto.split('\n')
        real = max(medir(linha, tamanho) for linha in linhas)
        if alinhamento == 'center' and largura:
            x += (largura - real) / 2
        altura = len(linhas) * tamanho * 1.25
        self._texto('\n'.join(linhas), x, y, real, altura, tamanho,
                    alinhamento=alinhamento, vertical='top', cor=cor)
        return y + altura

    def seta(self, *args, **kwargs):
        seta = super().seta(*args, **kwargs)
        # O exportador não deve recalcular os extremos de rotas já definidas.
        seta['startBinding'] = None
        seta['endBinding'] = None
        return seta


def experimental():
    d = Diagrama(14)
    d.cilindro('corpus', 0, 200, 200, 160,
               'RealVuln v1.0\n26 repositórios Python', 'neutro', tamanho=20)
    y = 380
    for linha in ('697 vulnerabilidades', '120 armadilhas de FP',
                  'revisões fixadas por hash', 'alvos anônimos ALVO-NNNN'):
        y = d.texto(5, y, '• ' + linha, 19, g.CINZA, 190) + 10
    faixas = [
        ('sast', 'SAST', 'Docker sem rede · 1 execução por alvo · 52 execuções', 0,
         [('c1', 'C1 · Bandit 1.9.4'), ('c2', 'C2 · Semgrep CE 1.172.0')]),
        ('ia', 'IA isolada', 'GPT-5.6 Luna nos dois produtos · 3 repetições · 156 execuções', 220,
         [('c3', 'C3 · Cursor'), ('c4', 'C4 · OpenAI Codex')]),
        ('hibrido', 'Híbrida', 'mesmos alertas para os dois · 3 repetições · 156 execuções', 440,
         [('c5', 'C5 · Cursor + alertas SAST'), ('c6', 'C6 · Codex + alertas SAST')]),
    ]
    for cor, titulo, nota, y0, condicoes in faixas:
        d.faixa('faixa-' + cor, 250, y0, 550, 210 if cor == 'sast' else 200, titulo, cor, tamanho=23)
        d.texto(420, y0 + 12, nota, 19, g.CINZA, 355)
        for k, (nome, texto) in enumerate(condicoes):
            d.caixa(nome, 270, y0 + 78 + k * 58, texto, 300, 48, cor, tamanho=20)
        d.seta('corpus', 'faixa-' + cor, lados=('direita', 'esquerda'),
               fim=(250, y0 + 100))
    d.caixa('alertas', 590, 75, 'União normalizada\n1.416 alertas\n1.410 após\ndeduplicação',
            190, 120, 'sast', tamanho=19)
    d.seta('c1', 'alertas', fim=(590, 102))
    d.seta('c2', 'alertas', fim=(590, 160))
    d.texto(600, 305, 'código no prompt,\nsem alertas', 19, g.CINZA, 170)
    for nome, y0 in [('c5', 542), ('c6', 600)]:
        d.seta('alertas', nome, lados=('base', 'direita'),
               inicio=(780, 135), via=((790, 135), (790, y0)), tracejado=True, cor=g.ACENTO['hibrido'])
    d.linha([(0, 680), (800, 680)], cor=g.BORDA_NO['avaliacao'])
    d.icone(8, 696, 'lock', g.ACENTO['avaliacao'], 22)
    d.texto(42, 696, 'Ground truth somente após o fechamento da coleta', 19, g.ACENTO['avaliacao'])
    d.cilindro('oracle', 0, 775, 170, 160, 'Ground truth\n817 entradas', 'avaliacao', tamanho=20)
    d.faixa('quanti', 220, 750, 275, 300, 'Avaliação quantitativa', 'avaliacao', tamanho=21)
    d.faixa('quali', 525, 750, 275, 300, 'Avaliação qualitativa', 'avaliacao', tamanho=21)
    for x, linhas in [(238, ('avaliador oficial do RealVuln', 'caminho, CWE aceitável e ±10 linhas',
                            'TP, FP, FN e TN por entrada', 'IC95%: 10.000 reamostragens por repositório')),
                      (543, ('300 relatos TP, 50 por condição', 'ordem opaca, sem indicar a condição',
                             'rubrica: correção, localização, acionabilidade e clareza',
                             'avaliador LLM de outra família'))]:
        y = 800
        for linha in linhas:
            y = d.texto(x, y, '• ' + linha, 19, g.TEXTO, 239) + 9
    d.seta('oracle', 'quanti', lados=('direita', 'esquerda'), tracejado=True,
           cor=g.ACENTO['avaliacao'])
    # Coletor comum: as três abordagens alimentam a avaliação quantitativa.
    for yc in (105, 310, 530):
        d.linha([(800, yc), (820, yc)], tracejado=False)
    d.linha([(820, 105), (820, 725)], tracejado=False)
    d.seta(None, 'quanti', inicio=(820, 725), via=((360, 725),), fim=(360, 750))
    d.texto(390, 650, 'saídas de C1–C6', 19, g.CINZA)
    d.seta('quanti', 'quali', inicio=(495, 900), fim=(525, 900))
    d.texto(240, 1070, 'TP da 1ª repetição → avaliação qualitativa', 19, g.CINZA)
    d.texto(0, 1110, '364 execuções válidas · 433 tentativas preservadas\nOrdem fixa dos alvos por repetição',
            19, g.CINZA, 800)
    return d


def custodia():
    d = Diagrama(16)
    d.faixa(None, 0, 0, 540, 640, 'resultados/ia/coleta/C3-ALVO-0007-R02/',
            'neutro', tamanho=20, icone='folder')
    d.faixa(None, 20, 55, 500, 110, 'tentativa-001 · falha de formato', 'avaliacao', tamanho=20)
    d.texto(38, 95, 'linha_final além do fim de sqli/views.py (162 > 160); pasta preservada',
            19, g.CINZA, 460)
    d.faixa('t2', 20, 185, 500, 435, 'tentativa-002 · concluída', 'hibrido', tamanho=20)
    arquivos = ['prompt.txt', 'payload-codigo.json', 'eventos.jsonl', 'stderr.txt',
                'resposta-bruta.txt', 'resposta.json']
    for k, nome in enumerate(arquivos):
        d.caixa(None, 40 + (k % 2) * 240, 245 + (k // 2) * 54,
                nome, 228, 44, 'branco', tamanho=19, icone='description')
    d.texto(38, 430, 'Em C5 e C6, também os alertas', 19, g.CINZA)
    d.caixa('manifesto', 40, 490, 'manifesto.json: SHA-256 de cada artefato, horários, duração, '
            'versão do cliente, modelo solicitado e exibido, tokens e estado',
            460, 120, 'hibrido', tamanho=20, destaque=True)
    d.seta(None, 'manifesto', inicio=(80, 455), fim=(80, 490))
    d.texto(110, 460, 'SHA-256 de cada arquivo', 19, g.CINZA)
    etapas = [('e1', 'Validação do contrato: esquema, caminhos, linhas e eventos proibidos', 'neutro'),
              ('e2', 'Seleção da maior tentativa válida, antes de abrir o oracle', 'hibrido'),
              ('e3', 'Auditoria de fechamento: 364 unidades e 433 tentativas', 'neutro'),
              ('e4', 'evidencias/: inventários ligados aos registros por hash', 'dados'),
              ('e5', 'Pontuação com o oracle no modo estrito', 'avaliacao')]
    for k, (nome, texto, cor) in enumerate(etapas):
        y = 30 + k * 120
        d.caixas['s' + nome] = d.selo(640, y + 17, str(k + 1), cor)
        rotulo = d.elementos[-1]
        rotulo.update(fontSize=19, width=9.5, height=23.75, x=653.25, y=y + 23.125)
        d.caixa(nome, 690, y, texto, 400, 78, cor, tamanho=20)
    for a, b in zip(etapas, etapas[1:]):
        d.seta(a[0], b[0])
    d.seta('manifesto', 'se1', lados=('direita', 'esquerda'), via=((590, 550), (590, 65)))
    d.texto(690, 615, 'Inválida na etapa 1: nova tentativa-NNN', 19, g.ACENTO['avaliacao'])
    return d


def relatos():
    d = Diagrama(17)
    amostra = {r['relatorio_id']: r for r in csv.DictReader(
        (g.REPO / 'evidencias/avaliacao/amostra-qualitativa-cega.csv').open(encoding='utf-8-sig'))}
    notas = {r['relatorio_id']: r for r in csv.DictReader(
        (g.REPO / 'evidencias/avaliacao-qualitativa/pontuacoes-condicoes.csv').open(encoding='utf-8-sig'))}
    grupo = {n['condicao']: rid for rid, n in notas.items() if n['grupo_comum'] == 'COMUM-003'}
    lados = [('C1', 'C1 · Bandit', 'sast'), ('C3', 'C3 · Cursor com GPT-5.6 Luna', 'ia')]
    severidades = {'media': 'média', 'alta': 'alta'}
    altura = lambda texto: len(d._quebrar(texto, 504, 19)) * 23.75
    descricoes = {c: '“' + amostra[grupo[c]]['descricao'] + '”' for c, _, _ in lados}
    recomendacoes = {c: ('“' + amostra[grupo[c]]['recomendacao'] + '”'
                          if amostra[grupo[c]]['recomendacao'] else '(ausente)') for c, _, _ in lados}
    y_recomendacao = 177 + max(map(altura, descricoes.values())) + 18
    y_barras = y_recomendacao + 30 + max(map(altura, recomendacoes.values())) + 28
    y_score = y_barras + 4 * 35 + 8
    fim = y_score + 58
    d.caixa(None, 0, 0, 'Mesma vulnerabilidade do recorte comum: CWE-89 (injeção de SQL) em '
            'sqli.py, linha 16', 1160, 54, 'neutro', tamanho=20, ajustar=False)
    for i, (c, titulo, cor) in enumerate(lados):
        x = i * 600
        relato, nota = amostra[grupo[c]], notas[grupo[c]]
        d.faixa(None, x, 80, 560, fim - 80, titulo, cor, tamanho=23)
        d.texto(x + 24, 119, relato['cwe_reportado'] + ' · severidade '
                + severidades[relato['severidade_reportada']] + ' · ' + relato['arquivo_reportado']
                + ':' + relato['linha_reportada'], 19, g.CINZA, 504)
        d.texto(x + 24, 151, 'Descrição', 19, g.ACENTO[cor])
        d.texto(x + 24, 177, descricoes[c], 19, g.TEXTO, 504)
        d.texto(x + 24, y_recomendacao, 'Recomendação', 19, g.ACENTO[cor])
        d.texto(x + 24, y_recomendacao + 30, recomendacoes[c], 19, g.TEXTO, 504)
        for k, (rotulo, campo) in enumerate([('Correção técnica', 'correcao_tecnica'),
                                            ('Localização', 'localizacao'),
                                            ('Acionabilidade', 'acionabilidade'), ('Clareza', 'clareza_total')]):
            y = y_barras + k * 35
            valor = int(nota[campo])
            d.texto(x + 24, y, rotulo, 19, g.TEXTO)
            d.retangulo(x + 200, y, 250, 22, '#F1F3F4')
            d.retangulo(x + 200, y, 250 * valor / 5, 22, g.DESTAQUE[cor])
            d.texto(x + 470, y, str(valor) + '/5', 19, g.TEXTO)
        d.texto(x + 24, y_score + 7, 'Score', 19, g.ACENTO[cor])
        score = format(float(nota['score_total']), '.2f').rstrip('0').rstrip('.').replace('.', ',')
        d.texto(x + 200, y_score, score, 30, g.ACENTO[cor])
    d.texto(0, fim + 20, 'Notas atribuídas pelo avaliador LLM; textos reproduzidos sem edição a partir da amostra cega.',
            19, g.CINZA, 1160)
    return d


if __name__ == '__main__':
    pasta = g.REPO / 'monografia/figs/excalidraw'
    for nome, construir in [('metodologia-desenho-experimental', experimental),
                             ('desenvolvimento-custodia', custodia),
                             ('avaliacao-exemplo-relatos', relatos)]:
        destino = pasta / (nome + '-legivel.excalidraw')
        destino.write_text(json.dumps(construir().documento(), ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
        print(destino.name)
