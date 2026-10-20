import logging
import time

from comum.banco import Banco
from comum.mensageria import Trabalhador


def executar(servico, modelo_cls):
    """Inicializa e executa microsserviços sem interface HTTP (como Entrega) até receber SIGINT."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    banco = Banco(servico)
    modelo = modelo_cls(banco)
    worker = Trabalhador(servico, banco, modelo.tratar)
    worker.iniciar()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        worker.fechar()
        if not worker.thread.is_alive():
            banco.fechar()
