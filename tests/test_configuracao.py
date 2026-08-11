import copy
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runner.configuracao import ErroConfiguracao, criar_configuracao, validar_configuracao
from runner.corpus import carregar_json


RAIZ = Path(__file__).resolve().parents[1]
DECISAO = {
    "schema_version": "1.0",
    "tipo": "host-risk-waiver-m2",
    "status": "accepted",
    "decision": "accept-residual-risk-m2",
    "decided_at": "2026-08-11",
    "authorized_by": "teste",
    "scope": "M2",
    "authorization": True,
}
HOST = {"git": "2.46.2.windows.1", "wsl": "2.0.14.0", "docker": "4.38.0"}


class ConfiguracaoTests(unittest.TestCase):
    def criar(self):
        return criar_configuracao(
            RAIZ,
            imagem_tag="tcc-sast:teste",
            imagem_id="sha256:" + "a" * 64,
            controlador_commit="b" * 40,
            timeout_segundos=180,
            host_observado=HOST,
            decisao=DECISAO,
            criada_em="2026-08-11T14:30:00Z",
        )

    def test_cria_configuracao_com_hashes_e_26_alvos(self):
        documento = self.criar()
        self.assertEqual("configuracao-coleta-c1-c2", documento["tipo"])
        self.assertEqual(26, len(documento["corpus"]["alvos"]))
        self.assertTrue(documento["risco"]["autorizacao_coleta"])
        self.assertEqual(64, len(documento["hashes"]["regras_bundle_sha256"]))

    def test_configuracao_publicada_valida_no_schema(self):
        schema = carregar_json(RAIZ / "runner/schemas/configuracao-coleta-c1-c2-v1.schema.json")
        erros = list(Draft202012Validator(schema).iter_errors(self.criar()))
        self.assertEqual([], [erro.message for erro in erros])

    def test_validacao_recalcula_locks_regras_e_inventarios(self):
        documento = self.criar()
        self.assertIs(documento, validar_configuracao(documento, RAIZ, RAIZ / "docker/regras-semgrep"))

    def test_recusa_configuracao_sem_autorizacao(self):
        documento = self.criar()
        documento["risco"]["autorizacao_coleta"] = False
        with self.assertRaisesRegex(ErroConfiguracao, "não autorizada"):
            validar_configuracao(documento, RAIZ, RAIZ / "docker/regras-semgrep")

    def test_recusa_decisao_com_escopo_m1(self):
        decisao = copy.deepcopy(DECISAO)
        decisao["scope"] = "M1"
        with self.assertRaisesRegex(ErroConfiguracao, "escopo M2"):
            criar_configuracao(
                RAIZ, imagem_tag="x", imagem_id="sha256:" + "a" * 64,
                controlador_commit="b" * 40, timeout_segundos=180,
                host_observado=HOST, decisao=decisao,
            )

    def test_recusa_hash_de_lock_adulterado(self):
        documento = self.criar()
        documento["hashes"]["fila_lock_sha256"] = "0" * 64
        with self.assertRaisesRegex(ErroConfiguracao, "fila_lock_sha256"):
            validar_configuracao(documento, RAIZ, RAIZ / "docker/regras-semgrep")

    def test_recusa_inventario_adulterado(self):
        documento = self.criar()
        documento["corpus"]["alvos"][0]["inventario_sha256"] = "0" * 64
        with self.assertRaisesRegex(ErroConfiguracao, "hash do inventário"):
            validar_configuracao(documento, RAIZ, RAIZ / "docker/regras-semgrep")

    def test_recusa_decisao_sem_autorizacao_explicita(self):
        decisao = copy.deepcopy(DECISAO)
        decisao["authorization"] = False
        with self.assertRaisesRegex(ErroConfiguracao, "autorização explícita"):
            criar_configuracao(
                RAIZ, imagem_tag="x", imagem_id="sha256:" + "a" * 64,
                controlador_commit="b" * 40, timeout_segundos=180,
                host_observado=HOST, decisao=decisao,
            )


if __name__ == "__main__":
    unittest.main()
