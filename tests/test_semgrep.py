import hashlib
import json
import socket
import subprocess
import unittest
import urllib.request
import warnings
from pathlib import Path
from unittest.mock import patch

from runner.adaptadores.comum import ErroAdaptador, Proveniencia
from runner.adaptadores.semgrep import (
    MAPA_SEVERIDADE,
    ResultadoParcialSemgrepWarning,
    normalizar,
)
from runner.modelos import Achado


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "semgrep"


def proveniencia(documento: bytes) -> Proveniencia:
    return Proveniencia(
        alvo="ALVO-0001",
        repeticao=1,
        execucao_id="C2-ALVO-0001-R01",
        saida_bruta_sha256=hashlib.sha256(documento).hexdigest(),
    )


def saida_semgrep(*, severidade="WARNING", metadata=None, **resultado):
    item = {
        "check_id": "python.regra.fixture",
        "path": "aplicacao.py",
        "start": {"line": 3, "col": 1, "offset": 10},
        "end": {"line": 3, "col": 8, "offset": 17},
        "extra": {
            "message": "Mensagem controlada.",
            "metadata": {} if metadata is None else metadata,
            "severity": severidade,
        },
    }
    item.update(resultado)
    return json.dumps(
        {
            "version": "1.172.0",
            "results": [item],
            "errors": [],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class AdaptadorSemgrepTest(unittest.TestCase):
    def test_normaliza_bytes_com_proveniencia_e_valores_originais(self):
        bruto = (FIXTURES / "achado_completo.json").read_bytes()

        achados = normalizar(bruto, proveniencia(bruto))

        self.assertIs(type(achados), list)
        self.assertEqual(1, len(achados))
        achado = achados[0]
        self.assertIsInstance(achado, Achado)
        self.assertEqual("1.0", achado.schema_version)
        self.assertEqual("C2", achado.condicao)
        self.assertEqual("semgrep", achado.ferramenta)
        self.assertEqual("ALVO-0001", achado.alvo)
        self.assertEqual(1, achado.repeticao)
        self.assertEqual("C2-ALVO-0001-R01", achado.execucao_id)
        self.assertEqual("src/consulta.py", achado.arquivo)
        self.assertEqual((11, 13), (achado.linha_inicial, achado.linha_final))
        self.assertEqual(
            "python.django.security.injection.sql.sql-injection",
            achado.regra,
        )
        self.assertEqual(
            (
                "CWE-89: Improper Neutralization of Special Elements used in an SQL Command",
            ),
            achado.cwe_original,
        )
        self.assertEqual("CWE-89", achado.cwe)
        self.assertEqual("WARNING", achado.severidade_original)
        self.assertEqual("media", achado.severidade)
        self.assertEqual("HIGH", achado.confianca_original)
        self.assertIsNone(achado.confianca)
        self.assertEqual(
            "Consulta SQL formada com dado não confiável.", achado.descricao
        )
        self.assertIn("cursor.execute", achado.evidencia)
        self.assertIn("%s", achado.recomendacao)
        self.assertEqual(proveniencia(bruto).saida_bruta_sha256, achado.saida_bruta_sha256)

    def test_texto_original_e_deterministico_e_texto_utf8_equivale_a_bytes(self):
        bruto = (FIXTURES / "achado_completo.json").read_bytes()
        documento = json.loads(bruto)
        esperado = json.dumps(
            documento["results"][0],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        por_bytes = normalizar(bruto, proveniencia(bruto))[0]
        por_texto = normalizar(bruto.decode("utf-8"), proveniencia(bruto))[0]

        self.assertEqual(esperado, por_bytes.texto_original)
        self.assertEqual(por_bytes, por_texto)
        self.assertIn('"fingerprint":"fixture-semgrep-1"', esperado)

    def test_normaliza_apenas_prefixos_de_entrada_e_separadores_sintaticos(self):
        casos = {
            "src\\pacote\\modulo.py": "src/pacote/modulo.py",
            "/entrada/src/pacote/modulo.py": "src/pacote/modulo.py",
            "/entrada\\src\\pacote\\modulo.py": "src/pacote/modulo.py",
            "./src/pacote/modulo.py": "src/pacote/modulo.py",
        }

        for original, esperado in casos.items():
            bruto = saida_semgrep(path=original)
            with self.subTest(original=original):
                achado = normalizar(bruto, proveniencia(bruto))[0]
                self.assertEqual(esperado, achado.arquivo)

        for invalido in (
            "/fora-da-entrada/modulo.py",
            "/entrada/../oracle/respostas.json",
            "C:\\segredo\\modulo.py",
            "",
        ):
            bruto = saida_semgrep(path=invalido)
            with self.subTest(invalido=invalido):
                with self.assertRaises(ErroAdaptador):
                    normalizar(bruto, proveniencia(bruto))

    def test_lista_vazia_e_saida_valida(self):
        bruto = (FIXTURES / "vazio.json").read_bytes()

        self.assertEqual([], normalizar(bruto, proveniencia(bruto)))

    def test_resultado_parcial_retorna_achado_e_sinaliza_erros_preservados(self):
        bruto = (FIXTURES / "parcial_com_erros.json").read_bytes()
        erros_esperados = tuple(json.loads(bruto)["errors"])

        with warnings.catch_warnings(record=True) as emitidos:
            warnings.simplefilter("always")
            achados = normalizar(bruto, proveniencia(bruto))

        self.assertEqual(1, len(emitidos))
        aviso = emitidos[0].message
        self.assertIsInstance(aviso, ResultadoParcialSemgrepWarning)
        self.assertEqual(erros_esperados, aviso.erros)
        self.assertEqual(proveniencia(bruto).saida_bruta_sha256, aviso.saida_bruta_sha256)
        self.assertEqual(1, len(achados))
        achado = achados[0]
        self.assertIsNone(achado.regra)
        self.assertEqual("pacote/modulo.py", achado.arquivo)
        self.assertEqual(7, achado.linha_inicial)
        self.assertIsNone(achado.linha_final)
        self.assertIsNone(achado.cwe_original)
        self.assertIsNone(achado.cwe)
        self.assertEqual("INFO", achado.severidade_original)
        self.assertEqual("baixa", achado.severidade)
        self.assertIsNone(achado.descricao)
        self.assertIsNone(achado.evidencia)
        self.assertIsNone(achado.recomendacao)

    def test_json_estrito_rejeita_sintaxe_utf8_chave_duplicada_e_nao_finito(self):
        casos = (
            (FIXTURES / "invalido.json").read_bytes(),
            b'{"version":"1.172.0","results":[],"results":[],"errors":[]}',
            b'{"version":"1.172.0","results":[NaN],"errors":[]}',
            b'{"version":"1.172.0","results":[],"errors":[],"x":"\xff"}',
        )

        for bruto in casos:
            with self.subTest(bruto=bruto):
                with self.assertRaises(ErroAdaptador):
                    normalizar(bruto, proveniencia(bruto))

    def test_rejeita_estrutura_incompativel_versao_e_hash_divergente(self):
        documentos = (
            [],
            {"version": "1.172.0", "errors": []},
            {"version": "1.172.0", "results": {}, "errors": []},
            {"version": "1.172.0", "results": [], "errors": {}},
            {"version": "1.172.0", "results": ["achado"], "errors": []},
            {"version": "1.171.0", "results": [], "errors": []},
        )
        for documento in documentos:
            bruto = json.dumps(documento).encode("utf-8")
            with self.subTest(documento=documento):
                with self.assertRaises(ErroAdaptador):
                    normalizar(bruto, proveniencia(bruto))

        bruto = (FIXTURES / "vazio.json").read_bytes()
        origem_incorreta = Proveniencia(
            alvo="ALVO-0001",
            repeticao=1,
            execucao_id="C2-ALVO-0001-R01",
            saida_bruta_sha256="0" * 64,
        )
        with self.assertRaisesRegex(ErroAdaptador, "hash|SHA-256"):
            normalizar(bruto, origem_incorreta)

        origem_de_c1 = Proveniencia(
            alvo="ALVO-0001",
            repeticao=1,
            execucao_id="C1-ALVO-0001-R01",
            saida_bruta_sha256=hashlib.sha256(bruto).hexdigest(),
        )
        with self.assertRaisesRegex(ErroAdaptador, "C2|execucao_id"):
            normalizar(bruto, origem_de_c1)

    def test_mapeamento_de_severidade_e_publico_e_fechado(self):
        self.assertEqual(
            {"INFO": "baixa", "WARNING": "media", "ERROR": "alta"},
            MAPA_SEVERIDADE,
        )
        with self.assertRaises(TypeError):
            MAPA_SEVERIDADE["INFO"] = "alta"

        casos = {
            "INFO": "baixa",
            "WARNING": "media",
            "ERROR": "alta",
            "EXPERIMENT": None,
        }

        for original, normalizada in casos.items():
            bruto = saida_semgrep(severidade=original)
            with self.subTest(original=original):
                achado = normalizar(bruto, proveniencia(bruto))[0]
                self.assertEqual(original, achado.severidade_original)
                self.assertEqual(normalizada, achado.severidade)

    def test_cwe_so_e_extraida_de_metadata_sem_oracle_ou_heuristica_textual(self):
        bruto = saida_semgrep(
            check_id="python.security.CWE-79",
            extra={
                "message": "Possível CWE-79 no texto, sem metadado CWE.",
                "metadata": {"confidence": "MEDIUM"},
                "severity": "ERROR",
            },
        )

        achado = normalizar(bruto, proveniencia(bruto))[0]

        self.assertIsNone(achado.cwe_original)
        self.assertIsNone(achado.cwe)
        self.assertEqual("MEDIUM", achado.confianca_original)
        self.assertIsNone(achado.confianca)

    def test_normalizacao_nao_acessa_disco_rede_registry_ou_processos(self):
        bruto = (FIXTURES / "achado_completo.json").read_bytes()
        origem = proveniencia(bruto)

        with (
            patch("builtins.open", side_effect=AssertionError("acesso a disco")),
            patch.object(socket, "socket", side_effect=AssertionError("rede")),
            patch.object(
                urllib.request,
                "urlopen",
                side_effect=AssertionError("registry"),
            ),
            patch.object(
                subprocess,
                "run",
                side_effect=AssertionError("processo externo"),
            ),
        ):
            achados = normalizar(bruto, origem)

        self.assertEqual(1, len(achados))


if __name__ == "__main__":
    unittest.main()
