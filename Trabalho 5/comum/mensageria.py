import logging
import os
import threading
import pika

from comum.banco import emitir
from comum.seguranca import Assinador

log = logging.getLogger(__name__)

EXCHANGE = "eCommerce.trabalho3"

FILAS = {
    "principal": [
        "pedido.estoque_ok",
        "estoque.indisponivel",
        "pagamento.checkout_criado",
        "pagamento.aprovado",
        "pagamento.recusado",
        "pedido.enviado",
    ],
    "estoque": ["pedido.criado", "pedido.excluido"],
    "pagamento": ["pedido.estoque_ok", "pedido.excluido"],
    "entrega": ["pagamento.aprovado"],
    "promocoes": ["interesse.promocao"],
}


def conectar():
    """Abre uma conexão AMQP com timeouts e heartbeat configurados."""
    parametros = pika.URLParameters(
        os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
    )
    parametros.heartbeat = 30
    parametros.socket_timeout = 5
    parametros.blocked_connection_timeout = 10
    return pika.BlockingConnection(parametros)


def declarar_topologia(canal):
    """Declara a exchange direct durável e as filas duráveis com bindings de cada microsserviço."""
    canal.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    for servico, tipos in FILAS.items():
        fila = f"trabalho3.{servico}"
        canal.queue_declare(queue=fila, durable=True)
        for tipo in tipos:
            canal.queue_bind(queue=fila, exchange=EXCHANGE, routing_key=tipo)


class Trabalhador:
    """Worker AMQP: uma thread é dona da conexão Pika; HTTP acessa apenas o banco local e a outbox."""

    def __init__(self, servico, banco, tratar):
        self.servico, self.banco, self.tratar = servico, banco, tratar
        self.assinador = Assinador.carregar(servico)
        self.parar = threading.Event()
        self.pronto = threading.Event()
        self.thread = threading.Thread(
            target=self.executar, name=f"amqp-{servico}", daemon=True
        )

    def iniciar(self):
        self.thread.start()

    def fechar(self):
        self.parar.set()
        self.thread.join(timeout=15)

    def receber(self, ch, metodo, propriedades, corpo):
        """Verifica a assinatura digital e processa negócio, inbox e outbox na mesma transação."""
        try:
            evento = self.assinador.verificar(corpo, metodo.routing_key)
            with self.banco.transacao() as con:
                # Deduplicação pelo ID único do evento (Inbox)
                if not con.execute(
                    "SELECT 1 FROM inbox WHERE event_id=?", (evento["event_id"],)
                ).fetchone():
                    for tipo, dados in self.tratar(con, evento["event_type"], evento["data"]):
                        emitir(con, self.assinador, tipo, dados)
                    con.execute("INSERT INTO inbox VALUES (?)", (evento["event_id"],))

        except ValueError as erro:
            log.warning("DESCARTADO %s: %s", metodo.routing_key, erro)
            ch.basic_reject(delivery_tag=metodo.delivery_tag, requeue=False)
            return

        ch.basic_ack(delivery_tag=metodo.delivery_tag)

    def executar(self):
        """Loop de conexão e consumo do RabbitMQ com publicação contínua da outbox."""
        while not self.parar.is_set():
            conexao = None
            try:
                conexao = conectar()
                canal = conexao.channel()
                declarar_topologia(canal)
                canal.confirm_delivery()
                canal.basic_qos(prefetch_count=1)
                canal.basic_consume(
                    queue=f"trabalho3.{self.servico}", on_message_callback=self.receber
                )

                self.pronto.set()
                log.info("PRONTO %s", self.servico)

                while not self.parar.is_set():
                    for row in self.banco.ler("SELECT * FROM outbox ORDER BY id LIMIT 50"):
                        canal.basic_publish(
                            exchange=EXCHANGE,
                            routing_key=row["tipo"],
                            body=row["corpo"],
                            mandatory=True,
                            properties=pika.BasicProperties(
                                content_type="application/json", delivery_mode=2
                            ),
                        )
                        with self.banco.transacao() as con:
                            con.execute("DELETE FROM outbox WHERE id=?", (row["id"],))
                        log.info("PUBLICADO %s", row["tipo"])

                    conexao.process_data_events(time_limit=0.2)

            except Exception:
                self.pronto.clear()
                log.exception("Falha AMQP em %s; nova tentativa em 3s", self.servico)
                self.parar.wait(3)
            finally:
                self.pronto.clear()
                if conexao and conexao.is_open:
                    try:
                        conexao.close()
                    except pika.exceptions.AMQPError:
                        pass
