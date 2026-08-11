# Harness experimental para avaliação de SAST e agentes de IA

**Visão:** construir um repositório controlador reproduzível para comparar Bandit, Semgrep Community Edition, Cursor, OpenAI Codex e as combinações híbridas descritas nos capítulos do TCC.
**Para:** o autor do TCC, avaliadores acadêmicos e pesquisadores que desejem auditar ou reproduzir o protocolo.
**Resolve:** a ausência de uma execução controlada, rastreável e segura que transforme os Capítulos 6 e 7 em artefatos e evidências verificáveis.

## Metas

- Executar as seis condições C1--C6 sobre os 26 repositórios do RealVuln v1.0, preservando 100% das saídas brutas, metadados e falhas.
- Garantir que toda entrada de terceiros seja fixada por URL oficial, commit ou versão e hash antes da coleta.
- Provar, por testes automatizados, que `oracle/` não é exposto às ferramentas e que as cópias de um alvo são idênticas entre condições.
- Produzir TP, FP, FN, TN, precisão, recall, F1, F2, F3, taxa de falsos positivos, estabilidade, priorização, duração e tokens conforme a metodologia.
- Gerar evidências que permitam substituir os campos prospectivos dos Capítulos 7 e 8 por configuração e resultados reais.

## Stack técnica

**Base:**

- Linguagem: Python 3.12.13 executado em contêiner, compatível com o requisito Python >=3.10 do RealVuln v1.0.
- Conteinerização: Docker Desktop/Engine; imagem-base oficial fixada por digest.
- Persistência: arquivos JSON versionados por esquema e escritas atômicas; nenhum banco de dados no primeiro marco.
- Controle de versão: Git local, branch `main`, sem remoto nesta etapa.

**Dependências-chave:** RealVuln v1.0 no commit fixado, Bandit 1.9.4, Semgrep 1.172.0 e regras Community Edition fixadas por commit e hash.

## Escopo

**v1 inclui:**

- aquisição e verificação de proveniência do benchmark e das dependências;
- sanitização, inventário e identificação opaca dos alvos;
- fila rastreável e retomada idempotente;
- execução isolada de C1 e C2 e adaptação para esquema comum;
- roteiros controlados de C3--C6, composição híbrida e preservação dos metadados disponíveis;
- reutilização do avaliador oficial e geração das análises previstas no TCC.

**Explicitamente fora de escopo:**

- executar aplicações vulneráveis, seus testes ou suas dependências;
- alterar o ground truth ou reimplementar silenciosamente o algoritmo oficial de pontuação;
- criar regras SAST ajustadas aos repositórios depois de observar resultados;
- automatizar login, burlar cotas ou contornar permissões de Cursor ou Codex;
- publicar credenciais, sessões, regras cuja licença vede redistribuição ou código de terceiros sem licença compatível.

## Restrições

- O corpus contém código intencionalmente vulnerável e deve ser tratado como não confiável.
- A coleta de IA depende de licenças, disponibilidade de modelos, cotas e interfaces dos produtos no período do piloto.
- O `oracle/` e o avaliador não podem estar em caminho ancestral ou volume exposto às ferramentas.
- Downloads e imagens flutuantes como `main`, `latest` ou tags sem commit/digest não são aceitos na coleta.
- O bloco complementar somente será executado se puder cobrir o corpus integralmente.
