# Estado e regras locais do Principal. Nenhuma linha deste arquivo abre rede.
# Os retornos (tipo, dados) são publicados por comum/mensageria.py ou pelo menu.
# O estado existe somente na memória deste processo durante a sessão.

# Copia também listas e dicionários internos, evitando compartilhar dados mutáveis.
from copy import deepcopy

# Lock reentrante: a mesma thread pode adquiri-lo novamente sem se bloquear.
from threading import RLock

# Gera o identificador aleatório do pedido; não é o event_id do envelope AMQP.
from uuid import uuid4

# Reutiliza a validação dos itens e os preços do catálogo local.
from comum.catalogo import montar_itens


# Classe que reúne pedidos, criação, exclusão e atualização de estado.
class Principal:

    # Construtor executado quando o programa cria Principal().
    def __init__(self):

        # Mapa pedido_id -> dados/status/motivo. Não há banco de dados ou persistência.
        self.pedidos = {}

        # Protege o acesso concorrente do menu e da thread consumidora.
        # RLock é necessário porque tratar chama excluir dentro do mesmo lock.
        self.lock = RLock()

    # Recebe o nome do cliente e pares (produto_id, quantidade) escolhidos no menu.
    def criar(self, cliente, selecao):

        # strip remove espaços das pontas; texto vazio ou só com espaços é recusado.
        if not cliente.strip():

            # Interrompe a criação para que o menu mostre a entrada inválida.
            raise ValueError("Informe o cliente.")

        # Valida produtos e quantidades, agrupa repetições e aplica preços do catálogo.
        itens = montar_itens(selecao)

        # Cria um UUID para o pedido, normaliza o nome e inclui a lista de itens.
        dados = {"pedido_id": str(uuid4()), "cliente": cliente.strip(), "itens": itens,

                 # Soma quantidade vezes preço unitário de cada item, em centavos.
                 "total_centavos": sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens)}

        # Adquire o lock; o with o libera automaticamente mesmo se ocorrer uma exceção.
        with self.lock:

            # Registra o novo pedido no estado criado e inicialmente sem motivo de exclusão.
            self.pedidos[dados["pedido_id"]] = {"dados": dados, "status": "criado", "motivo": ""}

        # Retorna um par de evento e uma cópia profunda dos dados.
        # É só um retorno local: o envio acontece em publicador.publicar no menu.
        return "pedido.criado", deepcopy(dados)

    # Exclusão lógica: motivo padrão é manual; cliente opcional restringe o dono.
    # Mesmo um pedido enviado pode ser excluído neste escopo, sem estorno ou
    # interrupção garantida da entrega. Não removemos seu registro do dicionário.
    def excluir(self, pedido_id, motivo="exclusão manual", cliente=None):

        # Serializa esta alteração com as atualizações recebidas pelo consumidor.
        with self.lock:

            # get consulta o dicionário em memória; não é HTTP GET.
            pedido = self.pedidos.get(pedido_id)

            # Recusa ID desconhecido ou um pedido pertencente a outro cliente informado.
            if pedido is None or (cliente is not None and pedido["dados"]["cliente"] != cliente):

                # A mesma mensagem cobre ausência e cliente incompatível.
                raise ValueError("Pedido não encontrado para este cliente.")

            # Verifica se uma solicitação anterior já marcou esse pedido como excluído.
            if pedido["status"] == "excluido":

                # Lista vazia significa que não há novo evento de saída: exclusão idempotente.
                return []

            # Altera status e motivo no registro existente, preservando os dados do pedido.
            pedido.update(status="excluido", motivo=motivo)

            # Retorna o evento que avisará o Estoque para devolver a reserva, se houver.
            # O transporte publicará essa saída; este método não acessa o RabbitMQ.
            return [("pedido.excluido", {"pedido_id": pedido_id, "motivo": motivo})]

    # Função de negócio chamada pelo consumidor após validar o envelope assinado.
    # Os tipos esperados são aqueles ligados à fila principal na topologia.
    def tratar(self, tipo, dados):

        # Obtém o ID dentro dos dados do evento recebido.
        pedido_id = dados.get("pedido_id")

        # Exige texto não vazio antes de usar o valor como chave do dicionário.
        if not isinstance(pedido_id, str) or not pedido_id:

            # ValueError fará o consumidor rejeitar a mensagem, sem encerrar o serviço.
            raise ValueError("pedido_id ausente ou inválido.")

        # Impede disputa com criação, consulta ou exclusão feita no menu.
        with self.lock:

            # Procura apenas pedidos conhecidos desta sessão.
            pedido = self.pedidos.get(pedido_id)

            # Ignora pedidos desconhecidos e impede reativar pedidos já excluídos.
            if pedido is None or pedido["status"] == "excluido":

                # Nada para publicar nesses casos; a mensageria ainda confirma a entrada válida.
                return []

            # Falhas de estoque ou pagamento causam exclusão automática.
            if tipo in ("estoque.indisponivel", "pagamento.recusado"):

                # Uma recusa atrasada não pode desfazer o estado enviado.
                if pedido["status"] == "enviado":

                    # Sai sem alterar estado e sem produzir uma exclusão automática tardia.
                    return []

                # Reutiliza a exclusão, usando o tipo da falha como motivo.
                # A chamada é local e readquire o RLock da mesma thread.
                saidas = self.excluir(pedido_id, tipo)

            # Demais eventos esperados representam avanço do fluxo.
            else:

                # Traduz confirmação da reserva para o nome do estado exibido pelo Principal.
                estados = {"pedido.estoque_ok": "estoque_reservado",

                           # Traduz aprovação e envio para seus respectivos estados locais.
                           "pagamento.aprovado": "pagamento_aprovado", "pedido.enviado": "enviado"}

                # Define uma ordem numérica para impedir que eventos atrasados façam retroceder.
                ordem = {"criado": 0, "estoque_reservado": 1, "pagamento_aprovado": 2, "enviado": 3}

                # Obtém o estado associado ao evento. O roteamento restringe os tipos esperados.
                estado = estados[tipo]

                # Só atualiza se o evento representar um estágio posterior ao estado atual.
                if ordem[estado] > ordem[pedido["status"]]:

                    # Grava o avanço; não exige que eventos de filas independentes cheguem em ordem.
                    pedido["status"] = estado

                # Atualizações bem-sucedidas não produzem outro evento pelo Principal.
                saidas = []

            # Exibe a atualização no terminal; flush evita aguardar o buffer de saída.
            print(f"STATUS {pedido_id} {pedido['status']} {pedido['motivo']}", flush=True)

            # Entrega à mensageria a lista de eventos de saída, possivelmente vazia.
            return saidas

    # Consulta os pedidos do nome de cliente informado; não faz comunicação remota.
    def listar(self, cliente):

        # Lê os pedidos de maneira consistente com as alterações das outras threads.
        with self.lock:

            # Filtra por cliente e retorna cópia profunda para o menu não alterar o estado.
            # O nome é identificação da demonstração, não autenticação de usuários.
            return deepcopy([p for p in self.pedidos.values() if p["dados"]["cliente"] == cliente])
