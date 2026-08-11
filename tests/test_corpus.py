import copy
import json
import tempfile
import unittest
from pathlib import Path

from runner.corpus import (
    ErroCorpus,
    carregar_json,
    caminho_excluido,
    criar_ordem_fila,
    hash_json_canonico,
    validar_lock_corpus,
    validar_lock_fila,
    validar_politica,
)


RAIZ = Path(__file__).resolve().parents[1]


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.politica = carregar_json(RAIZ / "config/politica-sanitizacao-v1.json")
        cls.corpus = carregar_json(RAIZ / "config/corpus-realvuln-v1.lock.json")
        cls.fila = carregar_json(RAIZ / "config/fila-c1-c2.lock.json")

    def test_contratos_publicados_sao_validos(self):
        self.assertIs(self.politica, validar_politica(self.politica))
        self.assertIs(self.corpus, validar_lock_corpus(self.corpus))
        self.assertIs(self.fila, validar_lock_fila(self.fila, self.corpus))

    def test_corpus_tem_26_ids_opacos_sequenciais(self):
        self.assertEqual(
            [f"ALVO-{indice:04d}" for indice in range(1, 27)],
            [item["alvo"] for item in self.corpus["alvos"]],
        )

    def test_corpus_preserva_mapeamento_auditavel(self):
        primeiro = self.corpus["alvos"][0]
        ultimo = self.corpus["alvos"][-1]
        self.assertEqual("realvuln-damn-vulnerable-flask-application", primeiro["realvuln_id"])
        self.assertEqual("realvuln-vulpy", ultimo["realvuln_id"])
        self.assertEqual("5249cc8b05a1c37f6b2f757b1cf16a509c327122", ultimo["commit"])

    def test_release_realvuln_esta_congelado(self):
        release = self.corpus["realvuln"]
        self.assertEqual("v1.0", release["tag"])
        self.assertEqual("d98e9fc91273702c9547663b6906d1fc494d4fcc", release["commit"])
        self.assertEqual(
            "477169e7852e4a405fc01c7f19aa663cf55447875f166018abbfcf1cd05e4247",
            release["manifesto_sha256"],
        )

    def test_fila_tem_produto_cartesiano_c1_c2(self):
        esperado = {
            f"{condicao}-ALVO-{indice:04d}-R01"
            for condicao in ("C1", "C2")
            for indice in range(1, 27)
        }
        self.assertEqual(esperado, set(self.fila["ordem"]))

    def test_ordem_e_deterministica(self):
        semente = self.fila["semente"]
        self.assertEqual(criar_ordem_fila(self.corpus, semente), criar_ordem_fila(self.corpus, semente))
        self.assertEqual(self.fila["ordem"], criar_ordem_fila(self.corpus, semente))

    def test_semente_diferente_muda_ordem(self):
        self.assertNotEqual(self.fila["ordem"], criar_ordem_fila(self.corpus, "outra-semente"))

    def test_hash_canonico_independe_da_ordem_das_chaves(self):
        reordenado = json.loads(json.dumps(self.corpus, sort_keys=True))
        self.assertEqual(hash_json_canonico(self.corpus), hash_json_canonico(reordenado))

    def test_hash_canonico_publicado(self):
        self.assertEqual(
            "e5aec31c7a890da81d14e3bae7e29d2b10bc4aabdcca434a1ff6059d932e80a5",
            hash_json_canonico(self.corpus),
        )

    def test_politica_exclui_segmentos_case_insensitive(self):
        self.assertTrue(caminho_excluido("src/__pycache__/mod.py", self.politica))
        self.assertTrue(caminho_excluido("GROUND-TRUTH/resposta.json", self.politica))
        self.assertTrue(caminho_excluido("vendor/NODE_MODULES/x.js", self.politica))

    def test_politica_exclui_arquivos_e_sufixos(self):
        self.assertTrue(caminho_excluido("src/.GITMODULES", self.politica))
        self.assertTrue(caminho_excluido("src/cache.PYC", self.politica))
        self.assertTrue(caminho_excluido("Thumbs.db", self.politica))

    def test_politica_preserva_codigo_e_configuracao(self):
        self.assertFalse(caminho_excluido("src/app.py", self.politica))
        self.assertFalse(caminho_excluido("requirements.txt", self.politica))
        self.assertFalse(caminho_excluido("Dockerfile", self.politica))

    def test_caminho_inseguro_e_recusado(self):
        for caminho in ("", "/app.py", "../app.py", "a//b", "a\\b"):
            with self.subTest(caminho=caminho), self.assertRaises(ErroCorpus):
                caminho_excluido(caminho, self.politica)

    def test_politica_recusa_campos_desconhecidos(self):
        alterada = copy.deepcopy(self.politica)
        alterada["extra"] = True
        with self.assertRaisesRegex(ErroCorpus, "campos"):
            validar_politica(alterada)

    def test_politica_recusa_lista_fora_da_ordem_canonica(self):
        alterada = copy.deepcopy(self.politica)
        alterada["arquivos_excluidos"] = list(reversed(alterada["arquivos_excluidos"]))
        with self.assertRaisesRegex(ErroCorpus, "ordem"):
            validar_politica(alterada)

    def test_politica_recusa_duplicata(self):
        alterada = copy.deepcopy(self.politica)
        alterada["sufixos_excluidos"].append(".pyc")
        with self.assertRaisesRegex(ErroCorpus, "duplicata"):
            validar_politica(alterada)

    def test_politica_recusa_modos_git_diferentes(self):
        alterada = copy.deepcopy(self.politica)
        alterada["modos_git_permitidos"] = ["100644"]
        with self.assertRaisesRegex(ErroCorpus, "modos Git"):
            validar_politica(alterada)

    def test_corpus_recusa_id_duplicado_ou_fora_de_posicao(self):
        alterado = copy.deepcopy(self.corpus)
        alterado["alvos"][1]["alvo"] = "ALVO-0001"
        with self.assertRaisesRegex(ErroCorpus, "ID opaco"):
            validar_lock_corpus(alterado)

    def test_corpus_recusa_repo_fora_da_ordem(self):
        alterado = copy.deepcopy(self.corpus)
        alterado["alvos"][0]["realvuln_id"], alterado["alvos"][1]["realvuln_id"] = (
            alterado["alvos"][1]["realvuln_id"],
            alterado["alvos"][0]["realvuln_id"],
        )
        with self.assertRaisesRegex(ErroCorpus, "ordenados"):
            validar_lock_corpus(alterado)

    def test_corpus_recusa_commit_abreviado(self):
        alterado = copy.deepcopy(self.corpus)
        alterado["alvos"][0]["commit"] = "55f6320"
        with self.assertRaisesRegex(ErroCorpus, "commit Git completo"):
            validar_lock_corpus(alterado)

    def test_corpus_recusa_url_nao_https(self):
        alterado = copy.deepcopy(self.corpus)
        alterado["alvos"][0]["url"] = "http://github.com/exemplo/repo"
        with self.assertRaisesRegex(ErroCorpus, "HTTPS"):
            validar_lock_corpus(alterado)

    def test_corpus_recusa_url_com_credencial_query_ou_fragmento(self):
        casos = (
            "https://usuario@github.com/exemplo/repo",
            "https://github.com/exemplo/repo?ref=x",
            "https://github.com/exemplo/repo#x",
        )
        for url in casos:
            alterado = copy.deepcopy(self.corpus)
            alterado["alvos"][0]["url"] = url
            with self.subTest(url=url), self.assertRaisesRegex(ErroCorpus, "HTTPS simples"):
                validar_lock_corpus(alterado)

    def test_corpus_recusa_quantidade_diferente(self):
        alterado = copy.deepcopy(self.corpus)
        alterado["quantidade_alvos"] = 25
        with self.assertRaisesRegex(ErroCorpus, "26"):
            validar_lock_corpus(alterado)

    def test_fila_recusa_hash_de_outro_corpus(self):
        alterada = copy.deepcopy(self.fila)
        alterada["corpus_lock_sha256"] = "0" * 64
        with self.assertRaisesRegex(ErroCorpus, "hash can.nico divergente"):
            validar_lock_fila(alterada, self.corpus)

    def test_fila_recusa_duplicata(self):
        alterada = copy.deepcopy(self.fila)
        alterada["ordem"][-1] = alterada["ordem"][0]
        with self.assertRaisesRegex(ErroCorpus, "duplicada"):
            validar_lock_fila(alterada, self.corpus)

    def test_fila_recusa_ordem_adulterada(self):
        alterada = copy.deepcopy(self.fila)
        alterada["ordem"][0], alterada["ordem"][1] = alterada["ordem"][1], alterada["ordem"][0]
        with self.assertRaisesRegex(ErroCorpus, "ranking"):
            validar_lock_fila(alterada, self.corpus)

    def test_fila_recusa_semente_vazia(self):
        alterada = copy.deepcopy(self.fila)
        alterada["semente"] = ""
        with self.assertRaisesRegex(ErroCorpus, "semente"):
            validar_lock_fila(alterada, self.corpus)

    def test_carregador_recusa_chave_json_duplicada(self):
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "duplicado.json"
            caminho.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ErroCorpus, "duplicada"):
                carregar_json(caminho)

    def test_carregador_recusa_constante_nao_finita(self):
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "nan.json"
            caminho.write_text('{"valor": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ErroCorpus, "n.o finita"):
                carregar_json(caminho)


if __name__ == "__main__":
    unittest.main()
