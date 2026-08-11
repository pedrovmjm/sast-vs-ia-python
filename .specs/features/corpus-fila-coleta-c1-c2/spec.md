# Especificação: corpus, fila e coleta C1/C2

**Status:** APROVADA PARA IMPLEMENTAÇÃO
**Aprovação:** solicitação do usuário em 2026-08-11 para continuar o M2, mantendo `06-metodologia.tex` como especificação do protocolo e `07-desenvolvimento.tex` como design de origem.
**Fontes de requisitos:** `06-metodologia.tex`, especialmente linhas 62--84, 88--130 e 247--265; `07-desenvolvimento.tex`, especialmente linhas 48--96, 126--153 e 179--231.

## Problema

O M1 comprovou o ambiente e C1/C2 em fumaça, mas o corpus completo ainda não foi adquirido nem sanitizado, não existe uma fila persistente para as 52 combinações e nenhuma execução integra a coleta principal. O M2 deve formar o censo integral do RealVuln v1.0, congelar o ambiente e concluir Bandit e Semgrep sobre entradas cegadas e equivalentes, preservando falhas em vez de remover projetos do denominador.

## Metas

- [ ] Adquirir e validar os 26 repositórios nos commits do manifesto RealVuln v1.0.
- [ ] Validar e preservar separadamente os 26 arquivos de ground truth sem expô-los aos scanners.
- [ ] Produzir 26 alvos opacos e inventários regeneráveis sob uma política de sanitização congelada.
- [ ] Criar uma fila determinística, auditável e retomável com 52 execuções C1/C2.
- [ ] Congelar imagem, regras, comandos, recursos e exceção de host antes do primeiro resultado de coleta.
- [ ] Levar todas as 52 tarefas a estado terminal, sem excluir falhas técnicas.
- [ ] Publicar evidência pequena suficiente para auditar corpus, fila e coleta sem redistribuir código ou regras de terceiros.

## Fora de escopo

| Recurso | Razão |
|---|---|
| Pontuação TP/FP/FN/TN e métricas | pertence ao M4 e exige acesso controlado ao oracle depois de encerradas as saídas |
| Deduplicação e união C1+C2 | necessária para C5/C6 e será implementada no M3 sem observar o ground truth |
| Cursor, Codex e C3--C6 | pertencem ao M3 e dependem do piloto de produtos/modelos |
| Alteração de rótulos RealVuln | proibida durante a coleta; eventual sensibilidade será separada |
| RealVuln v2 | estudo independente futuro, sem mistura com v1.0 |
| Distribuição do corpus, oracle, resultados brutos ou regras | depende das licenças e não é necessária para evidência auditável do M2 |

## Histórias e critérios de aceite

### P1: Corpus integral e verificável

**História:** Como pesquisador, quero preparar exatamente os 26 snapshots do RealVuln v1.0 para que todas as condições futuras recebam o mesmo censo aprovado.

1. QUANDO o manifesto for importado ENTÃO deverão existir exatamente 26 entradas, URLs HTTPS simples e commits Git completos, sem duplicatas.
2. QUANDO um repositório for adquirido ENTÃO origem oficial e commit observado deverão coincidir com o manifesto fixado; se a origem estiver indisponível, somente um espelho previamente publicado no lock de transporte poderá fornecer o mesmo objeto de commit completo; branch padrão, tag móvel, revisão diferente, submódulo, hook ou objeto especial não serão aceitos como substitutos.
3. QUANDO o ground truth for adquirido ENTÃO o validador oficial fixado deverá aprovar os 26 arquivos e o sistema deverá registrar hashes completos e as contagens observadas nos arquivos machine-readable fixados: 817 entradas, 697 vulnerabilidades e 120 armadilhas; a divergência ante 796/676/120 anunciados no README deverá permanecer explícita.
4. QUANDO o corpus for preparado ENTÃO cada alvo deverá receber exatamente um ID `ALVO-NNNN`; a correspondência original ficará fora das áreas montadas nos scanners.
5. QUANDO a política de sanitização for aplicada ENTÃO ela deverá ser única, versionada e anterior aos resultados; metadados VCS, caches, ambientes, artefatos gerados e caminhos de solução/walkthrough serão removidos sem regra específica por alvo.
6. QUANDO um alvo for regenerado ENTÃO seu inventário ordenado de caminhos, tamanhos e SHA-256 deverá ser byte a byte idêntico ao inventário congelado.

**Teste independente:** preparar todos os alvos duas vezes a partir dos objetos Git fixados, comparar os 26 inventários e verificar que nenhuma árvore contém caminhos proibidos ou oracle.

### P1: Fila C1/C2 retomável e estrita

**História:** Como pesquisador, quero uma fila persistente para retomar interrupções sem reutilizar áreas ou apagar tentativas.

1. QUANDO a fila for criada ENTÃO deverá conter exatamente 52 itens únicos: C1 e C2, repetição 1, para cada um dos 26 IDs opacos.
2. QUANDO a ordem for congelada ENTÃO deverá ser uma permutação verificável produzida antes da coleta por ranking SHA-256 com semente publicada, sem depender de resultados.
3. QUANDO uma tarefa iniciar ENTÃO uma área de entrada nova e uma tentativa de saída exclusiva deverão ser criadas; nenhuma saída existente será sobrescrita.
4. QUANDO o controlador for interrompido ENTÃO a tarefa `em_execucao` voltará a ser elegível com número de tentativa incrementado, preservando integralmente a tentativa anterior.
5. QUANDO uma execução concluir ou falhar ENTÃO o estado terminal, hashes e causa deverão ser incorporados atomicamente à fila; tarefas terminais não serão executadas de novo implicitamente.
6. QUANDO houver falha técnica terminal ENTÃO o alvo permanecerá na população e a falha será evidenciada para o modo estrito posterior.

**Teste independente:** simular inicialização, interrupção, retomada, falha e conclusão em diretórios temporários, provando idempotência e ausência de sobrescrita.

### P1: Coleta determinística C1/C2

**História:** Como pesquisador, quero executar Bandit e Semgrep sobre o corpus completo em ambiente congelado para obter as linhas de base determinísticas do estudo.

1. QUANDO a coleta for armada ENTÃO o preflight deverá reavaliar Git, WSL, Docker Desktop e Engine; uma exceção anterior só será aceita se seu escopo incluir explicitamente o M2 e a decisão for anterior à primeira execução.
2. QUANDO o bloco iniciar ENTÃO imagem por ID local, plataforma, versões, regras/hash, comandos, limites e timeouts deverão ser congelados; reconstrução ou troca dentro do bloco bloqueará a retomada.
3. QUANDO C1 e C2 analisarem o mesmo alvo ENTÃO `entrada_commit` e `entrada_sha256` deverão ser iguais aos valores congelados do corpus.
4. QUANDO um scanner executar ENTÃO permanecerão obrigatórios rede `none`, alvo somente leitura, saída exclusiva, rootfs somente leitura, UID/GID não root, capabilities removidas, `no-new-privileges`, limites e watchdog.
5. QUANDO o scanner terminar ENTÃO bruto, stdout/stderr, versões, processo, normalizado, avisos e manifestos de transição deverão ser preservados antes de a fila avançar.
6. QUANDO a coleta encerrar ENTÃO deverão existir 52 estados terminais verificáveis e nenhum contêiner, área de execução ou arquivo `.part` residual.
7. QUANDO um resumo for publicado ENTÃO deverá registrar contagens por estado/condição, janela temporal, ambiente congelado, hashes de corpus/fila/manifestos e referências aos brutos ignorados, sem calcular métricas de avaliação.

**Teste independente:** executar a fila inteira serialmente, revalidar cada manifesto pelo modelo v1, comparar artefatos aos hashes declarados e conferir cobertura exata do produto cartesiano 26×2.

## Casos extremos

- URL ou commit do manifesto divergente bloqueia o alvo e impede armar a coleta.
- Repositório indisponível só admite espelho publicado que contenha o commit exato; fork com revisão diferente mantém a aquisição incompleta.
- Symlink, submódulo, caminho absoluto, travessia, dispositivo ou reparse point é recusado antes da preparação.
- Alvo sanitizado vazio, inventário divergente ou colisão de ID bloqueia o corpus inteiro.
- Imagem/regras alteradas depois do congelamento bloqueiam a próxima tarefa e não alteram as já preservadas.
- JSON vazio válido conclui com zero achados; JSON inválido preserva bruto e falha por formato.
- Exit code Bandit `1` por achados é aceito; códigos fora da política são falha preservada.
- Timeout, OOM, watchdog e interrupção do host nunca apagam a tentativa.
- Falha em C1 não impede automaticamente C2 do mesmo alvo, e vice-versa; ambas permanecem unidades independentes da fila.

## Rastreabilidade

| ID | Requisito | Origem | Status |
|---|---|---|---|
| M2-01 | Censo RealVuln v1.0 com 26 snapshots fixados | `06:62-70`, `07:50-54` | Em tarefas |
| M2-02 | Ground truth oficial validado e isolado | `06:80-86`, `07:12,50-54` | Em tarefas |
| M2-03 | Sanitização única e IDs opacos | `06:72-78`, `07:56-62` | Em tarefas |
| M2-04 | Inventários iguais e regeneráveis | `06:74`, `07:60-62` | Em tarefas |
| M2-05 | Fila completa e retomável | `06:78,247-265`, `07:82-96` | Em tarefas |
| M2-06 | Ambiente C1/C2 congelado e isolado | `06:88-120`, `07:126-153` | Em tarefas |
| M2-07 | Preservação bruta e normalização sem oracle | `06:124-130`, `07:98-124` | Em tarefas |
| M2-08 | Modo estrito preserva falhas e população | `06:70,136`, `07:94` | Em tarefas |
| M2-09 | Evidência auditável sem redistribuição indevida | `07:14-46,195-231` | Em tarefas |
| M2-10 | Exceção de risco reavaliada antes da coleta | `STATE:AD-005`, todo pré-coleta | Em tarefas |

## Critérios de sucesso

- [ ] 26/26 alvos adquiridos, preparados e regenerados com commits/hashes conferidos.
- [ ] 26/26 ground truths aprovados pelo validador oficial e isolados dos scanners.
- [ ] 52/52 itens únicos presentes e terminais na fila final, incluindo falhas se ocorrerem.
- [ ] C1/C2 usam o mesmo hash de entrada por alvo e o mesmo ambiente congelado no bloco.
- [ ] Nenhum resultado de fumaça integra a coleta e nenhuma tarefa de coleta é omitida.
- [ ] Gate `build`, testes do M2 e auditoria de resíduos passam sem ignorados.
- [ ] Evidência e capítulos distinguem coleta de pontuação; nenhuma métrica final é antecipada.
