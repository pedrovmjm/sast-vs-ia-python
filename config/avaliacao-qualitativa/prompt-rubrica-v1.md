Avalie semanticamente somente o relato cego e o material fornecido. Não busque a
chave de condições nem resultados por condição. Não inferir recomendação ausente.
Orientações escritas na descrição contam como orientação fornecida, mesmo quando
o campo recomendação está vazio. Idioma não afeta nota se o texto é compreensível.
Não pontuar por extensão, palavras-chave, estilo de modelo ou rótulo de TP.

Correção técnica 1..5: 1 contradiz evidência ou mecanismo falso; 2 classe certa
com erro substancial de mecanismo/risco; 3 classe e risco plausíveis mas genéricos
ou ressalva relevante; 4 mecanismo/risco corretos com contexto e pequena omissão;
5 fonte/operação, pré-condição e consequência coerentes com evidências.
Não concluir bypass de autenticação só por SQLi se há check_password posterior;
não recomendar SHA256 ou usedforsecurity=False para armazenamento de senha;
não presumir shlex.escape, função inexistente; não confundir escaping HTML com
impedir SSTI nem abspath isolado com containment. Se código e oracle divergirem,
registrar divergência e apoiar julgamento no material efetivamente pertinente.

Localização 1..5: 1 operação/arquivo contraditos; 2 arquivo certo, trecho sem
vínculo causal; 3 região/função correta mas ambígua; 4 instrução ou bloco causal
com desvio pequeno; 5 instrução causal precisa. Linha faltante não vira zero nem
nota5 automática: nome da função pode apoiar nota3. Tolerância quantitativa de
dez linhas não implica boa localização. Excertos podem ter sido extraídos ao
redor da linha reportada e mostrar uma operação vizinha; use referência específica.

Acionabilidade 1..5: 1 ausente ou insegura; 2 intenção vaga/erro grave na solução;
3 direção aplicável com escolhas essenciais faltantes; 4 mudança concreta adequada
com detalhe secundário faltante; 5 controle/operação/contexto e condições de
aplicação suficientes. Não se exige patch ou teste completo em todo relato.

Clareza binária: problema identificável; risco/consequência explícitos (somente
nomear classe como SQLi não descreve sua consequência); contexto associado a
operação/entrada/local, mesmo genérico; concretude por mecanismo ou controle
específico; concisão sem redundância/ambiguidade prejudicial. Atribua 1 se
satisfeito, 0 caso contrário. Não recompense texto curto automaticamente.

Para cada um dos oito critérios retorne nota, status, evidência com fonte/trecho
e justificativa específica. Texto/recomendação são evidências para clareza e
acionabilidade; código/referência sustentam correção e localização. Se material
não sustenta decisão, use nota null, status abstencao e explique o que falta;
inclua nome do critério em abstencoes. Não confunda evidência contrária com falta
de evidência: contradição material pode receber nota baixa.

Score=25*((T-1)/4+(L-1)/4+(A-1)/4+soma(clareza)/5), de 0 a 100.
Se qualquer um dos oito critérios é não avaliável, score_total=null, sem imputar
nota ou renormalizar pesos. Registre limites e exatamente materiais consultados
com caminhos/hash fornecidos. Não alegue testes dinâmicos que não realizou.

Retorne somente objeto compatível com schema-julgamento.json. A validação de
status/abstenções, consistência da evidência e score é realizada separadamente.
