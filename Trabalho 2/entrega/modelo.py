# Registra uma nota e um envio simulados em memória, sem transportadora ou nota fiscal real.
# Recebe aprovação via RabbitMQ e devolve um evento para o callback publicar.

# Copia os itens para o registro não compartilhar estruturas mutáveis da entrada.
from copy import deepcopy

# Gera um identificador aleatório para a nota simulada.
from uuid import uuid4

# Reutiliza a validação local dos dados do pedido.
from comum.catalogo import validar_pedido


# Mantém o registro de entregas realizadas durante esta sessão.
class Entrega:

    # Inicializa uma instância do serviço.
    def __init__(self):

        # Mapa pedido_id -> nota; também controla repetição por pedido.
        self.notas = {}

    # A topologia fornece pagamento.aprovado; tipo mantém a interface dos modelos.
    def tratar(self, tipo, dados):

        # Confere os dados antes de criar qualquer registro de entrega.
        validar_pedido(dados)

        # Extrai o identificador já validado do pedido.
        pedido_id = dados["pedido_id"]

        # Detecta uma aprovação repetida para um pedido que já tem nota.
        if pedido_id in self.notas:

            # Não cria outra nota nem emite novo evento de envio.
            return []

        # Cria um número de nota e o associa ao ID do pedido.
        nota = {"numero": str(uuid4()), "pedido_id": pedido_id,

                # Copia o nome do cliente e o total em centavos para o registro.
                "cliente": dados["cliente"], "total_centavos": dados["total_centavos"],

                # deepcopy isola a lista de itens e seus dicionários internos.
                "itens": deepcopy(dados["itens"])}

        # Salva a nota somente na memória do processo.
        self.notas[pedido_id] = nota

        # Imprime a simulação; não realiza uma entrega física nem acessa outro sistema.
        print(f"NOTA_SIMULADA {nota} ENVIO_PREPARADO {pedido_id}", flush=True)

        # Retorna ID do pedido e ID da nota para o evento pedido.enviado.
        # O callback assina/publica no RabbitMQ; este return não faz comunicação de rede.
        return [("pedido.enviado", {"pedido_id": pedido_id, "nota_id": nota["numero"]})]
