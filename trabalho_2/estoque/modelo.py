# Controle local de saldo e reservas. O consumidor chama tratar e publica suas saídas.
# Não há chamadas de rede aqui. Os conjuntos evitam repetir efeitos por pedido_id
# na sessão; comum/mensageria.py também filtra repetições pelo event_id.

# Permite devolver dados independentes do objeto de entrada.
from copy import deepcopy

# Importa catálogo, saldo inicial e validação do contrato dos pedidos.
from comum.catalogo import CATALOGO, ESTOQUE_INICIAL, validar_pedido


# Classe responsável por reservar e devolver unidades dos produtos.
class Estoque:

    # Cria o estado de uma sessão nova do serviço Estoque.
    def __init__(self):

        # Compreensão de dicionário: cada ID do catálogo começa com dez unidades.
        self.saldos = {p: ESTOQUE_INICIAL for p in CATALOGO}

        # Mapa pedido_id -> quantidades reservadas por produto.
        self.reservas = {}

        # IDs cuja criação já foi examinada, inclusive tentativas sem estoque.
        self.criados = set()

        # IDs excluídos; guarda também exclusões que chegarem antes da criação.
        self.excluidos = set()

    # Recebe pedido.criado ou pedido.excluido, conforme os bindings da fila.
    def tratar(self, tipo, dados):

        # Lê o ID no dicionário local; não é uma requisição HTTP.
        pedido_id = dados.get("pedido_id")

        # Valida o ID antes de consultar conjuntos ou dicionários.
        if not isinstance(pedido_id, str) or not pedido_id:

            # Mensagem malformada será rejeitada pela mensageria.
            raise ValueError("pedido_id ausente.")

        # Exclusão usa apenas o ID; não exige itens nem os demais dados de criação.
        if tipo == "pedido.excluido":

            # Só devolve se ainda não processou uma exclusão para esse pedido.
            if pedido_id not in self.excluidos:

                # Registra a exclusão mesmo sem reserva, impedindo uma reserva futura atrasada.
                self.excluidos.add(pedido_id)

                # pop retira e retorna a reserva. Se não houver, usa dicionário vazio.
                # Remover o registro também impede devolver as mesmas unidades novamente.
                reserva = self.reservas.pop(pedido_id, {})

                # Percorre exatamente os produtos e quantidades que haviam sido reservados.
                for produto_id, quantidade in reserva.items():

                    # Devolve ao saldo a quantidade registrada, não uma quantidade da mensagem.
                    self.saldos[produto_id] += quantidade

                # Exibe a devolução e os novos saldos para acompanhar a demonstração.
                print(f"DEVOLUCAO {pedido_id} {reserva} SALDOS {self.saldos}", flush=True)

            # Exclusão não gera outro evento; repetidas também terminam aqui sem devolver.
            return []

        # Valida o pedido completo antes de modificar saldos ou registrar sua criação.
        validar_pedido(dados)

        # Impede nova reserva para criações repetidas ou exclusões recebidas antes.
        if pedido_id in self.criados or pedido_id in self.excluidos:

            # Não publica confirmação adicional nem altera o saldo nesses casos.
            return []

        # Marca a tentativa como examinada nesta sessão.
        self.criados.add(pedido_id)

        # Transforma os itens já validados em um mapa produto -> quantidade solicitada.
        reserva = {i["produto_id"]: i["quantidade"] for i in dados["itens"]}

        # any detecta se pelo menos um produto tem saldo insuficiente.
        # A conferência de todos os itens vem ANTES de descontar qualquer unidade.
        if any(self.saldos[p] < q for p, q in reserva.items()):

            # Retorna a falha que levará o Principal a excluir o pedido.
            # Não existe reserva parcial nesse caminho e não há publicação direta aqui.
            return [("estoque.indisponivel", {"pedido_id": pedido_id, "motivo": "Estoque insuficiente"})]

        # Somente após a conferência percorre os itens para efetivar a reserva local.
        for produto_id, quantidade in reserva.items():

            # Desconta do saldo disponível a quantidade de cada produto.
            self.saldos[produto_id] -= quantidade

        # Guarda a reserva por pedido para uma possível devolução posterior.
        self.reservas[pedido_id] = reserva

        # Mostra a reserva e os saldos no terminal.
        print(f"RESERVA {pedido_id} {reserva} SALDOS {self.saldos}", flush=True)

        # Retorna a confirmação com os dados completos para Pagamento e Principal.
        # O callback em comum/mensageria.py assina e publica esse evento.
        return [("pedido.estoque_ok", deepcopy(dados))]
