# Estado

**Última atualização:** 2026-08-11T00:18:08-03:00
**Trabalho atual:** ambiente-e-primeira-execucao-sast — T09

---

## Decisões recentes

### AD-001: Capítulos como especificação aprovada (2026-08-10)

**Decisão:** tratar `06-metodologia.tex` como especificação do protocolo e `07-desenvolvimento.tex` como design aprovado; criar tasks rastreáveis antes do código.
**Razão:** o usuário determinou explicitamente que os `.tex` servem como spec e design e solicitou a implementação.
**Trade-off:** inconsistências encontradas serão registradas e corrigidas de forma explícita, não presumidas silenciosamente.
**Impacto:** toda tarefa referencia requisito e seção de origem.

### AD-002: Python somente em ambiente conteinerizado (2026-08-10)

**Decisão:** não instalar Python diretamente no Windows; executar harness, testes e SAST em imagem Docker fixada.
**Razão:** o host não possui Python funcional, mas possui Docker operacional; a abordagem reduz deriva e software instalado no host.
**Trade-off:** os comandos de desenvolvimento dependem do Docker Desktop em execução.
**Impacto:** os gates de teste usam Docker e a imagem contém Python, Bandit e Semgrep.

### AD-003: RealVuln v1.0 fixado por commit (2026-08-10)

**Decisão:** usar `https://github.com/kolega-ai/Real-Vuln-Benchmark.git`, tag `v1.0`, commit desembrulhado `d98e9fc91273702c9547663b6906d1fc494d4fcc`.
**Razão:** a branch atual já corresponde ao v2 e não é comparável ao corpus de 26 repositórios/796 entradas descrito no TCC.
**Trade-off:** melhorias posteriores do benchmark não entram na coleta principal.
**Impacto:** o bootstrap deve rejeitar qualquer revisão diferente.

### AD-004: Regras Semgrep não serão redistribuídas (2026-08-10)

**Decisão:** registrar origem, commit e hash das regras, adquiri-las em diretório ignorado e não enviá-las ao futuro remoto.
**Razão:** a licença atual das Community Edition Rules permite uso em condições específicas, mas proíbe redistribuição.
**Trade-off:** a reprodução exige uma etapa de aquisição a partir da fonte oficial.
**Impacto:** o capítulo de desenvolvimento deve publicar o procedimento e os hashes, não uma cópia das regras.

### AD-005: Aceitar versões atuais do host com isolamento compensatório (2026-08-10)

**Decisão:** continuar o experimento com Git for Windows 2.46.2, WSL 2.0.14.0 e Docker Desktop 4.38.0/Engine 27.5.1, conforme autorização explícita do usuário em 2026-08-10.
**Razão:** o usuário aceitou as vulnerabilidades conhecidas desses componentes do sistema e autorizou o bypass da recomendação de atualização.
**Trade-off:** permanece um risco residual maior no host durante aquisição e análise do corpus vulnerável.
**Impacto:** o preflight emitirá aviso auditável, mas não bloqueará por versão; validação de origem/hash, ausência de hooks/submódulos, rede desligada, montagem somente leitura, usuário não root, capabilities removidas e `no-new-privileges` continuam obrigatórios.

### AD-006: Separar classificação bruta, forma normalizada e ciclo de falha (2026-08-10)

**Decisão:** o Achado v1 mantém campos `*_original` ao lado das classificações normalizadas; o Manifesto v1 usa somente os quatro estados do Capítulo 7, registra `timeout` em `falha_tipo` e exige artefato preservado antes de aceitar `concluida`.
**Razão:** os adaptadores precisam demonstrar que não inventaram classificação, e timeout descreve a causa da falha, não um estado adicional da fila.
**Trade-off:** o contrato possui mais campos nulos explícitos e validações condicionais.
**Impacto:** T05/T06 devem preencher valores originais diretamente da saída nativa e deixar normalizações sem regra congelada como `null`.

### AD-007: Orquestrar Docker no host e montar regras somente em C2 (2026-08-10)

**Decisão:** o PowerShell do host cria o contêiner pelo ID local da imagem; `runner.executor_sast` roda dentro dele e chama somente Bandit ou Semgrep. As regras Semgrep verificadas permanecem fora da imagem e são montadas como somente leitura apenas em C2.
**Razão:** o host não possui Python, o contêiner não deve receber `docker.sock` e a licença das regras impede redistribuir sua cópia no remoto ou na imagem compartilhável.
**Trade-off:** C2 possui uma montagem adicional e o hash do bundle precisa ser validado em cada execução; o texto prospectivo de `07-desenvolvimento.tex` que promete copiar regras para a imagem deve ser corrigido em T10.
**Impacto:** a imagem é reconstruída com o executor atualizado, executada com `--pull never`, recebe somente `/entrada:ro`, `/saida:rw` e, em C2, `/opt/regras-semgrep:ro`; timeout interno e watchdog total do host impedem bloqueio indefinido.

## Bloqueadores ativos

Nenhum bloqueador técnico impede o primeiro marco.

## Lições aprendidas

### L-001: A tag v1.0 difere da branch atual do benchmark

**Contexto:** a página principal do RealVuln apresenta v2.0.0 e 66 repositórios.
**Problema:** baixar `main` invalidaria o corpus descrito no TCC.
**Solução:** resolver a tag anotada e fixar o commit desembrulhado no manifesto local.
**Previne:** deriva silenciosa do corpus e números incompatíveis nos capítulos.

### L-002: Metadados de licença do RealVuln v1.0 divergem

**Contexto:** em v1.0, `pyproject.toml` declara Apache-2.0, enquanto o arquivo `LICENSE` contém MIT.
**Problema:** não é seguro afirmar uma licença única sem registrar a divergência.
**Solução:** preservar os arquivos originais, registrar a inconsistência e evitar redistribuição desnecessária do corpus.
**Previne:** afirmação jurídica não sustentada e perda de avisos upstream.

## Tarefas rápidas concluídas

| # | Descrição | Data | Commit | Status |
|---|---|---|---|---|
| 001 | Inicializar Git local e excluir artefatos inseguros/gerados | 2026-08-10 | `5bdadd3` | ✅ Concluída |
| 002 | Validar lock de fontes, hash das regras e exceção do host | 2026-08-10 | `feat(fontes): validar manifesto de proveniência` | ✅ Concluída |
| 003 | Construir e validar a imagem SAST fixada | 2026-08-10 | `build(docker): fixar ambiente SAST reproduzível` | ✅ Concluída |
| 004 | Definir Achado v1 e ManifestoExecucao v1 | 2026-08-10 | `feat(esquema): definir achado e execução versionados` | ✅ Concluída |
| 005 | Normalizar saída Bandit 1.9.4 sem inferência | 2026-08-10 | `feat(adaptadores): normalizar saída do Bandit` | ✅ Concluída |
| 006 | Normalizar saída Semgrep CE 1.172.0 sem inferência | 2026-08-10 | `feat(adaptadores): normalizar saída do Semgrep` | ✅ Concluída |
| 007 | Isolar C1/C2 em contêiner endurecido e preservar tentativas | 2026-08-11 | `feat(execucao): isolar condições SAST em Docker` | ✅ Concluída |
| 008 | Validar C1/C2 reais sobre fixture sintética não executável | 2026-08-11 | `test(fumaca): validar SAST fora do corpus` | ✅ Concluída |

## Ideias adiadas

- [ ] Suporte a RealVuln v2 em um experimento independente — capturado durante: planejamento M1.
- [ ] CI no remoto — capturado durante: inicialização Git.

## Todos

- [x] Fixar e testar o conjunto exato de regras públicas Python do Semgrep.
- [ ] Registrar o horário real e o digest da imagem produzida no relatório de fumaça.
- [ ] Corrigir no texto a promessa de publicar arquivos de regras incompatível com sua licença atual.
- [ ] Reavaliar a exceção de versões do host antes da coleta definitiva e registrar se foi mantida ou revogada.
- [ ] Revisar as licenças dos 67 pacotes transitivos antes de distribuir a imagem; o lock pode permanecer público.

## Preferências

**Orientação sobre modelos exibida:** nunca
