# Transporte AMQP. Apenas a thread do trabalhador acessa sua conexão Pika.

# Importa registro de informações, avisos e falhas no log.
import logging

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa threads, locks e sinais usados para coordenar acesso concorrente.
import threading

# Importa cliente AMQP que publica e consome mensagens do RabbitMQ.
import pika

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import emitir

# Importa assinaturas RSA e política de produtores autorizados.
from comum.seguranca import Assinador

# Prepara logger ou arquivo de log para esta etapa.
log = logging.getLogger(__name__)

# Prepara exchange direct exclusiva do Trabalho 3 para esta etapa.
EXCHANGE = "eCommerce.trabalho3"

# Prepara bindings dos eventos de cada serviço para esta etapa.
FILAS = {

    # Define o campo principal desta estrutura de dados.
    "principal": [

        # Fornece este valor textual à chamada ou coleção em construção.
        "pedido.estoque_ok",

        # Fornece este valor textual à chamada ou coleção em construção.
        "estoque.indisponivel",

        # Fornece este valor textual à chamada ou coleção em construção.
        "pagamento.checkout_criado",

        # Fornece este valor textual à chamada ou coleção em construção.
        "pagamento.aprovado",

        # Fornece este valor textual à chamada ou coleção em construção.
        "pagamento.recusado",

        # Fornece este valor textual à chamada ou coleção em construção.
        "pedido.enviado",

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    ],

    # Define o campo estoque desta estrutura de dados.
    "estoque": ["pedido.criado", "pedido.excluido"],

    # Define o campo pagamento desta estrutura de dados.
    "pagamento": ["pedido.estoque_ok", "pedido.excluido"],

    # Define o campo entrega desta estrutura de dados.
    "entrega": ["pagamento.aprovado"],

    # Define o campo promocoes desta estrutura de dados.
    "promocoes": ["interesse.promocao"],

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
}

# Abre uma conexão AMQP com timeouts e heartbeat configurados.
def conectar():

    # Prepara parâmetros da conexão ou da consulta para esta etapa.
    parametros = pika.URLParameters(

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )

    # Detecta perda da conexão AMQP por heartbeat a cada 30 segundos.
    parametros.heartbeat = 30

    # Limita a espera por operações de socket AMQP a cinco segundos.
    parametros.socket_timeout = 5

    # Limita a dez segundos a espera por uma conexão bloqueada pelo broker.
    parametros.blocked_connection_timeout = 10

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return pika.BlockingConnection(parametros)

# Cria exchange, filas duráveis e bindings exatos de cada microsserviço.
def declarar_topologia(canal):

    # Declara a exchange direct durável, que roteia por igualdade da routing key.
    canal.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)

    # Percorre FILAS.items() para processar cada (servico, tipos).
    for servico, tipos in FILAS.items():

        # Prepara fila do microsserviço para esta etapa.
        fila = f"trabalho3.{servico}"

        # Declara ou consulta a fila durável do serviço.
        canal.queue_declare(queue=fila, durable=True)

        # Percorre tipos para processar cada tipo.
        for tipo in tipos:

            # Liga a fila à exchange para receber somente o evento indicado.
            canal.queue_bind(queue=fila, exchange=EXCHANGE, routing_key=tipo)

# Centraliza o consumo e a publicação AMQP na thread dona da conexão Pika.
class Trabalhador:

    # Documenta a propriedade da conexão AMQP e a comunicação com as rotas HTTP pela outbox.
    """Uma thread é dona da conexão Pika; HTTP usa apenas o banco/outbox."""

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, servico, banco, tratar):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        self.servico, self.banco, self.tratar = servico, banco, tratar

        # Carrega ou armazena o assinador RSA do serviço que publica estes eventos.
        self.assinador = Assinador.carregar(servico)

        # Cria o sinal de parada cooperativa da thread AMQP.
        self.parar = threading.Event()

        # Mantém o sinal de conexão pronta; no teste usa um dublê sempre disponível.
        self.pronto = threading.Event()

        # Prepara a thread dona da conexão AMQP; no teste simula uma thread já parada.
        self.thread = threading.Thread(

            # Define a função executada pela thread.
            target=self.executar, name=f"amqp-{servico}", daemon=True

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Inicia a thread do worker; no dublê de teste, mantém a interface sem criar uma thread.
    def iniciar(self):

        # Inicia a thread ou ativa a substituição temporária preparada para o teste.
        self.thread.start()

    # Sinaliza a parada e aguarda até quinze segundos pelo fim do worker.
    def fechar(self):

        # Ativa o sinal de coordenação para informar conexão pronta ou solicitar parada.
        self.parar.set()

        # Aguarda a thread terminar até o prazo indicado.
        self.thread.join(timeout=15)

    # Verifica o evento e processa negócio, inbox e outbox dentro da mesma transação.
    def receber(self, ch, metodo, propriedades, corpo):

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Prepara envelope verificado para esta etapa.
            evento = self.assinador.verificar(corpo, metodo.routing_key)

            # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
            with self.banco.transacao() as con:

                # Confere a condição not con.execute('SELECT 1 FROM inbox WHERE event_id=?', (evento['event_id'],)).fetchone() antes de executar este bloco.
                if not con.execute(

                    # Fornece este valor textual à chamada ou coleção em construção.
                    "SELECT 1 FROM inbox WHERE event_id=?", (evento["event_id"],)

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ).fetchone():

                    # Percorre self.tratar(con, evento['event_type'], evento['data']) para processar cada (tipo, dados).
                    for tipo, dados in self.tratar(

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        con, evento["event_type"], evento["data"]

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    ):

                        # Assina o evento e o grava na outbox da transação atual, sem publicar por HTTP.
                        emitir(con, self.assinador, tipo, dados)

                    # Insere o registro em inbox; conflitos são tratados conforme a instrução.
                    con.execute("INSERT INTO inbox VALUES (?)", (evento["event_id"],))

        # Trata ValueError sem confundir falha com resultado válido.
        except ValueError as erro:

            # Registra o descarte da mensagem no log para permitir diagnóstico.
            log.warning("DESCARTADO %s: %s", metodo.routing_key, erro)

            # Rejeita a mensagem inválida sem colocá-la de volta na fila.
            ch.basic_reject(delivery_tag=metodo.delivery_tag, requeue=False)

            # Encerra esta operação sem produzir um valor de retorno.
            return

        # Exceções de infraestrutura fecham a conexão; a mensagem volta à fila.

        # Confirma ao broker que o evento já foi persistido e processado com sucesso.
        ch.basic_ack(delivery_tag=metodo.delivery_tag)

    # Reconecta ao RabbitMQ, publica a outbox e consome eventos até receber o sinal de parada.
    def executar(self):

        # Continua o ciclo enquanto o encerramento cooperativo não tiver sido solicitado.
        while not self.parar.is_set():

            # Prepara conexão AMQP para esta etapa.
            conexao = None

            # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
            try:

                # Prepara conexão AMQP para esta etapa.
                conexao = conectar()

                # Prepara canal AMQP para esta etapa.
                canal = conexao.channel()

                # Cria exchange, filas duráveis e bindings exatos de cada microsserviço.
                declarar_topologia(canal)

                # Habilita confirmações do broker antes de remover eventos da outbox.
                canal.confirm_delivery()

                # Limita a uma mensagem ainda não confirmada por consumidor.
                canal.basic_qos(prefetch_count=1)

                # Registra o callback de consumo da fila própria deste microsserviço.
                canal.basic_consume(

                    # Define o argumento ou campo queue desta operação.
                    queue=f"trabalho3.{self.servico}", on_message_callback=self.receber

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

                # Ativa o sinal de coordenação para informar conexão pronta ou solicitar parada.
                self.pronto.set()

                # Registra uma etapa normal do fluxo, como conexão pronta ou evento publicado.
                log.info("PRONTO %s", self.servico)

                # Continua o ciclo enquanto o encerramento cooperativo não tiver sido solicitado.
                while not self.parar.is_set():

                    # Percorre self.banco.ler('SELECT * FROM outbox ORDER BY id LIMIT 50') para processar cada row.
                    for row in self.banco.ler(

                        # Consulta registros de outbox; '?' recebe parâmetros separados do SQL.
                        "SELECT * FROM outbox ORDER BY id LIMIT 50"

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    ):

                        # Publica o envelope assinado com a routing key do evento; a mensagem é persistente.
                        canal.basic_publish(

                            # Define o argumento ou campo exchange desta operação.
                            exchange=EXCHANGE,

                            # Define o argumento ou campo routing_key desta operação.
                            routing_key=row["tipo"],

                            # Define o argumento ou campo body desta operação.
                            body=row["corpo"],

                            # Exige que o evento encontre ao menos uma fila compatível no broker.
                            mandatory=True,

                            # Define o argumento ou campo properties desta operação.
                            properties=pika.BasicProperties(

                                # Identifica o corpo AMQP como JSON para os consumidores.
                                content_type="application/json", delivery_mode=2

                            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                            ),

                        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                        )

                        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
                        with self.banco.transacao() as con:

                            # Remove da outbox o evento cuja publicação já foi confirmada pelo broker.
                            con.execute("DELETE FROM outbox WHERE id=?", (row["id"],))

                        # Registra uma etapa normal do fluxo, como conexão pronta ou evento publicado.
                        log.info("PUBLICADO %s", row["tipo"])

                    # Processa callbacks e heartbeat AMQP, limitando o intervalo do ciclo.
                    conexao.process_data_events(time_limit=0.2)

            # Trata Exception sem confundir falha com resultado válido.
            except Exception:

                # Desativa o sinal de conexão pronta porque o worker perdeu ou fechou o transporte.
                self.pronto.clear()

                # Registra a falha e seu traceback sem esconder o motivo do erro.
                log.exception("Falha AMQP em %s; nova tentativa em 3s", self.servico)

                # Executa self.parar.wait para concluir esta etapa do processamento.
                self.parar.wait(3)

            # Libera os recursos mesmo se ocorrer uma falha ou interrupção.
            finally:

                # Desativa o sinal de conexão pronta porque o worker perdeu ou fechou o transporte.
                self.pronto.clear()

                # Confere a condição conexao and conexao.is_open antes de executar este bloco.
                if conexao and conexao.is_open:

                    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
                    try:

                        # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
                        conexao.close()

                    # Trata pika.exceptions.AMQPError sem confundir falha com resultado válido.
                    except pika.exceptions.AMQPError:

                        # Não executa outra ação: o encerramento ou a simulação já foi tratado pelo contexto.
                        pass
