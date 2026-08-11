import ast
import unittest
from pathlib import Path

from runner.aquisicao import calcular_sha256_arvore


RAIZ = Path(__file__).resolve().parents[1]
FIXTURE = RAIZ / "tests" / "fixtures" / "alvo-sintetico"
HASH_FIXTURE = "1dbbff2e447b9ea0596f38b414c0d1e1ce4f5789e30f964b8dc568f39fd474ef"


class FixtureSinteticaTest(unittest.TestCase):
    def test_fixture_tem_inventario_e_hash_canonico_fixos(self):
        inventario = sorted(
            item.relative_to(FIXTURE).as_posix()
            for item in FIXTURE.rglob("*")
            if item.is_file()
        )

        self.assertEqual(["alvo_vulneravel.py"], inventario)
        self.assertEqual(HASH_FIXTURE, calcular_sha256_arvore(FIXTURE))

    def test_fixture_e_analisada_por_ast_sem_importar_codigo_alvo(self):
        arvore = ast.parse(
            (FIXTURE / "alvo_vulneravel.py").read_text(encoding="utf-8")
        )
        chamadas = [no for no in ast.walk(arvore) if isinstance(no, ast.Call)]
        nomes = {
            no.func.id
            for no in chamadas
            if isinstance(no.func, ast.Name)
        }
        atributos = {
            no.func.attr
            for no in chamadas
            if isinstance(no.func, ast.Attribute)
        }

        self.assertIn("eval", nomes)
        self.assertIn("Popen", atributos)
        self.assertIn("write_text", atributos)

    def test_gate_full_inclui_as_duas_execucoes_reais(self):
        gate = (RAIZ / "scripts" / "gate.ps1").read_text(encoding="utf-8")

        self.assertIn("test-fumaca-sintetica.ps1", gate)


if __name__ == "__main__":
    unittest.main()
