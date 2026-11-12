"""Executa os serviços locais e encerra somente seus subprocessos."""

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser

from comum.config import RAIZ
from comum.processos import encerrar


def main():
    """Inicia os subprocessos dos microsserviços, frontend e mock, monitorando sua execução."""
    parser = argparse.ArgumentParser(description="Inicializador dos serviços locais")
    parser.add_argument("--sem-navegador", action="store_true", help="Não abre o navegador automaticamente")
    args = parser.parse_args()

    node = shutil.which("node")
    if not node:
        raise SystemExit("Instale Node.js >= 20 para servir o frontend.")

    processos = []
    logs = []
    pasta = RAIZ / "dados" / "logs"
    pasta.mkdir(parents=True, exist_ok=True)

    servicos = (
        "estoque",
        "mock_pagamento",
        "pagamento",
        "entrega",
        "promocoes",
        "principal",
        "frontend",
    )

    try:
        for servico in servicos:
            log = (pasta / f"{servico}.log").open("a", encoding="utf-8")
            logs.append(log)

            comando = [node, "frontend/server.mjs"] if servico == "frontend" else [sys.executable, "-u", "-m", servico]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            ambiente = {**os.environ, "PYTHONUTF8": "1"}

            proc = subprocess.Popen(
                comando,
                cwd=RAIZ,
                env=ambiente,
                stdout=log,
                stderr=log,
                creationflags=flags,
            )
            processos.append((servico, proc))

        print("Loja: http://localhost:8080 | Swagger: http://localhost:8000/docs")
        print(f"Logs: {pasta}. Ctrl+C encerra todos os serviços locais.")
        time.sleep(3)

        if not args.sem_navegador:
            webbrowser.open("http://localhost:8080")

        # Monitora a saúde dos subprocessos
        while True:
            for nome, processo in processos:
                if processo.poll() is not None:
                    raise RuntimeError(f"{nome} encerrou prematuramente. Consulte {pasta / (nome + '.log')}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("Encerrando serviços…")
    finally:
        encerrar([processo for _, processo in processos])
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
