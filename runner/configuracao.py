"""Gera e valida a configuração imutável que arma a coleta M2."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from runner.aquisicao import calcular_sha256_arvore
from runner.corpus import (
    ErroCorpus,
    carregar_json,
    hash_json_canonico,
    validar_lock_corpus,
    validar_lock_fila,
    validar_politica,
)


class ErroConfiguracao(ValueError):
    """Indica uma configuração ausente, não autorizada ou divergente."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_TOP = frozenset(
    {
        "schema_version", "tipo", "criada_em", "controlador_commit", "imagem",
        "timeout_segundos", "hashes", "corpus", "risco", "limites", "comandos",
    }
)


def criar_configuracao(
    repo: str | Path,
    *,
    imagem_tag: str,
    imagem_id: str,
    controlador_commit: str,
    timeout_segundos: int,
    host_observado: Mapping[str, Any],
    decisao: Mapping[str, Any],
    criada_em: str | None = None,
) -> dict[str, Any]:
    raiz = Path(repo)
    if not _COMMIT.fullmatch(controlador_commit):
        raise ErroConfiguracao("controlador_commit deve ser SHA-1 completo")
    if not _DIGEST.fullmatch(imagem_id):
        raise ErroConfiguracao("imagem_id deve ser digest SHA-256 completo")
    if not isinstance(timeout_segundos, int) or isinstance(timeout_segundos, bool) or not 1 <= timeout_segundos <= 86400:
        raise ErroConfiguracao("timeout_segundos fora do intervalo")
    decisao_norm = _validar_decisao(decisao)
    corpus = validar_lock_corpus(carregar_json(raiz / "config/corpus-realvuln-v1.lock.json"))
    fila = validar_lock_fila(carregar_json(raiz / "config/fila-c1-c2.lock.json"), corpus)
    politica = validar_politica(carregar_json(raiz / "config/politica-sanitizacao-v1.json"))
    alvos = []
    for entrada in corpus["alvos"]:
        inventario = carregar_json(
            raiz / "evidencias/corpus-realvuln-v1" / f"{entrada['alvo']}-inventario.json"
        )
        entrada_sha = inventario.get("entrada_sha256")
        if not isinstance(entrada_sha, str) or not _SHA256.fullmatch(entrada_sha):
            raise ErroConfiguracao(f"inventário inválido para {entrada['alvo']}")
        alvos.append(
            {
                "alvo": entrada["alvo"],
                "commit": entrada["commit"],
                "entrada_sha256": entrada_sha,
                "inventario_sha256": hash_json_canonico(inventario),
            }
        )
    regras = raiz / "docker/regras-semgrep"
    if not regras.is_dir() or regras.is_symlink():
        raise ErroConfiguracao("bundle de regras Semgrep ausente ou inseguro")
    documento = {
        "schema_version": "1.0",
        "tipo": "configuracao-coleta-c1-c2",
        "criada_em": criada_em or _agora_utc(),
        "controlador_commit": controlador_commit,
        "imagem": {
            "tag": imagem_tag,
            "id": imagem_id,
            "os": "linux",
            "arquitetura": "amd64",
        },
        "timeout_segundos": timeout_segundos,
        "hashes": {
            "corpus_lock_sha256": hash_json_canonico(corpus),
            "fila_lock_sha256": hash_json_canonico(fila),
            "politica_sha256": hash_json_canonico(politica),
            "regras_bundle_sha256": calcular_sha256_arvore(regras),
            "host_risk_decision_sha256": hash_json_canonico(decisao_norm),
        },
        "corpus": {"quantidade_alvos": 26, "alvos": alvos},
        "risco": {
            "decisao": decisao_norm,
            "host_observado": copy.deepcopy(dict(host_observado)),
            "autorizacao_coleta": True,
        },
        "limites": {
            "rede": "none", "rootfs": "read-only", "usuario": "10001:10001",
            "capabilities": "ALL-dropped", "no_new_privileges": True,
            "pids": 256, "memoria": "3g", "cpus": 2,
        },
        "comandos": {
            "C1": ["/usr/local/bin/python", "-P", "-m", "runner.executor_sast", "--condicao", "C1"],
            "C2": ["/usr/local/bin/python", "-P", "-m", "runner.executor_sast", "--condicao", "C2"],
        },
    }
    return validar_configuracao(documento, raiz, regras)


def validar_configuracao(
    documento: Mapping[str, Any],
    repo: str | Path,
    regras: str | Path | None = None,
) -> dict[str, Any]:
    _chaves(documento, _TOP, "configuração")
    if documento["schema_version"] != "1.0" or documento["tipo"] != "configuracao-coleta-c1-c2":
        raise ErroConfiguracao("identidade da configuração inválida")
    if not isinstance(documento["criada_em"], str) or not _UTC.fullmatch(documento["criada_em"]):
        raise ErroConfiguracao("criada_em inválida")
    if not _COMMIT.fullmatch(str(documento["controlador_commit"])):
        raise ErroConfiguracao("controlador_commit inválido")
    imagem = _objeto(documento["imagem"], "imagem")
    for campo in ("tag", "os", "arquitetura"):
        if not isinstance(imagem.get(campo), str) or not imagem[campo]:
            raise ErroConfiguracao(f"imagem.{campo} inválido")
    if imagem["id"] and not _DIGEST.fullmatch(str(imagem["id"])):
        raise ErroConfiguracao("imagem.id inválido")
    if not isinstance(documento["timeout_segundos"], int) or isinstance(documento["timeout_segundos"], bool) or not 1 <= documento["timeout_segundos"] <= 86400:
        raise ErroConfiguracao("timeout_segundos inválido")
    risco = _objeto(documento["risco"], "risco")
    if risco.get("autorizacao_coleta") is not True:
        raise ErroConfiguracao("coleta não autorizada: decisão explícita M2 ausente")
    decisao = _validar_decisao(risco.get("decisao"))
    corpus = validar_lock_corpus(carregar_json(Path(repo) / "config/corpus-realvuln-v1.lock.json"))
    fila = validar_lock_fila(carregar_json(Path(repo) / "config/fila-c1-c2.lock.json"), corpus)
    politica = validar_politica(carregar_json(Path(repo) / "config/politica-sanitizacao-v1.json"))
    hashes = _objeto(documento["hashes"], "hashes")
    esperados = {
        "corpus_lock_sha256": hash_json_canonico(corpus),
        "fila_lock_sha256": hash_json_canonico(fila),
        "politica_sha256": hash_json_canonico(politica),
        "host_risk_decision_sha256": hash_json_canonico(decisao),
    }
    for campo, esperado in esperados.items():
        if hashes.get(campo) != esperado:
            raise ErroConfiguracao(f"{campo} diverge dos arquivos congelados")
    bundle = Path(regras) if regras is not None else Path(repo) / "docker/regras-semgrep"
    if hashes.get("regras_bundle_sha256") != calcular_sha256_arvore(bundle):
        raise ErroConfiguracao("regras_bundle_sha256 diverge do bundle atual")
    alvos = _objeto(documento["corpus"], "corpus").get("alvos")
    if not isinstance(alvos, list) or len(alvos) != 26:
        raise ErroConfiguracao("configuração deve conter 26 alvos")
    por_id = {item["alvo"]: item for item in corpus["alvos"]}
    vistos = set()
    for item in alvos:
        alvo = _objeto(item, "corpus.alvos")
        if alvo.get("alvo") in vistos or alvo.get("alvo") not in por_id:
            raise ErroConfiguracao("conjunto de alvos da configuração diverge")
        vistos.add(alvo["alvo"])
        inventario = carregar_json(Path(repo) / "evidencias/corpus-realvuln-v1" / f"{alvo['alvo']}-inventario.json")
        if alvo.get("commit") != por_id[alvo["alvo"]]["commit"] or alvo.get("entrada_sha256") != inventario.get("entrada_sha256"):
            raise ErroConfiguracao(f"proveniência congelada diverge em {alvo['alvo']}")
        if alvo.get("inventario_sha256") != hash_json_canonico(inventario):
            raise ErroConfiguracao(f"hash do inventário diverge em {alvo['alvo']}")
    if vistos != set(por_id):
        raise ErroConfiguracao("configuração não cobre os 26 alvos")
    return dict(documento)


def _validar_decisao(valor: Any) -> dict[str, Any]:
    decisao = _objeto(valor, "decisão de risco")
    if decisao.get("schema_version") != "1.0" or decisao.get("tipo") != "host-risk-waiver-m2":
        raise ErroConfiguracao("decisão não é um waiver M2 versionado")
    if decisao.get("status") not in {"accepted", "updated"} or decisao.get("scope") != "M2":
        raise ErroConfiguracao("decisão deve aceitar explicitamente o escopo M2")
    if decisao.get("authorized_by") in {None, ""} or decisao.get("decided_at") in {None, ""}:
        raise ErroConfiguracao("decisão M2 exige responsável e data")
    if decisao.get("authorization") is not True:
        raise ErroConfiguracao("decisão M2 não contém autorização explícita")
    return dict(decisao)


def _objeto(valor: Any, campo: str) -> Mapping[str, Any]:
    if not isinstance(valor, Mapping):
        raise ErroConfiguracao(f"{campo} deve ser objeto")
    return valor


def _chaves(valor: Mapping[str, Any], esperadas: set[str] | frozenset[str], campo: str) -> None:
    if set(valor) != set(esperadas):
        raise ErroConfiguracao(f"campos inválidos em {campo}")


def _agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _emitir(valor: Mapping[str, Any]) -> None:
    print(json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    criar = sub.add_parser("criar")
    criar.add_argument("--repo", required=True)
    criar.add_argument("--imagem-tag", required=True)
    criar.add_argument("--imagem-id", required=True)
    criar.add_argument("--controlador-commit", required=True)
    criar.add_argument("--timeout-segundos", required=True, type=int)
    criar.add_argument("--host-json", required=True)
    criar.add_argument("--decisao-json", required=True)
    criar.add_argument("--saida", required=True)
    criar.add_argument("--regras", required=True)
    validar = sub.add_parser("validar")
    validar.add_argument("--repo", required=True)
    validar.add_argument("--configuracao", required=True)
    validar.add_argument("--regras", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.comando == "criar":
            documento = criar_configuracao(
                args.repo,
                imagem_tag=args.imagem_tag,
                imagem_id=args.imagem_id,
                controlador_commit=args.controlador_commit,
                timeout_segundos=args.timeout_segundos,
                host_observado=carregar_json(args.host_json),
                decisao=carregar_json(args.decisao_json),
                criada_em=_agora_utc(),
            )
            destino = Path(args.saida)
            if destino.exists() or destino.is_symlink():
                raise ErroConfiguracao("configuração de saída já existe")
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporario = destino.with_name(f".{destino.name}.{os.getpid()}.tmp")
            dados = (json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            try:
                with temporario.open("xb") as arquivo:
                    arquivo.write(dados)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
                os.link(temporario, destino)
            finally:
                temporario.unlink(missing_ok=True)
            _emitir({"configuracao_sha256": hash_json_canonico(documento), "arquivo": str(destino)})
        else:
            _emitir(validar_configuracao(carregar_json(args.configuracao), args.repo, args.regras))
        return 0
    except (ErroConfiguracao, ErroCorpus, OSError, ValueError) as exc:
        print(f"erro de configuração: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
