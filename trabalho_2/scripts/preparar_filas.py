import argparse

from comum.mensageria import FILAS, conectar, declarar_topologia


def preparar(limpar=False):
    conexao = conectar()
    try:
        canal = conexao.channel()
        declarar_topologia(canal)
        if limpar:
            # Confere todas as filas antes de remover qualquer mensagem.
            if any(canal.queue_declare(queue=fila, passive=True).method.consumer_count for fila in FILAS):
                raise RuntimeError("Encerre todos os processos antes de limpar as filas.")
            for fila in FILAS:
                canal.queue_purge(queue=fila)
        print("Topologia pronta: duas exchanges e seis filas." + (" Filas limpas." if limpar else ""))
    finally:
        if conexao.is_open:
            conexao.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limpar", action="store_true", help="Limpar somente com todos os processos parados")
    preparar(parser.parse_args().limpar)
