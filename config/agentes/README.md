# Protocolo comum dos agentes de IA

Cursor (C3/C5) e Codex (C4/C6) recebem o mesmo prompt-base, no mesmo arquivo:
`prompt-relatorio-ia-v1.txt`. Não existem instruções específicas por produto.
Os dois perfis apontam para esse caminho e para o mesmo SHA-256; os executores
interrompem a tarefa se o hash observado divergir da configuração congelada.

Nas condições isoladas, C3 e C4 recebem exatamente o mesmo prompt efetivo para
um mesmo alvo. Nas condições híbridas, C5 e C6 recebem o mesmo prompt-base e os
mesmos bytes de `alertas-sast.json`. Diferenças de CLI, sandbox e metadados são
responsabilidade dos adaptadores e não alteram a instrução de análise.

C6 possui configuração própria em `codex-c6-v1.json`, pois sua entrada inclui
alertas. O arquivo `alertas-sast-c6-v1.lock.json` congela SHA-256, contagem e
tentativas-fonte dos 26 arquivos produzidos a partir de C1/C2. Planejamento e
execução recusam qualquer arquivo que não corresponda ao lock.

O schema comum é aplicado localmente às respostas dos dois produtos. Ele não é
enviado como `--output-schema` ao Codex, pois a saída estruturada dessa CLI
exige objeto na raiz, enquanto o protocolo experimental e o Cursor usam uma
lista JSON. Aplicar essa restrição somente ao Codex também criaria tratamento
assimétrico. Respostas brutas são preservadas antes da validação comum.

O `codex exec --json` não garante um campo de modelo efetivamente servido nos
eventos documentados. Quando ele não aparece, o manifesto mantém
`modelo_exibido=null` e registra
`modelo_verificacao=nao_exposto_jsonl_codex`; o adaptador nunca copia o valor
solicitado para o campo observado. Cursor continua exigindo o modelo no evento
de sistema do piloto.

## Decisões de elaboração do prompt

O contrato foi organizado em objetivo, evidência mínima, invariantes, critérios
de exclusão, tratamento dos alertas, taxonomia, severidade e condição de parada.
O conteúdo dinâmico fica no fim e é delimitado como dado não confiável. O
relatório exige uma cadeia plausível entre origem controlável, fluxo, operação
sensível ou controle ausente e impacto; lacunas não podem ser preenchidas com
suposições externas.

A taxonomia segue a orientação de mapeamento de causa raiz do CWE: usar Base ou
Variant quando possível, evitar categorias e preferir `null` a uma associação
sem sustentação. Alertas de Bandit/Semgrep são pistas, não rótulos adjudicados.

## Skills avaliadas

- `openai/skills: security-best-practices`: pertinente para Python e revisão de
  segurança; seus princípios de contexto, controles e evidência foram adaptados
  ao prompt comum.
- `openai/plugins: codex-security`: inadequada para as execuções C3–C6 porque
  introduz fases, ferramentas e artefatos exclusivos do Codex.
- skills SAST genéricas que executam Bandit, Semgrep, CodeQL ou comandos locais:
  incompatíveis com a proibição experimental de executar analisadores.

Nenhuma skill externa é carregada durante a coleta. Instalá-la em somente um
produto criaria um tratamento diferente e confundiria o efeito comparado. Toda
orientação que afeta a análise fica, portanto, explícita no prompt compartilhado
e versionado.

O mapa completo de executores, arquivos entregues e controles de restrição está
em [`docs/FLUXO-E-RASTREABILIDADE.md`](../../docs/FLUXO-E-RASTREABILIDADE.md).
O significado de `Read(**)`, o diretório efetivo do Cursor e a localização das
saídas C3/C5 estão detalhados em
[`docs/ISOLAMENTO-E-SAIDAS-CURSOR.md`](../../docs/ISOLAMENTO-E-SAIDAS-CURSOR.md).

## Referências de elaboração

- OpenAI, *Model guidance — Prompting best practices*:
  https://developers.openai.com/api/docs/guides/latest-model
- OpenAI, `security-best-practices`:
  https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices
- MITRE, *CVE → CWE Root Cause Mapping Guidance*:
  https://cwe.mitre.org/documents/cwe_usage/guidance.html
- OWASP, *Code Review Guide*:
  https://owasp.org/projects/code-review-guide

Essas referências orientam o instrumento; não são disponibilizadas aos agentes
durante as execuções e não fazem parte da evidência usada para julgar achados.
