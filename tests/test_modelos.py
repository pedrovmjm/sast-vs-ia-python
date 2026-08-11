import json
import math
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from runner.modelos import Achado, ErroModelo, ManifestoExecucao


RAIZ = Path(__file__).resolve().parents[1]
SHA_BRUTO = "a" * 64
SHA_ENTRADA = "b" * 64
SHA_ARTEFATO = "c" * 64
IMAGEM_DIGEST = "sha256:" + "d" * 64


def achado_valido(**alteracoes):
    documento = {
        "schema_version": "1.0",
        "condicao": "C1",
        "ferramenta": "bandit",
        "alvo": "ALVO-0001",
        "repeticao": 1,
        "execucao_id": "C1-ALVO-0001-R01",
        "arquivo": "src/aplicacao.py",
        "linha_inicial": 10,
        "linha_final": 12,
        "regra": "B608",
        "cwe_original": "89",
        "cwe": "CWE-89",
        "severidade_original": "MEDIUM",
        "severidade": "media",
        "confianca_original": "HIGH",
        "confianca": "alta",
        "descricao": "Consulta formada por concatenação.",
        "evidencia": None,
        "recomendacao": None,
        "texto_original": None,
        "saida_bruta_sha256": SHA_BRUTO,
    }
    documento.update(alteracoes)
    return documento


def manifesto_valido(**alteracoes):
    documento = {
        "schema_version": "1.0",
        "execucao_id": "C1-ALVO-0001-R01",
        "condicao": "C1",
        "ferramenta": "bandit",
        "bloco": None,
        "alvo": "ALVO-0001",
        "repeticao": 1,
        "entrada_commit": None,
        "entrada_sha256": SHA_ENTRADA,
        "comando": ["bandit", "-r", "/alvo", "-f", "json"],
        "imagem": "tcc-sast:fixada",
        "imagem_digest": IMAGEM_DIGEST,
        "finalidade": "fumaca",
        "inicio_utc": "2026-08-11T01:00:00.000000Z",
        "termino_utc": "2026-08-11T01:00:01.250000Z",
        "duracao_monotonica_segundos": 1.25,
        "codigo_saida": 0,
        "estado": "concluida",
        "falha_tipo": None,
        "falha_mensagem": None,
        "tentativa": 1,
        "artefatos_sha256": {"brutos/bandit.json": SHA_ARTEFATO},
    }
    documento.update(alteracoes)
    return documento


class AchadoTest(unittest.TestCase):
    def test_round_trip_preserva_todos_os_nulos(self):
        documento = achado_valido(
            arquivo=None,
            linha_inicial=None,
            linha_final=None,
            regra=None,
            cwe_original=None,
            cwe=None,
            severidade_original=None,
            severidade=None,
            confianca_original=None,
            confianca=None,
            descricao=None,
            evidencia=None,
            recomendacao=None,
            texto_original=None,
        )

        achado = Achado.from_dict(documento)

        self.assertEqual(documento, achado.to_dict())
        self.assertEqual(documento, json.loads(achado.to_json()))

    def test_json_e_deterministico_e_sem_ascii_forcado(self):
        achado = Achado.from_dict(achado_valido())

        primeiro = achado.to_json()
        segundo = Achado.from_json(primeiro).to_json()

        self.assertEqual(primeiro, segundo)
        self.assertIn("concatenação", primeiro)
        self.assertNotIn("\": ", primeiro)
        self.assertNotIn("\", ", primeiro)

    def test_rejeita_caminhos_absolutos_travessia_e_separador_windows(self):
        invalidos = (
            "/etc/passwd",
            "C:/segredo.txt",
            "C:\\segredo.txt",
            "src/../segredo.txt",
            "src\\aplicacao.py",
        )

        for caminho in invalidos:
            with self.subTest(caminho=caminho):
                with self.assertRaisesRegex(ErroModelo, "arquivo"):
                    Achado.from_dict(achado_valido(arquivo=caminho))

    def test_rejeita_linhas_nao_positivas_booleanas_ou_invertidas(self):
        invalidos = (
            {"linha_inicial": 0},
            {"linha_inicial": -1},
            {"linha_inicial": True},
            {"linha_inicial": 12, "linha_final": 10},
            {"linha_inicial": None, "linha_final": 10},
            {"arquivo": None, "linha_inicial": 10, "linha_final": 10},
        )

        for alteracoes in invalidos:
            with self.subTest(alteracoes=alteracoes):
                with self.assertRaisesRegex(ErroModelo, "linha"):
                    Achado.from_dict(achado_valido(**alteracoes))

    def test_rejeita_hash_incompleto_ou_em_maiusculas(self):
        for valor in ("a" * 12, "A" * 64, "sha256:" + "a" * 64):
            with self.subTest(valor=valor):
                with self.assertRaisesRegex(ErroModelo, "SHA-256"):
                    Achado.from_dict(achado_valido(saida_bruta_sha256=valor))

    def test_rejeita_condicao_repeticao_e_cwe_invalidos(self):
        casos = (
            ({"condicao": "C7"}, "condicao"),
            ({"ferramenta": "semgrep"}, "ferramenta"),
            ({"repeticao": 0}, "repeticao"),
            ({"repeticao": 2}, "repeticao"),
            ({"repeticao": True}, "repeticao"),
            ({"cwe": "89"}, "cwe"),
            ({"severidade": "MEDIUM"}, "severidade"),
            ({"confianca": "HIGH"}, "confianca"),
        )

        for alteracoes, mensagem in casos:
            with self.subTest(alteracoes=alteracoes):
                with self.assertRaisesRegex(ErroModelo, mensagem):
                    Achado.from_dict(achado_valido(**alteracoes))

    def test_cwe_original_preserva_string_lista_ou_nulo(self):
        for original in ("89", ["CWE-89", "CWE-564"], None):
            with self.subTest(original=original):
                documento = achado_valido(cwe_original=original)
                self.assertEqual(
                    original,
                    Achado.from_dict(documento).to_dict()["cwe_original"],
                )

    def test_rejeita_campos_ausentes_desconhecidos_e_versao(self):
        sem_alvo = achado_valido()
        sem_alvo.pop("alvo")
        com_extra = achado_valido(campo_inventado=True)
        versao = achado_valido(schema_version="2.0")

        for documento in (sem_alvo, com_extra, versao):
            with self.subTest(documento=documento):
                with self.assertRaises(ErroModelo):
                    Achado.from_dict(documento)

    def test_json_estrito_rejeita_chave_duplicada_e_nan(self):
        base = Achado.from_dict(achado_valido()).to_json()
        duplicado = base.replace(
            '"schema_version":"1.0"',
            '"schema_version":"1.0","schema_version":"1.0"',
        )
        nao_finito = base.replace('"linha_inicial":10', '"linha_inicial":NaN')

        for documento in (duplicado, nao_finito):
            with self.subTest(documento=documento):
                with self.assertRaises(ErroModelo):
                    Achado.from_json(documento)


class ManifestoExecucaoTest(unittest.TestCase):
    def test_round_trip_preserva_vetor_nulos_e_hashes(self):
        documento = manifesto_valido()

        manifesto = ManifestoExecucao.from_dict(documento)

        self.assertEqual(documento, manifesto.to_dict())
        self.assertEqual(documento, json.loads(manifesto.to_json()))

    def test_json_ordena_hashes_de_artefatos(self):
        hashes = {
            "normalizados/z.json": "e" * 64,
            "brutos/a.json": "f" * 64,
        }
        primeiro = ManifestoExecucao.from_dict(
            manifesto_valido(artefatos_sha256=hashes)
        ).to_json()
        segundo = ManifestoExecucao.from_dict(
            manifesto_valido(artefatos_sha256=dict(reversed(tuple(hashes.items()))))
        ).to_json()

        self.assertEqual(primeiro, segundo)

    def test_comando_deve_ser_vetor_nao_vazio_sem_nulos(self):
        invalidos = (
            "bandit -r /alvo",
            {"bandit": "-r"},
            [],
            ["bandit", ""],
            ["bandit", "argumento\x00invalido"],
        )

        for comando in invalidos:
            with self.subTest(comando=comando):
                with self.assertRaisesRegex(ErroModelo, "comando"):
                    ManifestoExecucao.from_dict(manifesto_valido(comando=comando))

    def test_timestamps_devem_ser_utc_canonico_e_ordenados(self):
        casos = (
            {"inicio_utc": "2026-08-10T22:00:00-03:00"},
            {"termino_utc": "2026-08-10T22:00:00"},
            {
                "inicio_utc": "2026-08-11T01:00:02.000000Z",
                "termino_utc": "2026-08-11T01:00:01.000000Z",
            },
        )

        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                with self.assertRaisesRegex(ErroModelo, "UTC|termino"):
                    ManifestoExecucao.from_dict(manifesto_valido(**alteracoes))

    def test_estado_pendente_nao_pode_conter_resultado(self):
        alteracoes = {
            "inicio_utc": None,
            "termino_utc": None,
            "duracao_monotonica_segundos": None,
            "codigo_saida": None,
            "estado": "pendente",
            "artefatos_sha256": {},
        }

        ManifestoExecucao.from_dict(manifesto_valido(**alteracoes))

        with self.assertRaisesRegex(ErroModelo, "pendente"):
            ManifestoExecucao.from_dict(
                manifesto_valido(estado="pendente", codigo_saida=None)
            )

    def test_estado_em_execucao_exige_inicio_sem_termino(self):
        valido = manifesto_valido(
            termino_utc=None,
            duracao_monotonica_segundos=None,
            codigo_saida=None,
            estado="em_execucao",
            artefatos_sha256={},
        )
        ManifestoExecucao.from_dict(valido)

        with self.assertRaisesRegex(ErroModelo, "em_execucao"):
            ManifestoExecucao.from_dict(
                manifesto_valido(
                    inicio_utc=None,
                    termino_utc=None,
                    duracao_monotonica_segundos=None,
                    codigo_saida=None,
                    estado="em_execucao",
                    artefatos_sha256={},
                )
            )

    def test_estado_terminal_exige_tempos_e_duracao(self):
        for estado in ("concluida", "falha"):
            with self.subTest(estado=estado):
                alteracoes = {
                    "estado": estado,
                    "termino_utc": None,
                    "duracao_monotonica_segundos": None,
                    "codigo_saida": None,
                    "falha_tipo": "timeout" if estado == "falha" else None,
                }
                with self.assertRaisesRegex(ErroModelo, "terminal"):
                    ManifestoExecucao.from_dict(manifesto_valido(**alteracoes))

    def test_conclusao_exige_saida_preservada(self):
        with self.assertRaisesRegex(ErroModelo, "artefato"):
            ManifestoExecucao.from_dict(
                manifesto_valido(artefatos_sha256={})
            )

    def test_timeout_e_tipo_de_falha_e_nao_estado(self):
        falha = manifesto_valido(
            estado="falha",
            codigo_saida=None,
            falha_tipo="timeout",
            falha_mensagem="limite monotônico excedido",
        )
        ManifestoExecucao.from_dict(falha)

        with self.assertRaisesRegex(ErroModelo, "estado"):
            ManifestoExecucao.from_dict(
                manifesto_valido(estado="timeout", codigo_saida=None)
            )

    def test_falha_exige_tipo_que_e_nulo_fora_de_falha(self):
        with self.assertRaisesRegex(ErroModelo, "falha_tipo"):
            ManifestoExecucao.from_dict(
                manifesto_valido(estado="falha", codigo_saida=None)
            )
        with self.assertRaisesRegex(ErroModelo, "falha_tipo"):
            ManifestoExecucao.from_dict(
                manifesto_valido(falha_tipo="timeout")
            )

    def test_rejeita_duracao_nao_finita_negativa_e_tentativa_invalida(self):
        casos = (
            ({"duracao_monotonica_segundos": -0.1}, "duracao"),
            ({"duracao_monotonica_segundos": math.inf}, "duracao"),
            ({"tentativa": 0}, "tentativa"),
            ({"codigo_saida": True}, "codigo_saida"),
        )

        for alteracoes, mensagem in casos:
            with self.subTest(alteracoes=alteracoes):
                with self.assertRaisesRegex(ErroModelo, mensagem):
                    ManifestoExecucao.from_dict(manifesto_valido(**alteracoes))

    def test_rejeita_commit_digest_e_hashes_de_artefatos_invalidos(self):
        casos = (
            {"entrada_commit": "a" * 12},
            {"imagem_digest": "d" * 64},
            {"artefatos_sha256": {"/absoluto.json": SHA_ARTEFATO}},
            {"artefatos_sha256": {"bruto.json": "c" * 12}},
        )

        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                with self.assertRaises(ErroModelo):
                    ManifestoExecucao.from_dict(manifesto_valido(**alteracoes))


class SchemaTest(unittest.TestCase):
    def setUp(self):
        self.schemas = {}
        for nome in ("achado-v1.schema.json", "execucao-v1.schema.json"):
            caminho = RAIZ / "runner" / "schemas" / nome
            self.schemas[nome] = json.loads(caminho.read_text(encoding="utf-8"))

    def test_schemas_publicados_sao_json_estrito_e_versionado(self):
        for nome in ("achado-v1.schema.json", "execucao-v1.schema.json"):
            with self.subTest(nome=nome):
                documento = self.schemas[nome]

                self.assertEqual("https://json-schema.org/draft/2020-12/schema", documento["$schema"])
                self.assertEqual("1.0", documento["properties"]["schema_version"]["const"])
                self.assertFalse(documento["additionalProperties"])
                self.assertEqual(set(documento["properties"]), set(documento["required"]))
                self.assertTrue(documento["x-tcc-semantic-invariants"])
                Draft202012Validator.check_schema(documento)

    def test_schema_achado_rejeita_implicacoes_e_caminho_invalido(self):
        validador = Draft202012Validator(self.schemas["achado-v1.schema.json"])
        invalidos = (
            achado_valido(linha_inicial=None, linha_final=10),
            achado_valido(arquivo="src/"),
            achado_valido(arquivo=None, linha_inicial=10, linha_final=10),
        )

        validador.validate(achado_valido())
        for documento in invalidos:
            with self.subTest(documento=documento):
                with self.assertRaises(ValidationError):
                    validador.validate(documento)

    def test_schema_execucao_rejeita_data_impossivel_e_conclusao_sem_saida(self):
        validador = Draft202012Validator(
            self.schemas["execucao-v1.schema.json"],
            format_checker=FormatChecker(),
        )
        invalidos = (
            manifesto_valido(inicio_utc="2026-02-31T01:00:00Z"),
            manifesto_valido(artefatos_sha256={}),
            manifesto_valido(estado="timeout", codigo_saida=None),
        )

        validador.validate(manifesto_valido())
        for documento in invalidos:
            with self.subTest(documento=documento):
                with self.assertRaises(ValidationError):
                    validador.validate(documento)


if __name__ == "__main__":
    unittest.main()
