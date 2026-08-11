# Especificação: ambiente e primeira execução SAST

**Status:** APROVADA
**Aprovação:** solicitação do usuário em 2026-08-10 para usar os capítulos `.tex` como spec/design, criar tasks e executar o desenvolvimento.
**Fontes de requisitos:** `06-metodologia.tex`, `07-desenvolvimento.tex`.

## Problema

O TCC define um protocolo comparativo e uma arquitetura, mas ainda não possui ambiente, código, imagem, testes ou evidências de execução. O primeiro incremento deve criar uma base segura e reproduzível, validar fontes antes de baixar e provar C1/C2 em uma execução descartável sem contaminar o corpus ou expor o oracle.

## Metas

- [ ] Inicializar e documentar o ambiente sem instalar Python no host.
- [ ] Fixar todas as entradas externas por origem oficial, versão/commit/digest e hash.
- [ ] Executar Bandit e Semgrep em contêiner endurecido sobre fixture externa ao corpus.
- [ ] Executar fumaça descartável em um alvo RealVuln fixado e registrar evidências.
- [ ] Atualizar o Capítulo 7 apenas com valores observados e verificáveis.

## Fora de escopo

| Recurso | Razão |
|---|---|
| Coleta completa de C1/C2 | pertence ao marco M2, depois da fumaça e do congelamento do ambiente |
| Execução de Cursor/Codex e C3--C6 | depende do piloto e pertence ao marco M3 |
| Cálculo final de métricas e preenchimento do Capítulo 8 | depende da coleta completa |
| Execução das aplicações vulneráveis | é proibida pelo protocolo e desnecessária ao SAST |
| Publicação das regras Semgrep atuais | a licença oficial v1.0 veda redistribuição |

## Histórias de usuário

### P1: Ambiente confiável e reproduzível ⭐ MVP

**História:** Como pesquisador, quero construir o ambiente a partir de fontes oficiais fixadas para que outra pessoa possa reproduzir exatamente as ferramentas usadas.

**Critérios de aceite:**

1. QUANDO o bootstrap consultar o RealVuln ENTÃO o sistema DEVERÁ aceitar somente o commit `d98e9fc91273702c9547663b6906d1fc494d4fcc` da origem oficial.
2. QUANDO a imagem for construída ENTÃO o sistema DEVERÁ usar Python por tag completa e digest e instalar Bandit/Semgrep por lock com hashes.
3. QUANDO uma origem, licença, hash ou revisão divergir do manifesto ENTÃO o sistema DEVERÁ parar antes de executar o artefato.
4. QUANDO o repositório for transferido para um remoto ENTÃO credenciais, corpus, oracle, resultados e regras não redistribuíveis NÃO DEVERÃO estar rastreados.

**Teste independente:** validar o manifesto, construir a imagem e comparar versões/digests observados aos valores fixados.

### P1: Primeiras execuções SAST isoladas ⭐ MVP

**História:** Como pesquisador, quero executar Bandit e Semgrep de maneira isolada para comprovar os comandos e adaptadores antes da coleta.

**Critérios de aceite:**

1. QUANDO C1 ou C2 iniciar ENTÃO o alvo DEVERÁ estar montado somente para leitura, sem rede, com usuário não privilegiado, capacidades removidas e saída separada.
2. QUANDO a ferramenta encerrar ENTÃO a saída original, comando, versões, início, término, duração e código de saída DEVERÃO ser preservados antes da normalização.
3. QUANDO um campo não estiver presente na saída nativa ENTÃO o adaptador DEVERÁ manter `null`, sem consultar ground truth ou inventar valor.
4. QUANDO a fixture externa contiver padrões detectáveis ENTÃO ambos os adaptadores DEVERÃO produzir JSON válido no esquema comum.

**Teste independente:** executar a fixture própria, validar os brutos e o normalizado e inspecionar o contêiner.

### P2: Fumaça descartável no benchmark

**História:** Como pesquisador, quero uma execução ponta a ponta em um alvo real para detectar falhas de integração antes de congelar a coleta.

**Critérios de aceite:**

1. QUANDO o alvo de fumaça for adquirido ENTÃO sua URL e commit DEVERÃO corresponder ao manifesto oficial v1.0.
2. QUANDO C1 e C2 receberem o alvo ENTÃO os inventários de entrada DEVERÃO ter o mesmo SHA-256.
3. QUANDO a fumaça terminar ENTÃO o sistema DEVERÁ marcar a evidência como `descartavel` e impedir sua inclusão na coleta principal.
4. QUANDO a fumaça for descartada ENTÃO o alvo DEVERÁ poder ser regenerado com o mesmo hash.

**Teste independente:** adquirir um alvo, executar C1/C2, comparar inventários, remover a área temporária e regenerá-la.

## Casos extremos

- QUANDO Docker não estiver disponível ENTÃO o bootstrap DEVERÁ falhar sem instalar alternativas no host.
- QUANDO Git, WSL ou Docker estiverem abaixo das versões recomendadas ENTÃO o preflight DEVERÁ registrar o risco; uma exceção explícita e datada PODERÁ permitir a continuação sem desativar os demais controles.
- QUANDO a branch atual do RealVuln apontar para v2 ENTÃO ela DEVERÁ ser ignorada em favor do commit v1.0.
- QUANDO o metadado de licença do RealVuln divergir do arquivo `LICENSE` ENTÃO a divergência DEVERÁ ser registrada, sem conclusão jurídica inventada.
- QUANDO as regras Semgrep não puderem ser usadas ou adquiridas sob seus termos ENTÃO C2 DEVERÁ permanecer bloqueada e nenhuma regra substituta será escolhida depois de observar o corpus.
- QUANDO a ferramenta retornar JSON vazio ENTÃO a execução DEVERÁ ser válida e conter zero achados.
- QUANDO houver JSON inválido ou código de saída inesperado ENTÃO o bruto DEVERÁ ser preservado e a execução marcada como falha.

## Rastreabilidade de requisitos

| ID | Requisito | Origem | Status |
|---|---|---|---|
| AMB-01 | Git local seguro e transferível | solicitação do usuário; `07:46` | Verificado |
| AMB-02 | RealVuln v1.0 fixado e validado | `06:64-70`, `07:50-54` | Verificado em T02 |
| AMB-03 | Proveniência/licença/hash antes do download | `06:70`, `07:46,54,130` | Parcial em T02; lock transitivo em T03 |
| AMB-04 | Python e ferramentas em imagem imutável | `06:118`, `07:128-132` | Em tarefas |
| AMB-05 | Execução SAST endurecida e offline | `06:118`, `07:132` | Em tarefas |
| AMB-06 | Saída bruta preservada antes da normalização | `07:98-124` | Em tarefas |
| AMB-07 | Esquema comum sem inferência | `06:126-130`, `07:100-124` | Em tarefas |
| AMB-08 | Adaptador Bandit | `07:134-142` | Em tarefas |
| AMB-09 | Adaptador Semgrep com regras locais fixadas | `07:144-153` | Em tarefas |
| AMB-10 | Testes artificiais externos ao corpus | `06:130`, `07:189-191` | Em tarefas |
| AMB-11 | Fumaça descartável e regenerável | `07:193` | Em tarefas |
| AMB-12 | Registro real no Capítulo 7 | `07:195-221` | Em tarefas |
| AMB-13 | Preflight do host e exceção de risco auditável | decisão AD-005 | Verificado em T02 |

**Cobertura:** 13 requisitos, 13 mapeados para tarefas, 0 não mapeados.

## Critérios de sucesso

- [ ] Gate `build` com zero falhas e sem testes ignorados.
- [ ] Versões observadas iguais às fixadas e imagem identificada por digest.
- [ ] C1 e C2 produzem bruto e normalizado sobre fixture externa.
- [ ] Fumaça RealVuln marcada como descartável, com hashes de entrada iguais.
- [ ] Capítulo 7 contém apenas dados copiados de evidências geradas.
