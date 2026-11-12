# Entrada do processo Estoque: python -m estoque.
# O estado fica no modelo; a comunicação e as assinaturas ficam no módulo comum.

# Importa o laço consumidor com tratamento de erros e conexão RabbitMQ.
from comum.mensageria import executar

# Importa a classe que controla os saldos e as reservas.
from estoque.modelo import Estoque

# Só inicia o serviço quando este módulo é executado como programa.
if __name__ == "__main__":

    # [AMQP VIA COMUM] Cria o modelo e entrega seu método tratar como função.
    # executar chama consumir, que se conecta, registra o consumidor na fila
    # e processa as entregas recebidas do RabbitMQ.
    # Estoque().tratar não tem parênteses finais: não executa a regra neste momento.
    executar("estoque", Estoque().tratar)
