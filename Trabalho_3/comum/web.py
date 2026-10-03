# Fábrica FastAPI: abre banco e worker no startup e libera recursos no shutdown.

# Importa registro de informações, avisos e falhas no log.
import logging

# Importa gerenciadores de contexto, responsáveis por iniciar e finalizar recursos.
from contextlib import asynccontextmanager

# Importa servidor HTTP, parâmetros de rotas e respostas de erro.
from fastapi import FastAPI

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import Banco

# Importa worker AMQP, topologia do RabbitMQ e criação de conexões.
from comum.mensageria import Trabalhador

# Configura nível e formato das mensagens de log, incluindo horário e severidade.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Monta a API FastAPI com banco próprio e worker AMQP gerenciados pelo lifespan.
def criar_app(servico, modelo_cls):

    # Transforma a função em gerenciador de contexto para cuidar de início e finalização.
    @asynccontextmanager

    # Prepara os recursos na inicialização e os encerra após o servidor terminar.
    async def lifespan(app):

        # Prepara banco para esta etapa.
        banco = Banco(servico)

        # Prepara modelo de regras do serviço para esta etapa.
        modelo = modelo_cls(banco)

        # Prepara trabalhador AMQP para esta etapa.
        worker = Trabalhador(servico, banco, modelo.tratar)

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        app.state.banco, app.state.modelo, app.state.worker = banco, modelo, worker

        # Executa worker.iniciar para concluir esta etapa do processamento.
        worker.iniciar()

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Entrega o próximo conteúdo ao consumidor do gerador, sem fechar o stream.
            yield

        # Libera os recursos mesmo se ocorrer uma falha ou interrupção.
        finally:

            # Libera o recurso do serviço depois do processamento.
            worker.fechar()

            # Confere a condição not worker.thread.is_alive() antes de executar este bloco.
            if not worker.thread.is_alive():

                # Libera o recurso do serviço depois do processamento.
                banco.fechar()

    # Prepara aplicação FastAPI para esta etapa.
    app = FastAPI(title=f"Trabalho 3 - {servico}", lifespan=lifespan)

    # Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
    @app.get("/saude", tags=["Infraestrutura"])

    # Informa que o serviço está ativo e, quando aplicável, se está conectado ao RabbitMQ.
    def saude():

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return {"servico": servico, "rabbitmq": app.state.worker.pronto.is_set()}

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return app
