# Entrada do processo Pagamento: python -m pagamento.
# A variável de ambiente controla a simulação, sem acesso a serviços financeiros.

# Acessa variáveis do ambiente do próprio processo.
import os

# Importa a função que abre o consumo RabbitMQ e trata falhas do serviço.
from comum.mensageria import executar

# Importa a regra local de aprovação ou recusa.
from pagamento.modelo import Pagamento

# Inicia apenas quando executado como programa.
if __name__ == "__main__":

    # Separa erros de configuração das falhas durante o consumo.
    try:

        # Lê PROB_APROVACAO com padrão 0.5, converte para número e cria o modelo.
        # float pode rejeitar texto inválido; Pagamento valida o intervalo de 0 a 1.
        modelo = Pagamento(float(os.environ.get("PROB_APROVACAO", "0.5")))

    # Captura erro de conversão ou de probabilidade fora do intervalo.
    except ValueError as erro:

        # Encerra mostrando a mensagem de configuração inválida.
        raise SystemExit(str(erro))

    # [AMQP VIA COMUM] Abre o consumidor de pedido.estoque_ok.
    # Passa modelo.tratar como callback de negócio; não o executa antecipadamente.
    executar("pagamento", modelo.tratar)
