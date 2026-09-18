# Entrada do processo Entrega: python -m entrega.

# Importa a infraestrutura de consumo AMQP e tratamento de falhas.
from comum.mensageria import executar

# Importa as regras de nota e envio simulados.
from entrega.modelo import Entrega

# Evita iniciar o laço ao apenas importar este módulo.
if __name__ == "__main__":

    # [AMQP VIA COMUM] Instancia Entrega e passa o método tratar ao consumidor.
    # A fila recebe pagamento.aprovado; o callback publicará pedido.enviado
    # quando esse método devolver o evento de saída.
    executar("entrega", Entrega().tratar)
