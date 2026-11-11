# Arquivos de imagem da monografia

Conferência realizada em 10 de novembro de 2026 a partir das inclusões nos
fontes LaTeX e dos registros `INPUT` de `monografia/dissertacao.fls` da
compilação local. São **17 figuras e o logotipo da capa**: 12 gráficos PDF,
três diagramas PNG, dois diagramas TikZ e um logotipo PNG.

## Arquivos efetivamente usados

Todos os caminhos abaixo são relativos a `monografia/figs/`.

| Uso | Arquivo |
| --- | --- |
| Capa | `logo.png` |
| Desenho experimental | `excalidraw/metodologia-desenho-experimental-legivel.png` |
| Fluxo de preparação, coleta e avaliação | `fluxo-desenvolvimento.tex` |
| Controles de isolamento | `controles-isolamento.tex` |
| Cadeia de custódia | `excalidraw/desenvolvimento-custodia-legivel.png` |
| Precisão e recall | `graficos/deteccao-precisao-recall.pdf` |
| Falsos positivos | `graficos/deteccao-falsos-positivos.pdf` |
| Recall por severidade | `graficos/deteccao-recall-severidade.pdf` |
| Exemplo dos relatos | `excalidraw/avaliacao-exemplo-relatos-legivel.png` |
| Dimensões de qualidade | `graficos/qualidade-dimensoes.pdf` |
| Distribuição do score | `graficos/qualidade-distribuicao-score.pdf` |
| Qualidade com alertas SAST | `graficos/hibrido-qualidade-dimensoes.pdf` |
| Clareza | `graficos/qualidade-clareza.pdf` |
| Comparações pareadas | `graficos/hibrido-comparacoes-pareadas.pdf` |
| Estabilidade entre repetições | `graficos/estabilidade-repeticoes.pdf` |
| Priorização por severidade | `graficos/priorizacao-severidade.pdf` |
| Tempo e tokens | `graficos/operacional-tempo-tokens.pdf` |
| Síntese de precisão e qualidade | `graficos/sintese-precisao-qualidade.pdf` |

O logotipo está em `pretextual/capa.tex`; o desenho experimental, em
`capitulos/metodologia.tex`; o fluxo, os controles e a custódia, em
`capitulos/desenvolvimento.tex`. As demais inclusões estão em
`capitulos/resultados.tex`.

## Seleção para o GitHub

Na conferência inicial, apenas o logotipo e os dois diagramas TikZ já estavam
versionados. Os PNG e as cenas Excalidraw estavam sem rastreamento, assim como
os SVG dos gráficos. Os 12 PDFs eram ignorados pela regra global `*.pdf`.

A seleção recomendada inclui:

- os 12 pares PDF/SVG de `monografia/figs/graficos/`: o LaTeX usa o PDF
  vetorial; o SVG permite edição e reutilização;
- os três pares `*-legivel.png`/`*-legivel.excalidraw` da tabela: preservam a
  imagem usada e a cena editável correspondente;
- `scripts/icones-material/`, incluindo `FONTE.txt`, com a origem e a licença
  declarada dos ícones incorporados pelo gerador de diagramas;
- este inventário e os scripts de geração, que já estão versionados.

Os PNG `conferencia-pagina-*.png` são capturas locais de revisão e estão
ignorados. Os demais diagramas e as versões sem `-legivel` não são incluídos
pelo LaTeX atual; podem ser preservados como material complementar, mas não
são necessários para compilar a monografia.

O `.gitignore` permite os PDFs em `monografia/figs/graficos/`; o PDF final da
monografia e os arquivos auxiliares de compilação continuam ignorados.

## Origem e reprodução

| Arquivo ou recurso | Gerador ou origem |
| --- | --- |
| Gráficos PDF/SVG | `scripts/gerar-graficos-monografia.py`, usando as evidências da avaliação |
| Cenas Excalidraw originais | `scripts/gerar-diagramas-excalidraw.py` |
| Três cenas com sufixo `-legivel` | `scripts/ajustar-figuras-legibilidade.py` |
| Exportações PNG das cenas | `scripts/exportar-excalidraw-png.py` |
| Ícones SVG dos diagramas | `scripts/icones-material/`; proveniência em `FONTE.txt` |
| Diagramas TikZ | Fontes `.tex` da tabela, processados diretamente pelo LaTeX |
| Logotipo | Arquivo existente no repositório; os geradores acima não o produzem |

Para regenerar os gráficos, é necessário Python com Matplotlib. O ajuste de
legibilidade usa Pillow e a fonte Arial do Windows (diretamente ou via WSL).
A exportação PNG usa Chrome/Chromium e acesso às bibliotecas por CDN.
Os arquivos finais permitem compilar sem executar esses geradores.

```powershell
python scripts/gerar-graficos-monografia.py
python scripts/ajustar-figuras-legibilidade.py
python scripts/exportar-excalidraw-png.py metodologia-desenho-experimental-legivel desenvolvimento-custodia-legivel avaliacao-exemplo-relatos-legivel
```
