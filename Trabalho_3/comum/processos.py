import os
import subprocess


def encerrar(processos):
    """Encerra graciosamente subprocessos e seus filhos no Windows e POSIX."""
    for processo in reversed(processos):
        if processo.poll() is not None:
            continue

        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        else:
            processo.terminate()

    for processo in processos:
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()
