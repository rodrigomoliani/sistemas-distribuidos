from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from comum.banco import Banco
from comum.mensageria import Trabalhador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def criar_app(servico, modelo_cls):
    """Cria uma aplicação FastAPI com ciclo de vida (lifespan) acoplado ao worker AMQP e SQLite."""
    @asynccontextmanager
    async def lifespan(app):
        banco = Banco(servico)
        modelo = modelo_cls(banco)
        worker = Trabalhador(servico, banco, modelo.tratar)
        app.state.banco, app.state.modelo, app.state.worker = banco, modelo, worker
        worker.iniciar()

        try:
            yield
        finally:
            worker.fechar()
            if not worker.thread.is_alive():
                banco.fechar()

    app = FastAPI(title=f"Trabalho 3 - {servico}", lifespan=lifespan)

    @app.get("/saude", tags=["Infraestrutura"])
    def saude():
        """Verifica integridade do serviço e conexão com o RabbitMQ."""
        return {"servico": servico, "rabbitmq": app.state.worker.pronto.is_set()}

    return app
