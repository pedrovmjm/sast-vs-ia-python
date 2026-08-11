import copy
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from runner.corpus import (
    ErroCorpus,
    auditar_ground_truth,
    carregar_json,
    caminho_excluido,
    criar_ordem_fila,
    extrair_tar_git,
    hash_json_canonico,
    validar_lock_corpus,
    validar_lock_espelhos,
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
        cls.espelhos = carregar_json(
            RAIZ / "config/espelhos-corpus-realvuln-v1.lock.json"
        )

    def test_contratos_publicados_sao_validos(self):
        self.assertIs(self.politica, validar_politica(self.politica))
        self.assertIs(self.corpus, validar_lock_corpus(self.corpus))
        self.assertIs(self.fila, validar_lock_fila(self.fila, self.corpus))
        self.assertIs(self.espelhos, validar_lock_espelhos(self.espelhos, self.corpus))

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
            "8d1a6453c2efe58d1b5c56402a50f8c33e61625c4edb93da58318e6e4b65cdc2",
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
            "54e98c0d00980ed9baba9943a8fa5f82734739dd037632909ca19c6eef980168",
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
        self.assertTrue(caminho_excluido("UI/STATIC/CSS/FONTS", self.politica))
        self.assertTrue(caminho_excluido("bad/payloads/payload.js", self.politica))
        self.assertTrue(caminho_excluido("good/payloads/payload.js", self.politica))

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

    def test_espelhos_cobrem_exatamente_as_tres_fontes_indisponiveis(self):
        self.assertEqual(
            ["ALVO-0015", "ALVO-0021", "ALVO-0023"],
            [item["alvo"] for item in self.espelhos["espelhos"]],
        )

    def test_espelho_recusa_commit_divergente(self):
        alterado = copy.deepcopy(self.espelhos)
        alterado["espelhos"][0]["commit"] = "0" * 40
        with self.assertRaisesRegex(ErroCorpus, "corpus oficial"):
            validar_lock_espelhos(alterado, self.corpus)

    def test_espelho_recusa_url_oficial_divergente(self):
        alterado = copy.deepcopy(self.espelhos)
        alterado["espelhos"][0]["url_oficial"] = "https://github.com/exemplo/outro"
        with self.assertRaisesRegex(ErroCorpus, "corpus oficial"):
            validar_lock_espelhos(alterado, self.corpus)

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


class GroundTruthAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.oracle = self.raiz / "oracle"
        self.gt = self.oracle / "ground-truth"
        self.gt.mkdir(parents=True)
        self.corpus = carregar_json(RAIZ / "config/corpus-realvuln-v1.lock.json")
        for indice, alvo in enumerate(self.corpus["alvos"]):
            diretorio = self.gt / alvo["realvuln_id"]
            diretorio.mkdir()
            quantidade_vulneraveis = 47 if indice == 0 else 26
            vulneraveis = [
                {"is_vulnerable": True} for _ in range(quantidade_vulneraveis)
            ]
            quantidade_fp = 5 if indice < 16 else 4
            armadilhas = [{"is_vulnerable": False} for _ in range(quantidade_fp)]
            documento = {
                "repo_id": alvo["realvuln_id"],
                "repo_url": alvo["url"],
                "commit_sha": alvo["commit"],
                "findings": vulneraveis + armadilhas,
            }
            (diretorio / "ground-truth.json").write_text(
                json.dumps(documento), encoding="utf-8"
            )

    def test_auditoria_confere_censo_e_nao_expoe_achados(self):
        resumo = auditar_ground_truth(self.oracle, self.corpus)
        self.assertEqual(26, resumo["repositorios"])
        self.assertEqual(817, resumo["entradas"])
        self.assertEqual(697, resumo["vulnerabilidades"])
        self.assertEqual(120, resumo["armadilhas_fp"])
        self.assertEqual(0, resumo["divergencias_url_ground_truth"])
        self.assertNotIn("findings", json.dumps(resumo))
        self.assertEqual("ALVO-0001", resumo["itens"][0]["alvo"])

    def test_auditoria_recusa_commit_divergente(self):
        arquivo = next(self.gt.glob("*/ground-truth.json"))
        documento = json.loads(arquivo.read_text(encoding="utf-8"))
        documento["commit_sha"] = "0" * 40
        arquivo.write_text(json.dumps(documento), encoding="utf-8")
        with self.assertRaisesRegex(ErroCorpus, "commit_sha"):
            auditar_ground_truth(self.oracle, self.corpus)

    def test_auditoria_registra_url_upstream_divergente(self):
        arquivo = next(self.gt.glob("*/ground-truth.json"))
        documento = json.loads(arquivo.read_text(encoding="utf-8"))
        documento["repo_url"] = "https://github.com/exemplo/placeholder"
        arquivo.write_text(json.dumps(documento), encoding="utf-8")
        resumo = auditar_ground_truth(self.oracle, self.corpus)
        self.assertEqual(1, resumo["divergencias_url_ground_truth"])
        item = next(item for item in resumo["itens"] if not item["repo_url_confere"])
        self.assertEqual("https://github.com/exemplo/placeholder", item["ground_truth_repo_url"])

    def test_auditoria_recusa_repositorio_ausente(self):
        diretorio = next(self.gt.iterdir())
        (diretorio / "ground-truth.json").unlink()
        diretorio.rmdir()
        with self.assertRaisesRegex(ErroCorpus, "incompleto"):
            auditar_ground_truth(self.oracle, self.corpus)

    def test_auditoria_recusa_repositorio_extra(self):
        (self.gt / "realvuln-extra").mkdir()
        with self.assertRaisesRegex(ErroCorpus, "inesperado"):
            auditar_ground_truth(self.oracle, self.corpus)

    def test_auditoria_recusa_contagem_divergente(self):
        arquivo = next(self.gt.glob("*/ground-truth.json"))
        documento = json.loads(arquivo.read_text(encoding="utf-8"))
        documento["findings"].pop()
        arquivo.write_text(json.dumps(documento), encoding="utf-8")
        with self.assertRaisesRegex(ErroCorpus, "contagens"):
            auditar_ground_truth(self.oracle, self.corpus)

    def test_auditoria_recusa_is_vulnerable_nao_booleano(self):
        arquivo = next(self.gt.glob("*/ground-truth.json"))
        documento = json.loads(arquivo.read_text(encoding="utf-8"))
        documento["findings"][0]["is_vulnerable"] = 1
        arquivo.write_text(json.dumps(documento), encoding="utf-8")
        with self.assertRaisesRegex(ErroCorpus, "booleano"):
            auditar_ground_truth(self.oracle, self.corpus)

    def test_auditoria_recusa_arquivo_auxiliar(self):
        diretorio = next(self.gt.iterdir())
        (diretorio / "extra.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(ErroCorpus, "estrutura"):
            auditar_ground_truth(self.oracle, self.corpus)


class GitArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name)
        self.archive = self.raiz / "repo.tar"

    def criar_tar(self, membros):
        with tarfile.open(self.archive, "w") as pacote:
            for nome, tipo, conteudo in membros:
                info = tarfile.TarInfo(nome)
                info.mode = 0o644
                if tipo == "arquivo":
                    dados = conteudo.encode("utf-8")
                    info.size = len(dados)
                    pacote.addfile(info, io.BytesIO(dados))
                elif tipo == "diretorio":
                    info.type = tarfile.DIRTYPE
                    pacote.addfile(info)
                else:
                    info.type = tarfile.SYMTYPE
                    info.linkname = conteudo
                    pacote.addfile(info)

    def test_extrai_somente_arquivos_regulares(self):
        self.criar_tar(
            [("src/", "diretorio", ""), ("src/app.py", "arquivo", "print(1)\n")]
        )
        destino = self.raiz / "exportacao"
        self.assertEqual(1, extrair_tar_git(self.archive, destino))
        self.assertEqual("print(1)\n", (destino / "src/app.py").read_text(encoding="utf-8"))

    def test_recusa_link_simbolico(self):
        self.criar_tar([("atalho", "link", "arquivo")])
        with self.assertRaisesRegex(ErroCorpus, "não regular"):
            extrair_tar_git(self.archive, self.raiz / "exportacao")

    def test_recusa_travessia(self):
        self.criar_tar([("../escape.py", "arquivo", "x")])
        with self.assertRaisesRegex(ErroCorpus, "inseguro"):
            extrair_tar_git(self.archive, self.raiz / "exportacao")
        self.assertFalse((self.raiz.parent / "escape.py").exists())

    def test_recusa_colisao_casefold(self):
        self.criar_tar(
            [("App.py", "arquivo", "a"), ("app.py", "arquivo", "b")]
        )
        with self.assertRaisesRegex(ErroCorpus, "ambíguo"):
            extrair_tar_git(self.archive, self.raiz / "exportacao")

    def test_recusa_destino_existente(self):
        self.criar_tar([("app.py", "arquivo", "x")])
        destino = self.raiz / "exportacao"
        destino.mkdir()
        with self.assertRaisesRegex(ErroCorpus, "novo"):
            extrair_tar_git(self.archive, destino)


class CorpusEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raiz = RAIZ / "evidencias/corpus-realvuln-v1"
        cls.resumo = carregar_json(cls.raiz / "resumo.json")
        cls.gt = carregar_json(cls.raiz / "ground-truth-resumo.json")
        cls.oficial = carregar_json(cls.raiz / "validacao-oficial.json")

    def test_resumo_contem_26_alvos_e_tres_espelhos(self):
        self.assertEqual(26, self.resumo["quantidade_alvos"])
        self.assertEqual(26, len(self.resumo["alvos"]))
        self.assertEqual(
            {"ALVO-0015", "ALVO-0021", "ALVO-0023"},
            {item["alvo"] for item in self.resumo["alvos"] if item["espelho_usado"]},
        )

    def test_resumo_registra_tres_links_omitidos(self):
        exclusoes = [
            (item["alvo"], exclusao["caminho"], exclusao["destino_link"])
            for item in self.resumo["alvos"]
            for exclusao in item["exclusoes_git"]
        ]
        self.assertEqual(
            [
                ("ALVO-0020", "ui/static/css/fonts", "../fonts"),
                ("ALVO-0026", "bad/payloads/payload.js", "keylogger.js"),
                ("ALVO-0026", "good/payloads/payload.js", "keylogger.js"),
            ],
            exclusoes,
        )

    def test_validador_oficial_aprovou_817_entradas(self):
        self.assertEqual(0, self.oficial["codigo_saida"])
        texto = "\n".join(self.oficial["saida"])
        self.assertIn("Validated 26 ground truth files, 817 total findings", texto)
        self.assertTrue(texto.endswith("ALL PASSED"))

    def test_auditoria_ground_truth_confere_contagens(self):
        self.assertEqual(26, self.gt["repositorios"])
        self.assertEqual(817, self.gt["entradas"])
        self.assertEqual(697, self.gt["vulnerabilidades"])
        self.assertEqual(120, self.gt["armadilhas_fp"])
        self.assertEqual(3, self.gt["divergencias_url_ground_truth"])

    def test_hashes_dos_inventarios_e_relatorios_conferem(self):
        for item in self.resumo["alvos"]:
            alvo = item["alvo"]
            inventario_path = self.raiz / f"{alvo}-inventario.json"
            relatorio_path = self.raiz / f"{alvo}-sanitizacao.json"
            inventario = carregar_json(inventario_path)
            relatorio = carregar_json(relatorio_path)
            with self.subTest(alvo=alvo):
                self.assertEqual(item["entrada_sha256"], inventario["entrada_sha256"])
                self.assertEqual(item["arquivos"], inventario["arquivos"])
                self.assertEqual(
                    item["inventario_sha256"],
                    hashlib.sha256(inventario_path.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    item["sanitizacao_sha256"],
                    hashlib.sha256(relatorio_path.read_bytes()).hexdigest(),
                )
                self.assertEqual(inventario["arquivos"], relatorio["arquivos_incluidos"])

    def test_evidencia_nao_publica_oracle(self):
        nomes = {path.name.casefold() for path in self.raiz.iterdir()}
        self.assertNotIn("ground-truth", nomes)
        self.assertNotIn("validate_gt.py", nomes)
        for path in self.raiz.glob("*.json"):
            with self.subTest(arquivo=path.name):
                self.assertNotIn('"is_vulnerable"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
