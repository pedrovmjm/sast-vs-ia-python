"""Orquestra a avaliação e publica tabelas intermediárias auditáveis."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .amostra import preparar_amostra
from .dados import avaliar_execucoes, carregar_execucoes, sha256_arquivo
from .estatistica import (
    detalhamentos,
    estabilidade,
    metricas_por_repeticao,
    metricas_por_repositorio,
    operacional,
    priorizacao,
    resumo_condicoes_bootstrap,
)


def escrever_json(caminho: Path, documento: Any) -> None:
    caminho.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def escrever_csv(caminho: Path, linhas: list[dict[str, Any]]) -> None:
    if not linhas:
        raise ValueError(f"não há linhas para {caminho.name}")
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=list(linhas[0]), lineterminator="\n"
        )
        escritor.writeheader()
        escritor.writerows(linhas)


def _achatar_operacional(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    for linha in linhas:
        registro: dict[str, Any] = {"condicao": linha["condicao"]}
        for grupo in ("duracao_segundos", "tokens_entrada", "tokens_saida", "tokens_total"):
            for chave, valor in linha[grupo].items():
                registro[f"{grupo}_{chave}"] = valor
        saida.append(registro)
    return saida


def _hash_ground_truth(repo: Path) -> str:
    digest = hashlib.sha256()
    raiz = repo / "oracle" / "realvuln-v1" / "ground-truth"
    arquivos = sorted(raiz.glob("*/ground-truth.json"), key=lambda item: item.as_posix())
    for arquivo in arquivos:
        relativo = arquivo.relative_to(raiz).as_posix().encode("utf-8")
        digest.update(len(relativo).to_bytes(4, "big"))
        digest.update(relativo)
        conteudo = arquivo.read_bytes()
        digest.update(len(conteudo).to_bytes(8, "big"))
        digest.update(conteudo)
    return digest.hexdigest()


def _formatar_percentual(valor: float) -> str:
    return f"{valor * 100:.1f}".replace(".", ",") + r"\%"


def _tabela_metricas_tex(resumo: list[dict[str, Any]]) -> str:
    linhas = [
        r"% Gerado por scripts/avaliar-resultados.py; não editar manualmente.",
        r"\begin{tabular}{lrrrrrr}",
        r"\hline",
        r"Condição & Precisão & Recall & F1 & F2 & F3 & Taxa de FP \\",
        r"\hline",
    ]
    for item in resumo:
        linhas.append(
            "{} & {} & {} & {} & {} & {} & {} \\\\".format(
                item["condicao"],
                _formatar_percentual(item["precision"]),
                _formatar_percentual(item["recall"]),
                _formatar_percentual(item["f1"]),
                _formatar_percentual(item["f2"]),
                _formatar_percentual(item["f3"]),
                _formatar_percentual(item["fpr"]),
            )
        )
    linhas.extend((r"\hline", r"\end{tabular}", ""))
    return "\n".join(linhas)


def executar_avaliacao(
    repo: Path,
    saida: Path,
    iteracoes_bootstrap: int = 10_000,
    semente: int = 20260928,
) -> dict[str, Any]:
    repo = repo.resolve()
    saida = saida.resolve()
    if iteracoes_bootstrap < 1_000:
        raise ValueError("use ao menos 1.000 iterações de bootstrap")
    saida.mkdir(parents=True, exist_ok=True)

    execucoes, alvos, lock = carregar_execucoes(repo)
    avaliadas, familias = avaliar_execucoes(repo, execucoes, alvos)
    por_repeticao = metricas_por_repeticao(avaliadas)
    por_repositorio = metricas_por_repositorio(avaliadas)
    resumo_condicoes, comparacoes = resumo_condicoes_bootstrap(
        avaliadas, iteracoes_bootstrap, semente
    )
    estabilidade_entradas, estabilidade_resumo = estabilidade(avaliadas)
    operacional_resumo = operacional(avaliadas)
    priorizacao_linhas = priorizacao(avaliadas)
    correspondencias, por_cwe, por_severidade = detalhamentos(avaliadas)
    amostra_cega, chave_amostra, segundo_avaliador, resumo_amostra = preparar_amostra(
        avaliadas, semente
    )

    arquivos_csv = {
        "metricas-por-repeticao.csv": por_repeticao,
        "metricas-por-repositorio.csv": por_repositorio,
        "metricas-condicoes.csv": resumo_condicoes,
        "comparacoes-pareadas.csv": comparacoes,
        "correspondencias-achados.csv": correspondencias,
        "metricas-por-cwe.csv": por_cwe,
        "metricas-por-severidade.csv": por_severidade,
        "estabilidade-entradas.csv": estabilidade_entradas,
        "estabilidade-resumo.csv": estabilidade_resumo,
        "operacional.csv": _achatar_operacional(operacional_resumo),
        "priorizacao.csv": priorizacao_linhas,
        "amostra-qualitativa-cega.csv": amostra_cega,
        "chave-amostra-qualitativa.csv": chave_amostra,
        "amostra-segundo-avaliador.csv": segundo_avaliador,
    }
    for nome, linhas in arquivos_csv.items():
        escrever_csv(saida / nome, linhas)

    resumo = {
        "schema_version": "1.0",
        "modo": "estrito",
        "microcontagem": True,
        "unidades_selecionadas": len(execucoes),
        "alvos": len(alvos),
        "bootstrap": {
            "nivel": "repositorio",
            "pareado": True,
            "metodo_ic": "percentil",
            "confianca": 0.95,
            "iteracoes": iteracoes_bootstrap,
            "semente": semente,
        },
        "metricas_por_repeticao": por_repeticao,
        "metricas_condicoes": resumo_condicoes,
        "comparacoes_pareadas": comparacoes,
        "estabilidade": estabilidade_resumo,
        "operacional": operacional_resumo,
        "priorizacao": priorizacao_linhas,
        "amostra_qualitativa": resumo_amostra,
        "notas": [
            "C1 e C2 têm uma repetição; C3--C6 são pontuadas separadamente em R1, R2 e R3.",
            "O resumo de C3--C6 é a média das métricas microcontadas das três repetições; não há união nem voto majoritário.",
            "O bootstrap reamostra os 26 repositórios como conglomerados e preserva o pareamento entre condições.",
            "Achados não associados ao ground truth contam como FP na métrica global, conforme o scorer oficial.",
            "O bloco complementar Auto/Terra não foi executado e não integra estes resultados.",
        ],
    }
    escrever_json(saida / "resumo.json", resumo)
    (saida / "tabela-metricas.tex").write_text(
        _tabela_metricas_tex(resumo_condicoes), encoding="utf-8"
    )

    source = json.loads(
        (repo / "runner" / "avaliacao" / "vendor" / "SOURCE.json").read_text(encoding="utf-8")
    )
    arquivos_gerados = sorted(
        caminho for caminho in saida.iterdir() if caminho.is_file() and caminho.name != "manifesto-avaliacao.json"
    )
    manifesto = {
        "schema_version": "1.0",
        "tipo": "manifesto-avaliacao",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "realvuln": {
            "tag": lock["realvuln"]["tag"],
            "commit": lock["realvuln"]["commit"],
            "scorer_oficial": source,
            "ground_truth_conjunto_sha256": _hash_ground_truth(repo),
        },
        "selecao": {
            "unidades": len(execucoes),
            "regra": "maior tentativa concluida, estruturalmente valida e com hash conferido",
            "oracle_usado_na_selecao": False,
        },
        "protocolo": resumo["bootstrap"],
        "artefatos_sha256": {
            caminho.name: sha256_arquivo(caminho) for caminho in arquivos_gerados
        },
    }
    escrever_json(saida / "manifesto-avaliacao.json", manifesto)
    return resumo
