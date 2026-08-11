# Limites de Contexto

## Limites de tamanho de arquivo

| Arquivo | Máximo de tokens | ~Palavras | Aviso em |
| --------------- | ---------- | ------ | ----------- |
| PROJETO.md | 2.000 | 1.200 | 1.600 (80%) |
| ROTEIRO.md | 3.000 | 1.800 | 2.400 |
| ESTADO.md | 10.000 | 6.000 | 7.000 (70%) |
| especificação.md | 5.000 | 3.000 | 4.000 |
| design.md | 8.000 | 4.800 | 6.400 |
| tarefas.md | 10.000 | 6.000 | 8.000 |
| PILHA.md | 2.000 | 1.200 | 1.600 |
| ARQUITETURA.md | 4.000 | 2.400 | 3.200 |
| CONVENÇÕES.md | 3.000 | 1.800 | 2.400 |
| ESTRUTURA.md | 2.000 | 1.200 | 1.600 |
| TESTE.md | 4.000 | 2.400 | 3.200 |
| INTEGRAÇÕES.md | 5.000 | 3.000 | 4.000 |

## Zonas de Contexto

🟢 **Saudável** (<40k no total): Silencioso
🟡 **Moderado** (40-60k): Nota de rodapé discreta
🔴 **Crítico** (>60k): aviso ativo, sugestão de otimização

## Monitoramento

Exibir o status do contexto no rodapé quando >40k:

```
📊 Context: 52k tokens (moderate)
  - STATE.md: 8k (yellow zone)
  - tasks.md: 11k (ok)
  - Total: 52k / 200k (26%)
```

## Princípios

**Meta:** <40 mil tokens carregados (20% da janela)
**Reserva:** mais de 160 mil tokens para trabalho, raciocínio e resultados