"""Contratos congelados do corpus RealVuln v1 e da fila C1/C2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import uuid
from pathlib import Path
from pathlib import PurePosixPath
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
        "caminhos_excluidos",
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
_CAMPOS_ESPELHOS = frozenset(
    {"schema_version", "verificado_em", "metodo_descoberta", "espelhos"}
)
_CAMPOS_ESPELHO = frozenset(
    {"alvo", "url_oficial", "url_espelho", "commit", "motivo"}
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
    caminhos = _lista_textos_unicos(
        politica["caminhos_excluidos"], "caminhos_excluidos"
    )
    modos = _lista_textos_unicos(
        politica["modos_git_permitidos"], "modos_git_permitidos"
    )
    for nome, valores in (
        ("segmentos_excluidos", segmentos),
        ("arquivos_excluidos", arquivos),
        ("sufixos_excluidos", sufixos),
        ("caminhos_excluidos", caminhos),
    ):
        if list(valores) != sorted(valores, key=lambda item: item.encode("utf-8")):
            raise ErroCorpus(f"{nome} deve usar ordem UTF-8 canônica")
        if any(valor != valor.casefold() for valor in valores):
            raise ErroCorpus(f"{nome} deve conter somente valores casefold")
    if modos != ("100644", "100755"):
        raise ErroCorpus("modos Git permitidos devem ser exatamente 100644 e 100755")
    if any(
        caminho.startswith("/")
        or "\\" in caminho
        or any(parte in {"", ".", ".."} for parte in caminho.split("/"))
        for caminho in caminhos
    ):
        raise ErroCorpus("caminhos_excluidos contém caminho inseguro")
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


def validar_lock_espelhos(
    documento: Mapping[str, Any], lock_corpus: Mapping[str, Any]
) -> Mapping[str, Any]:
    lock = _objeto(documento, "lock de espelhos")
    _chaves(lock, _CAMPOS_ESPELHOS, "lock de espelhos")
    if lock["schema_version"] != "1.0":
        raise ErroCorpus("schema_version dos espelhos deve ser 1.0")
    if lock["verificado_em"] != "2026-08-11":
        raise ErroCorpus("data de verificação dos espelhos diverge")
    if lock["metodo_descoberta"] != "GitHub Search Commits API por SHA-1 completo":
        raise ErroCorpus("método de descoberta dos espelhos diverge")
    corpus = validar_lock_corpus(lock_corpus)
    por_alvo = {item["alvo"]: item for item in corpus["alvos"]}
    espelhos = lock["espelhos"]
    if not isinstance(espelhos, list) or len(espelhos) != 3:
        raise ErroCorpus("lock deve conter exatamente três espelhos necessários")
    ids: list[str] = []
    urls: set[str] = set()
    for indice, item in enumerate(espelhos):
        espelho = _objeto(item, f"espelhos[{indice}]")
        _chaves(espelho, _CAMPOS_ESPELHO, f"espelhos[{indice}]")
        alvo_id = espelho["alvo"]
        if alvo_id not in por_alvo:
            raise ErroCorpus(f"espelho referencia alvo desconhecido: {alvo_id}")
        alvo = por_alvo[alvo_id]
        if espelho["url_oficial"] != alvo["url"] or espelho["commit"] != alvo["commit"]:
            raise ErroCorpus(f"espelho de {alvo_id} diverge do corpus oficial")
        _https(espelho["url_espelho"], f"url_espelho de {alvo_id}")
        if espelho["url_espelho"] == alvo["url"]:
            raise ErroCorpus(f"espelho de {alvo_id} não pode repetir URL oficial")
        if espelho["motivo"] != "fonte_primaria_indisponivel":
            raise ErroCorpus(f"motivo inválido no espelho de {alvo_id}")
        ids.append(alvo_id)
        urls.add(espelho["url_espelho"])
    if ids != sorted(ids) or len(set(ids)) != 3 or len(urls) != 3:
        raise ErroCorpus("espelhos devem ter alvos/URLs únicos em ordem canônica")
    if set(ids) != {"ALVO-0015", "ALVO-0021", "ALVO-0023"}:
        raise ErroCorpus("conjunto de espelhos diverge das fontes indisponíveis observadas")
    return lock


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
    normalizado = "/".join(normalizadas)
    if normalizado in documento["caminhos_excluidos"]:
        return True
    if nome in documento["arquivos_excluidos"]:
        return True
    return any(nome.endswith(sufixo) for sufixo in documento["sufixos_excluidos"])


def auditar_ground_truth(
    raiz_oracle: str | Path, lock_corpus: Mapping[str, Any]
) -> dict[str, Any]:
    """Confere identidade e contagens do GT, sem expor seu conteúdo no resultado."""

    corpus = validar_lock_corpus(lock_corpus)
    raiz = Path(raiz_oracle)
    if raiz.is_symlink() or not raiz.is_dir():
        raise ErroCorpus(f"oracle deve ser diretório real: {raiz}")
    ground_truth = raiz / "ground-truth"
    if ground_truth.is_symlink() or not ground_truth.is_dir():
        raise ErroCorpus("oracle não contém ground-truth real")

    esperados = {item["realvuln_id"]: item for item in corpus["alvos"]}
    observados: dict[str, Path] = {}
    try:
        with os.scandir(ground_truth) as entradas:
            for entrada in entradas:
                path = Path(entrada.path)
                if entrada.is_symlink() or _eh_juncao(path):
                    raise ErroCorpus(f"link ou junção proibido no oracle: {path}")
                if not entrada.is_dir(follow_symlinks=False):
                    raise ErroCorpus(f"entrada inesperada em ground-truth: {path.name}")
                if path.name not in esperados:
                    raise ErroCorpus(f"repositório inesperado no ground-truth: {path.name}")
                with os.scandir(path) as arquivos:
                    conteudo = list(arquivos)
                if len(conteudo) != 1 or conteudo[0].name != "ground-truth.json":
                    raise ErroCorpus(f"estrutura inesperada no ground-truth de {path.name}")
                arquivo = Path(conteudo[0].path)
                if conteudo[0].is_symlink() or not conteudo[0].is_file(follow_symlinks=False):
                    raise ErroCorpus(f"ground-truth.json deve ser arquivo regular: {path.name}")
                observados[path.name] = arquivo
    except OSError as exc:
        raise ErroCorpus(f"não foi possível percorrer ground-truth: {exc}") from exc
    if set(observados) != set(esperados):
        ausentes = sorted(set(esperados) - set(observados))
        raise ErroCorpus(f"ground-truth incompleto; ausentes={ausentes}")

    itens: list[dict[str, Any]] = []
    ground_truth_ids: set[str] = set()
    total_vulneraveis = 0
    total_armadilhas = 0
    divergencias_url = 0
    for repo_id in sorted(esperados, key=lambda item: item.encode("utf-8")):
        alvo = esperados[repo_id]
        arquivo = observados[repo_id]
        documento = carregar_json(arquivo)
        ground_truth_id = documento.get("repo_id")
        if (
            not isinstance(ground_truth_id, str)
            or not ground_truth_id
            or len(ground_truth_id.encode("utf-8")) > 200
            or ground_truth_id in ground_truth_ids
        ):
            raise ErroCorpus(f"{repo_id}.repo_id é ausente, inválido ou duplicado")
        ground_truth_ids.add(ground_truth_id)
        ground_truth_url = documento.get("repo_url")
        _https(ground_truth_url, f"{repo_id}.repo_url")
        url_confere = ground_truth_url == alvo["url"]
        if not url_confere:
            divergencias_url += 1
        if documento.get("commit_sha") != alvo["commit"]:
            raise ErroCorpus(f"{repo_id}.commit_sha diverge do lock do corpus")
        findings = documento.get("findings")
        if not isinstance(findings, list) or not findings:
            raise ErroCorpus(f"{repo_id}.findings deve ser lista não vazia")
        vulneraveis = 0
        armadilhas = 0
        for indice, finding in enumerate(findings):
            if not isinstance(finding, Mapping):
                raise ErroCorpus(f"{repo_id}.findings[{indice}] deve ser objeto")
            valor = finding.get("is_vulnerable")
            if valor is True:
                vulneraveis += 1
            elif valor is False:
                armadilhas += 1
            else:
                raise ErroCorpus(
                    f"{repo_id}.findings[{indice}].is_vulnerable deve ser booleano"
                )
        total_vulneraveis += vulneraveis
        total_armadilhas += armadilhas
        itens.append(
            {
                "alvo": alvo["alvo"],
                "realvuln_id": repo_id,
                "ground_truth_repo_id": ground_truth_id,
                "ground_truth_repo_url": ground_truth_url,
                "repo_url_confere": url_confere,
                "arquivo_sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest(),
                "vulnerabilidades": vulneraveis,
                "armadilhas_fp": armadilhas,
                "entradas": vulneraveis + armadilhas,
            }
        )
    total = total_vulneraveis + total_armadilhas
    if (len(itens), total, total_vulneraveis, total_armadilhas) != (26, 817, 697, 120):
        raise ErroCorpus(
            "contagens do ground-truth divergem de 26/817/697/120; "
            f"observado={len(itens)}/{total}/{total_vulneraveis}/{total_armadilhas}"
        )
    return {
        "schema_version": "1.0",
        "benchmark_version": BENCHMARK_VERSION,
        "ground_truth_content_identifier": corpus["realvuln"][
            "ground_truth_content_identifier"
        ],
        "repositorios": len(itens),
        "entradas": total,
        "vulnerabilidades": total_vulneraveis,
        "armadilhas_fp": total_armadilhas,
        "divergencias_url_ground_truth": divergencias_url,
        "itens": itens,
    }


def extrair_tar_git(arquivo_tar: str | Path, destino: str | Path) -> int:
    """Extrai um `git archive` sem seguir links nem aceitar caminhos ambíguos."""

    origem = Path(arquivo_tar)
    saida = Path(destino)
    if origem.is_symlink() or not origem.is_file():
        raise ErroCorpus(f"archive deve ser arquivo regular: {origem}")
    if saida.exists() or saida.is_symlink():
        raise ErroCorpus("destino da exportação deve ser novo")
    pai = saida.parent
    if pai.is_symlink() or not pai.is_dir():
        raise ErroCorpus("pai da exportação deve ser diretório real")
    temporario = pai / f".{saida.name}.extraindo-{uuid.uuid4().hex}"
    temporario.mkdir(mode=0o700)
    vistos: set[str] = set()
    arquivos = 0
    try:
        with tarfile.open(origem, mode="r:") as pacote:
            for membro in pacote:
                nome = membro.name.removesuffix("/")
                partes = PurePosixPath(nome).parts
                if (
                    not nome
                    or nome.startswith("/")
                    or "\\" in nome
                    or "\x00" in nome
                    or any(ord(caractere) < 32 for caractere in nome)
                    or any(parte in {"", ".", ".."} for parte in partes)
                ):
                    raise ErroCorpus(f"caminho inseguro no archive: {membro.name!r}")
                reservados_windows = {"con", "prn", "aux", "nul"} | {
                    f"{prefixo}{indice}"
                    for prefixo in ("com", "lpt")
                    for indice in range(1, 10)
                }
                if any(
                    ":" in parte
                    or parte.endswith((" ", "."))
                    or parte.split(".", 1)[0].casefold() in reservados_windows
                    for parte in partes
                ):
                    raise ErroCorpus(f"caminho incompatível com o host: {nome}")
                chave = nome.casefold()
                if chave in vistos:
                    raise ErroCorpus(f"caminho duplicado ou ambíguo no archive: {nome}")
                vistos.add(chave)
                alvo = temporario.joinpath(*partes)
                if membro.isdir():
                    alvo.mkdir(parents=True, exist_ok=False)
                    continue
                # `git archive` representa blobs 100644/100755 como 0664/0775.
                if not membro.isfile() or membro.mode not in (0o644, 0o664, 0o755, 0o775):
                    raise ErroCorpus(f"entrada não regular ou modo proibido no archive: {nome}")
                alvo.parent.mkdir(parents=True, exist_ok=True)
                fonte = pacote.extractfile(membro)
                if fonte is None:
                    raise ErroCorpus(f"conteúdo ausente no archive: {nome}")
                with fonte, alvo.open("xb") as destino_aberto:
                    while bloco := fonte.read(1024 * 1024):
                        destino_aberto.write(bloco)
                arquivos += 1
        if arquivos == 0:
            raise ErroCorpus("archive Git não pode estar vazio")
        temporario.replace(saida)
        return arquivos
    except (tarfile.TarError, OSError) as exc:
        raise ErroCorpus(f"archive Git inválido: {exc}") from exc
    finally:
        if temporario.exists():
            shutil.rmtree(temporario, ignore_errors=True)


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


def _eh_juncao(path: Path) -> bool:
    detector = getattr(path, "is_junction", None)
    return bool(detector()) if detector is not None else False


def _escrever_json_novo(caminho: str | Path, documento: Mapping[str, Any]) -> None:
    destino = Path(caminho)
    if destino.exists() or destino.is_symlink():
        raise ErroCorpus(f"saída já existe: {destino}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(f".{destino.name}.{uuid.uuid4().hex}.tmp")
    try:
        dados = (
            json.dumps(
                documento,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        with temporario.open("xb") as arquivo:
            arquivo.write(dados)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        temporario.replace(destino)
    except Exception:
        temporario.unlink(missing_ok=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="comando", required=True)
    auditar = subparsers.add_parser("auditar-ground-truth")
    auditar.add_argument("--oracle", required=True)
    auditar.add_argument("--corpus-lock", required=True)
    auditar.add_argument("--saida", required=True)
    exportar = subparsers.add_parser("extrair-tar-git")
    exportar.add_argument("--arquivo", required=True)
    exportar.add_argument("--destino", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    try:
        if argumentos.comando == "auditar-ground-truth":
            resumo = auditar_ground_truth(
                argumentos.oracle, carregar_json(argumentos.corpus_lock)
            )
            _escrever_json_novo(argumentos.saida, resumo)
            print(
                f"repositorios={resumo['repositorios']} entradas={resumo['entradas']} "
                f"vulnerabilidades={resumo['vulnerabilidades']} "
                f"armadilhas_fp={resumo['armadilhas_fp']}"
            )
        elif argumentos.comando == "extrair-tar-git":
            quantidade = extrair_tar_git(argumentos.arquivo, argumentos.destino)
            print(f"arquivos={quantidade}")
        return 0
    except (ErroCorpus, OSError, ValueError) as exc:
        print(f"erro de corpus: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
