"""Contratos congelados do corpus RealVuln v1 e da fila C1/C2."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit


class ErroCorpus(ValueError):
    """Indica lock, política ou fila incompatível com o protocolo M2."""


REALVULN_URL = "https://github.com/kolega-ai/Real-Vuln-Benchmark.git"
REALVULN_TAG = "v1.0"
REALVULN_TAG_OBJECT = "aa9f7321c8c53fe417b8faa517f1c4308b69b389"
REALVULN_COMMIT = "d98e9fc91273702c9547663b6906d1fc494d4fcc"
BENCHMARK_VERSION = "1.0.0"
QUANTIDADE_ALVOS = 26
QUANTIDADE_EXECUCOES = 52
POLITICA_ID = "sanitizacao-v1"
ALGORITMO_ORDEM = "sha256-ranking-v1"
DOMINIO_ORDEM = b"fila-c1-c2-v1\0"

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALVO_RE = re.compile(r"^ALVO-[0-9]{4}$")
_REPO_ID_RE = re.compile(r"^realvuln-[a-z0-9][a-z0-9-]*$")
_EXECUCAO_RE = re.compile(r"^C[12]-ALVO-[0-9]{4}-R01$")

_CAMPOS_POLITICA = frozenset(
    {
        "schema_version",
        "politica_id",
        "segmentos_excluidos",
        "arquivos_excluidos",
        "sufixos_excluidos",
        "modos_git_permitidos",
    }
)
_CAMPOS_CORPUS = frozenset(
    {
        "schema_version",
        "realvuln",
        "politica_sanitizacao",
        "quantidade_alvos",
        "alvos",
    }
)
_CAMPOS_REALVULN = frozenset(
    {
        "url",
        "tag",
        "tag_object",
        "commit",
        "benchmark_version",
        "manifesto_sha256",
        "ground_truth_content_identifier",
    }
)
_CAMPOS_ALVO = frozenset({"alvo", "realvuln_id", "url", "commit"})
_CAMPOS_FILA = frozenset(
    {
        "schema_version",
        "algoritmo_ordem",
        "semente",
        "corpus_lock_sha256",
        "quantidade_execucoes",
        "ordem",
    }
)


def carregar_json(caminho: str | Path) -> dict[str, Any]:
    """Lê JSON UTF-8 estrito, recusando duplicatas e constantes não finitas."""

    path = Path(caminho)
    if path.is_symlink() or not path.is_file():
        raise ErroCorpus(f"JSON deve ser arquivo regular: {path}")
    try:
        texto = path.read_text(encoding="utf-8")
        documento = json.loads(
            texto,
            object_pairs_hook=_objeto_sem_duplicatas,
            parse_constant=_constante_invalida,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ErroCorpus(f"JSON inválido em {path}: {exc}") from exc
    return _objeto(documento, str(path))


def validar_politica(documento: Mapping[str, Any]) -> Mapping[str, Any]:
    politica = _objeto(documento, "política")
    _chaves(politica, _CAMPOS_POLITICA, "política")
    if politica["schema_version"] != "1.0":
        raise ErroCorpus("schema_version da política deve ser 1.0")
    if politica["politica_id"] != POLITICA_ID:
        raise ErroCorpus(f"politica_id deve ser {POLITICA_ID}")
    segmentos = _lista_textos_unicos(
        politica["segmentos_excluidos"], "segmentos_excluidos"
    )
    arquivos = _lista_textos_unicos(
        politica["arquivos_excluidos"], "arquivos_excluidos"
    )
    sufixos = _lista_textos_unicos(
        politica["sufixos_excluidos"], "sufixos_excluidos"
    )
    modos = _lista_textos_unicos(
        politica["modos_git_permitidos"], "modos_git_permitidos"
    )
    for nome, valores in (
        ("segmentos_excluidos", segmentos),
        ("arquivos_excluidos", arquivos),
        ("sufixos_excluidos", sufixos),
    ):
        if list(valores) != sorted(valores, key=lambda item: item.encode("utf-8")):
            raise ErroCorpus(f"{nome} deve usar ordem UTF-8 canônica")
        if any(valor != valor.casefold() for valor in valores):
            raise ErroCorpus(f"{nome} deve conter somente valores casefold")
    if modos != ("100644", "100755"):
        raise ErroCorpus("modos Git permitidos devem ser exatamente 100644 e 100755")
    obrigatorios = {".git", "ground-truth", "oracle", "__pycache__"}
    if not obrigatorios.issubset(segmentos):
        raise ErroCorpus("política omite segmento de segurança obrigatório")
    if ".gitmodules" not in arquivos:
        raise ErroCorpus("política deve excluir .gitmodules")
    if not {".pyc", ".pyo"}.issubset(sufixos):
        raise ErroCorpus("política deve excluir bytecode Python")
    return politica


def validar_lock_corpus(documento: Mapping[str, Any]) -> Mapping[str, Any]:
    lock = _objeto(documento, "lock do corpus")
    _chaves(lock, _CAMPOS_CORPUS, "lock do corpus")
    if lock["schema_version"] != "1.0":
        raise ErroCorpus("schema_version do corpus deve ser 1.0")
    if lock["politica_sanitizacao"] != POLITICA_ID:
        raise ErroCorpus("lock referencia política de sanitização inesperada")
    if lock["quantidade_alvos"] != QUANTIDADE_ALVOS:
        raise ErroCorpus("quantidade_alvos deve ser 26")

    realvuln = _objeto(lock["realvuln"], "realvuln")
    _chaves(realvuln, _CAMPOS_REALVULN, "realvuln")
    esperados = {
        "url": REALVULN_URL,
        "tag": REALVULN_TAG,
        "tag_object": REALVULN_TAG_OBJECT,
        "commit": REALVULN_COMMIT,
        "benchmark_version": BENCHMARK_VERSION,
        "ground_truth_content_identifier": "sha256:a57347fbdf2a",
    }
    for campo, esperado in esperados.items():
        if realvuln[campo] != esperado:
            raise ErroCorpus(f"realvuln.{campo} diverge do release aprovado")
    _https_exata(realvuln["url"], REALVULN_URL, "realvuln.url")
    _sha256(realvuln["manifesto_sha256"], "realvuln.manifesto_sha256")

    alvos = lock["alvos"]
    if not isinstance(alvos, list) or len(alvos) != QUANTIDADE_ALVOS:
        raise ErroCorpus("alvos deve conter exatamente 26 objetos")
    ids: set[str] = set()
    repos: set[str] = set()
    urls: set[str] = set()
    commits: set[str] = set()
    repos_ordenados: list[str] = []
    for indice, item in enumerate(alvos, 1):
        alvo = _objeto(item, f"alvos[{indice - 1}]")
        _chaves(alvo, _CAMPOS_ALVO, f"alvos[{indice - 1}]")
        id_esperado = f"ALVO-{indice:04d}"
        if alvo["alvo"] != id_esperado or not _ALVO_RE.fullmatch(alvo["alvo"]):
            raise ErroCorpus(f"ID opaco deve ser {id_esperado}")
        repo_id = alvo["realvuln_id"]
        if not isinstance(repo_id, str) or not _REPO_ID_RE.fullmatch(repo_id):
            raise ErroCorpus(f"realvuln_id inválido em {id_esperado}")
        _https(alvo["url"], f"URL de {id_esperado}")
        _commit(alvo["commit"], f"commit de {id_esperado}")
        ids.add(alvo["alvo"])
        repos.add(repo_id)
        urls.add(alvo["url"])
        commits.add(alvo["commit"])
        repos_ordenados.append(repo_id)
    if len(ids) != 26 or len(repos) != 26 or len(urls) != 26 or len(commits) != 26:
        raise ErroCorpus("IDs, repos, URLs e commits do corpus devem ser únicos")
    if repos_ordenados != sorted(repos_ordenados, key=lambda item: item.encode("utf-8")):
        raise ErroCorpus("alvos devem ser ordenados por realvuln_id UTF-8")
    return lock


def hash_json_canonico(documento: Mapping[str, Any]) -> str:
    """Calcula SHA-256 da representação JSON canônica independente de whitespace."""

    try:
        dados = json.dumps(
            documento,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ErroCorpus(f"documento não serializável: {exc}") from exc
    return hashlib.sha256(dados).hexdigest()


def criar_ordem_fila(lock_corpus: Mapping[str, Any], semente: str) -> list[str]:
    """Deriva a permutação C1/C2 por ranking SHA-256 publicado."""

    corpus = validar_lock_corpus(lock_corpus)
    if (
        not isinstance(semente, str)
        or not semente
        or len(semente.encode("utf-8")) > 200
        or "\x00" in semente
    ):
        raise ErroCorpus("semente deve ser texto UTF-8 não vazio, sem NUL, até 200 bytes")
    ids = [
        f"{condicao}-{alvo['alvo']}-R01"
        for alvo in corpus["alvos"]
        for condicao in ("C1", "C2")
    ]
    seed = semente.encode("utf-8")

    def chave(execucao_id: str) -> tuple[bytes, bytes]:
        identificador = execucao_id.encode("utf-8")
        digest = hashlib.sha256(DOMINIO_ORDEM + seed + b"\0" + identificador).digest()
        return digest, identificador

    return sorted(ids, key=chave)


def validar_lock_fila(
    documento: Mapping[str, Any], lock_corpus: Mapping[str, Any]
) -> Mapping[str, Any]:
    fila = _objeto(documento, "lock da fila")
    _chaves(fila, _CAMPOS_FILA, "lock da fila")
    if fila["schema_version"] != "1.0":
        raise ErroCorpus("schema_version da fila deve ser 1.0")
    if fila["algoritmo_ordem"] != ALGORITMO_ORDEM:
        raise ErroCorpus(f"algoritmo_ordem deve ser {ALGORITMO_ORDEM}")
    if fila["quantidade_execucoes"] != QUANTIDADE_EXECUCOES:
        raise ErroCorpus("quantidade_execucoes deve ser 52")
    _sha256(fila["corpus_lock_sha256"], "corpus_lock_sha256")
    esperado_corpus = hash_json_canonico(validar_lock_corpus(lock_corpus))
    if fila["corpus_lock_sha256"] != esperado_corpus:
        raise ErroCorpus("fila referencia hash canônico divergente do corpus")
    ordem = fila["ordem"]
    if not isinstance(ordem, list) or len(ordem) != 52:
        raise ErroCorpus("ordem deve conter exatamente 52 execuções")
    if any(not isinstance(item, str) or not _EXECUCAO_RE.fullmatch(item) for item in ordem):
        raise ErroCorpus("ordem contém execucao_id inválido")
    if len(set(ordem)) != 52:
        raise ErroCorpus("ordem contém execução duplicada")
    esperada = criar_ordem_fila(lock_corpus, fila["semente"])
    if ordem != esperada:
        raise ErroCorpus("ordem não corresponde ao ranking SHA-256 congelado")
    return fila


def caminho_excluido(caminho_relativo: str, politica: Mapping[str, Any]) -> bool:
    """Decide exclusão apenas pelo caminho POSIX e pela política validada."""

    documento = validar_politica(politica)
    if (
        not isinstance(caminho_relativo, str)
        or not caminho_relativo
        or caminho_relativo.startswith("/")
        or "\\" in caminho_relativo
        or "\x00" in caminho_relativo
    ):
        raise ErroCorpus("caminho relativo deve ser POSIX seguro")
    partes = caminho_relativo.split("/")
    if any(parte in {"", ".", ".."} for parte in partes):
        raise ErroCorpus("caminho relativo contém segmento inseguro")
    normalizadas = [parte.casefold() for parte in partes]
    if any(parte in documento["segmentos_excluidos"] for parte in normalizadas):
        return True
    nome = normalizadas[-1]
    if nome in documento["arquivos_excluidos"]:
        return True
    return any(nome.endswith(sufixo) for sufixo in documento["sufixos_excluidos"])


def _https(valor: Any, campo: str) -> str:
    if not isinstance(valor, str):
        raise ErroCorpus(f"{campo} deve ser URL HTTPS")
    partes = urlsplit(valor)
    try:
        porta = partes.port
    except ValueError as exc:
        raise ErroCorpus(f"{campo} contém porta inválida") from exc
    if (
        partes.scheme != "https"
        or not partes.hostname
        or partes.username
        or partes.password
        or porta not in (None, 443)
        or partes.query
        or partes.fragment
        or "\\" in valor
        or "/../" in partes.path
        or "/./" in partes.path
    ):
        raise ErroCorpus(f"{campo} deve ser URL HTTPS simples")
    return valor


def _https_exata(valor: Any, esperada: str, campo: str) -> None:
    _https(valor, campo)
    if valor != esperada:
        raise ErroCorpus(f"{campo} diverge da URL aprovada")


def _commit(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _COMMIT_RE.fullmatch(valor):
        raise ErroCorpus(f"{campo} deve ser commit Git completo")


def _sha256(valor: Any, campo: str) -> None:
    if not isinstance(valor, str) or not _SHA256_RE.fullmatch(valor):
        raise ErroCorpus(f"{campo} deve ser SHA-256 completo")


def _lista_textos_unicos(valor: Any, campo: str) -> tuple[str, ...]:
    if not isinstance(valor, list) or not valor:
        raise ErroCorpus(f"{campo} deve ser lista não vazia")
    itens = tuple(valor)
    if any(not isinstance(item, str) or not item or "\x00" in item for item in itens):
        raise ErroCorpus(f"{campo} contém texto inválido")
    if len(set(itens)) != len(itens):
        raise ErroCorpus(f"{campo} contém duplicata")
    return itens


def _objeto(valor: Any, campo: str) -> Mapping[str, Any]:
    if not isinstance(valor, Mapping):
        raise ErroCorpus(f"{campo} deve ser objeto")
    return valor


def _chaves(objeto: Mapping[str, Any], esperadas: frozenset[str], campo: str) -> None:
    atuais = set(objeto)
    if atuais != esperadas:
        raise ErroCorpus(
            f"campos inválidos em {campo}; "
            f"ausentes={sorted(esperadas - atuais)}, desconhecidos={sorted(atuais - esperadas)}"
        )


def _objeto_sem_duplicatas(pares: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    objeto: dict[str, Any] = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroCorpus(f"chave JSON duplicada: {chave}")
        objeto[chave] = valor
    return objeto


def _constante_invalida(valor: str) -> None:
    raise ErroCorpus(f"constante JSON não finita proibida: {valor}")
