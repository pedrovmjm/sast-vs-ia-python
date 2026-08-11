import copy
import os
import tempfile
import unittest
from pathlib import Path

from runner.aquisicao import (
    ErroProveniencia,
    calcular_sha256_arvore,
    carregar_json,
    validar_manifesto,
    verificar_bundle_regras,
    verificar_fontes,
    verificar_versoes_host,
)


RAIZ = Path(__file__).resolve().parents[1]
LOCK = RAIZ / "config" / "fontes.lock.json"
EXCECAO = RAIZ / "config" / "host-risk-waiver.json"


class ValidacaoManifestoTest(unittest.TestCase):
    def setUp(self):
        self.manifesto = carregar_json(LOCK)

    def test_manifesto_oficial_e_valido(self):
        validado = validar_manifesto(self.manifesto)

        self.assertEqual("1.0", validado["schema_version"])
        self.assertEqual(
            "d98e9fc91273702c9547663b6906d1fc494d4fcc",
            validado["sources"]["realvuln"]["commit"],
        )

    def test_rejeita_revisao_realvuln_divergente(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["realvuln"]["commit"] = "0" * 40

        with self.assertRaisesRegex(ErroProveniencia, "RealVuln"):
            validar_manifesto(alterado)

    def test_rejeita_identificador_upstream_divergente(self):
        alterado = copy.deepcopy(self.manifesto)
        abreviados = alterado["sources"]["realvuln"][
            "upstream_abbreviated_identifiers"
        ]
        abreviados["ground_truth_content_hash"] = "sha256:000000000000"

        with self.assertRaisesRegex(ErroProveniencia, "identificador"):
            validar_manifesto(alterado)

    def test_rejeita_licenca_realvuln_divergente(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["realvuln"]["license_observed"] = ["qualquer"]

        with self.assertRaisesRegex(ErroProveniencia, "licença"):
            validar_manifesto(alterado)

    def test_rejeita_dominio_nao_oficial(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["realvuln"]["url"] = (
            "https://github.example/Real-Vuln-Benchmark.git"
        )

        with self.assertRaisesRegex(ErroProveniencia, "origem"):
            validar_manifesto(alterado)

    def test_rejeita_outro_repositorio_no_dominio_oficial(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["bandit"]["source_url"] = (
            "https://github.com/terceiro/bandit"
        )

        with self.assertRaisesRegex(ErroProveniencia, "origem"):
            validar_manifesto(alterado)

    def test_rejeita_sha256_incompleto(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["bandit"]["wheel_sha256"] = "a57347fbdf2a"

        with self.assertRaisesRegex(ErroProveniencia, "SHA-256"):
            validar_manifesto(alterado)

    def test_rejeita_sha256_completo_mas_divergente(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["semgrep"]["wheel_sha256"] = "0" * 64

        with self.assertRaisesRegex(ErroProveniencia, "diverge"):
            validar_manifesto(alterado)

    def test_rejeita_referencia_flutuante(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["python_image"]["reference"] = "python:latest"

        with self.assertRaisesRegex(ErroProveniencia, "flutuante"):
            validar_manifesto(alterado)

    def test_rejeita_campos_desconhecidos(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["realvuln"]["command"] = "git clone"

        with self.assertRaisesRegex(ErroProveniencia, "campos"):
            validar_manifesto(alterado)

    def test_rejeita_rebaixamento_da_politica_do_host(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["host_policy"]["git"] = {
            "recommended": "0.0.0",
            "source": "https://evil.example/policy",
        }

        with self.assertRaisesRegex(ErroProveniencia, "política"):
            validar_manifesto(alterado)

    def test_regras_exigem_caminhos_e_hash_do_bundle(self):
        alterado = copy.deepcopy(self.manifesto)
        alterado["sources"]["semgrep_rules"].pop("bundle_sha256", None)

        with self.assertRaisesRegex(ErroProveniencia, "bundle"):
            validar_manifesto(alterado)


class LeituraJsonTest(unittest.TestCase):
    def test_rejeita_chave_json_duplicada(self):
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "duplicado.json"
            caminho.write_text('{"schema_version":"1.0","schema_version":"2.0"}')

            with self.assertRaisesRegex(ErroProveniencia, "duplicada"):
                carregar_json(caminho)


class HashCanonicoTest(unittest.TestCase):
    def test_hash_da_arvore_independe_de_mtime(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            (raiz / "sub").mkdir()
            (raiz / "b.yml").write_bytes(b"regra-b\n")
            (raiz / "sub" / "a.yml").write_bytes(b"regra-a\n")
            primeiro = calcular_sha256_arvore(raiz)

            os.utime(raiz / "b.yml", (1_700_000_000, 1_700_000_000))
            segundo = calcular_sha256_arvore(raiz)

            self.assertEqual(primeiro, segundo)

    def test_hash_da_arvore_muda_com_conteudo(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            arquivo = raiz / "regra.yml"
            arquivo.write_bytes(b"antes\n")
            primeiro = calcular_sha256_arvore(raiz)
            arquivo.write_bytes(b"depois\n")

            self.assertNotEqual(primeiro, calcular_sha256_arvore(raiz))

    def test_hash_da_arvore_rejeita_link_simbolico(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            (raiz / "real.yml").write_bytes(b"regra\n")
            os.symlink("real.yml", raiz / "link.yml")

            with self.assertRaisesRegex(ErroProveniencia, "link"):
                calcular_sha256_arvore(raiz)

    def test_bundle_regras_rejeita_hash_divergente(self):
        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario)
            (raiz / "python").mkdir()
            (raiz / "python" / "regra.yml").write_bytes(b"regra\n")
            fonte = {"paths": ["python"], "bundle_sha256": "0" * 64}

            with self.assertRaisesRegex(ErroProveniencia, "bundle"):
                verificar_bundle_regras(raiz, fonte)


class PreflightHostTest(unittest.TestCase):
    def setUp(self):
        self.manifesto = carregar_json(LOCK)
        self.politica = self.manifesto["host_policy"]
        self.excecao = carregar_json(EXCECAO)

    def test_versoes_recomendadas_nao_geram_aviso(self):
        observadas = {
            "git": "2.55.0.windows.3",
            "wsl": "2.1.5",
            "docker_desktop": "4.86.0",
            "docker_engine": "29.7.2",
        }

        self.assertEqual([], verificar_versoes_host(observadas, self.politica))

    def test_versoes_antigas_sem_excecao_bloqueiam(self):
        with self.assertRaisesRegex(ErroProveniencia, "exceção"):
            verificar_versoes_host(self.excecao["versions"], self.politica)

    def test_versoes_antigas_com_excecao_geram_avisos(self):
        avisos = verificar_versoes_host(
            self.excecao["versions"], self.politica, self.excecao
        )

        self.assertEqual(4, len(avisos))
        self.assertTrue(all("AD-005" in aviso for aviso in avisos))

    def test_excecao_nao_vale_para_versao_diferente(self):
        observadas = dict(self.excecao["versions"])
        observadas["git"] = "2.45.0.windows.1"

        with self.assertRaisesRegex(ErroProveniencia, "não corresponde"):
            verificar_versoes_host(observadas, self.politica, self.excecao)

    def test_excecao_nao_autoriza_acao_fora_do_escopo(self):
        with self.assertRaisesRegex(ErroProveniencia, "ação"):
            verificar_versoes_host(
                self.excecao["versions"],
                self.politica,
                self.excecao,
                acao="publicar-remoto",
            )

    def test_excecao_editada_nao_autoautoriza_acao(self):
        alterada = copy.deepcopy(self.excecao)
        alterada["allowed_actions"].append("publicar-remoto")

        with self.assertRaisesRegex(ErroProveniencia, "ações"):
            verificar_versoes_host(
                alterada["versions"],
                self.politica,
                alterada,
                acao="publicar-remoto",
            )

    def test_excecao_editada_nao_autoautoriza_versao(self):
        alterada = copy.deepcopy(self.excecao)
        alterada["versions"]["git"] = "2.45.0.windows.1"

        with self.assertRaisesRegex(ErroProveniencia, "versões aprovadas"):
            verificar_versoes_host(
                alterada["versions"], self.politica, alterada
            )

    def test_verificacao_pura_retorna_hashes_e_avisos(self):
        relatorio = verificar_fontes(
            LOCK,
            observadas=self.excecao["versions"],
            caminho_excecao=EXCECAO,
            acao="preflight",
        )

        self.assertEqual(64, len(relatorio["manifest_sha256"]))
        self.assertEqual(64, len(relatorio["waiver_sha256"]))
        self.assertEqual(4, len(relatorio["warnings"]))


if __name__ == "__main__":
    unittest.main()
