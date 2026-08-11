import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runner.coleta import (
    ErroColeta,
    copiar_manifesto_evidencia,
    plano_seco,
    preparar_tentativa,
    remover_area_tentativa,
    resumir_fila,
    validar_manifesto_terminal,
)
from runner.corpus import carregar_json
from runner.fila import criar_fila_runtime
from runner.preparacao import criar_inventario


RAIZ = Path(__file__).resolve().parents[1]
IMAGEM = "tcc-sast:teste"
DIGEST = "sha256:" + "d" * 64
COMMIT = "c" * 40
ENTRADA_SHA = "e" * 64
T0 = "2026-08-11T12:00:00Z"
T1 = "2026-08-11T12:00:01Z"


class ColetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = carregar_json(RAIZ / "config/corpus-realvuln-v1.lock.json")
        cls.fila = carregar_json(RAIZ / "config/fila-c1-c2.lock.json")
        cls.inventarios = {
            f"ALVO-{numero:04d}": carregar_json(
                RAIZ / f"evidencias/corpus-realvuln-v1/ALVO-{numero:04d}-inventario.json"
            )
            for numero in range(1, 27)
        }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)

    def manifesto(self, *, estado="concluida", falha_tipo=None, finalidade="coleta"):
        saida = self.raiz / "resultados/C1-ALVO-0001-R01/tentativa-001"
        saida.mkdir(parents=True)
        artefato = saida / "bruto.json"
        artefato.write_bytes(b"{}\n")
        digest = hashlib.sha256(artefato.read_bytes()).hexdigest()
        documento = {
            "schema_version": "1.0", "execucao_id": "C1-ALVO-0001-R01",
            "condicao": "C1", "ferramenta": "bandit", "bloco": None,
            "alvo": "ALVO-0001", "repeticao": 1, "entrada_commit": COMMIT,
            "entrada_sha256": ENTRADA_SHA, "comando": ["bandit", "/entrada"],
            "imagem": IMAGEM, "imagem_digest": DIGEST, "finalidade": finalidade,
            "inicio_utc": T0, "termino_utc": T1,
            "duracao_monotonica_segundos": 1.0,
            "codigo_saida": 0 if estado == "concluida" else None,
            "estado": estado, "falha_tipo": falha_tipo,
            "falha_mensagem": "falhou" if falha_tipo else None,
            "tentativa": 1, "artefatos_sha256": {"bruto.json": digest},
        }
        caminho = saida / "manifesto.json"
        caminho.write_text(json.dumps(documento), encoding="utf-8")
        return caminho

    def validar(self, caminho):
        return validar_manifesto_terminal(
            caminho, execucao_id="C1-ALVO-0001-R01", alvo="ALVO-0001",
            condicao="C1", tentativa=1, entrada_commit=COMMIT,
            entrada_sha256=ENTRADA_SHA, imagem=IMAGEM, imagem_digest=DIGEST,
        )

    def test_plano_seco_cobre_produto_exato_na_ordem(self):
        plano = plano_seco(self.fila, self.corpus, self.inventarios)
        self.assertEqual(52, plano["quantidade"])
        self.assertEqual(self.fila["ordem"], [i["execucao_id"] for i in plano["tarefas"]])
        self.assertEqual({"C1", "C2"}, {i["condicao"] for i in plano["tarefas"]})
        self.assertEqual(26, len({i["alvo"] for i in plano["tarefas"]}))

    def test_plano_seco_liga_commit_e_hash_do_corpus(self):
        plano = plano_seco(self.fila, self.corpus, self.inventarios)
        por_alvo = {a["alvo"]: a for a in self.corpus["alvos"]}
        for tarefa in plano["tarefas"]:
            self.assertEqual(por_alvo[tarefa["alvo"]]["commit"], tarefa["entrada_commit"])
            self.assertEqual(
                self.inventarios[tarefa["alvo"]]["entrada_sha256"],
                tarefa["entrada_sha256"],
            )

    def test_preparacao_cria_copia_nova_identica(self):
        origem = self.raiz / "origem"
        origem.mkdir()
        (origem / "app.py").write_text("print('dado')\n", encoding="utf-8")
        esperado = criar_inventario(origem)
        destino = self.raiz / "C1-ALVO-0001-R01-T001"
        observado = preparar_tentativa(origem, destino, esperado)
        self.assertEqual(esperado, observado)
        self.assertEqual("print('dado')\n", (destino / "app.py").read_text(encoding="utf-8"))

    def test_preparacao_recusa_destino_existente(self):
        origem = self.raiz / "origem"
        destino = self.raiz / "destino"
        origem.mkdir(); destino.mkdir()
        (origem / "a.py").write_text("x=1")
        with self.assertRaisesRegex(ErroColeta, "destino deve ser novo"):
            preparar_tentativa(origem, destino, criar_inventario(origem))

    def test_preparacao_divergente_remove_somente_area_nova(self):
        origem = self.raiz / "origem"
        origem.mkdir()
        (origem / "a.py").write_text("x=1")
        esperado = criar_inventario(origem)
        esperado = copy.deepcopy(esperado)
        esperado["entrada_sha256"] = "0" * 64
        destino = self.raiz / "C1-ALVO-0001-R01-T001"
        with self.assertRaisesRegex(ErroColeta, "diverge"):
            preparar_tentativa(origem, destino, esperado)
        self.assertFalse(destino.exists())
        self.assertTrue(origem.exists())

    def test_manifesto_concluido_e_artefatos_validam(self):
        recibo = self.validar(self.manifesto())
        self.assertEqual("concluida", recibo["estado"])
        self.assertEqual(1, recibo["artefatos"])

    def test_manifesto_de_falha_permanece_terminal(self):
        recibo = self.validar(self.manifesto(estado="falha", falha_tipo="timeout"))
        self.assertEqual("falha", recibo["estado"])
        self.assertEqual("timeout", recibo["falha_tipo"])

    def test_manifesto_de_fumaca_nao_entra_na_coleta(self):
        with self.assertRaisesRegex(ErroColeta, "finalidade"):
            self.validar(self.manifesto(finalidade="fumaca"))

    def test_manifesto_com_identidade_divergente_e_recusado(self):
        with self.assertRaisesRegex(ErroColeta, "entrada_commit"):
            validar_manifesto_terminal(
                self.manifesto(), execucao_id="C1-ALVO-0001-R01", alvo="ALVO-0001",
                condicao="C1", tentativa=1, entrada_commit="f" * 40,
                entrada_sha256=ENTRADA_SHA, imagem=IMAGEM, imagem_digest=DIGEST,
            )

    def test_manifesto_recusa_artefato_adulterado(self):
        caminho = self.manifesto()
        (caminho.parent / "bruto.json").write_bytes(b"adulterado")
        with self.assertRaisesRegex(ErroColeta, "hash do artefato"):
            self.validar(caminho)

    def test_manifesto_recusa_part_residual(self):
        caminho = self.manifesto()
        (caminho.parent / "resto.part").write_bytes(b"x")
        with self.assertRaisesRegex(ErroColeta, "part residual"):
            self.validar(caminho)

    def test_copia_de_evidencia_e_exclusiva(self):
        origem = self.manifesto()
        destino = self.raiz / "evidencias/manifesto.json"
        digest = copiar_manifesto_evidencia(origem, destino)
        self.assertEqual(hashlib.sha256(origem.read_bytes()).hexdigest(), digest)
        with self.assertRaisesRegex(ErroColeta, "já existe"):
            copiar_manifesto_evidencia(origem, destino)

    def test_cleanup_exige_nome_de_area_propria(self):
        area = self.raiz / "nao-remover"
        area.mkdir()
        with self.assertRaisesRegex(ErroColeta, "deve terminar"):
            remover_area_tentativa(area, "C1-ALVO-0001-R01", 1)
        self.assertTrue(area.exists())

    def test_cleanup_remove_area_propria(self):
        area = self.raiz / "C1-ALVO-0001-R01-T001"
        area.mkdir()
        remover_area_tentativa(area, "C1-ALVO-0001-R01", 1)
        self.assertFalse(area.exists())

    def test_resumo_preserva_falhas_no_denominador(self):
        runtime = criar_fila_runtime(self.fila, self.corpus, "a" * 64, T0)
        runtime["itens"][0].update({"estado": "falha", "tentativa": 1,
            "inicio_utc": T0, "termino_utc": T1,
            "manifesto_relativo": "resultados/C1-ALVO-0025-R01/tentativa-001/manifesto.json",
            "falha_tipo": "timeout"})
        resumo = resumir_fila(runtime)
        self.assertEqual(52, resumo["quantidade"])
        self.assertEqual(1, resumo["terminais"])
        self.assertEqual(1, resumo["falhas"]["timeout"])
        self.assertEqual({"C1": 26, "C2": 26}, resumo["condicoes"])

    def test_orquestrador_revalida_freeze_antes_de_cada_claim(self):
        texto = (RAIZ / "scripts/executar-coleta-c1-c2.ps1").read_text(encoding="utf-8")
        trecho = texto[texto.index("while ($true)") : texto.index("$claim = Invoke-Fila")]
        self.assertIn("Assert-Freeze $Config", trecho)

    def test_orquestrador_usa_wrapper_publico_com_finalidade_coleta(self):
        texto = (RAIZ / "scripts/executar-coleta-c1-c2.ps1").read_text(encoding="utf-8")
        self.assertIn("& $Wrapper -Condicao", texto)
        self.assertIn("-Finalidade coleta", texto)
        self.assertNotIn("runner.executor_sast", texto)

    def test_orquestrador_limpa_area_no_finally_sem_apagar_resultados(self):
        texto = (RAIZ / "scripts/executar-coleta-c1-c2.ps1").read_text(encoding="utf-8")
        self.assertIn("finally {", texto)
        self.assertIn('"limpar-area"', texto)
        self.assertNotIn("Remove-Item", texto)

    def test_gate_full_executa_teste_do_orquestrador(self):
        texto = (RAIZ / "scripts/gate.ps1").read_text(encoding="utf-8")
        self.assertIn('"test-coleta-c1-c2.ps1"', texto)


if __name__ == "__main__":
    unittest.main()
