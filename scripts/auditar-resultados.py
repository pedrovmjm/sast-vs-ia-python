"""Conferência independente dos artefatos recalculados, sem chamadas a modelos."""
import csv
import argparse
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--reavaliacao", type=Path,
                    default=ROOT / "build/auditoria-resultados-2026-10-06")
OUT = parser.parse_args().reavaliacao.resolve()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


checks = []
for new in sorted(OUT.glob("*.csv")):
    old = ROOT / "evidencias/avaliacao" / new.name
    a, b = read_csv(old), read_csv(new)
    differences = []
    for i, (left, right) in enumerate(zip(a, b)):
        for key in left:
            if left[key] != right[key]:
                try:
                    x, y = float(left[key]), float(right[key])
                    equivalent = math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)
                    error = abs(x - y)
                except ValueError:
                    equivalent, error = False, None
                differences.append(dict(linha=i + 2, campo=key, equivalente=equivalent, erro=error))
    checks.append(dict(arquivo=new.name, linhas=len(b), mesmo_sha256=digest(old) == digest(new),
                       equivalente=len(a) == len(b) and all(d["equivalente"] for d in differences),
                       diferencas=differences))
    assert checks[-1]["equivalente"], new.name

matches = read_csv(OUT / "correspondencias-achados.csv")
cards = read_csv(OUT / "metricas-por-repositorio.csv")
groups = defaultdict(list)
sets = defaultdict(set)
for row in matches:
    key = (row["condicao"], row["alvo"], row["repeticao"])
    groups[key].append(row)
    if row["classificacao"] == "TP":
        sets[(row["condicao"], row["repeticao"])].add((row["alvo"], row["ground_truth_id"]))
for row in cards:
    entries = groups[(row["condicao"], row["alvo"], row["repeticao"])]
    counts = Counter(e["classificacao"] for e in entries)
    ids = [e["ground_truth_id"] for e in entries if e["classificacao"] == "TP"]
    assert counts["TP"] == int(row["tp"]) and counts["FP"] == int(row["fp"])
    assert len(ids) == len(set(ids)), "TP duplicado"
    tp, fp, fn, tn = (int(row[k]) for k in ("tp", "fp", "fn", "tn"))
    div = lambda n, d: n / d if d else 0
    p, r = div(tp, tp + fp), div(tp, tp + fn)
    expected = {"precision": p, "recall": r, "f1": div(2*p*r, p+r),
                "f2": div(5*p*r, 4*p+r), "f3": div(10*p*r, 9*p+r), "fpr": div(fp, fp+tn)}
    assert all(math.isclose(float(row[k]), v, abs_tol=1e-12) for k, v in expected.items())

localization_issues = []
raw_structure_issues = []
null_lines = Counter()
for row in cards:
    if row["condicao"] in ("C1", "C2"):
        continue
    execution = f"{row['condicao']}-{row['alvo']}-R{int(row['repeticao']):02d}"
    attempt = ROOT / "resultados/ia/coleta" / execution / f"tentativa-{int(row['tentativa']):03d}"
    manifest = json.loads((attempt / "manifesto.json").read_text(encoding="utf-8-sig"))
    for filename, expected in manifest["artefatos_sha256"].items():
        assert digest(attempt / filename) == expected, f"hash divergente: {attempt / filename}"
    raw = json.loads((attempt / "resposta-bruta.txt").read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raw_structure_issues.append(execution)
        raw = [raw]
    extracted = json.loads((attempt / "resposta.json").read_text(encoding="utf-8-sig"))
    if isinstance(extracted, dict):
        extracted = extracted.get("value", [extracted])
    assert extracted == raw, f"extração divergente: {execution}"
    payload = json.loads((attempt / "payload-codigo.json").read_text(encoding="utf-8-sig"))
    lengths = {f["caminho"]: len(f["conteudo_utf8"].splitlines()) for f in payload["arquivos"]}
    for finding in raw:
        if set(finding) != {"arquivo", "linha_inicial", "linha_final", "cwe", "severidade", "descricao", "recomendacao"}:
            raw_structure_issues.append(execution)
        length = lengths.get(finding["arquivo"])
        errors = []
        if length is None:
            errors.append("arquivo ausente no payload")
        for key in ("linha_inicial", "linha_final"):
            value = finding[key]
            if value is None:
                null_lines[(row["condicao"], key)] += 1
            elif type(value) is not int or value < 1 or (length is not None and value > length):
                errors.append(f"{key}={value}; arquivo com {length} linhas")
        if finding["linha_inicial"] is not None and finding["linha_final"] is not None and finding["linha_final"] < finding["linha_inicial"]:
            errors.append("intervalo invertido")
        if errors:
            localization_issues.append(dict(execucao=execution, arquivo=finding["arquivo"], erros=errors))

# Contrastes exploratórios adicionais, com a mesma reamostragem pareada.
repositories = sorted({r["alvo"] for r in cards})
counts = {(r["condicao"], r["alvo"], int(r["repeticao"])):
          tuple(int(r[k]) for k in ("tp", "fp", "fn", "tn")) for r in cards}
rng = random.Random(20260928)
bootstrap_values = defaultdict(list)
for _ in range(10000):
    sample = [repositories[rng.randrange(26)] for _ in repositories]
    for condition in ("C1", "C2", "C3", "C4"):
        values = []
        for repetition in ((1,) if condition in ("C1", "C2") else (1, 2, 3)):
            tp, fp, fn, tn = [sum(counts[(condition, repo, repetition)][i] for repo in sample) for i in range(4)]
            p, r = div(tp, tp+fp), div(tp, tp+fn)
            values.append({"precision": p, "recall": r, "f3": div(10*p*r, 9*p+r)})
        for field in ("precision", "recall", "f3"):
            bootstrap_values[(condition, field)].append(statistics.mean(v[field] for v in values))


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered)-1)*fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper]-ordered[lower])*(position-lower)


metrics = {r["condicao"]: r for r in read_csv(OUT / "metricas-condicoes.csv")}
contrasts = []
for ia in ("C3", "C4"):
    for sast_condition in ("C1", "C2"):
        for field in ("precision", "recall", "f3"):
            values = [a-b for a,b in zip(bootstrap_values[(ia,field)], bootstrap_values[(sast_condition,field)])]
            contrasts.append(dict(comparacao=f"{ia}-{sast_condition}", metrica=field,
                                  delta_pp=(float(metrics[ia][field])-float(metrics[sast_condition][field]))*100,
                                  ic95_inferior_pp=percentile(values,.025)*100,
                                  ic95_superior_pp=percentile(values,.975)*100))

sast = sets[("C1", "1")] | sets[("C2", "1")]
complements = []
for condition in ("C3", "C4", "C5", "C6"):
    for repetition in ("1", "2", "3"):
        ia = sets[(condition, repetition)]
        complements.append(dict(condicao=condition, repeticao=int(repetition), tp=len(ia),
                                compartilhadas_sast=len(ia & sast), apenas_ia=len(ia - sast),
                                apenas_sast=len(sast - ia), uniao=len(ia | sast)))

quality_root = ROOT / "evidencias/avaliacao-qualitativa"
notes = read_csv(quality_root / "pontuacoes-condicoes.csv")
judgments = [json.loads(line) for line in (quality_root / "julgamentos.jsonl").read_text(encoding="utf-8").splitlines()]
index = {j["relatorio_id"]: j for j in judgments}
assert len(notes) == len(index) == 300
ordinal = ("correcao_tecnica", "localizacao", "acionabilidade")
binary = ("clareza_problema", "clareza_risco", "clareza_contexto", "clareza_concretude", "clareza_concisao")
evidence_issues = []
for n in notes:
    j = index[n["relatorio_id"]]
    for field in (*ordinal, *binary):
        assert float(n[field]) == j["criterios"][field]["nota"]
        assert j["criterios"][field]["justificativa"].strip()
        evidence = j["criterios"][field]["evidencias"]
        if not isinstance(evidence, list) or not evidence:
            evidence_issues.append((n["relatorio_id"], field, type(evidence).__name__))
    t, l, a = (int(n[k]) for k in ordinal)
    clarity = sum(int(n[k]) for k in binary)
    assert all(1 <= int(n[k]) <= 5 for k in ordinal)
    assert all(int(n[k]) in (0, 1) for k in binary)
    score = 25*((t-1)/4+(l-1)/4+(a-1)/4+clarity/5)
    assert math.isclose(float(n["score_total"]), score) and math.isclose(j["score_total"], score)

summary = read_csv(quality_root / "resumo-dimensoes.csv")
for row in summary:
    selected = [n for n in notes if n["condicao"] == row["condicao"] and
                (row["tipo_recorte"] == "total" or n["tipo_recorte"] == row["tipo_recorte"])]
    expected = statistics.mean(float(n[row["dimensao"]]) for n in selected)
    assert math.isclose(expected, float(row["media"]), abs_tol=1e-12)
common = {(n["condicao"], n["grupo_comum"]): n for n in notes if n["tipo_recorte"] == "comum"}
for row in read_csv(quality_root / "deltas-comuns.csv"):
    left, right = row["comparacao"].split("-")
    group, field = row["grupo_comum"], row["dimensao"]
    assert math.isclose(float(row["delta"]), float(common[(left, group)][field])-float(common[(right, group)][field]), abs_tol=1e-12)
for row in read_csv(quality_root / "resumo-deltas-comuns.csv"):
    left, right = row["comparacao"].split("-")
    field = row["dimensao"]
    values = [float(common[(left, group)][field])-float(common[(right, group)][field])
              for condition, group in common if condition == left]
    assert len(values) == 20 and math.isclose(statistics.mean(values), float(row["media"]), abs_tol=1e-12)

original_manifest = json.loads((ROOT / "evidencias/avaliacao/manifesto-avaliacao.json").read_text(encoding="utf-8"))
vendor = ROOT / "runner/avaliacao/vendor"
for relative, expected in original_manifest["realvuln"]["scorer_oficial"]["arquivos"].items():
    data = (vendor / relative).read_bytes()
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == expected

result = dict(unidades_reavaliadas=len(cards), arquivos_comparados=checks,
              formulas_independentes_conferidas=364,
              tp_unicos_sast_uniao=len(sast), complementaridade_por_repeticao=complements,
              notas_e_scores_conferidos=len(notes), deltas_qualitativos_conferidos=True,
              evidencias_qualitativas_vazias_ou_fora_do_tipo=len(evidence_issues),
              exemplos_problemas_evidencias=evidence_issues[:5], scorer_integridade=True,
              problemas_estrutura_bruta=raw_structure_issues,
              problemas_localizacao_selecionadas=localization_issues,
              linhas_ausentes=[dict(condicao=k[0], campo=k[1], quantidade=v) for k,v in null_lines.items()],
              contrastes_ia_sast_exploratorios=contrasts)
(OUT / "conferencia.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(unidades_reavaliadas=len(cards), arquivos_equivalentes=len(checks),
                      scores_conferidos=len(notes), problemas_estrutura=len(raw_structure_issues),
                      problemas_localizacao=len(localization_issues),
                      saida=str(OUT / "conferencia.json")), ensure_ascii=False))
