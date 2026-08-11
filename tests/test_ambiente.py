import copy
import re
import unittest
from pathlib import Path

from runner.aquisicao import (
    ErroProveniencia,
    carregar_json,
    validar_manifesto,
    verificar_lock_dependencias,
)


RAIZ = Path(__file__).resolve().parents[1]
DOCKERFILE = RAIZ / "docker" / "Dockerfile"
REQUIREMENTS_IN = RAIZ / "docker" / "requirements.in"
REQUIREMENTS_LOCK = RAIZ / "docker" / "requirements.lock"
COMPOSE = RAIZ / "compose.yaml"
DOCKERIGNORE = RAIZ / ".dockerignore"
FONTES_LOCK = RAIZ / "config" / "fontes.lock.json"
GATE_SCRIPT = RAIZ / "scripts" / "gate.ps1"

BASE_FIXADA = (
    "python:3.12.13-slim-bookworm@"
    "sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af"
)


class DockerfileTest(unittest.TestCase):
    def setUp(self):
        self.texto = DOCKERFILE.read_text(encoding="utf-8")

    def test_base_usa_tag_completa_e_digest(self):
        self.assertIn(f"FROM --platform=linux/amd64 {BASE_FIXADA}", self.texto)
        self.assertNotRegex(self.texto, r"(?im)^FROM\s+[^\s]*(?:latest|main)")

    def test_pip_exige_lock_hashes_e_somente_wheels(self):
        self.assertIn("--require-hashes", self.texto)
        self.assertIn("--only-binary=:all:", self.texto)
        self.assertIn("--no-cache-dir", self.texto)
        self.assertIn("docker/requirements.lock", self.texto)

    def test_usuario_final_nao_e_root(self):
        self.assertRegex(self.texto, r"(?m)^USER 10001:10001$")
        self.assertIn("/opt/tcc/runner", self.texto)

    def test_imagem_nao_copia_dados_do_experimento(self):
        proibidos = ("benchmark", "alvos", "oracle", "execucoes", "resultados")
        copias = [
            linha.strip()
            for linha in self.texto.splitlines()
            if linha.lstrip().upper().startswith(("COPY ", "ADD "))
        ]
        self.assertTrue(copias)
        self.assertFalse(any(nome in linha for nome in proibidos for linha in copias))
        self.assertFalse(any(linha.upper().startswith("ADD ") for linha in copias))


class LockDependenciasTest(unittest.TestCase):
    def test_entrada_contem_somente_topos_fixados(self):
        linhas = {
            linha.strip()
            for linha in REQUIREMENTS_IN.read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.lstrip().startswith("#")
        }
        self.assertEqual({"bandit==1.9.4", "semgrep==1.172.0"}, linhas)

    def test_lock_e_totalmente_pinado_e_hasheado(self):
        texto = REQUIREMENTS_LOCK.read_text(encoding="utf-8")
        logicas = re.sub(r"\\\r?\n\s*", " ", texto).splitlines()
        requisitos = [
            linha.strip()
            for linha in logicas
            if linha.strip()
            and not linha.lstrip().startswith(("#", "--"))
        ]
        self.assertGreaterEqual(len(requisitos), 20)
        for requisito in requisitos:
            self.assertRegex(requisito, r"^[A-Za-z0-9_.-]+==[^\s;]+")
            self.assertRegex(requisito, r"--hash=sha256:[0-9a-f]{64}")
            self.assertNotRegex(requisito, r"(?i)(https?://|git\+|latest|>=|~=|\*)")

    def test_hashes_do_input_e_lock_conferem_com_manifesto(self):
        manifesto = carregar_json(FONTES_LOCK)
        fonte = manifesto["sources"]["python_packages"]

        observados = verificar_lock_dependencias(RAIZ, fonte)

        self.assertEqual(fonte["input_sha256"], observados["input_sha256"])
        self.assertEqual(fonte["lock_sha256"], observados["lock_sha256"])

    def test_rejeita_hash_de_lock_completo_mas_divergente(self):
        manifesto = carregar_json(FONTES_LOCK)
        alterado = copy.deepcopy(manifesto)
        alterado["sources"]["python_packages"]["lock_sha256"] = "0" * 64

        with self.assertRaisesRegex(ErroProveniencia, "lock.*diverge"):
            validar_manifesto(alterado)


class IsolamentoComposeTest(unittest.TestCase):
    def setUp(self):
        self.compose = COMPOSE.read_text(encoding="utf-8")

    def test_servico_aplica_controles_compensatorios(self):
        obrigatorios = (
            "network_mode: none",
            "platform: linux/amd64",
            "read_only: true",
            "cap_drop:",
            "- ALL",
            "no-new-privileges:true",
            'user: "10001:10001"',
            "pids_limit:",
            "mem_limit:",
            "cpus:",
            "tmpfs:",
            "PYTHONPYCACHEPREFIX: /tmp/pycache",
        )
        for controle in obrigatorios:
            self.assertIn(controle, self.compose)

    def test_servico_nao_monta_raiz_oracle_corpus_ou_socket(self):
        self.assertNotRegex(self.compose, r"(?m)^\s*-\s*\.:/")
        for proibido in ("benchmark", "alvos", "oracle", "docker.sock"):
            self.assertNotIn(proibido, self.compose)

    def test_contexto_de_build_usa_allowlist(self):
        linhas = [
            linha.strip()
            for linha in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.lstrip().startswith("#")
        ]
        self.assertEqual("**", linhas[0])
        for proibido in ("benchmark", "alvos", "oracle", "execucoes", "resultados"):
            self.assertFalse(any(linha.startswith(f"!{proibido}") for linha in linhas))
        self.assertIn("!docker/Dockerfile", linhas)
        self.assertIn("!docker/requirements.in", linhas)
        self.assertIn("!docker/requirements.lock", linhas)
        self.assertIn("!runner/**", linhas)
        self.assertIn("!config/*.json", linhas)

    def test_gate_build_inclui_compilacao_sonda_e_dependencias(self):
        gate = GATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("compileall", gate)
        self.assertIn("tests/runtime_probe.py", gate)
        self.assertIn('"pip", "check"', gate)
        self.assertIn('"semgrep", "--version"', gate)


if __name__ == "__main__":
    unittest.main()
