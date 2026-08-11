# Perfil Cursor (C3/C5)

Este diretório é o ponto de configuração do adaptador Cursor. Credenciais, cache, sessões e respostas não são versionados. O adaptador deve carregar a configuração comum de `../cursor-c3-v1.json`, o prompt comum e, em C5, o `alertas-sast.json` específico do alvo.

Restrições obrigatórias: somente leitura, sem execução de código/testes, sem Bandit/Semgrep, sem oracle, sessão nova por repetição e resposta JSON validada pelo schema comum.
