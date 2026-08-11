"""Fila C1/C2 persistente, estrita e retomável por tentativa."""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from runner.corpus import (
    ErroCorpus,
    carregar_json,
    hash_json_canonico,
    validar_lock_corpus,
    validar_lock_fila,
)


class ErroFila(ValueError):
    """Indica corrupção, deriva ou transição inválida da fila."""


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EXECUCAO_RE = re.compile(r"^(C[12])-(ALVO-[0-9]{4})-R01$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_ESTADOS = frozenset({"pendente", "em_execucao", "concluida", "falha"})
_DESFECHOS = frozenset({"concluida", "falha", "interrompida"})
_FALHAS = frozenset(
    {
        "proveniencia",
        "preflight",
        "timeout",
        "codigo_saida",
        "formato",
        "interrompida",
        "contaminada",
        "indisponibilidade",
        "interna",
    }
)
_CAMPOS_TOPO = frozenset(
    {
        "schema_version",
        "tipo",
        "fila_lock_sha256",
        "corpus_lock_sha256",
        "configuracao_sha256",
        "revision",
        "criada_em",
        "atualizada_em",
        "itens",
    }
)
_CAMPOS_ITEM = frozenset(
    {
        "execucao_id",
        "alvo",
        "condicao",
        "repeticao",
        "estado",
        "tentativa",
        "inicio_utc",
        "termino_utc",
        "manifesto_relativo",
        "falha_tipo",
        "historico",
    }
)
_CAMPOS_HISTORICO = frozenset(
    {
        "tentativa",
        "inicio_utc",
        "termino_utc",
        "desfecho",
        "manifesto_relativo",
        "falha_tipo",
    }
)


def criar_fila_runtime(
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
    agora: str,
) -> dict[str, Any]:
    fila = validar_lock_fila(fila_lock, corpus_lock)
    _sha256(configuracao_sha256, "configuracao_sha256")
    _timestamp(agora, "agora")
    itens = []
    for execucao_id in fila["ordem"]:
        correspondencia = _EXECUCAO_RE.fullmatch(execucao_id)
        assert correspondencia is not None
        itens.append(
            {
                "execucao_id": execucao_id,
                "alvo": correspondencia.group(2),
                "condicao": correspondencia.group(1),
                "repeticao": 1,
                "estado": "pendente",
                "tentativa": 0,
                "inicio_utc": None,
                "termino_utc": None,
                "manifesto_relativo": None,
                "falha_tipo": None,
                "historico": [],
            }
        )
    documento = {
        "schema_version": "1.0",
        "tipo": "fila-c1-c2-runtime",
        "fila_lock_sha256": hash_json_canonico(fila),
        "corpus_lock_sha256": hash_json_canonico(validar_lock_corpus(corpus_lock)),
        "configuracao_sha256": configuracao_sha256,
        "revision": 0,
        "criada_em": agora,
        "atualizada_em": agora,
        "itens": itens,
    }
    return dict(validar_fila_runtime(documento, fila_lock, corpus_lock, configuracao_sha256))


def validar_fila_runtime(
    documento: Mapping[str, Any],
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
) -> Mapping[str, Any]:
    runtime = _objeto(documento, "fila runtime")
    _chaves(runtime, _CAMPOS_TOPO, "fila runtime")
    fila = validar_lock_fila(fila_lock, corpus_lock)
    corpus = validar_lock_corpus(corpus_lock)
    _sha256(configuracao_sha256, "configuracao_sha256 esperado")
    if runtime["schema_version"] != "1.0" or runtime["tipo"] != "fila-c1-c2-runtime":
        raise ErroFila("identidade da fila runtime inválida")
    if runtime["fila_lock_sha256"] != hash_json_canonico(fila):
        raise ErroFila("hash do lock da fila diverge")
    if runtime["corpus_lock_sha256"] != hash_json_canonico(corpus):
        raise ErroFila("hash do lock do corpus diverge")
    if runtime["configuracao_sha256"] != configuracao_sha256:
        raise ErroFila("hash da configuração congelada diverge")
    revision = runtime["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ErroFila("revision deve ser inteiro não negativo")
    criada = _timestamp(runtime["criada_em"], "criada_em")
    atualizada = _timestamp(runtime["atualizada_em"], "atualizada_em")
    if atualizada < criada:
        raise ErroFila("atualizada_em anterior a criada_em")
    itens = runtime["itens"]
    if not isinstance(itens, list) or len(itens) != 52:
        raise ErroFila("fila runtime deve conter exatamente 52 itens")
    if [item.get("execucao_id") if isinstance(item, Mapping) else None for item in itens] != fila["ordem"]:
        raise ErroFila("ordem ou conjunto da fila runtime diverge do lock")
    ativos = 0
    revision_esperada = 0
    ultimo_evento = criada
    for indice, valor in enumerate(itens):
        item = _objeto(valor, f"itens[{indice}]")
        _chaves(item, _CAMPOS_ITEM, f"itens[{indice}]")
        correspondencia = _EXECUCAO_RE.fullmatch(str(item["execucao_id"]))
        if correspondencia is None:
            raise ErroFila(f"execucao_id inválido em itens[{indice}]")
        if (
            item["alvo"] != correspondencia.group(2)
            or item["condicao"] != correspondencia.group(1)
            or item["repeticao"] != 1
            or isinstance(item["repeticao"], bool)
        ):
            raise ErroFila(f"identidade incoerente em {item['execucao_id']}")
        estado = item["estado"]
        if estado not in _ESTADOS:
            raise ErroFila(f"estado inválido em {item['execucao_id']}")
        tentativa = item["tentativa"]
        if (
            not isinstance(tentativa, int)
            or isinstance(tentativa, bool)
            or tentativa < 0
            or tentativa > 999
        ):
            raise ErroFila(f"tentativa inválida em {item['execucao_id']}")
        historico = item["historico"]
        if not isinstance(historico, list) or len(historico) != tentativa:
            raise ErroFila(f"histórico diverge da tentativa em {item['execucao_id']}")
        termino_anterior = criada
        for numero, entrada in enumerate(historico, 1):
            _validar_historico(entrada, numero, item["execucao_id"])
            inicio_historico = _timestamp(
                entrada["inicio_utc"], "inicio_utc histórico"
            )
            if inicio_historico < termino_anterior:
                raise ErroFila(
                    f"histórico fora de ordem temporal em {item['execucao_id']}"
                )
            revision_esperada += 1
            ultimo_evento = max(ultimo_evento, inicio_historico)
            if entrada["desfecho"] is not None:
                revision_esperada += 1
                termino_anterior = _timestamp(
                    entrada["termino_utc"], "termino_utc histórico"
                )
                ultimo_evento = max(ultimo_evento, termino_anterior)
        _validar_estado_item(item)
        if estado == "em_execucao":
            ativos += 1
    if ativos > 1:
        raise ErroFila("somente uma execução pode estar ativa")
    if revision != revision_esperada:
        raise ErroFila("revision diverge do histórico de transições")
    if atualizada != ultimo_evento:
        raise ErroFila("atualizada_em diverge do último evento")
    return runtime


def inicializar(
    caminho: str | Path,
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
    agora: str | None = None,
) -> dict[str, Any]:
    destino = Path(caminho)
    instante = agora or _agora_utc()
    documento = criar_fila_runtime(fila_lock, corpus_lock, configuracao_sha256, instante)
    with _mutex(destino):
        if destino.exists() or destino.is_symlink():
            raise ErroFila(f"fila já existe: {destino}")
        _salvar_atomico(destino, documento, conteudo_anterior=None)
    return documento


def claim(
    caminho: str | Path,
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
    agora: str | None = None,
) -> dict[str, Any] | None:
    instante = agora or _agora_utc()

    def alterar(documento: dict[str, Any]) -> dict[str, Any] | None:
        if any(item["estado"] == "em_execucao" for item in documento["itens"]):
            raise ErroFila("fila já possui execução ativa")
        item = next((item for item in documento["itens"] if item["estado"] == "pendente"), None)
        if item is None:
            return None
        tentativa = item["tentativa"] + 1
        item.update(
            {
                "estado": "em_execucao",
                "tentativa": tentativa,
                "inicio_utc": instante,
                "termino_utc": None,
                "manifesto_relativo": None,
                "falha_tipo": None,
            }
        )
        item["historico"].append(
            {
                "tentativa": tentativa,
                "inicio_utc": instante,
                "termino_utc": None,
                "desfecho": None,
                "manifesto_relativo": None,
                "falha_tipo": None,
            }
        )
        return _recibo(item)

    return _mutar(caminho, fila_lock, corpus_lock, configuracao_sha256, instante, alterar)


def finalizar(
    caminho: str | Path,
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
    execucao_id: str,
    tentativa: int,
    estado: str,
    manifesto_relativo: str,
    falha_tipo: str | None = None,
    agora: str | None = None,
) -> dict[str, Any]:
    if estado not in {"concluida", "falha"}:
        raise ErroFila("finalização exige estado concluida ou falha")
    _manifesto(manifesto_relativo, execucao_id, tentativa)
    if estado == "concluida" and falha_tipo is not None:
        raise ErroFila("conclusão não aceita falha_tipo")
    if estado == "falha" and falha_tipo not in _FALHAS:
        raise ErroFila("falha exige falha_tipo válido")
    instante = agora or _agora_utc()

    def alterar(documento: dict[str, Any]) -> dict[str, Any]:
        item = _localizar_ativo(documento, execucao_id, tentativa)
        if _timestamp(instante, "agora") < _timestamp(item["inicio_utc"], "inicio_utc"):
            raise ErroFila("término anterior ao início")
        item.update(
            {
                "estado": estado,
                "termino_utc": instante,
                "manifesto_relativo": manifesto_relativo,
                "falha_tipo": falha_tipo,
            }
        )
        item["historico"][-1].update(
            {
                "termino_utc": instante,
                "desfecho": estado,
                "manifesto_relativo": manifesto_relativo,
                "falha_tipo": falha_tipo,
            }
        )
        return _recibo(item)

    resultado = _mutar(
        caminho, fila_lock, corpus_lock, configuracao_sha256, instante, alterar
    )
    assert resultado is not None
    return resultado


def retomar_orfa(
    caminho: str | Path,
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
    execucao_id: str,
    tentativa: int,
    agora: str | None = None,
) -> dict[str, Any]:
    instante = agora or _agora_utc()

    def alterar(documento: dict[str, Any]) -> dict[str, Any]:
        item = _localizar_ativo(documento, execucao_id, tentativa)
        if _timestamp(instante, "agora") < _timestamp(item["inicio_utc"], "inicio_utc"):
            raise ErroFila("retomada anterior ao início")
        item["historico"][-1].update(
            {
                "termino_utc": instante,
                "desfecho": "interrompida",
                "manifesto_relativo": None,
                "falha_tipo": "interrompida",
            }
        )
        item.update(
            {
                "estado": "pendente",
                "inicio_utc": None,
                "termino_utc": None,
                "manifesto_relativo": None,
                "falha_tipo": None,
            }
        )
        return _recibo(item)

    resultado = _mutar(
        caminho, fila_lock, corpus_lock, configuracao_sha256, instante, alterar
    )
    assert resultado is not None
    return resultado


def reabrir_falha(
    caminho: str | Path,
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
    execucao_id: str,
    agora: str | None = None,
) -> dict[str, Any]:
    """Reabre explicitamente uma falha terminal para uma nova tentativa."""
    instante = agora or _agora_utc()

    def alterar(documento: dict[str, Any]) -> dict[str, Any]:
        item = next((x for x in documento["itens"] if x["execucao_id"] == execucao_id), None)
        if item is None:
            raise ErroFila(f"execucao inexistente: {execucao_id}")
        if item["estado"] != "falha":
            raise ErroFila("somente falha terminal pode ser reaberta")
        item.update({"estado": "pendente", "inicio_utc": None, "termino_utc": None,
                     "manifesto_relativo": None, "falha_tipo": None})
        return _recibo(item)

    resultado = _mutar(caminho, fila_lock, corpus_lock, configuracao_sha256, instante, alterar)
    assert resultado is not None
    return resultado


def ler_validada(
    caminho: str | Path,
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    configuracao_sha256: str,
) -> dict[str, Any]:
    try:
        documento = carregar_json(caminho)
        validar_fila_runtime(documento, fila_lock, corpus_lock, configuracao_sha256)
        return dict(documento)
    except ErroCorpus as exc:
        raise ErroFila(str(exc)) from exc


def _mutar(caminho, fila_lock, corpus_lock, configuracao_sha256, instante, alterar):
    destino = Path(caminho)
    _timestamp(instante, "agora")
    with _mutex(destino):
        anterior_bytes = _ler_bytes_regulares(destino)
        try:
            documento = json.loads(
                anterior_bytes.decode("utf-8"),
                object_pairs_hook=_objeto_sem_duplicatas,
                parse_constant=_constante_invalida,
            )
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ErroFila(f"fila contém JSON inválido: {exc}") from exc
        validar_fila_runtime(documento, fila_lock, corpus_lock, configuracao_sha256)
        if _timestamp(instante, "agora") < _timestamp(
            documento["atualizada_em"], "atualizada_em"
        ):
            raise ErroFila("transição anterior à atualização corrente")
        novo = copy.deepcopy(documento)
        resultado = alterar(novo)
        if resultado is None:
            return None
        novo["revision"] += 1
        novo["atualizada_em"] = instante
        validar_fila_runtime(novo, fila_lock, corpus_lock, configuracao_sha256)
        _salvar_atomico(destino, novo, conteudo_anterior=anterior_bytes)
        return resultado


def _validar_historico(valor, numero, execucao_id):
    entrada = _objeto(valor, f"histórico de {execucao_id}")
    _chaves(entrada, _CAMPOS_HISTORICO, f"histórico de {execucao_id}")
    if entrada["tentativa"] != numero:
        raise ErroFila(f"numeração do histórico diverge em {execucao_id}")
    inicio = _timestamp(entrada["inicio_utc"], "inicio_utc histórico")
    desfecho = entrada["desfecho"]
    if desfecho is None:
        if any(
            entrada[campo] is not None
            for campo in ("termino_utc", "manifesto_relativo", "falha_tipo")
        ):
            raise ErroFila(f"tentativa aberta incoerente em {execucao_id}")
        return
    if desfecho not in _DESFECHOS:
        raise ErroFila(f"desfecho inválido em {execucao_id}")
    termino = _timestamp(entrada["termino_utc"], "termino_utc histórico")
    if termino < inicio:
        raise ErroFila(f"histórico com tempo invertido em {execucao_id}")
    if desfecho == "interrompida":
        if entrada["manifesto_relativo"] is not None or entrada["falha_tipo"] != "interrompida":
            raise ErroFila(f"interrupção incoerente em {execucao_id}")
    else:
        _manifesto(entrada["manifesto_relativo"], execucao_id, numero)
        if desfecho == "concluida" and entrada["falha_tipo"] is not None:
            raise ErroFila(f"conclusão histórica contém falha em {execucao_id}")
        if desfecho == "falha" and entrada["falha_tipo"] not in _FALHAS:
            raise ErroFila(f"falha histórica inválida em {execucao_id}")


def _validar_estado_item(item):
    estado = item["estado"]
    historico = item["historico"]
    if estado == "pendente":
        if any(item[campo] is not None for campo in ("inicio_utc", "termino_utc", "manifesto_relativo", "falha_tipo")):
            raise ErroFila(f"pendente contém dados ativos em {item['execucao_id']}")
        if historico and historico[-1]["desfecho"] != "interrompida":
            raise ErroFila(f"pendente possui histórico terminal em {item['execucao_id']}")
    elif estado == "em_execucao":
        _timestamp(item["inicio_utc"], "inicio_utc")
        if any(item[campo] is not None for campo in ("termino_utc", "manifesto_relativo", "falha_tipo")):
            raise ErroFila(f"execução ativa contém resultado em {item['execucao_id']}")
        if not historico or historico[-1]["desfecho"] is not None:
            raise ErroFila(f"execução ativa sem tentativa aberta em {item['execucao_id']}")
        if item["inicio_utc"] != historico[-1]["inicio_utc"]:
            raise ErroFila(f"início ativo diverge do histórico em {item['execucao_id']}")
    else:
        _timestamp(item["inicio_utc"], "inicio_utc")
        _timestamp(item["termino_utc"], "termino_utc")
        if not historico or historico[-1]["desfecho"] != estado:
            raise ErroFila(f"terminal diverge do histórico em {item['execucao_id']}")
        if any(
            item[campo] != historico[-1][campo]
            for campo in ("inicio_utc", "termino_utc", "manifesto_relativo", "falha_tipo")
        ):
            raise ErroFila(f"terminal diverge dos dados da tentativa em {item['execucao_id']}")
        _manifesto(item["manifesto_relativo"], item["execucao_id"], item["tentativa"])
        if estado == "concluida" and item["falha_tipo"] is not None:
            raise ErroFila(f"conclusão contém falha em {item['execucao_id']}")
        if estado == "falha" and item["falha_tipo"] not in _FALHAS:
            raise ErroFila(f"falha terminal inválida em {item['execucao_id']}")


def _localizar_ativo(documento, execucao_id, tentativa):
    itens = [item for item in documento["itens"] if item["execucao_id"] == execucao_id]
    if len(itens) != 1:
        raise ErroFila(f"execução desconhecida: {execucao_id}")
    item = itens[0]
    if item["estado"] != "em_execucao" or item["tentativa"] != tentativa:
        raise ErroFila("execução/tentativa não corresponde ao claim ativo")
    return item


def _recibo(item):
    return {
        "execucao_id": item["execucao_id"],
        "alvo": item["alvo"],
        "condicao": item["condicao"],
        "repeticao": item["repeticao"],
        "estado": item["estado"],
        "tentativa": item["tentativa"],
        "inicio_utc": item["inicio_utc"],
        "termino_utc": item["termino_utc"],
        "manifesto_relativo": item["manifesto_relativo"],
        "falha_tipo": item["falha_tipo"],
    }


def _manifesto(valor, execucao_id, tentativa):
    esperado = f"resultados/{execucao_id}/tentativa-{tentativa:03d}/manifesto.json"
    if valor != esperado:
        raise ErroFila(f"manifesto deve usar caminho canônico: {esperado}")


def _timestamp(valor, campo):
    if not isinstance(valor, str) or not _UTC_RE.fullmatch(valor):
        raise ErroFila(f"{campo} deve ser timestamp UTC canônico")
    try:
        return datetime.fromisoformat(valor.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ErroFila(f"{campo} contém data impossível") from exc


def _agora_utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(valor, campo):
    if not isinstance(valor, str) or not _SHA256_RE.fullmatch(valor):
        raise ErroFila(f"{campo} deve ser SHA-256 completo")


def _objeto(valor, campo):
    if not isinstance(valor, Mapping):
        raise ErroFila(f"{campo} deve ser objeto")
    return valor


def _chaves(objeto, esperadas, campo):
    atuais = set(objeto)
    if atuais != esperadas:
        raise ErroFila(
            f"campos inválidos em {campo}; ausentes={sorted(esperadas - atuais)}, "
            f"desconhecidos={sorted(atuais - esperadas)}"
        )


def _objeto_sem_duplicatas(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroFila(f"chave JSON duplicada: {chave}")
        objeto[chave] = valor
    return objeto


def _constante_invalida(valor):
    raise ErroFila(f"constante JSON não finita proibida: {valor}")


def _ler_bytes_regulares(caminho):
    if caminho.is_symlink() or not caminho.is_file():
        raise ErroFila(f"fila deve ser arquivo regular: {caminho}")
    try:
        return caminho.read_bytes()
    except OSError as exc:
        raise ErroFila(f"não foi possível ler fila: {exc}") from exc


def _salvar_atomico(caminho, documento, conteudo_anterior):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(f".{caminho.name}.{uuid.uuid4().hex}.tmp")
    try:
        if conteudo_anterior is not None and _ler_bytes_regulares(caminho) != conteudo_anterior:
            raise ErroFila("fila foi alterada externamente durante a transição")
        dados = (
            json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
        with temporario.open("xb") as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        if conteudo_anterior is None:
            try:
                os.link(temporario, caminho)
            except FileExistsError as exc:
                raise ErroFila(f"fila já existe: {caminho}") from exc
            temporario.unlink()
        else:
            os.replace(temporario, caminho)
        _fsync_diretorio(caminho.parent)
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


def _fsync_diretorio(caminho):
    if os.name == "nt":
        return
    descritor = os.open(caminho, os.O_RDONLY)
    try:
        os.fsync(descritor)
    finally:
        os.close(descritor)


@contextlib.contextmanager
def _mutex(caminho: Path) -> Iterator[None]:
    lock = caminho.with_name(f".{caminho.name}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as arquivo:
        arquivo.seek(0, os.SEEK_END)
        if arquivo.tell() == 0:
            arquivo.write(b"0")
            arquivo.flush()
        arquivo.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ErroFila("fila está bloqueada por outro processo") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estado", required=True)
    parser.add_argument("--fila-lock", required=True)
    parser.add_argument("--corpus-lock", required=True)
    parser.add_argument("--configuracao-sha256", required=True)
    subparsers = parser.add_subparsers(dest="comando", required=True)
    subparsers.add_parser("inicializar")
    subparsers.add_parser("validar")
    subparsers.add_parser("claim")
    finalizar_parser = subparsers.add_parser("finalizar")
    finalizar_parser.add_argument("--execucao-id", required=True)
    finalizar_parser.add_argument("--tentativa", required=True, type=int)
    finalizar_parser.add_argument("--resultado", choices=("concluida", "falha"), required=True)
    finalizar_parser.add_argument("--manifesto-relativo", required=True)
    finalizar_parser.add_argument("--falha-tipo", choices=sorted(_FALHAS))
    retomar_parser = subparsers.add_parser("retomar-orfa")
    retomar_parser.add_argument("--execucao-id", required=True)
    retomar_parser.add_argument("--tentativa", required=True, type=int)
    reabrir_parser = subparsers.add_parser("reabrir-falha")
    reabrir_parser.add_argument("--execucao-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    try:
        fila_lock = carregar_json(argumentos.fila_lock)
        corpus_lock = carregar_json(argumentos.corpus_lock)
        comuns = (argumentos.estado, fila_lock, corpus_lock, argumentos.configuracao_sha256)
        if argumentos.comando == "inicializar":
            resultado = inicializar(*comuns)
            saida = {"revision": resultado["revision"], "itens": len(resultado["itens"])}
        elif argumentos.comando == "validar":
            resultado = ler_validada(*comuns)
            saida = {"revision": resultado["revision"], "itens": len(resultado["itens"])}
        elif argumentos.comando == "claim":
            saida = claim(*comuns)
        elif argumentos.comando == "finalizar":
            saida = finalizar(
                *comuns,
                argumentos.execucao_id,
                argumentos.tentativa,
                argumentos.resultado,
                argumentos.manifesto_relativo,
                argumentos.falha_tipo,
            )
        elif argumentos.comando == "retomar-orfa":
            saida = retomar_orfa(
                *comuns, argumentos.execucao_id, argumentos.tentativa
            )
        else:
            saida = reabrir_falha(*comuns, argumentos.execucao_id)
        print(json.dumps(saida, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except (ErroFila, ErroCorpus, OSError, ValueError) as exc:
        print(f"erro de fila: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
