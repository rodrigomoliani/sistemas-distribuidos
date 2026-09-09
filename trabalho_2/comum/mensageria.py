import os
import threading

import pika

from comum.seguranca import Assinador

ECOMMERCE = "eCommerce"
PROMOCOES = "Promoções"
FILAS = {
    "principal": (ECOMMERCE, ["pedido.estoque_ok", "estoque.indisponivel",
                              "pagamento.aprovado", "pagamento.recusado", "pedido.enviado"]),
    "estoque": (ECOMMERCE, ["pedido.criado", "pedido.excluido"]),
    "pagamento": (ECOMMERCE, ["pedido.estoque_ok"]),
    "entrega": (ECOMMERCE, ["pagamento.aprovado"]),
    "promocoes.c1": (PROMOCOES, ["promocao.categoria.A", "promocao.categoria.B"]),
    "promocoes.c2": (PROMOCOES, ["promocao.categoria.*"]),
}


def conectar():
    parametros = pika.URLParameters(os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"))
    # O publicador do terminal pode ficar ocioso enquanto o usuário digita.
    parametros.heartbeat = 0
    parametros.blocked_connection_timeout = 10
    parametros.socket_timeout = 5
    return pika.BlockingConnection(parametros)


def declarar_topologia(canal):
    canal.exchange_declare(exchange=ECOMMERCE, exchange_type="direct", durable=False)
    canal.exchange_declare(exchange=PROMOCOES, exchange_type="topic", durable=False)
    for fila, (exchange, bindings) in FILAS.items():
        canal.queue_declare(queue=fila, durable=False, exclusive=False, auto_delete=False)
        for chave in bindings:
            canal.queue_bind(queue=fila, exchange=exchange, routing_key=chave)


class Publicador:
    """Conexão usada somente pela thread que criou esta instância."""
    def __init__(self, servico):
        self.assinador = Assinador.carregar(servico)
        self.conexao = conectar()
        self.canal = self.conexao.channel()
        declarar_topologia(self.canal)
        self.canal.confirm_delivery()

    def publicar(self, tipo, dados):
        corpo = self.assinador.assinar(tipo, dados)
        publicar_corpo(self.canal, tipo, corpo)

    def fechar(self):
        if self.conexao.is_open:
            self.conexao.close()


def publicar_corpo(canal, tipo, corpo):
    exchange = PROMOCOES if tipo.startswith("promocao.") else ECOMMERCE
    canal.basic_publish(exchange=exchange, routing_key=tipo, body=corpo, mandatory=True,
                        properties=pika.BasicProperties(content_type="application/json", delivery_mode=1))
    print(f"PUBLICADO {tipo}", flush=True)


def consumir(servico, tratar, parar=None, pronto=None):
    assinador = Assinador.carregar(servico)
    fila = f"promocoes.{servico}" if servico in ("c1", "c2") else servico
    parar = parar or threading.Event()
    vistos = set()
    conexao = conectar()
    try:
        canal = conexao.channel()
        declarar_topologia(canal)
        canal.confirm_delivery()
        canal.basic_qos(prefetch_count=1)

        def receber(ch, metodo, propriedades, corpo):
            try:
                evento = assinador.verificar(corpo, metodo.routing_key)
                if evento["event_id"] not in vistos:
                    saidas = tratar(evento["event_type"], evento["data"])
                    for tipo, dados in saidas:
                        publicar_corpo(ch, tipo, assinador.assinar(tipo, dados))
                    vistos.add(evento["event_id"])
            except ValueError as erro:
                print(f"DESCARTADO {metodo.routing_key}: {erro}", flush=True)
                ch.basic_reject(delivery_tag=metodo.delivery_tag, requeue=False)
                return
            # Falhas de conexão/publicação encerram a sessão, sem confirmar a entrada.
            ch.basic_ack(delivery_tag=metodo.delivery_tag)

        canal.basic_consume(queue=fila, on_message_callback=receber, auto_ack=False)
        print(f"PRONTO {servico} fila={fila}", flush=True)
        if pronto:
            pronto.set()
        while not parar.is_set():
            conexao.process_data_events(time_limit=0.5)
    finally:
        if conexao.is_open:
            conexao.close()


def executar(servico, tratar):
    try:
        consumir(servico, tratar)
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, pika.exceptions.AMQPError) as erro:
        print(f"FALHA {servico}: {type(erro).__name__}. Verifique RabbitMQ/chaves e reinicie a sessão limpa.", flush=True)
        raise SystemExit(1)
