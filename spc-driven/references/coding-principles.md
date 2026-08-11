# Princípios de codificação

Viés comportamental, não lista de verificação. Leia antes de cada implementação.

---

## Antes da codificação

- Declare explicitamente as suposições. Se não tiver certeza, pergunte.
- Existem múltiplas interpretações? Apresente tudo - não escolha silenciosamente.
- Existe uma abordagem mais simples? Diga isso. Empurre para trás quando necessário.
- Algo não está claro? Parar. Nomeie o que é confuso. Perguntar.
- A abordagem do usuário parece errada? Discordo honestamente. Não seja bajulador.

---

## Durante a implementação

### Simplicidade

- Nenhum recurso além do que foi solicitado
- Sem abstrações para código de uso único
- Nenhuma "flexibilidade" ou "configuração" não solicitada
- Sem tratamento de erros para cenários impossíveis
- 200 linhas que poderiam ser 50? Reescreva.

### Alterações Cirúrgicas

- Não "melhore" código, comentários ou formatação adjacentes
- Não refatore coisas que não estão quebradas
- Combine o estilo existente, mesmo se você fizesse diferente
- Código morto não relacionado notado? Mencione isso - não exclua
- Remova SOMENTE importações/variáveis/funções SUAS alterações órfãs
- Não remova código morto pré-existente, a menos que solicitado

### Teste de integridade

- NUNCA enfraqueça uma afirmação de teste existente para fazê-la passar
- NUNCA exclua um teste para reduzir a contagem de falhas
- NUNCA use o mecanismo de ignorar/desativar/pendente da estrutura de teste para ignorar um teste com falha
- NUNCA modifique testes escritos na fase VERMELHA durante a fase VERDE
- Se um teste estiver genuinamente errado, PARE e confirme com o usuário antes de alterá-lo
- Os testes são as especificações - a implementação está em conformidade com os testes, e não o contrário

### Orientado por metas

- Transforme tarefas vagas em metas verificáveis
- Trabalho em várias etapas? Apresentar um breve plano com pontos de verificação de verificação
- Cada linha alterada deve ser rastreada diretamente para a solicitação do usuário

---

## Após cada alteração

Pergunte: "O engenheiro sênior consideraria isso complicado demais?"
Se sim → simplifique antes de prosseguir.