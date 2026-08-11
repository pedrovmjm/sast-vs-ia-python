import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from jsonschema import Draft202012Validator

from runner.corpus import carregar_json
from runner.fila import (
    ErroFila,
    _mutex,
    claim,
    criar_fila_runtime,
    finalizar,
    inicializar,
    ler_validada,
    main,
    retomar_orfa,
    validar_fila_runtime,
)


RAIZ = Path(__file__).resolve().parents[1]
CONFIGURACAO = "a" * 64
T0 = "2026-08-11T12:00:00Z"
T1 = "2026-08-11T12:01:00Z"
T2 = "2026-08-11T12:02:00Z"
T3 = "2026-08-11T12:03:00Z"


class FilaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.estado = self.raiz / "fila.json"
        self.corpus = carregar_json(RAIZ / "config/corpus-realvuln-v1.lock.json")
        self.fila_lock = carregar_json(RAIZ / "config/fila-c1-c2.lock.json")

    def criar(self):
        return inicializar(
            self.estado, self.fila_lock, self.corpus, CONFIGURACAO, agora=T0
        )

    def reclamar(self):
        return claim(
            self.estado, self.fila_lock, self.corpus, CONFIGURACAO, agora=T1
        )

    def test_cria_52_pendentes_na_ordem_congelada(self):
        documento = self.criar()
        self.assertEqual(52, len(documento["itens"]))
        self.assertEqual(self.fila_lock["ordem"], [i["execucao_id"] for i in documento["itens"]])
        self.assertEqual({"pendente"}, {i["estado"] for i in documento["itens"]})
        self.assertTrue(all(i["tentativa"] == 0 for i in documento["itens"]))

    def test_documento_inicial_valida_no_schema_publicado(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        schema = carregar_json(RAIZ / "runner/schemas/fila-c1-c2-v1.schema.json")
        erros = list(Draft202012Validator(schema).iter_errors(documento))
        self.assertEqual([], [erro.message for erro in erros])

    def test_claim_reclama_primeiro_item_e_incrementa_revision(self):
        self.criar()
        recibo = self.reclamar()
        self.assertIsNotNone(recibo)
        self.assertEqual(self.fila_lock["ordem"][0], recibo["execucao_id"])
        self.assertEqual("em_execucao", recibo["estado"])
        self.assertEqual(1, recibo["tentativa"])
        self.assertEqual(1, ler_validada(self.estado, self.fila_lock, self.corpus, CONFIGURACAO)["revision"])

    def test_segundo_claim_e_recusado_enquanto_ha_ativo(self):
        self.criar()
        self.reclamar()
        with self.assertRaisesRegex(ErroFila, "ativa"):
            claim(self.estado, self.fila_lock, self.corpus, CONFIGURACAO, agora=T2)

    def test_finaliza_sucesso_com_manifesto_canonico(self):
        self.criar()
        recibo = self.reclamar()
        execucao_id = recibo["execucao_id"]
        manifesto = f"resultados/{execucao_id}/tentativa-001/manifesto.json"
        final = finalizar(
            self.estado,
            self.fila_lock,
            self.corpus,
            CONFIGURACAO,
            execucao_id,
            1,
            "concluida",
            manifesto,
            agora=T2,
        )
        self.assertEqual("concluida", final["estado"])
        self.assertIsNone(final["falha_tipo"])
        documento = ler_validada(self.estado, self.fila_lock, self.corpus, CONFIGURACAO)
        self.assertEqual(2, documento["revision"])
        self.assertEqual("concluida", documento["itens"][0]["historico"][0]["desfecho"])

    def test_finaliza_falha_com_tipo_explicito(self):
        self.criar()
        recibo = self.reclamar()
        execucao_id = recibo["execucao_id"]
        manifesto = f"resultados/{execucao_id}/tentativa-001/manifesto.json"
        final = finalizar(
            self.estado,
            self.fila_lock,
            self.corpus,
            CONFIGURACAO,
            execucao_id,
            1,
            "falha",
            manifesto,
            "timeout",
            T2,
        )
        self.assertEqual("falha", final["estado"])
        self.assertEqual("timeout", final["falha_tipo"])

    def test_falha_sem_tipo_e_recusada(self):
        self.criar()
        recibo = self.reclamar()
        caminho = f"resultados/{recibo['execucao_id']}/tentativa-001/manifesto.json"
        with self.assertRaisesRegex(ErroFila, "falha_tipo"):
            finalizar(
                self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
                recibo["execucao_id"], 1, "falha", caminho, agora=T2
            )

    def test_sucesso_com_tipo_de_falha_e_recusado(self):
        self.criar()
        recibo = self.reclamar()
        caminho = f"resultados/{recibo['execucao_id']}/tentativa-001/manifesto.json"
        with self.assertRaisesRegex(ErroFila, "não aceita"):
            finalizar(
                self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
                recibo["execucao_id"], 1, "concluida", caminho, "timeout", T2
            )

    def test_manifesto_de_outra_tentativa_e_recusado(self):
        self.criar()
        recibo = self.reclamar()
        errado = f"resultados/{recibo['execucao_id']}/tentativa-002/manifesto.json"
        with self.assertRaisesRegex(ErroFila, "canônico"):
            finalizar(
                self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
                recibo["execucao_id"], 1, "concluida", errado, agora=T2
            )

    def test_terminal_e_imutavel(self):
        self.criar()
        recibo = self.reclamar()
        caminho = f"resultados/{recibo['execucao_id']}/tentativa-001/manifesto.json"
        finalizar(
            self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
            recibo["execucao_id"], 1, "concluida", caminho, agora=T2
        )
        with self.assertRaisesRegex(ErroFila, "claim ativo"):
            finalizar(
                self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
                recibo["execucao_id"], 1, "concluida", caminho, agora=T3
            )

    def test_retomada_preserva_interrupcao_e_proxima_tentativa(self):
        self.criar()
        primeiro = self.reclamar()
        retomar_orfa(
            self.estado,
            self.fila_lock,
            self.corpus,
            CONFIGURACAO,
            primeiro["execucao_id"],
            1,
            agora=T2,
        )
        segundo = claim(
            self.estado, self.fila_lock, self.corpus, CONFIGURACAO, agora=T3
        )
        self.assertEqual(primeiro["execucao_id"], segundo["execucao_id"])
        self.assertEqual(2, segundo["tentativa"])
        documento = ler_validada(self.estado, self.fila_lock, self.corpus, CONFIGURACAO)
        historico = documento["itens"][0]["historico"]
        self.assertEqual("interrompida", historico[0]["desfecho"])
        self.assertIsNone(historico[0]["manifesto_relativo"])
        self.assertIsNone(historico[1]["desfecho"])

    def test_retomada_de_tentativa_errada_e_recusada(self):
        self.criar()
        recibo = self.reclamar()
        with self.assertRaisesRegex(ErroFila, "claim ativo"):
            retomar_orfa(
                self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
                recibo["execucao_id"], 2, agora=T2
            )

    def test_configuracao_divergente_bloqueia_leitura_e_mutacao(self):
        self.criar()
        with self.assertRaisesRegex(ErroFila, "configuração"):
            ler_validada(self.estado, self.fila_lock, self.corpus, "b" * 64)
        with self.assertRaisesRegex(ErroFila, "configuração"):
            claim(self.estado, self.fila_lock, self.corpus, "b" * 64, agora=T1)

    def test_inicializacao_nao_sobrescreve(self):
        self.criar()
        antes = self.estado.read_bytes()
        with self.assertRaisesRegex(ErroFila, "já existe"):
            self.criar()
        self.assertEqual(antes, self.estado.read_bytes())

    def test_mutex_exclusivo_recusa_operacao_concorrente(self):
        self.criar()
        with _mutex(self.estado):
            with self.assertRaisesRegex(ErroFila, "bloqueada"):
                self.reclamar()

    def test_recusa_link_simbolico_como_estado(self):
        alvo = self.raiz / "real.json"
        alvo.write_text("{}", encoding="utf-8")
        try:
            self.estado.symlink_to(alvo)
        except OSError:
            self.skipTest("plataforma não permite link simbólico")
        with self.assertRaisesRegex(ErroFila, "arquivo regular"):
            ler_validada(self.estado, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_json_com_chave_duplicada(self):
        self.estado.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf-8")
        with self.assertRaisesRegex(ErroFila, "duplicada"):
            claim(self.estado, self.fila_lock, self.corpus, CONFIGURACAO, agora=T1)

    def test_recusa_item_ausente_ou_extra(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        for alterado in (documento["itens"][:-1], documento["itens"] + [documento["itens"][0]]):
            copia = copy.deepcopy(documento)
            copia["itens"] = alterado
            with self.subTest(tamanho=len(alterado)), self.assertRaisesRegex(ErroFila, "52"):
                validar_fila_runtime(copia, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_ordem_adulterada(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        documento["itens"][0], documento["itens"][1] = documento["itens"][1], documento["itens"][0]
        with self.assertRaisesRegex(ErroFila, "ordem"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_campos_desconhecidos(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        documento["extra"] = True
        with self.assertRaisesRegex(ErroFila, "campos"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_duas_execucoes_ativas(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        for item in documento["itens"][:2]:
            item.update({"estado": "em_execucao", "tentativa": 1, "inicio_utc": T1})
            item["historico"] = [{
                "tentativa": 1, "inicio_utc": T1, "termino_utc": None,
                "desfecho": None, "manifesto_relativo": None, "falha_tipo": None,
            }]
        with self.assertRaisesRegex(ErroFila, "somente uma"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_tentativa_sem_historico(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        documento["itens"][0]["tentativa"] = 1
        with self.assertRaisesRegex(ErroFila, "histórico"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_timestamp_impossivel_ou_invertido(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        documento["atualizada_em"] = "2026-02-30T00:00:00Z"
        with self.assertRaisesRegex(ErroFila, "impossível"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)
        documento["atualizada_em"] = "2026-08-11T11:59:59Z"
        with self.assertRaisesRegex(ErroFila, "anterior"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_revision_adulterada(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        documento["revision"] = 1
        with self.assertRaisesRegex(ErroFila, "revision diverge"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_atualizacao_sem_evento(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        documento["atualizada_em"] = T1
        with self.assertRaisesRegex(ErroFila, "último evento"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_terminal_divergente_do_historico(self):
        self.criar()
        recibo = self.reclamar()
        caminho = f"resultados/{recibo['execucao_id']}/tentativa-001/manifesto.json"
        finalizar(
            self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
            recibo["execucao_id"], 1, "concluida", caminho, agora=T2
        )
        documento = carregar_json(self.estado)
        documento["itens"][0]["termino_utc"] = T3
        with self.assertRaisesRegex(ErroFila, "diverge dos dados"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_recusa_transicao_anterior_ao_estado_corrente(self):
        self.criar()
        self.reclamar()
        with self.assertRaisesRegex(ErroFila, "anterior à atualização"):
            retomar_orfa(
                self.estado, self.fila_lock, self.corpus, CONFIGURACAO,
                self.fila_lock["ordem"][0], 1, agora=T0
            )

    def test_recusa_nova_tentativa_anterior_a_interrupcao(self):
        documento = criar_fila_runtime(self.fila_lock, self.corpus, CONFIGURACAO, T0)
        item = documento["itens"][0]
        item.update({"estado": "em_execucao", "tentativa": 2, "inicio_utc": T1})
        item["historico"] = [
            {
                "tentativa": 1, "inicio_utc": T0, "termino_utc": T2,
                "desfecho": "interrompida", "manifesto_relativo": None,
                "falha_tipo": "interrompida",
            },
            {
                "tentativa": 2, "inicio_utc": T1, "termino_utc": None,
                "desfecho": None, "manifesto_relativo": None, "falha_tipo": None,
            },
        ]
        documento["revision"] = 3
        documento["atualizada_em"] = T2
        with self.assertRaisesRegex(ErroFila, "fora de ordem temporal"):
            validar_fila_runtime(documento, self.fila_lock, self.corpus, CONFIGURACAO)

    def test_cli_inicializa_valida_e_emite_json(self):
        estado = self.raiz / "cli.json"
        comuns = [
            "--estado", str(estado),
            "--fila-lock", str(RAIZ / "config/fila-c1-c2.lock.json"),
            "--corpus-lock", str(RAIZ / "config/corpus-realvuln-v1.lock.json"),
            "--configuracao-sha256", CONFIGURACAO,
        ]
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.assertEqual(0, main(comuns + ["inicializar"]))
        self.assertEqual(52, json.loads(saida.getvalue())["itens"])
        saida = io.StringIO()
        with redirect_stdout(saida):
            self.assertEqual(0, main(comuns + ["validar"]))
        self.assertEqual(0, json.loads(saida.getvalue())["revision"])

    def test_cli_retorna_dois_em_erro_sem_traceback(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            codigo = main(
                [
                    "--estado", str(self.estado),
                    "--fila-lock", str(RAIZ / "config/fila-c1-c2.lock.json"),
                    "--corpus-lock", str(RAIZ / "config/corpus-realvuln-v1.lock.json"),
                    "--configuracao-sha256", CONFIGURACAO,
                    "validar",
                ]
            )
        self.assertEqual(2, codigo)
        self.assertIn("erro de fila", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
