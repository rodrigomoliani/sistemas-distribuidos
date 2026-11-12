# Simulação local do pagamento: não chama banco, cartão ou API externa.
# A fila recebe pedido.estoque_ok; o callback publica o resultado retornado aqui.
# IDs processados e decisões não persistem após encerrar a sessão.

# Fornece o sorteio pseudoaleatório usado na simulação.
import random

# Copia todos os dados do pedido para compor a saída sem compartilhar referências.
from copy import deepcopy

# Valida a estrutura, os produtos e os valores do pedido recebido.
from comum.catalogo import validar_pedido


# Reúne a configuração de aprovação e o controle de pedidos processados.
class Pagamento:

    # Probabilidade padrão 0.5 representa 50%. sortear permite injetar uma função
    # controlada em testes; não é uma chamada a outro serviço.
    def __init__(self, probabilidade=0.5, sortear=None):

        # Exige valor entre zero e um, incluindo os extremos.
        if not 0 <= probabilidade <= 1:

            # Recusa configuração fora do intervalo permitido.
            raise ValueError("PROB_APROVACAO deve estar entre 0 e 1.")

        # Guarda o limite que será comparado com o valor sorteado.
        self.probabilidade = probabilidade

        # Guarda a função recebida ou random.random, sem executá-la neste momento.
        self.sortear = sortear or random.random

        # Conjunto em memória para não decidir duas vezes sobre o mesmo pedido.
        self.processados = set()

    # Contrato comum tratar(tipo, dados). tipo não é usado na decisão;
    # a topologia entrega a este serviço o evento pedido.estoque_ok.
    def tratar(self, tipo, dados):

        # Recusa entrada malformada antes de registrar o pedido como processado.
        validar_pedido(dados)

        # Obtém o identificador já validado do pedido.
        pedido_id = dados["pedido_id"]

        # Consulta se já tomou uma decisão para esse pedido nesta sessão.
        if pedido_id in self.processados:

            # Não gera nova decisão nem evento para a repetição.
            return []

        # Marca o ID antes de sortear. Este estado local não forma uma transação
        # com a publicação posterior; falhas exigem reiniciar a sessão limpa.
        self.processados.add(pedido_id)

        # Com random.random, o valor fica em [0, 1). O teste '<' aprova sempre
        # com probabilidade 1 e recusa sempre com 0; no padrão aprova cerca de 50%.
        aprovado = self.sortear() < self.probabilidade

        # Escolhe o nome do evento de acordo com o resultado booleano.
        evento = "pagamento.aprovado" if aprovado else "pagamento.recusado"

        # Registra a decisão no terminal; não envia a mensagem ao broker.
        print(f"PAGAMENTO {pedido_id} {evento}", flush=True)

        # Retorna uma lista contendo o evento e os dados completos do pedido.
        # A mensageria publica: aprovado vai ao Principal e à Entrega; recusado ao Principal.
        return [(evento, deepcopy(dados))]
