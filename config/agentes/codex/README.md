# Perfil Codex (C4/C6)

Este diretório é o ponto de configuração do adaptador Codex. Credenciais, cache, sessões e respostas não são versionados. O adaptador deve carregar a configuração comum de `../codex-c4-v1.json`, o prompt comum e, em C6, o `alertas-sast.json` específico do alvo.

Restrições obrigatórias: somente leitura, sem execução de código/testes, sem Bandit/Semgrep, sem oracle, sessão nova por repetição e resposta JSON validada pelo schema comum.
