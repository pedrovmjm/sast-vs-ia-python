"""Carregamento estrito das coletas e adaptação para o scorer oficial."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parsers.base import NormalisedFinding, normalise_path
from scorer.matcher import MatchResult, load_ground_truth, match_findings
from scorer.metrics import ScoreCard, compute_scorecard


CONDICOES = ("C1", "C2", "C3", "C4", "C5", "C6")
CONDICOES_IA = ("C3", "C4", "C5", "C6")
EXECUCAO_RE = re.compile(r"^(C[1-6])-(ALVO-[0-9]{4})-R(0[1-3])$")
TENTATIVA_RE = re.compile(r"^tentativa-([0-9]{3,})$")


@dataclass(frozen=True)
class ExecucaoSelecionada:
    condicao: str
    alvo: str
    repeticao: int
    tentativa: int
    diretorio: Path
    manifesto: dict[str, Any]
    achados_brutos: list[dict[str, Any]]
    achados: list[NormalisedFinding]

    @property
    def execucao_id(self) -> str:
        return str(self.manifesto["execucao_id"])


@dataclass(frozen=True)
class ExecucaoAvaliada:
    execucao: ExecucaoSelecionada
    ground_truth: dict[str, Any]
    correspondencias: list[MatchResult]
    scorecard: ScoreCard


def carregar_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8-sig"))


def sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def carregar_lock_corpus(repo: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    documento = carregar_json(repo / "config" / "corpus-realvuln-v1.lock.json")
    alvos = {item["alvo"]: item for item in documento["alvos"]}
    if len(alvos) != 26 or documento.get("quantidade_alvos") != 26:
        raise ValueError("o lock do corpus deve conter exatamente 26 alvos")
    return alvos, documento


def _diretorios_execucao(repo: Path, condicao: str) -> list[Path]:
    raiz = repo / "resultados" if condicao in ("C1", "C2") else repo / "resultados" / "ia" / "coleta"
    return sorted(caminho for caminho in raiz.glob(f"{condicao}-ALVO-*-R*") if caminho.is_dir())


def _tentativas(execucao: Path) -> list[tuple[int, Path, dict[str, Any]]]:
    saida: list[tuple[int, Path, dict[str, Any]]] = []
    for diretorio in execucao.glob("tentativa-*"):
        match = TENTATIVA_RE.fullmatch(diretorio.name)
        manifesto_path = diretorio / "manifesto.json"
        if not match or not manifesto_path.is_file():
            continue
        saida.append((int(match.group(1)), diretorio, carregar_json(manifesto_path)))
    return sorted(saida, key=lambda item: item[0])


def _selecionar_tentativa(execucao: Path, condicao: str) -> tuple[int, Path, dict[str, Any], Path]:
    candidatas: list[tuple[int, Path, dict[str, Any], Path]] = []
    for numero, diretorio, manifesto in _tentativas(execucao):
        arquivo = diretorio / ("normalizado.json" if condicao in ("C1", "C2") else "resposta.json")
        valida = (
            manifesto.get("finalidade") == "coleta"
            and manifesto.get("estado") == "concluida"
            and arquivo.is_file()
        )
        if condicao in CONDICOES_IA:
            valida = valida and manifesto.get("resposta_valida") is True
        if valida:
            candidatas.append((numero, diretorio, manifesto, arquivo))
    if not candidatas:
        raise ValueError(f"nenhuma tentativa válida e concluída em {execucao}")
    return candidatas[-1]


def _validar_artefato(manifesto: dict[str, Any], nome: str, caminho: Path) -> None:
    esperado = manifesto.get("artefatos_sha256", {}).get(nome)
    if not esperado:
        raise ValueError(f"hash ausente para {nome} em {caminho.parent}")
    observado = sha256_arquivo(caminho)
    if observado != esperado:
        raise ValueError(f"hash divergente para {caminho}: {observado} != {esperado}")


def _lista_achados(documento: Any, caminho: Path) -> list[dict[str, Any]]:
    if isinstance(documento, list):
        achados = documento
    elif isinstance(documento, dict) and {
        "arquivo",
        "linha_inicial",
        "cwe",
        "severidade",
        "descricao",
        "recomendacao",
    }.issubset(documento):
        # O extrator das coletas preservou 20 respostas unitárias como objeto,
        # embora o contrato lógico seja uma lista de achados.
        achados = [documento]
    elif isinstance(documento, dict) and isinstance(documento.get("value"), list):
        achados = documento["value"]
    else:
        raise ValueError(f"lista de achados inválida em {caminho}")
    if not all(isinstance(item, dict) for item in achados):
        raise ValueError(f"achado não é objeto em {caminho}")
    return achados


def _normalizar_achados(
    itens: list[dict[str, Any]], condicao: str, execucao_id: str
) -> list[NormalisedFinding]:
    ferramenta = {"C1": "bandit", "C2": "semgrep", "C3": "cursor", "C4": "codex", "C5": "cursor", "C6": "codex"}[condicao]
    achados: list[NormalisedFinding] = []
    for indice, item in enumerate(itens, start=1):
        arquivo = item.get("arquivo")
        if isinstance(arquivo, str):
            arquivo = normalise_path(arquivo)
        else:
            arquivo = ""
        cwe = item.get("cwe")
        linha = item.get("linha_inicial")
        achados.append(
            NormalisedFinding(
                file=arquivo,
                cwe=cwe if isinstance(cwe, str) else "",
                line=linha if isinstance(linha, int) else None,
                function=None,
                severity=item.get("severidade"),
                rule_id=item.get("regra"),
                message=item.get("descricao"),
                scanner=ferramenta,
                finding_id=f"{execucao_id}-A{indice:04d}",
            )
        )
    return achados


def carregar_execucoes(repo: Path) -> tuple[list[ExecucaoSelecionada], dict[str, dict[str, Any]], dict[str, Any]]:
    """Seleciona a última tentativa válida de cada unidade prevista.

    A seleção usa apenas estado, finalidade, validade estrutural e integridade
    do artefato. Nenhum dado do oracle participa desta etapa.
    """
    alvos, lock = carregar_lock_corpus(repo)
    execucoes: list[ExecucaoSelecionada] = []
    vistos: set[tuple[str, str, int]] = set()

    for condicao in CONDICOES:
        for diretorio_execucao in _diretorios_execucao(repo, condicao):
            match = EXECUCAO_RE.fullmatch(diretorio_execucao.name)
            if not match or match.group(1) != condicao:
                continue
            alvo = match.group(2)
            repeticao = int(match.group(3))
            if alvo not in alvos:
                continue
            chave = (condicao, alvo, repeticao)
            if chave in vistos:
                raise ValueError(f"unidade duplicada: {chave}")

            tentativa, diretorio, manifesto, arquivo_achados = _selecionar_tentativa(
                diretorio_execucao, condicao
            )
            nome_artefato = arquivo_achados.name
            _validar_artefato(manifesto, nome_artefato, arquivo_achados)
            if manifesto.get("execucao_id") != diretorio_execucao.name:
                raise ValueError(f"execucao_id divergente em {diretorio}")
            if manifesto.get("entrada_commit") != alvos[alvo]["commit"]:
                raise ValueError(f"commit de entrada divergente em {diretorio}")
            if manifesto.get("condicao") != condicao or manifesto.get("alvo") != alvo:
                raise ValueError(f"identidade divergente em {diretorio}")
            if int(manifesto.get("repeticao", 0)) != repeticao:
                raise ValueError(f"repetição divergente em {diretorio}")
            if int(manifesto.get("tentativa", 0)) != tentativa:
                raise ValueError(f"tentativa divergente em {diretorio}")

            itens = _lista_achados(carregar_json(arquivo_achados), arquivo_achados)
            execucoes.append(
                ExecucaoSelecionada(
                    condicao=condicao,
                    alvo=alvo,
                    repeticao=repeticao,
                    tentativa=tentativa,
                    diretorio=diretorio,
                    manifesto=manifesto,
                    achados_brutos=itens,
                    achados=_normalizar_achados(itens, condicao, diretorio_execucao.name),
                )
            )
            vistos.add(chave)

    esperadas = {
        (condicao, alvo, repeticao)
        for condicao in CONDICOES
        for alvo in alvos
        for repeticao in (range(1, 4) if condicao in CONDICOES_IA else (1,))
    }
    ausentes = sorted(esperadas - vistos)
    extras = sorted(vistos - esperadas)
    if ausentes or extras:
        raise ValueError(f"grade de execução inválida; ausentes={ausentes[:10]}, extras={extras[:10]}")
    if len(execucoes) != 364:
        raise ValueError(f"esperadas 364 unidades selecionadas; encontradas {len(execucoes)}")
    return sorted(execucoes, key=lambda item: (item.condicao, item.alvo, item.repeticao)), alvos, lock


def avaliar_execucoes(
    repo: Path,
    execucoes: list[ExecucaoSelecionada],
    alvos: dict[str, dict[str, Any]],
) -> tuple[list[ExecucaoAvaliada], dict[str, Any]]:
    familias = carregar_json(
        repo / "runner" / "avaliacao" / "vendor" / "config" / "cwe-families.json"
    )
    cache_gt: dict[str, dict[str, Any]] = {}
    avaliadas: list[ExecucaoAvaliada] = []
    for execucao in execucoes:
        if execucao.alvo not in cache_gt:
            gt_path = (
                repo
                / "oracle"
                / "realvuln-v1"
                / "ground-truth"
                / alvos[execucao.alvo]["realvuln_id"]
                / "ground-truth.json"
            )
            cache_gt[execucao.alvo] = load_ground_truth(str(gt_path))
        gt = cache_gt[execucao.alvo]
        correspondencias = match_findings(execucao.achados, gt)
        scorecard = compute_scorecard(
            repo_id=gt["repo_id"],
            scanner=execucao.condicao,
            timestamp=str(execucao.manifesto.get("termino_utc", "")),
            match_results=correspondencias,
            cwe_families=familias,
        )
        avaliadas.append(
            ExecucaoAvaliada(
                execucao=execucao,
                ground_truth=gt,
                correspondencias=correspondencias,
                scorecard=scorecard,
            )
        )
    return avaliadas, familias
