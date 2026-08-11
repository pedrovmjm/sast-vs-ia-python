# Roadmap

**Marco atual:** M2 — corpus, fila e coleta C1/C2
**Status:** PLANEJADO

---

## M0 — Fundação do projeto

**Meta:** preservar os capítulos existentes e estabelecer planejamento rastreável em Git local.
**Alvo:** repositório `main` com commit inicial e documentos SPC aprovados.

### Recursos

**Git local e proteção de artefatos** — COMPLETO

- histórico local sem remoto;
- dados adquiridos, resultados, credenciais e `Zone.Identifier` fora do commit;
- identidade Git saneada apenas no escopo local.

**Planejamento orientado às especificações** — COMPLETO

- visão, decisões e roadmap em `.specs/project/`;
- especificação, design e tarefas do primeiro incremento;
- requisitos rastreados até testes e evidências.

---

## M1 — Ambiente e primeira execução SAST

**Meta:** construir o ambiente reprodutível, validar adaptadores fora do corpus e executar fumaça descartável de C1 e C2.
**Alvo:** imagem fixada, testes verdes e relatório de primeira execução com hashes e versões reais.

### Recursos

**Cadeia de suprimentos verificável** — COMPLETO

- origens oficiais, versões, licenças, commits, digests e hashes documentados;
- RealVuln v1.0 adquirido pelo commit, nunca pela branch atual;
- regras Semgrep obtidas localmente sem redistribuição indevida.

**Executores e adaptadores SAST** — COMPLETO

- contêiner sem rede, sem privilégios e com alvo somente leitura;
- Bandit e Semgrep com saídas brutas preservadas;
- achados convertidos ao esquema comum sem consultar o oracle.

**Fumaça descartável** — COMPLETO

- fixture artificial externa ao corpus;
- um alvo RealVuln regenerável, sem incorporar o resultado à coleta;
- evidência de versões, comandos, duração, códigos de saída e hashes.

---

## M2 — Corpus, fila e coleta C1/C2

**Meta:** adquirir e sanitizar os 26 alvos, formar a fila e concluir as condições determinísticas.

### Recursos

**Corpus verificável** — PLANEJADO

**Orquestração retomável** — PLANEJADO

**Coleta Bandit e Semgrep** — PLANEJADO

---

## M3 — Agentes e condições híbridas

**Meta:** executar C3--C6 com sessões novas, permissões equivalentes e três repetições por alvo.

### Recursos

**Contrato JSON e prompts versionados** — PLANEJADO

**Cursor e Codex isolados** — PLANEJADO

**União SAST e execução híbrida** — PLANEJADO

---

## M4 — Pontuação, análise e redação final

**Meta:** reutilizar o avaliador oficial, gerar métricas e preencher os capítulos com evidências reais.

### Recursos

**Pontuação e intervalos de confiança** — PLANEJADO

**Rubrica qualitativa e concordância** — PLANEJADO

**Tabelas, figuras e capítulos finais** — PLANEJADO

---

## Considerações futuras

- Reexecutar o protocolo sobre RealVuln v2 apenas como estudo separado, sem misturar resultados com v1.0.
- Adicionar CI no repositório remoto depois que ele for criado pelo usuário.
- Empacotar o harness para outros benchmarks somente após concluir o protocolo do TCC.
