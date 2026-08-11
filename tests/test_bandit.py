import hashlib
import json
import socket
import subprocess
import unittest
import urllib.request
import warnings
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from runner.adaptadores.bandit import (
    MAPA_CONFIANCA,
    MAPA_SEVERIDADE,
    ResultadoParcialBanditWarning,
    normalizar,
)
from runner.adaptadores.comum import ErroAdaptador, Proveniencia


RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / "tests" / "fixtures" / "bandit"
BRUTO_ACHADOS = (FIXTURES / "achados.json").read_bytes()
BRUTO_VAZIO = (FIXTURES / "vazio.json").read_bytes()
SHA_BRUTO = hashlib.sha256(BRUTO_ACHADOS).hexdigest()


def proveniencia_valida(documento=BRUTO_ACHADOS, **alteracoes):
    bruto = documento.encode("utf-8") if isinstance(documento, str) else documento
    dados = {
        "alvo": "ALVO-0001",
        "repeticao": 1,
        "execucao_id": "C1-ALVO-0001-R01",
        "saida_bruta_sha256": hashlib.sha256(bruto).hexdigest(),
    }
    dados.update(alteracoes)
    return Proveniencia(**dados)


class BanditAdapterTest(unittest.TestCase):
    def test_normaliza_bytes_e_preserva_campos_originais(self):
        bruto = BRUTO_ACHADOS

        achados = normalizar(bruto, proveniencia_valida())

        self.assertEqual(2, len(achados))
        primeiro = achados[0]
        self.assertEqual("C1", primeiro.condicao)
        self.assertEqual("bandit", primeiro.ferramenta)
        self.assertEqual("ALVO-0001", primeiro.alvo)
        self.assertEqual(1, primeiro.repeticao)
        self.assertEqual("C1-ALVO-0001-R01", primeiro.execucao_id)
        self.assertEqual("src/banco.py", primeiro.arquivo)
        self.assertEqual((10, 11), (primeiro.linha_inicial, primeiro.linha_final))
        self.assertEqual("B608", primeiro.regra)
        self.assertEqual("89", primeiro.cwe_original)
        self.assertEqual("CWE-89", primeiro.cwe)
        self.assertEqual("MEDIUM", primeiro.severidade_original)
        self.assertEqual("media", primeiro.severidade)
        self.assertEqual("HIGH", primeiro.confianca_original)
        self.assertEqual("alta", primeiro.confianca)
        self.assertEqual("10 query = \"SELECT \" + entrada\n", primeiro.evidencia)
        self.assertIsNone(primeiro.recomendacao)
        self.assertEqual(SHA_BRUTO, primeiro.saida_bruta_sha256)

        original = json.loads(primeiro.texto_original)
        self.assertEqual("hardcoded_sql_expressions", original["test_name"])
        self.assertEqual(
            primeiro.texto_original,
            json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def test_cwe_ausente_permanece_nulo(self):
        achado = normalizar(
            BRUTO_ACHADOS.decode("utf-8"),
            proveniencia_valida(BRUTO_ACHADOS.decode("utf-8")),
        )[1]

        self.assertIsNone(achado.cwe_original)
        self.assertIsNone(achado.cwe)
        self.assertEqual("src/entrada.py", achado.arquivo)

    def test_normaliza_prefixo_de_entrada_e_separador_windows(self):
        documento = json.loads(BRUTO_ACHADOS.decode("utf-8"))
        documento["results"][1]["filename"] = ".\\src\\janela.py"
        texto = json.dumps(documento, ensure_ascii=False)

        achados = normalizar(texto, proveniencia_valida(texto))

        self.assertEqual("src/banco.py", achados[0].arquivo)
        self.assertEqual("src/janela.py", achados[1].arquivo)

    def test_lista_vazia_e_valida_e_a_proveniencia_e_imutavel(self):
        proveniencia = proveniencia_valida()

        self.assertEqual(
            [],
            normalizar(
                BRUTO_VAZIO,
                proveniencia_valida(BRUTO_VAZIO),
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            proveniencia.alvo = "ALVO-9999"

    def test_resultado_parcial_sinaliza_erros_sem_descartar_achados(self):
        documento = json.loads((FIXTURES / "achados.json").read_text(encoding="utf-8"))
        documento["errors"] = [
            {"filename": "/entrada/quebrado.py", "reason": "syntax error"}
        ]
        bruto = json.dumps(documento, ensure_ascii=False).encode("utf-8")

        with warnings.catch_warnings(record=True) as emitidos:
            warnings.simplefilter("always")
            achados = normalizar(bruto, proveniencia_valida(bruto))

        self.assertEqual(2, len(achados))
        self.assertEqual(1, len(emitidos))
        aviso = emitidos[0].message
        self.assertIsInstance(aviso, ResultadoParcialBanditWarning)
        self.assertEqual(tuple(documento["errors"]), aviso.erros)
        self.assertEqual(hashlib.sha256(bruto).hexdigest(), aviso.saida_bruta_sha256)

    def test_mapeamentos_sao_fechados_e_desconhecido_nao_e_inventado(self):
        self.assertEqual(
            {"LOW": "baixa", "MEDIUM": "media", "HIGH": "alta"},
            MAPA_SEVERIDADE,
        )
        self.assertEqual(
            {"LOW": "baixa", "MEDIUM": "media", "HIGH": "alta"},
            MAPA_CONFIANCA,
        )
        documento = json.loads((FIXTURES / "achados.json").read_text(encoding="utf-8"))
        documento["results"][0]["issue_severity"] = "UNDEFINED"
        documento["results"][0]["issue_confidence"] = "UNDEFINED"

        texto = json.dumps(documento, ensure_ascii=False)
        achado = normalizar(texto, proveniencia_valida(texto))[0]

        self.assertEqual("UNDEFINED", achado.severidade_original)
        self.assertIsNone(achado.severidade)
        self.assertEqual("UNDEFINED", achado.confianca_original)
        self.assertIsNone(achado.confianca)

        with self.assertRaises(TypeError):
            MAPA_SEVERIDADE["CRITICAL"] = "critica"

    def test_preserva_achados_duplicados_na_ordem_de_emissao(self):
        documento = json.loads(BRUTO_ACHADOS.decode("utf-8"))
        primeiro = documento["results"][0]
        documento["results"] = [primeiro, primeiro]
        texto = json.dumps(documento, ensure_ascii=False)

        achados = normalizar(texto, proveniencia_valida(texto))

        self.assertEqual(2, len(achados))
        self.assertEqual(achados[0], achados[1])

    def test_rejeita_json_com_chave_duplicada_ou_nao_finito(self):
        for nome in ("duplicado.json", "nao-finito.json"):
            with self.subTest(nome=nome):
                with self.assertRaisesRegex(ErroAdaptador, "duplicada|finita"):
                    documento = (FIXTURES / nome).read_bytes()
                    normalizar(documento, proveniencia_valida(documento))

    def test_rejeita_utf8_json_raiz_e_resultados_invalidos(self):
        invalidos = (
            b"\xff",
            "[]",
            '{"results": {}}',
            '{"results": [1]}',
            '{"results": [{"filename": "/fora/app.py", "line_number": 1}]}',
            '{"results": [{"filename": "C:\\\\segredo.py", "line_number": 1}]}',
            '{"results": [{"filename": "../oracle.py", "line_number": 1}]}',
        )

        for documento in invalidos:
            with self.subTest(documento=documento):
                with self.assertRaises(ErroAdaptador):
                    normalizar(documento, proveniencia_valida(documento))

    def test_rejeita_errors_ausente_ou_com_tipo_invalido(self):
        for documento in ('{"results": []}', '{"results": [], "errors": {}}'):
            with self.subTest(documento=documento):
                with self.assertRaisesRegex(ErroAdaptador, "errors"):
                    normalizar(documento, proveniencia_valida(documento))

    def test_rejeita_proveniencia_invalida_mesmo_sem_achados(self):
        casos = (
            {"alvo": "../oracle"},
            {"repeticao": True},
            {"execucao_id": "id com espaço"},
            {"saida_bruta_sha256": "a" * 12},
        )

        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                with self.assertRaises(ErroAdaptador):
                    proveniencia_valida(**alteracoes)

        repeticao_invalida_para_c1 = proveniencia_valida(BRUTO_VAZIO, repeticao=2)
        with self.assertRaisesRegex(ErroAdaptador, "repeticao"):
            normalizar(BRUTO_VAZIO, repeticao_invalida_para_c1)

    def test_rejeita_hash_que_nao_corresponde_ao_bruto(self):
        proveniencia = proveniencia_valida(saida_bruta_sha256="0" * 64)

        with self.assertRaisesRegex(ErroAdaptador, "SHA-256.*bruto"):
            normalizar(BRUTO_ACHADOS, proveniencia)

    def test_rejeita_execucao_id_de_outra_condicao(self):
        proveniencia = proveniencia_valida(execucao_id="C2-ALVO-0001-R01")

        with self.assertRaisesRegex(ErroAdaptador, "execucao_id.*C1"):
            normalizar(BRUTO_ACHADOS, proveniencia)

    def test_rejeita_intervalo_invertido_ou_incoerente_sem_corrigir(self):
        documento = json.loads(BRUTO_ACHADOS.decode("utf-8"))
        for linha, intervalo in ((10, [11, 10]), (10, [9, 11])):
            documento["results"][0]["line_number"] = linha
            documento["results"][0]["line_range"] = intervalo
            texto = json.dumps(documento, ensure_ascii=False)
            with self.subTest(intervalo=intervalo):
                with self.assertRaisesRegex(ErroAdaptador, "line_range"):
                    normalizar(texto, proveniencia_valida(texto))

    def test_texto_original_independe_da_ordem_das_chaves(self):
        documento = json.loads((FIXTURES / "achados.json").read_text(encoding="utf-8"))
        invertido = dict(reversed(tuple(documento["results"][0].items())))
        documento_invertido = {
            "errors": [],
            "results": [invertido, documento["results"][1]],
        }

        texto_normal = json.dumps(documento, ensure_ascii=False)
        texto_reordenado = json.dumps(documento_invertido, ensure_ascii=False)
        normal = normalizar(texto_normal, proveniencia_valida(texto_normal))[0]
        reordenado = normalizar(
            texto_reordenado, proveniencia_valida(texto_reordenado)
        )[0]

        self.assertEqual(normal.texto_original, reordenado.texto_original)

    def test_normalizacao_nao_acessa_disco_rede_ou_processos(self):
        with (
            patch("builtins.open", side_effect=AssertionError("disco")),
            patch.object(socket, "socket", side_effect=AssertionError("rede")),
            patch.object(urllib.request, "urlopen", side_effect=AssertionError("rede")),
            patch.object(subprocess, "run", side_effect=AssertionError("processo")),
        ):
            achados = normalizar(BRUTO_ACHADOS, proveniencia_valida())

        self.assertEqual(2, len(achados))


if __name__ == "__main__":
    unittest.main()
