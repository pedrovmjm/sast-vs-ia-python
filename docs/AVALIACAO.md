# Avaliação dos resultados

Esta etapa é deliberadamente separada da coleta. Os scripts deste diretório
podem consultar `oracle/`, mas os executores C1--C6 e a regra que escolhe a
tentativa válida não usam o *ground truth*.

## Regras fixadas

1. A unidade de avaliação é a entrada rotulada do RealVuln v1.0. A unidade de
   reamostragem é o repositório completo.
2. A seleção usa a tentativa de maior número que esteja concluída, pertença à
   finalidade `coleta`, possua resposta estruturalmente válida e tenha o hash
   do artefato confirmado. A seleção ocorre antes da abertura do oracle.
3. O algoritmo de correspondência é o código oficial do commit
   `d98e9fc91273702c9547663b6906d1fc494d4fcc`, copiado sem alteração em
   `runner/avaliacao/vendor/`. Os IDs de blob estão em `SOURCE.json`.
4. A correspondência exige caminho normalizado, CWE aceitável e linha dentro
   da faixa oficial com tolerância de 10 linhas. Localizações alternativas
   públicas também são consideradas. Cada entrada do *ground truth* só pode
   ser consumida uma vez e, em ambiguidades, uma entrada vulnerável precede
   uma armadilha co-localizada.
5. Um achado associado a entrada vulnerável é TP; associado a armadilha ou
   não associado é FP; vulnerabilidade ignorada é FN; armadilha ignorada é TN.
6. A pontuação global é estrita e usa microcontagem. Falhas completas não
   podem ser removidas do denominador. A coleta atual contém as 364 unidades
   válidas previstas; qualquer ausência futura interrompe o carregamento em
   vez de ser confundida com arquivo vazio.
7. C1 e C2 são avaliadas uma vez. C3--C6 são avaliadas separadamente em R1,
   R2 e R3. O resumo de cada condição de IA é a média das três métricas
   microcontadas, sem unir achados e sem voto majoritário.
8. Precisão, *recall*, F1, F2, F3 e taxa de FP são reportadas. O arquivo
   oficial `scorer/metrics.py` da revisão fixada contém F2 e F3, embora trechos
   da documentação upstream alternem qual delas é chamada de principal. O
   trabalho mantém F3 como medida principal previamente especificada e
   publica ambas.
9. Os intervalos de 95% usam *bootstrap* percentil com 10.000 reamostragens de
   repositórios. A mesma amostra é aplicada às condições comparadas. Os deltas
   C5--C3 e C6--C4 são, portanto, pareados por repositório e repetição.
10. A estabilidade é a frequência de detecção de cada entrada vulnerável em
    zero, uma, duas ou três repetições. Essa frequência não é convertida em
    decisão por maioria.
11. Tempos são descritos por mediana, Q1, Q3, mínimo e máximo. Tokens são
    reportados apenas quando fornecidos pelo produto e nunca são estimados.
12. Severidade ausente reduz a cobertura de priorização e não é inferida. A
    concordância usa a escala ordinal baixa--média--alta--crítica e Kappa
    quadrático ponderado.
13. A amostra qualitativa usa apenas R1. Sorteia até 20 entradas detectadas por
    todas as condições e completa cada condição até 50 TPs por amostragem
    estratificada por CWE e severidade. A semente e a chave de cegamento são
    publicadas. Um recorte estratificado de pelo menos 20% é preparado para o
    segundo avaliador.
14. O bloco complementar Cursor Auto/Codex Terra não foi executado e não pode
    ser combinado com o bloco principal Luna.

Achados globais sem associação contam como FP, mas não podem ser atribuídos a
uma CWE ou severidade de referência. Por isso, as tabelas estratificadas deixam
essa parcela fora do estrato, enquanto as métricas globais preservam a
penalização integral.

## Execução

O host não precisa ter bibliotecas estatísticas ou de gráficos. Os scripts usam
somente a biblioteca padrão do Python e podem ser executados com a imagem já
fixada do estudo:

```powershell
docker run --rm --network none --entrypoint python `
  -v "${PWD}:/workspace:ro" `
  -v "${PWD}/evidencias/avaliacao:/saida" `
  tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0 `
  /workspace/scripts/avaliar-resultados.py `
  --repo /workspace --saida /saida --bootstrap 10000 --semente 20260928

docker run --rm --network none --entrypoint python `
  -v "${PWD}:/workspace:ro" `
  -v "${PWD}/evidencias/avaliacao:/saida" `
  tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0 `
  /workspace/scripts/gerar-graficos-avaliacao.py `
  --dados /saida --saida /saida/graficos
```

O primeiro comando gera CSVs auditáveis, `resumo.json`, um manifesto com os
hashes das saídas, uma tabela LaTeX e os formulários cegos da rubrica. O segundo
gera SVGs vetoriais adequados para inclusão na monografia.

Depois que os dois avaliadores preencherem suas respectivas planilhas, execute
o analisador na mesma imagem fixada:

```powershell
docker run --rm --network none --entrypoint python `
  -v "${PWD}:/workspace:ro" `
  -v "${PWD}/evidencias/avaliacao:/saida" `
  tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0 `
  /workspace/scripts/analisar-rubrica.py `
  --principal /saida/amostra-qualitativa-cega.csv `
  --segundo /saida/amostra-segundo-avaliador.csv `
  --chave /saida/chave-amostra-qualitativa.csv `
  --saida /saida/rubrica
```

Esse passo valida as escalas, resume separadamente os recortes comum e
estratificado, calcula Kappa ponderado para as dimensões ordinais, concordância
e Kappa não ponderado para os itens binários e produz o índice de Flesch como
medida secundária.

## Artefatos principais

- `metricas-por-repeticao.csv`: microcontagens de cada repetição;
- `metricas-condicoes.csv`: estimativas, IC95%, amplitude e desvio entre
  repetições;
- `comparacoes-pareadas.csv`: deltas C5--C3 e C6--C4;
- `correspondencias-achados.csv`: classificação auditável de cada alerta;
- `metricas-por-cwe.csv` e `metricas-por-severidade.csv`: recortes do oracle;
- `estabilidade-entradas.csv`: frequência 0--3 de cada vulnerabilidade;
- `operacional.csv` e `priorizacao.csv`: medidas complementares;
- `amostra-qualitativa-cega.csv`: formulário sem identificação da condição;
- `chave-amostra-qualitativa.csv`: chave separada para abertura posterior;
- `amostra-segundo-avaliador.csv`: subconjunto independente mínimo de 20%;
- `manifesto-avaliacao.json`: proveniência, configuração e hashes.
