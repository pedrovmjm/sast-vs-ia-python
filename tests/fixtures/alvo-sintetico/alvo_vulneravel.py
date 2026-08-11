"""Fixture sintética: deve ser analisada como texto e jamais executada."""

import subprocess
from pathlib import Path


# Se algum componente importar ou executar a fixture, a tentativa será contaminada.
Path("/saida/FIXTURE_EXECUTADA").write_text("proibido", encoding="utf-8")

comando_nao_confiavel = input()
subprocess.Popen(comando_nao_confiavel, shell=True)
eval(input())
