from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from runner.avaliacao.estatistica import (
    kappa_ponderado_quadratico,
    metricas_contagens,
    percentil,
    resumo_distribuicao,
)
from runner.avaliacao.rubrica import flesch_portugues, kappa_nao_ponderado


class MetricasTests(unittest.TestCase):
    def test_f_scores_e_fpr(self):
        metricas = metricas_contagens(tp=8, fp=2, fn=2, tn=8)
        self.assertAlmostEqual(0.8, metricas["precision"])
        self.assertAlmostEqual(0.8, metricas["recall"])
        self.assertAlmostEqual(0.8, metricas["f1"])
        self.assertAlmostEqual(0.8, metricas["f2"])
        self.assertAlmostEqual(0.8, metricas["f3"])
        self.assertAlmostEqual(0.2, metricas["fpr"])

    def test_denominador_zero_produz_zero(self):
        metricas = metricas_contagens(tp=0, fp=0, fn=0, tn=0)
        self.assertTrue(all(valor == 0 for valor in metricas.values()))

    def test_percentil_interpolado(self):
        self.assertEqual(1.0, percentil([1], 0.5))
        self.assertAlmostEqual(1.75, percentil([1, 2, 3, 4], 0.25))
        self.assertAlmostEqual(3.25, percentil([1, 2, 3, 4], 0.75))

    def test_resumo_distribuicao(self):
        resumo = resumo_distribuicao([1, 2, 3, 4])
        self.assertEqual(4, resumo["n"])
        self.assertEqual(1.0, resumo["minimo"])
        self.assertEqual(4.0, resumo["maximo"])
        self.assertEqual(2.5, resumo["mediana"])

    def test_kappa_perfeito(self):
        pares = [(0, 0), (1, 1), (2, 2), (3, 3)]
        self.assertAlmostEqual(1.0, kappa_ponderado_quadratico(pares))

    def test_kappa_binario_perfeito(self):
        self.assertAlmostEqual(1.0, kappa_nao_ponderado([(0, 0), (1, 1)]))

    def test_flesch_remove_codigo_e_produz_indice(self):
        resultado = flesch_portugues("A falha permite ataque. Use `safe_call(valor)` no arquivo app/main.py.")
        self.assertGreater(resultado["palavras"], 0)
        self.assertIsInstance(resultado["indice"], float)
        self.assertNotIn("safe_call", resultado["texto_limpo"])


class VendorTests(unittest.TestCase):
    def test_blobs_oficiais_nao_foram_alterados(self):
        raiz = RAIZ / "runner" / "avaliacao" / "vendor"
        source = json.loads((raiz / "SOURCE.json").read_text(encoding="utf-8"))
        for relativo, esperado in source["arquivos"].items():
            conteudo = (raiz / relativo).read_bytes()
            cabecalho = f"blob {len(conteudo)}\0".encode("ascii")
            observado = hashlib.sha1(cabecalho + conteudo).hexdigest()
            self.assertEqual(esperado, observado, relativo)


if __name__ == "__main__":
    unittest.main()
