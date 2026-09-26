# Documentação do artefato

Este repositório contém **duas coisas**: o texto do TCC (`*.tex` na raiz) e o
artefato experimental que o Capítulo 7 descreve — um repositório controlador que
executa e registra o protocolo comparativo.

Esta pasta documenta o artefato.

---

## Por onde começar

| Se você quer... | Leia |
|---|---|
| entender o que cada pasta é e o que pode apagar | [`ESTRUTURA.md`](ESTRUTURA.md) |
| saber o que significa cada arquivo `.json` | [`ARTEFATOS_JSON.md`](ARTEFATOS_JSON.md) |
| saber onde o Capítulo 6 diverge do que existe hoje | [`AUDITORIA-CAPITULO-06.md`](AUDITORIA-CAPITULO-06.md) |
| saber onde o Capítulo 7 diverge do que existe hoje | [`AUDITORIA-CAPITULO-07.md`](AUDITORIA-CAPITULO-07.md) |
| reproduzir o ambiente e a fumaça | [`EXECUCAO.md`](EXECUCAO.md) |
| verificar origem, licença e integridade de cada dependência | [`FONTES_E_INTEGRIDADE.md`](FONTES_E_INTEGRIDADE.md) |
| entender por que uma decisão foi tomada | [`../.specs/project/STATE.md`](../.specs/project/STATE.md) |

> **Nota de atualidade:** `EXECUCAO.md` e `FONTES_E_INTEGRIDADE.md` foram
> escritos no fechamento do marco M1 e descrevem o estado daquele momento.
> Continuam corretos sobre ambiente, proveniência e reprodução da fumaça, mas a
> seção "Limites atuais" do `EXECUCAO.md` está desatualizada: os 26 alvos **já
> foram adquiridos** e a coleta C1/C2 **já foi executada**. Ver
> `AUDITORIA-CAPITULO-07.md`, item C-1.

---

## O que o experimento faz, em cinco frases

1. Fixa o benchmark **RealVuln v1.0** num commit e adquire os **26 projetos
   Python vulneráveis** nos commits que o manifesto oficial declara.
2. Exporta cada revisão para uma árvore **sanitizada e opaca** (`ALVO-0001` a
   `ALVO-0026`), sem `.git`, sem *walkthroughs* e sem qualquer pista da resposta.
3. Submete essas árvores a **seis condições** e preserva a saída bruta de cada
   execução, sem editar nada.
4. Converte as saídas nativas a um **esquema comum de achados**, sem inferir
   nenhum valor que a ferramenta não tenha informado.
5. Só **depois** de a saída bruta estar fechada e hasheada, dá acesso ao
   *ground truth* e invoca o avaliador oficial.

### As seis condições

| Condição | Ferramenta | Entrada | Estado hoje |
|---|---|---|---|
| **C1** | Bandit 1.9.4 | código sanitizado | **Concluída** — 26 execuções |
| **C2** | Semgrep CE 1.172.0 | código sanitizado | **Concluída** — 26 execuções |
| **C3** | Cursor (GPT-5.6 Luna) | código sanitizado | Configurado, aguarda piloto |
| **C4** | Codex (GPT-5.6 Luna) | código sanitizado | **Coleta concluída** — 78 unidades válidas; auditoria de metadados legados pendente |
| **C5** | Cursor | código + `alertas-sast.json` de C1/C2 | Não iniciada |
| **C6** | Codex | código + `alertas-sast.json` de C1/C2 | 26 entradas congeladas; aguarda piloto |

C1 e C2 são determinísticas, por isso rodam uma vez (`R01`). C3 a C6 são
estocásticas e terão **três repetições** por alvo — 78 execuções por condição,
312 no total.

---

## As cinco regras que sustentam a validade do estudo

Se algo no repositório parecer excessivamente rígido, é por causa de uma destas.

**1. O oracle é inalcançável até a pontuação.**
`oracle/` é irmão de `alvos/`, nunca ancestral. Nenhum contêiner o monta. A
política de sanitização exclui `ground-truth`, `oracle`, `solution`,
`walkthrough` e `writeup` da árvore entregue à ferramenta.

**2. O alvo é opaco.**
A ferramenta vê `ALVO-0007`, nunca `dvpwa`, nunca a CWE, nunca a URL. A tabela
de correspondência mora em `config/corpus-realvuln-v1.lock.json`, que não é
montado na análise.

**3. A ordem foi sorteada antes dos resultados.**
`config/fila-c1-c2.lock.json` congela as 52 execuções por um ranking SHA-256 com
semente publicada. Não é possível reordenar depois de ver os achados.

**4. Nada é sobrescrito.**
Cada retomada cria uma `tentativa-NNN` nova. As falhas ficam em disco com o
manifesto delas. As 9 falhas iniciais do Bandit continuam lá, ao lado das
reexecuções bem-sucedidas.

**5. O harness não inventa dados.**
Campo que a ferramenta não informou fica `null`. Severidade sem mapa congelado
fica `null`. Intervalo de linhas ausente **não** é reconstruído a partir do
texto. Isso existe para impedir que a normalização aumente artificialmente a
chance de casar com o benchmark.

---

## Como o ambiente funciona

O host é Windows e tem **apenas Git, PowerShell e Docker Desktop** — não há
Python instalado (decisão AD-002). Tudo roda dentro de uma imagem fixada:

```
tcc-sast:py3.12.13-bandit1.9.4-semgrep1.172.0
```

A divisão de trabalho é estrita: **o PowerShell fala com o Docker; o Python roda
dentro do contêiner e nunca chama Docker.** O contêiner não recebe
`docker.sock`, roda sem rede, com raiz somente leitura, usuário `10001`,
*capabilities* removidas e `no-new-privileges`.

Verificação rápida, com o Docker Desktop em execução:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gate.ps1 quick
```

O portão completo de marco é `gate.ps1 build`. Ver `EXECUCAO.md`.

---

## Onde estão os números que o TCC cita

Sempre em `evidencias/`. Nunca em `resultados/`, que é grande e ignorado pelo
Git.

| Número | Arquivo |
|---|---|
| Corpus: 26 alvos, commits, hashes de entrada | `evidencias/corpus-realvuln-v1/resumo.json` |
| *Ground truth*: 817 entradas, 697 vulnerabilidades, 120 armadilhas | `evidencias/corpus-realvuln-v1/ground-truth-resumo.json` |
| Validação por terceiro (validador oficial do benchmark) | `evidencias/corpus-realvuln-v1/validacao-oficial.json` |
| Configuração congelada da coleta | `evidencias/coleta-c1-c2/configuracao.json` |
| Fechamento do M2: 52/52, 0 falhas, 11 tentativas preservadas | `evidencias/coleta-c1-c2/auditoria-m2-t08.json` |
| Achados e tempos por execução | `evidencias/graficos-sast/sast-resumo.csv` |
| Fumaça do M1 (**não** entra nas métricas) | `evidencias/primeira-execucao/resumo.json` |

---

## Estado do projeto

| Marco | Escopo | Estado |
|---|---|---|
| M0 | Git local, planejamento rastreável | Completo |
| M1 | Ambiente, adaptadores, fumaça descartável | Completo |
| M2 | Corpus, fila, coleta C1/C2 | **Completo** (auditoria fechada em 11/08/2026) |
| M3 | Agentes C3–C6 e condições híbridas | Em andamento; C4 coletada e C6 pronta para piloto |
| M4 | Pontuação, análise e redação final | Não iniciado |

O `ROADMAP.md` em `.specs/project/` ainda descreve o M2 como em andamento —
ver `AUDITORIA-CAPITULO-07.md`, ação 12.
