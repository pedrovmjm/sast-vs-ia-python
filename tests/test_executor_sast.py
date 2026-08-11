import hashlib
import json
import os
import signal
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

from runner.adaptadores.bandit import ResultadoParcialBanditWarning
from runner.aquisicao import calcular_sha256_arvore
from runner.executor_sast import (
    ConfiguracaoExecucao,
    ErroExecucao,
    ResultadoProcesso,
    _escrever_bytes_atomico,
    _executar_processo,
    _listar_interfaces_rede,
    _verificar_regras,
    comando_scanner,
    executar_sast,
)


RAIZ = Path(__file__).resolve().parents[1]
BRUTO_BANDIT = (RAIZ / "tests" / "fixtures" / "bandit" / "achados.json").read_bytes()
BRUTO_SEMGREP = (
    RAIZ / "tests" / "fixtures" / "semgrep" / "achado_completo.json"
).read_bytes()
IMAGEM_DIGEST = "sha256:" + "d" * 64


class ExecucaoFixture:
    def __init__(self, condicao="C1"):
        self.temporario = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporario.name)
        self.entrada = self.raiz / "entrada"
        self.saida = self.raiz / "saida"
        self.regras = self.raiz / "regras" if condicao == "C2" else None
        self.entrada.mkdir()
        self.saida.mkdir()
        (self.entrada / "app.py").write_text("valor = input()\n", encoding="utf-8")
        if self.regras is not None:
            (self.regras / "python").mkdir(parents=True)
            (self.regras / "python" / "regra.yml").write_text(
                "rules: []\n", encoding="utf-8"
            )
        self.entrada_sha256 = calcular_sha256_arvore(self.entrada)
        self.config = ConfiguracaoExecucao(
            condicao=condicao,
            execucao_id=f"{condicao}-ALVO-0001-R01",
            alvo="ALVO-0001",
            entrada_commit=None,
            entrada_sha256=self.entrada_sha256,
            finalidade="fumaca",
            tentativa=1,
            imagem="tcc-sast:fixada",
            imagem_digest=IMAGEM_DIGEST,
            timeout_segundos=30,
            entrada_dir=self.entrada,
            saida_dir=self.saida,
            regras_dir=self.regras,
        )

    def cleanup(self):
        self.temporario.cleanup()


def runner_controlado(bruto, codigo=0, *, timeout=False):
    chamadas = []

    def executar(comando, stdout, stderr, limite):
        chamadas.append((tuple(comando), limite))
        stdout.write(b"stdout controlado\n")
        stderr.write(b"stderr controlado\n")
        caminho = Path(comando[comando.index("--output") + 1])
        caminho.write_bytes(bruto)
        return ResultadoProcesso(codigo_saida=None if timeout else codigo, timeout=timeout)

    executar.chamadas = chamadas
    return executar


def dependencias_controladas(**extras):
    valores = {
        "validar_ambiente": lambda configuracao: None,
        "verificar_regras": lambda configuracao: "a" * 64,
        "obter_versoes": lambda configuracao: {
            "python": "3.12.13",
            "bandit": "1.9.4",
            "semgrep": "1.172.0",
        },
        "agora_utc": iter(
            (
                "2026-08-11T02:00:00.000000Z",
                "2026-08-11T02:00:00.100000Z",
                "2026-08-11T02:00:00.850000Z",
                "2026-08-11T02:00:01.000000Z",
            )
        ).__next__,
        "monotonic_ns": iter(
            (1_000_000_000, 1_100_000_000, 1_850_000_000, 2_250_000_000)
        ).__next__,
    }
    valores.update(extras)
    return valores


class ComandoScannerTest(unittest.TestCase):
    def test_bandit_tem_vetor_fixo_e_codigos_zero_um(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        comando, codigos = comando_scanner(fixture.config)

        self.assertEqual(
            (
                "/usr/local/bin/bandit",
                "--recursive",
                str(fixture.entrada),
                "--format",
                "json",
                "--output",
                str(fixture.saida / "bruto.json.part"),
            ),
            comando,
        )
        self.assertEqual(frozenset({0, 1}), codigos)

    def test_semgrep_tem_regras_locais_jobs_um_e_codigo_zero(self):
        fixture = ExecucaoFixture("C2")
        self.addCleanup(fixture.cleanup)

        comando, codigos = comando_scanner(fixture.config)

        self.assertEqual(
            (
                "/usr/local/bin/semgrep",
                "scan",
                "--config",
                str(fixture.regras / "python"),
                "--json",
                "--metrics=off",
                "--jobs",
                "1",
                "--output",
                str(fixture.saida / "bruto.json.part"),
                str(fixture.entrada),
            ),
            comando,
        )
        self.assertEqual(frozenset({0}), codigos)

    def test_configuracao_liga_condicao_id_regras_e_timeout(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)
        base = fixture.config.to_dict()

        casos = (
            {"execucao_id": "C2-ALVO-0001-R01"},
            {"regras_dir": fixture.raiz / "regras"},
            {"timeout_segundos": 0},
            {"tentativa": True},
        )
        for alteracoes in casos:
            with self.subTest(alteracoes=alteracoes):
                dados = dict(base)
                dados.update(alteracoes)
                with self.assertRaises(ErroExecucao):
                    ConfiguracaoExecucao(**dados)


class ExecutorSastTest(unittest.TestCase):
    def test_bandit_codigo_um_conclui_depois_de_bruto_hash_e_normalizado(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)
        executor = runner_controlado(BRUTO_BANDIT, codigo=1)

        manifesto = executar_sast(
            fixture.config,
            executar_processo=executor,
            **dependencias_controladas(),
        )

        self.assertEqual("concluida", manifesto.estado)
        self.assertEqual(1, manifesto.codigo_saida)
        self.assertEqual(1.25, manifesto.duracao_monotonica_segundos)
        self.assertEqual(2, len(json.loads((fixture.saida / "normalizado.json").read_text())))
        self.assertEqual(
            hashlib.sha256(BRUTO_BANDIT).hexdigest(),
            manifesto.to_dict()["artefatos_sha256"]["bruto.json"],
        )
        processo = json.loads((fixture.saida / "processo.json").read_text())
        self.assertEqual(1, processo["codigo_saida"])
        self.assertEqual(0.75, processo["duracao_monotonica_segundos"])
        self.assertIn("processo.json", manifesto.to_dict()["artefatos_sha256"])
        self.assertTrue((fixture.saida / "manifesto.em_execucao.json").is_file())
        self.assertTrue((fixture.saida / "manifesto.pendente.json").is_file())
        self.assertTrue((fixture.saida / "manifesto.json").is_file())
        self.assertFalse(any(fixture.saida.glob("*.part")))

    def test_semgrep_codigo_zero_valida_regras_e_conclui(self):
        fixture = ExecucaoFixture("C2")
        self.addCleanup(fixture.cleanup)
        verificador = Mock(return_value="a" * 64)

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_SEMGREP, codigo=0),
            **dependencias_controladas(verificar_regras=verificador),
        )

        self.assertEqual("concluida", manifesto.estado)
        self.assertEqual(
            [fixture.config, fixture.config],
            [chamada.args[0] for chamada in verificador.call_args_list],
        )
        achados = json.loads((fixture.saida / "normalizado.json").read_text())
        self.assertEqual("semgrep", achados[0]["ferramenta"])

    def test_codigo_inesperado_falha_sem_normalizar_e_preserva_bruto(self):
        fixture = ExecucaoFixture("C2")
        self.addCleanup(fixture.cleanup)
        normalizador = Mock(side_effect=AssertionError("não deve normalizar"))

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_SEMGREP, codigo=2),
            normalizadores={"C1": normalizador, "C2": normalizador},
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("codigo_saida", manifesto.falha_tipo)
        self.assertEqual(2, manifesto.codigo_saida)
        self.assertTrue((fixture.saida / "bruto.json").is_file())
        self.assertFalse((fixture.saida / "normalizado.json").exists())
        normalizador.assert_not_called()

    def test_mutacao_das_regras_depois_do_scanner_marca_contaminada(self):
        fixture = ExecucaoFixture("C2")
        self.addCleanup(fixture.cleanup)
        verificador = Mock(side_effect=("a" * 64, "b" * 64))

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_SEMGREP, codigo=0),
            **dependencias_controladas(verificar_regras=verificador),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("contaminada", manifesto.falha_tipo)
        self.assertTrue((fixture.saida / "bruto.json").is_file())
        self.assertFalse((fixture.saida / "normalizado.json").exists())

    def test_timeout_falha_sem_codigo_e_preserva_partes(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_BANDIT[:50], timeout=True),
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("timeout", manifesto.falha_tipo)
        self.assertIsNone(manifesto.codigo_saida)
        self.assertTrue((fixture.saida / "bruto.json").is_file())

    def test_json_invalido_falha_formato_apos_preservar_bruto(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)
        bruto = b'{"errors":[],"results":['

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(bruto, codigo=0),
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("formato", manifesto.falha_tipo)
        self.assertEqual(bruto, (fixture.saida / "bruto.json").read_bytes())

    def test_warning_parcial_vira_artefato_estruturado(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        def normalizador(bruto, proveniencia):
            warnings.warn(
                ResultadoParcialBanditWarning(
                    [{"filename": "quebrado.py"}], proveniencia.saida_bruta_sha256
                )
            )
            return []

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_BANDIT, codigo=0),
            normalizadores={"C1": normalizador, "C2": normalizador},
            **dependencias_controladas(),
        )

        avisos = json.loads((fixture.saida / "avisos.json").read_text())
        self.assertEqual("ResultadoParcialBanditWarning", avisos[0]["categoria"])
        self.assertEqual("quebrado.py", avisos[0]["erros"][0]["filename"])
        self.assertIn("avisos.json", manifesto.to_dict()["artefatos_sha256"])

    def test_metadados_e_brutos_existem_antes_da_normalizacao(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        def normalizador(bruto, proveniencia):
            for nome in (
                "manifesto.pendente.json",
                "manifesto.em_execucao.json",
                "versoes.json",
                "processo.json",
                "stdout.bin",
                "stderr.bin",
                "bruto.json",
            ):
                self.assertTrue((fixture.saida / nome).is_file(), nome)
            self.assertFalse(any(fixture.saida.glob("*.part")))
            return []

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_BANDIT, codigo=0),
            normalizadores={"C1": normalizador, "C2": normalizador},
            **dependencias_controladas(),
        )

        self.assertEqual("concluida", manifesto.estado)

    def test_scanner_nao_pode_apagar_metadado_preexistente(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)
        normalizador = Mock(side_effect=AssertionError("não deve normalizar"))

        def executor(comando, stdout, stderr, limite):
            stdout.write(b"stdout\n")
            stderr.write(b"stderr\n")
            Path(comando[comando.index("--output") + 1]).write_bytes(BRUTO_BANDIT)
            (fixture.saida / "versoes.json").unlink()
            return ResultadoProcesso(codigo_saida=0, timeout=False)

        manifesto = executar_sast(
            fixture.config,
            executar_processo=executor,
            normalizadores={"C1": normalizador, "C2": normalizador},
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("contaminada", manifesto.falha_tipo)
        self.assertEqual(0, manifesto.codigo_saida)
        normalizador.assert_not_called()

    def test_falha_interna_do_normalizador_ainda_fecha_manifesto(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        def normalizador(bruto, proveniencia):
            raise RuntimeError("falha controlada do adaptador")

        manifesto = executar_sast(
            fixture.config,
            executar_processo=runner_controlado(BRUTO_BANDIT, codigo=0),
            normalizadores={"C1": normalizador, "C2": normalizador},
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("interna", manifesto.falha_tipo)
        self.assertIn("RuntimeError", manifesto.falha_mensagem)
        self.assertTrue((fixture.saida / "manifesto.json").is_file())

    def test_hash_de_entrada_divergente_bloqueia_antes_do_processo(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)
        dados = fixture.config.to_dict()
        dados["entrada_sha256"] = "0" * 64
        config = ConfiguracaoExecucao(**dados)
        executor = Mock()

        manifesto = executar_sast(
            config,
            executar_processo=executor,
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("proveniencia", manifesto.falha_tipo)
        executor.assert_not_called()

    def test_mutacao_da_entrada_depois_do_scanner_marca_contaminada(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        def executor(comando, stdout, stderr, limite):
            stdout.write(b"stdout\n")
            stderr.write(b"stderr\n")
            Path(comando[comando.index("--output") + 1]).write_bytes(BRUTO_BANDIT)
            (fixture.entrada / "app.py").write_text("alterado = True\n", encoding="utf-8")
            return ResultadoProcesso(codigo_saida=0, timeout=False)

        manifesto = executar_sast(
            fixture.config,
            executar_processo=executor,
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("contaminada", manifesto.falha_tipo)
        self.assertEqual(0, manifesto.codigo_saida)
        self.assertTrue((fixture.saida / "bruto.json").is_file())

    def test_artefato_inesperado_falha_mas_manifesto_terminal_permanece(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)

        def executor(comando, stdout, stderr, limite):
            stdout.write(b"stdout\n")
            stderr.write(b"stderr\n")
            Path(comando[comando.index("--output") + 1]).write_bytes(BRUTO_BANDIT)
            (fixture.saida / "inesperado.txt").write_text("x", encoding="utf-8")
            return ResultadoProcesso(codigo_saida=0, timeout=False)

        manifesto = executar_sast(
            fixture.config,
            executar_processo=executor,
            **dependencias_controladas(),
        )

        self.assertEqual("falha", manifesto.estado)
        self.assertEqual("interna", manifesto.falha_tipo)
        self.assertTrue((fixture.saida / "manifesto.json").is_file())

    def test_regras_validam_manifesto_completo_antes_do_bundle(self):
        fixture = ExecucaoFixture("C2")
        self.addCleanup(fixture.cleanup)
        lock = {"sources": {"semgrep_rules": {"paths": ["python"]}}}

        with (
            patch("runner.executor_sast.carregar_json", return_value=lock),
            patch("runner.executor_sast.validar_manifesto") as validar,
            patch(
                "runner.executor_sast.verificar_bundle_regras",
                return_value="a" * 64,
            ) as verificar,
        ):
            observado = _verificar_regras(fixture.config)

        self.assertEqual("a" * 64, observado)
        validar.assert_called_once_with(lock)
        verificar.assert_called_once_with(
            fixture.regras, lock["sources"]["semgrep_rules"]
        )

    def test_saida_deve_ser_nova_vazia_e_sem_links(self):
        fixture = ExecucaoFixture("C1")
        self.addCleanup(fixture.cleanup)
        (fixture.saida / "existente.txt").write_text("não sobrescrever")

        with self.assertRaisesRegex(ErroExecucao, "vazi"):
            executar_sast(
                fixture.config,
                executar_processo=Mock(),
                **dependencias_controladas(),
            )


class ProcessoEAtomicidadeTest(unittest.TestCase):
    def test_interfaces_ignoram_arquivos_auxiliares_do_sysfs(self):
        with tempfile.TemporaryDirectory() as temporario:
            sysfs = Path(temporario)
            (sysfs / "lo").mkdir()
            (sysfs / "bonding_masters").write_text("", encoding="utf-8")

            self.assertEqual({"lo"}, _listar_interfaces_rede(sysfs))

    def test_processo_usa_vetor_sem_shell_e_nova_sessao(self):
        processo = Mock()
        processo.wait.return_value = 0
        popen = Mock(return_value=processo)
        stdout = Mock()
        stderr = Mock()

        resultado = _executar_processo(
            ("bandit", "--version"),
            stdout,
            stderr,
            10,
            popen_factory=popen,
        )

        self.assertEqual(ResultadoProcesso(codigo_saida=0, timeout=False), resultado)
        _, kwargs = popen.call_args
        self.assertTrue(kwargs["start_new_session"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual("/tmp", kwargs["cwd"])
        self.assertEqual("/usr/local/bin:/usr/bin:/bin", kwargs["env"]["PATH"])
        self.assertNotIn("PYTHONPATH", kwargs["env"])

    def test_timeout_encerra_grupo_com_term_e_kill(self):
        processo = Mock(pid=4321)
        processo.wait.side_effect = (
            subprocess.TimeoutExpired("scanner", 10),
            subprocess.TimeoutExpired("scanner", 5),
            -signal.SIGKILL,
        )
        popen = Mock(return_value=processo)

        with patch("runner.executor_sast.os.killpg") as killpg:
            resultado = _executar_processo(
                ("scanner",), Mock(), Mock(), 10, popen_factory=popen
            )

        self.assertEqual(ResultadoProcesso(codigo_saida=None, timeout=True), resultado)
        self.assertEqual(
            [(4321, signal.SIGTERM), (4321, signal.SIGKILL)],
            [chamada.args for chamada in killpg.call_args_list],
        )

    def test_timeout_tolera_grupo_que_encerra_antes_do_sinal(self):
        processo = Mock(pid=4321)
        processo.wait.side_effect = (
            subprocess.TimeoutExpired("scanner", 10),
            143,
        )
        popen = Mock(return_value=processo)

        with patch(
            "runner.executor_sast.os.killpg", side_effect=ProcessLookupError
        ):
            resultado = _executar_processo(
                ("/usr/local/bin/scanner",),
                Mock(),
                Mock(),
                10,
                popen_factory=popen,
            )

        self.assertEqual(ResultadoProcesso(codigo_saida=None, timeout=True), resultado)

    def test_escrita_atomica_nao_sobrescreve_destino(self):
        with tempfile.TemporaryDirectory() as temporario:
            destino = Path(temporario) / "evidencia.json"
            _escrever_bytes_atomico(destino, b"primeiro")
            with self.assertRaises(ErroExecucao):
                _escrever_bytes_atomico(destino, b"segundo")

            self.assertEqual(b"primeiro", destino.read_bytes())
            self.assertFalse((Path(temporario) / "evidencia.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
