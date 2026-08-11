"""Preparação segura e inventário canônico de alvos do experimento.

O módulo trata código de terceiros exclusivamente como dados: não importa módulos
do alvo, não executa arquivos e recusa links, junções e metadados do benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from runner.aquisicao import calcular_sha256_arquivo


class ErroPreparacao(ValueError):
    """Indica que uma árvore não pode ser usada como alvo sanitizado."""


_SEGMENTOS_PROIBIDOS = frozenset(
    {".git", ".hg", ".svn", "ground-truth", "oracle"}
)
_ARQUIVOS_PROIBIDOS = frozenset(
    {".gitmodules", "benchmark-manifest.json", "clone_repos.py", "validate_gt.py"}
)


def criar_inventario(caminho: str | Path) -> dict[str, Any]:
    """Inventaria arquivos regulares e calcula o hash canônico da entrada."""

    raiz = Path(caminho)
    _validar_raiz_real(raiz, "raiz do alvo")
    entradas = _listar_arquivos_seguros(raiz)
    if not entradas:
        raise ErroPreparacao("alvo sanitizado não pode estar vazio")

    digest = hashlib.sha256(b"tree-sha256-v1\0")
    itens: list[dict[str, Any]] = []
    tamanho_total = 0
    for relativo_bytes, relativo, arquivo in entradas:
        tamanho = arquivo.stat().st_size
        conteudo_sha256 = calcular_sha256_arquivo(arquivo)
        digest.update(relativo_bytes)
        digest.update(b"\0")
        digest.update(str(tamanho).encode("ascii"))
        digest.update(b"\0")
        digest.update(conteudo_sha256.encode("ascii"))
        digest.update(b"\n")
        tamanho_total += tamanho
        itens.append(
            {
                "caminho": relativo,
                "tamanho_bytes": tamanho,
                "sha256": conteudo_sha256,
            }
        )
    return {
        "schema_version": "1.0",
        "algoritmo": "tree-sha256-v1",
        "arquivos": len(itens),
        "tamanho_total_bytes": tamanho_total,
        "entrada_sha256": digest.hexdigest(),
        "itens": itens,
    }


def preparar_alvo(
    origem: str | Path,
    destino: str | Path,
) -> dict[str, Any]:
    """Copia uma exportação verificada para uma árvore opaca e sanitizada nova."""

    fonte = Path(origem)
    saida = Path(destino)
    _validar_raiz_real(fonte, "origem")
    arquivos = _listar_arquivos_seguros(fonte)
    if not arquivos:
        raise ErroPreparacao("origem não pode estar vazia")
    if saida.exists() or saida.is_symlink():
        raise ErroPreparacao("destino deve ser novo")

    fonte_resolvida = fonte.resolve(strict=True)
    pai_resolvido = saida.parent.resolve(strict=True)
    saida_resolvida = pai_resolvido / saida.name
    if _contem_caminho(fonte_resolvida, saida_resolvida) or _contem_caminho(
        saida_resolvida, fonte_resolvida
    ):
        raise ErroPreparacao("origem e destino não podem se sobrepor")

    temporario = saida.parent / f".{saida.name}.preparando-{uuid.uuid4().hex}"
    temporario.mkdir(mode=0o700)
    try:
        for _, relativo, arquivo in arquivos:
            alvo = temporario.joinpath(*relativo.split("/"))
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(arquivo, alvo, follow_symlinks=False)
        inventario = criar_inventario(temporario)
        temporario.replace(saida)
        return inventario
    except Exception:
        shutil.rmtree(temporario, ignore_errors=True)
        raise


def validar_inventarios_iguais(
    primeiro: Mapping[str, Any], segundo: Mapping[str, Any]
) -> str:
    """Exige igualdade integral entre dois inventários e retorna o hash comum."""

    for nome, documento in (("primeiro", primeiro), ("segundo", segundo)):
        if not isinstance(documento, Mapping):
            raise ErroPreparacao(f"{nome} inventário deve ser objeto")
        if documento.get("algoritmo") != "tree-sha256-v1":
            raise ErroPreparacao(f"{nome} inventário usa algoritmo inválido")
        sha256 = documento.get("entrada_sha256")
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(c not in "0123456789abcdef" for c in sha256)
        ):
            raise ErroPreparacao(f"{nome} inventário contém hash inválido")
    if dict(primeiro) != dict(segundo):
        raise ErroPreparacao("inventários C1/C2 divergem")
    return str(primeiro["entrada_sha256"])


def escrever_json_atomico(caminho: str | Path, documento: Mapping[str, Any]) -> None:
    """Persiste JSON canônico por criação exclusiva e rename atômico."""

    destino = Path(caminho)
    if destino.exists() or destino.is_symlink():
        raise ErroPreparacao(f"arquivo de evidência já existe: {destino}")
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


def _listar_arquivos_seguros(
    raiz: Path,
) -> list[tuple[bytes, str, Path]]:
    entradas: list[tuple[bytes, str, Path]] = []
    pendentes = [raiz]
    try:
        while pendentes:
            diretorio = pendentes.pop()
            with os.scandir(diretorio) as itens:
                for item in itens:
                    path = Path(item.path)
                    if item.is_symlink() or _eh_juncao(path):
                        raise ErroPreparacao(f"link ou junção proibido no alvo: {path}")
                    relativo = path.relative_to(raiz).as_posix()
                    _validar_relativo(relativo)
                    if item.is_dir(follow_symlinks=False):
                        pendentes.append(path)
                    elif item.is_file(follow_symlinks=False):
                        relativo_bytes = relativo.encode("utf-8")
                        entradas.append((relativo_bytes, relativo, path))
                    else:
                        raise ErroPreparacao(f"entrada especial proibida no alvo: {path}")
    except OSError as exc:
        raise ErroPreparacao(f"não foi possível percorrer o alvo {raiz}: {exc}") from exc
    return sorted(entradas, key=lambda item: item[0])


def _validar_relativo(relativo: str) -> None:
    partes = relativo.split("/")
    if (
        not relativo
        or relativo.startswith("/")
        or "\\" in relativo
        or "\x00" in relativo
        or any(parte in {"", ".", ".."} for parte in partes)
    ):
        raise ErroPreparacao(f"caminho inseguro no alvo: {relativo!r}")
    if any(parte.casefold() in _SEGMENTOS_PROIBIDOS for parte in partes):
        raise ErroPreparacao(f"metadado proibido no alvo: {relativo}")
    if partes[-1].casefold() in _ARQUIVOS_PROIBIDOS:
        raise ErroPreparacao(f"arquivo interno do benchmark proibido no alvo: {relativo}")


def _validar_raiz_real(raiz: Path, campo: str) -> None:
    if raiz.is_symlink() or _eh_juncao(raiz) or not raiz.is_dir():
        raise ErroPreparacao(f"{campo} deve ser diretório real: {raiz}")


def _contem_caminho(candidato: Path, raiz: Path) -> bool:
    try:
        candidato.relative_to(raiz)
        return True
    except ValueError:
        return False


def _eh_juncao(path: Path) -> bool:
    detector = getattr(path, "is_junction", None)
    return bool(detector()) if detector is not None else False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="comando", required=True)
    preparar = subparsers.add_parser("preparar")
    preparar.add_argument("--origem", required=True)
    preparar.add_argument("--destino", required=True)
    preparar.add_argument("--inventario", required=True)
    inventariar = subparsers.add_parser("inventariar")
    inventariar.add_argument("--entrada", required=True)
    inventariar.add_argument("--inventario", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argumentos = _parser().parse_args(argv)
    try:
        if argumentos.comando == "preparar":
            documento = preparar_alvo(argumentos.origem, argumentos.destino)
        else:
            documento = criar_inventario(argumentos.entrada)
        escrever_json_atomico(argumentos.inventario, documento)
        print(documento["entrada_sha256"])
        return 0
    except (ErroPreparacao, OSError, ValueError) as exc:
        print(f"erro de preparação: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
