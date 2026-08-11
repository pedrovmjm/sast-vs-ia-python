import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from runner.preparacao import (
    ErroPreparacao,
    criar_inventario,
    escrever_json_atomico,
    preparar_alvo,
    validar_inventarios_iguais,
)


class PreparacaoTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.origem = self.raiz / "origem"
        self.origem.mkdir()
        (self.origem / "app.py").write_bytes(b"print('dado')\n")
        (self.origem / "pkg").mkdir()
        (self.origem / "pkg" / "mod.py").write_bytes(b"x = 1\n")

    def test_inventario_deterministico_e_ordenado(self):
        primeiro = criar_inventario(self.origem)
        segundo = criar_inventario(self.origem)
        self.assertEqual(primeiro, segundo)
        self.assertEqual(2, primeiro["arquivos"])
        self.assertEqual(["app.py", "pkg/mod.py"], [i["caminho"] for i in primeiro["itens"]])

    def test_hash_muda_com_conteudo(self):
        antes = criar_inventario(self.origem)["entrada_sha256"]
        (self.origem / "app.py").write_bytes(b"alterado\n")
        depois = criar_inventario(self.origem)["entrada_sha256"]
        self.assertNotEqual(antes, depois)

    def test_hash_muda_com_caminho(self):
        antes = criar_inventario(self.origem)["entrada_sha256"]
        (self.origem / "app.py").rename(self.origem / "outro.py")
        depois = criar_inventario(self.origem)["entrada_sha256"]
        self.assertNotEqual(antes, depois)

    def test_recusa_arvore_vazia(self):
        vazio = self.raiz / "vazio"
        vazio.mkdir()
        with self.assertRaisesRegex(ErroPreparacao, "vazio"):
            criar_inventario(vazio)

    def test_recusa_ground_truth(self):
        (self.origem / "ground-truth").mkdir()
        (self.origem / "ground-truth" / "resposta.json").write_text("{}")
        with self.assertRaisesRegex(ErroPreparacao, "proibido"):
            criar_inventario(self.origem)

    def test_recusa_manifesto_interno_do_benchmark(self):
        (self.origem / "benchmark-manifest.json").write_text("{}")
        with self.assertRaisesRegex(ErroPreparacao, "benchmark"):
            preparar_alvo(self.origem, self.raiz / "ALVO-0001")

    def test_recusa_link_simbolico(self):
        link = self.origem / "atalho.py"
        try:
            link.symlink_to(self.origem / "app.py")
        except OSError:
            self.skipTest("host não permite criar link simbólico")
        with self.assertRaisesRegex(ErroPreparacao, "link"):
            criar_inventario(self.origem)

    def test_prepara_copia_sem_alterar_origem(self):
        origem_antes = criar_inventario(self.origem)
        destino = self.raiz / "ALVO-0001"
        observado = preparar_alvo(self.origem, destino)
        self.assertEqual(origem_antes, observado)
        self.assertEqual(origem_antes, criar_inventario(destino))
        self.assertEqual(b"print('dado')\n", (destino / "app.py").read_bytes())

    def test_recusa_destino_existente(self):
        destino = self.raiz / "ALVO-0001"
        destino.mkdir()
        with self.assertRaisesRegex(ErroPreparacao, "novo"):
            preparar_alvo(self.origem, destino)

    def test_recusa_destino_sobreposto(self):
        with self.assertRaisesRegex(ErroPreparacao, "sobrepor"):
            preparar_alvo(self.origem, self.origem / "copia")

    def test_compara_inventarios_integralmente(self):
        inventario = criar_inventario(self.origem)
        self.assertEqual(
            inventario["entrada_sha256"],
            validar_inventarios_iguais(inventario, dict(inventario)),
        )
        divergente = dict(inventario)
        divergente["arquivos"] = 99
        with self.assertRaisesRegex(ErroPreparacao, "divergem"):
            validar_inventarios_iguais(inventario, divergente)

    def test_escrita_json_atomica_sem_sobrescrita(self):
        destino = self.raiz / "evidencia" / "inventario.json"
        escrever_json_atomico(destino, {"b": 2, "a": 1})
        self.assertEqual({"a": 1, "b": 2}, json.loads(destino.read_text("utf-8")))
        self.assertEqual('{"a":1,"b":2}\n', destino.read_text("utf-8"))
        with self.assertRaisesRegex(ErroPreparacao, "existe"):
            escrever_json_atomico(destino, {"a": 1})


class EvidenciaPrimeiraExecucaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raiz = Path(__file__).parents[1] / "evidencias" / "primeira-execucao"
        cls.resumo = json.loads((cls.raiz / "resumo.json").read_text("utf-8"))
        cls.inventario_c1_bytes = (cls.raiz / "inventario-C1.json").read_bytes()
        cls.inventario_c2_bytes = (cls.raiz / "inventario-C2.json").read_bytes()
        cls.inventario = json.loads(cls.inventario_c1_bytes)

    def test_evidencia_e_descartavel_e_excluida_por_finalidade(self):
        self.assertEqual("descartavel", self.resumo["status"])
        self.assertEqual("fumaca", self.resumo["finalidade"])
        self.assertEqual("finalidade=fumaca", self.resumo["exclusao_coleta_principal"])

    def test_revisoes_correspondem_ao_manifesto_v1(self):
        alvo = self.resumo["alvo"]
        self.assertEqual("d98e9fc91273702c9547663b6906d1fc494d4fcc", alvo["realvuln_commit"])
        self.assertEqual("7d40f4b7939c901610ed9b85724552d60e7d63fa", alvo["commit"])

    def test_inventarios_c1_c2_sao_identicos(self):
        self.assertEqual(self.inventario_c1_bytes, self.inventario_c2_bytes)
        self.assertEqual(self.resumo["entrada"]["sha256"], self.inventario["entrada_sha256"])
        self.assertTrue(self.resumo["entrada"]["inventarios_c1_c2_iguais"])
        self.assertTrue(self.resumo["entrada"]["regeneracao_verificada"])

    def test_hash_do_inventario_e_recalculavel(self):
        digest = hashlib.sha256(b"tree-sha256-v1\0")
        for item in self.inventario["itens"]:
            digest.update(item["caminho"].encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(item["tamanho_bytes"]).encode("ascii"))
            digest.update(b"\0")
            digest.update(item["sha256"].encode("ascii"))
            digest.update(b"\n")
        self.assertEqual(self.inventario["entrada_sha256"], digest.hexdigest())

    def test_inventario_nao_expoe_metadados_do_benchmark(self):
        caminhos = [item["caminho"].casefold() for item in self.inventario["itens"]]
        self.assertFalse(any("ground-truth" in caminho for caminho in caminhos))
        self.assertFalse(any("oracle" in caminho for caminho in caminhos))
        self.assertFalse(any(".git" in caminho for caminho in caminhos))
        self.assertEqual(self.inventario["arquivos"], len(caminhos))

    def test_manifestos_e_resumo_conferem(self):
        from runner.modelos import ManifestoExecucao

        por_condicao = {item["condicao"]: item for item in self.resumo["execucoes"]}
        self.assertEqual({"C1", "C2"}, set(por_condicao))
        for condicao in ("C1", "C2"):
            caminho = self.raiz / f"manifesto-{condicao}.json"
            manifesto = ManifestoExecucao.from_json(caminho.read_text("utf-8"))
            caso = por_condicao[condicao]
            self.assertEqual("concluida", manifesto.estado)
            self.assertEqual("fumaca", manifesto.finalidade)
            self.assertEqual(self.inventario["entrada_sha256"], manifesto.entrada_sha256)
            self.assertEqual(manifesto.execucao_id, caso["execucao_id"])
            self.assertEqual(
                hashlib.sha256(caminho.read_bytes()).hexdigest(),
                caso["manifesto_sha256"],
            )

    def test_versoes_e_imagem_estao_registradas(self):
        imagem = self.resumo["imagem"]
        self.assertRegex(imagem["id"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual("linux", imagem["os"])
        self.assertEqual("amd64", imagem["arquitetura"])
        casos = {item["condicao"]: item for item in self.resumo["execucoes"]}
        self.assertEqual("1.9.4", casos["C1"]["versoes"]["bandit"])
        self.assertEqual("1.172.0", casos["C2"]["versoes"]["semgrep"])
        self.assertEqual("3.12.13", casos["C2"]["versoes"]["python"])


if __name__ == "__main__":
    unittest.main()
