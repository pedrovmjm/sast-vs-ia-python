"""Sonda de integração executada apenas no serviço Docker endurecido."""

import json
from pathlib import Path


def _status_processo() -> dict[str, str]:
    linhas = Path("/proc/self/status").read_text(encoding="utf-8").splitlines()
    return {
        chave: valor.strip()
        for linha in linhas
        if ":" in linha
        for chave, valor in [linha.split(":", 1)]
    }


status = _status_processo()
assert status["Uid"].split()[0] == "10001"
assert status["Gid"].split()[0] == "10001"
assert int(status["CapEff"], 16) == 0
assert status["NoNewPrivs"] == "1"

interfaces = sorted(
    path.name for path in Path("/sys/class/net").iterdir() if path.is_dir()
)
assert interfaces == ["lo"]

proibidos = ("benchmark", "alvos", "oracle", "execucoes", "resultados")
assert not any((Path("/") / nome).exists() for nome in proibidos)

try:
    Path("/probe-escrita").write_text("proibido", encoding="utf-8")
except OSError:
    raiz_somente_leitura = True
else:
    raiz_somente_leitura = False
assert raiz_somente_leitura

temporario = Path("/tmp/probe-escrita")
temporario.write_text("permitido", encoding="utf-8")
temporario.unlink()

print(
    json.dumps(
        {
            "cap_eff": 0,
            "corpus_ausente": True,
            "gid": 10001,
            "interfaces": interfaces,
            "no_new_privs": 1,
            "rootfs_read_only": True,
            "tmpfs_writable": True,
            "uid": 10001,
        },
        sort_keys=True,
    )
)
