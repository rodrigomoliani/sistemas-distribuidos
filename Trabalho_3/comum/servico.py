# Ciclo de vida de Entrega e outros serviços sem API HTTP, cada um com seu banco próprio.

# Importa registro de informações, avisos e falhas no log.
import logging

# Importa relógios, timestamps e pausas do agendamento e dos testes.
import time

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import Banco

# Importa worker AMQP, topologia do RabbitMQ e criação de conexões.
from comum.mensageria import Trabalhador

# Executa o serviço sem HTTP até Ctrl+C e encerra worker e banco.
def executar(servico, modelo_cls):

    # Configura nível e formato das mensagens de log, incluindo horário e severidade.
    logging.basicConfig(

        # Define o argumento ou campo level desta operação.
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )

    # Prepara banco para esta etapa.
    banco = Banco(servico)

    # Prepara modelo de regras do serviço para esta etapa.
    modelo = modelo_cls(banco)

    # Prepara trabalhador AMQP para esta etapa.
    worker = Trabalhador(servico, banco, modelo.tratar)

    # Executa worker.iniciar para concluir esta etapa do processamento.
    worker.iniciar()

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Repete o bloco enquanto True permitir continuar.
        while True:

            # Pausa o ciclo pelo intervalo indicado, evitando ocupar a CPU em espera contínua.
            time.sleep(1)

    # Trata KeyboardInterrupt sem confundir falha com resultado válido.
    except KeyboardInterrupt:

        # Não executa outra ação: o encerramento ou a simulação já foi tratado pelo contexto.
        pass

    # Libera os recursos mesmo se ocorrer uma falha ou interrupção.
    finally:

        # Libera o recurso do serviço depois do processamento.
        worker.fechar()

        # Confere a condição not worker.thread.is_alive() antes de executar este bloco.
        if not worker.thread.is_alive():

            # Libera o recurso do serviço depois do processamento.
            banco.fechar()
