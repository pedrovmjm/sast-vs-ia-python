#!/usr/bin/env python3
"""Exporta diagramas .excalidraw para PNG com a biblioteca oficial do Excalidraw.

Equivale à exportação manual em https://excalidraw.com (escala 3x, fundo branco):
cada arquivo é embutido numa página que carrega o Excalidraw por CDN, e o Chrome
sem interface devolve o PNG em base64 no DOM.

Uso: python3 scripts/exportar-excalidraw-png.py [nome ...]
"""

import argparse
import base64
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PASTA = REPO / "monografia" / "figs" / "excalidraw"
VERSAO = "0.17.6"
CHROMES = [
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium",
]

PAGINA = """<!doctype html><html><head><meta charset="utf-8">
<script>window.EXCALIDRAW_ASSET_PATH = "https://unpkg.com/@excalidraw/excalidraw@{versao}/dist/";</script>
<script src="https://unpkg.com/react@18.2.0/umd/react.production.min.js"></script>
<script src="https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@excalidraw/excalidraw@{versao}/dist/excalidraw.production.min.js"></script>
</head><body><pre id="saida">pendente</pre>
<script id="cena" type="application/json">{cena}</script>
<script>
(async () => {{
  const saida = document.getElementById("saida");
  try {{
    const cena = JSON.parse(document.getElementById("cena").textContent);
    const blob = await ExcalidrawLib.exportToBlob({{
      elements: cena.elements, files: cena.files, mimeType: "image/png", exportPadding: 20,
      appState: {{ exportBackground: true, viewBackgroundColor: "#ffffff",
                   exportWithDarkMode: false, exportScale: {escala} }},
    }});
    const leitor = new FileReader();
    leitor.onload = () => {{ saida.textContent = "PNG:" + leitor.result.split(",")[1]; }};
    leitor.readAsDataURL(blob);
  }} catch (erro) {{ saida.textContent = "ERRO:" + erro; }}
}})();
</script></body></html>"""


def chrome():
    for caminho in CHROMES:
        if Path(caminho).exists():
            return caminho
    encontrado = shutil.which("chrome") or shutil.which("google-chrome")
    if not encontrado:
        raise SystemExit("Chrome não encontrado")
    return encontrado


def caminho_para_chrome(caminho, executavel):
    if executavel.endswith(".exe") and str(caminho).startswith("/mnt/"):
        return subprocess.run(["wslpath", "-w", str(caminho)], capture_output=True, text=True,
                              check=True).stdout.strip()
    return str(caminho)


def exportar(nome, escala, executavel):
    cena = (PASTA / (nome + ".excalidraw")).read_text(encoding="utf-8")
    cena = cena.replace("</", "<\\/")
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=PASTA, delete=False,
                                     encoding="utf-8") as pagina:
        pagina.write(PAGINA.format(versao=VERSAO, cena=cena, escala=escala))
    try:
        url = "file:///" + caminho_para_chrome(pagina.name, executavel).replace("\\", "/")
        dom = subprocess.run([executavel, "--headless=new", "--disable-gpu",
                              "--virtual-time-budget=30000", "--dump-dom", url],
                             capture_output=True, text=True, encoding="utf-8", timeout=180).stdout
    finally:
        Path(pagina.name).unlink()
    resultado = re.search(r'<pre id="saida">(.*?)</pre>', dom, re.S)
    texto = resultado.group(1) if resultado else "ERRO: página sem resultado"
    if not texto.startswith("PNG:"):
        raise SystemExit(nome + ": " + texto[:300])
    destino = PASTA / (nome + ".png")
    destino.write_bytes(base64.b64decode(texto[4:]))
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nomes", nargs="*", help="diagramas sem extensão; padrão: todos")
    parser.add_argument("--escala", type=int, default=3)
    args = parser.parse_args()
    nomes = args.nomes or sorted(p.stem for p in PASTA.glob("*.excalidraw"))
    executavel = chrome()
    gerados = [str(exportar(nome, args.escala, executavel).name) for nome in nomes]
    print(json.dumps({"png": gerados}, ensure_ascii=False))


if __name__ == "__main__":
    main()
