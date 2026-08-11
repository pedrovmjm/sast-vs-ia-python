"""Prepara e audita tentativas da coleta serial C1/C2.

Este módulo nunca executa código do corpus. Ele copia arquivos regulares,
confere inventários congelados e valida a saída produzida pelo wrapper SAST.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from runner.aquisicao import calcular_sha256_arquivo
from runner.corpus import carregar_json, hash_json_canonico, validar_lock_corpus, validar_lock_fila
from runner.modelos import ErroModelo, ManifestoExecucao
from runner.preparacao import ErroPreparacao, criar_inventario, preparar_alvo


class ErroColeta(ValueError):
    """Indica deriva, contaminação ou produto inválido da coleta."""


def plano_seco(
    fila_lock: Mapping[str, Any],
    corpus_lock: Mapping[str, Any],
    inventarios: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    fila = validar_lock_fila(fila_lock, corpus_lock)
    corpus = validar_lock_corpus(corpus_lock)
    por_alvo = {item["alvo"]: item for item in corpus["alvos"]}
    tarefas = []
    for execucao_id in fila["ordem"]:
        condicao = execucao_id[:2]
        alvo = execucao_id[3:12]
        entrada = por_alvo[alvo]
        inventario = inventarios.get(alvo)
        if not isinstance(inventario, Mapping):
            raise ErroColeta(f"inventário congelado ausente para {alvo}")
        entrada_sha256 = inventario.get("entrada_sha256")
        if not isinstance(entrada_sha256, str) or len(entrada_sha256) != 64:
            raise ErroColeta(f"inventário congelado inválido para {alvo}")
        tarefas.append(
            {
                "execucao_id": execucao_id,
                "condicao": condicao,
                "alvo": alvo,
                "entrada_commit": entrada["commit"],
                "entrada_sha256": entrada_sha256,
            }
        )
    return {
        "schema_version": "1.0",
        "tipo": "plano-seco-coleta-c1-c2",
        "quantidade": len(tarefas),
        "fila_lock_sha256": hash_json_canonico(fila),
        "corpus_lock_sha256": hash_json_canonico(corpus),
        "tarefas": tarefas,
    }


def preparar_tentativa(
    origem: str | Path,
    destino: str | Path,
    inventario_congelado: Mapping[str, Any],
) -> dict[str, Any]:
    """Cria área nova e exige igualdade integral com o inventário publicado."""

    try:
        observado = preparar_alvo(origem, destino)
    except (ErroPreparacao, OSError) as exc:
        raise ErroColeta(str(exc)) from exc
    if dict(observado) != dict(inventario_congelado):
        _remover_area_propria(Path(destino))
        raise ErroColeta("inventário da tentativa diverge do corpus congelado")
    return observado


def remover_area_tentativa(caminho: str | Path, execucao_id: str, tentativa: int) -> None:
    area = Path(caminho)
    esperado = f"{execucao_id}-T{tentativa:03d}"
    if area.name != esperado:
        raise ErroColeta(f"área própria deve terminar em {esperado}")
    _remover_area_propria(area)


def validar_manifesto_terminal(
    caminho: str | Path,
    *,
    execucao_id: str,
    alvo: str,
    condicao: str,
    tentativa: int,
    entrada_commit: str,
    entrada_sha256: str,
    imagem: str,
    imagem_digest: str,
) -> dict[str, Any]:
    manifesto_path = Path(caminho)
    if manifesto_path.is_symlink() or not manifesto_path.is_file():
        raise ErroColeta("manifesto terminal deve ser arquivo regular")
    try:
        manifesto = ManifestoExecucao.from_json(manifesto_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ErroModelo) as exc:
        raise ErroColeta(f"manifesto terminal inválido: {exc}") from exc
    esperados = {
        "execucao_id": execucao_id,
        "alvo": alvo,
        "condicao": condicao,
        "tentativa": tentativa,
        "entrada_commit": entrada_commit,
        "entrada_sha256": entrada_sha256,
        "imagem": imagem,
        "imagem_digest": imagem_digest,
        "finalidade": "coleta",
        "repeticao": 1,
    }
    for campo, esperado in esperados.items():
        if getattr(manifesto, campo) != esperado:
            raise ErroColeta(f"{campo} do manifesto diverge da tarefa congelada")
    if manifesto.estado not in {"concluida", "falha"}:
        raise ErroColeta("manifesto deve estar em estado terminal")
    saida = manifesto_path.parent
    declarados = dict(manifesto.artefatos_sha256)
    for relativo, digest in declarados.items():
        artefato = _artefato_seguro(saida, relativo)
        if calcular_sha256_arquivo(artefato) != digest:
            raise ErroColeta(f"hash do artefato diverge: {relativo}")
    partes = [p for p in saida.rglob("*.part") if p.is_file() or p.is_symlink()]
    if partes:
        raise ErroColeta("tentativa terminal contém arquivo .part residual")
    return {
        "schema_version": "1.0",
        "execucao_id": execucao_id,
        "tentativa": tentativa,
        "estado": manifesto.estado,
        "falha_tipo": manifesto.falha_tipo,
        "manifesto_sha256": calcular_sha256_arquivo(manifesto_path),
        "inicio_utc": manifesto.inicio_utc,
        "termino_utc": manifesto.termino_utc,
        "duracao_monotonica_segundos": manifesto.duracao_monotonica_segundos,
        "artefatos": len(declarados),
    }


def copiar_manifesto_evidencia(origem: str | Path, destino: str | Path) -> str:
    fonte = Path(origem)
    saida = Path(destino)
    if fonte.is_symlink() or not fonte.is_file():
        raise ErroColeta("manifesto de origem deve ser arquivo regular")
    if saida.exists() or saida.is_symlink():
        raise ErroColeta("manifesto de evidência já existe")
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_name(f".{saida.name}.{os.getpid()}.tmp")
    try:
        with fonte.open("rb") as entrada, temporario.open("xb") as arquivo:
            shutil.copyfileobj(entrada, arquivo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.link(temporario, saida)
        temporario.unlink()
        return calcular_sha256_arquivo(saida)
    except FileExistsError as exc:
        raise ErroColeta("manifesto de evidência já existe") from exc
    finally:
        temporario.unlink(missing_ok=True)


def resumir_fila(documento: Mapping[str, Any]) -> dict[str, Any]:
    itens = documento.get("itens")
    if not isinstance(itens, list) or len(itens) != 52:
        raise ErroColeta("resumo exige fila validada com 52 itens")
    estados: dict[str, int] = {}
    condicoes = {"C1": 0, "C2": 0}
    falhas: dict[str, int] = {}
    terminais = 0
    for item in itens:
        estado = item["estado"]
        estados[estado] = estados.get(estado, 0) + 1
        condicoes[item["condicao"]] += 1
        if estado in {"concluida", "falha"}:
            terminais += 1
        if item["falha_tipo"] is not None:
            falhas[item["falha_tipo"]] = falhas.get(item["falha_tipo"], 0) + 1
    return {
        "schema_version": "1.0",
        "tipo": "resumo-coleta-c1-c2",
        "quantidade": len(itens),
        "terminais": terminais,
        "estados": dict(sorted(estados.items())),
        "condicoes": condicoes,
        "falhas": dict(sorted(falhas.items())),
    }


def _artefato_seguro(raiz: Path, relativo: str) -> Path:
    if not isinstance(relativo, str):
        raise ErroColeta("caminho de artefato deve ser texto")
    puro = PurePosixPath(relativo)
    if puro.is_absolute() or not puro.parts or any(p in {"", ".", ".."} for p in puro.parts):
        raise ErroColeta(f"caminho de artefato inseguro: {relativo}")
    caminho = raiz.joinpath(*puro.parts)
    if caminho.is_symlink() or not caminho.is_file():
        raise ErroColeta(f"artefato deve ser arquivo regular: {relativo}")
    return caminho


def _remover_area_propria(caminho: Path) -> None:
    if caminho.is_symlink() or not caminho.is_dir():
        raise ErroColeta("área de tentativa deve ser diretório regular existente")
    shutil.rmtree(caminho)


def _emitir(documento: Mapping[str, Any]) -> None:
    print(json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    seco = sub.add_parser("plano-seco")
    seco.add_argument("--fila-lock", required=True)
    seco.add_argument("--corpus-lock", required=True)
    seco.add_argument("--inventarios-dir", required=True)
    preparar = sub.add_parser("preparar")
    preparar.add_argument("--origem", required=True)
    preparar.add_argument("--destino", required=True)
    preparar.add_argument("--inventario", required=True)
    limpar = sub.add_parser("limpar-area")
    limpar.add_argument("--caminho", required=True)
    limpar.add_argument("--execucao-id", required=True)
    limpar.add_argument("--tentativa", required=True, type=int)
    validar = sub.add_parser("validar-manifesto")
    validar.add_argument("--manifesto", required=True)
    validar.add_argument("--execucao-id", required=True)
    validar.add_argument("--alvo", required=True)
    validar.add_argument("--condicao", required=True)
    validar.add_argument("--tentativa", required=True, type=int)
    validar.add_argument("--entrada-commit", required=True)
    validar.add_argument("--entrada-sha256", required=True)
    validar.add_argument("--imagem", required=True)
    validar.add_argument("--imagem-digest", required=True)
    copiar = sub.add_parser("copiar-evidencia")
    copiar.add_argument("--origem", required=True)
    copiar.add_argument("--destino", required=True)
    hash_parser = sub.add_parser("hash-json")
    hash_parser.add_argument("--arquivo", required=True)
    resumo_parser = sub.add_parser("resumir")
    resumo_parser.add_argument("--fila", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.comando == "plano-seco":
            inventarios_dir = Path(args.inventarios_dir)
            inventarios = {
                f"ALVO-{numero:04d}": carregar_json(
                    inventarios_dir / f"ALVO-{numero:04d}-inventario.json"
                )
                for numero in range(1, 27)
            }
            _emitir(
                plano_seco(
                    carregar_json(args.fila_lock),
                    carregar_json(args.corpus_lock),
                    inventarios,
                )
            )
        elif args.comando == "preparar":
            _emitir(preparar_tentativa(args.origem, args.destino, carregar_json(args.inventario)))
        elif args.comando == "limpar-area":
            remover_area_tentativa(args.caminho, args.execucao_id, args.tentativa)
            _emitir({"removida": True})
        elif args.comando == "validar-manifesto":
            _emitir(
                validar_manifesto_terminal(
                    args.manifesto,
                    execucao_id=args.execucao_id,
                    alvo=args.alvo,
                    condicao=args.condicao,
                    tentativa=args.tentativa,
                    entrada_commit=args.entrada_commit,
                    entrada_sha256=args.entrada_sha256,
                    imagem=args.imagem,
                    imagem_digest=args.imagem_digest,
                )
            )
        elif args.comando == "copiar-evidencia":
            _emitir({"sha256": copiar_manifesto_evidencia(args.origem, args.destino)})
        elif args.comando == "hash-json":
            _emitir({"sha256": hash_json_canonico(carregar_json(args.arquivo))})
        else:
            _emitir(resumir_fila(carregar_json(args.fila)))
        return 0
    except (ErroColeta, ValueError, OSError) as exc:
        print(f"erro de coleta: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
