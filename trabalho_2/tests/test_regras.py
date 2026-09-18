# Testes unitários das regras: executam os modelos no mesmo processo, sem broker.
# As chamadas diretas entre modelos existem apenas neste teste para isolar o negócio.
# Na aplicação, os serviços são processos separados e trocam eventos via RabbitMQ.
# Cada assert registra um resultado esperado; uma divergência faz o teste falhar.

# Framework padrão do Python que descobre e executa os métodos test_*.
import unittest

# Modelo de nota/envio simulado que será instanciado somente para o teste.
from entrega.modelo import Entrega

# Modelo de saldos e reservas.
from estoque.modelo import Estoque

# Modelo do pagamento com probabilidade controlável.
from pagamento.modelo import Pagamento

# Modelo dos pedidos e suas transições de estado.
from principal.modelo import Principal


# Agrupa os cenários e herda métodos de asserção de unittest.TestCase.
class RegrasTest(unittest.TestCase):

    # Executa antes de CADA teste, garantindo estado independente dos anteriores.
    def setUp(self):

        # Cria um Principal sem pedidos.
        self.principal = Principal()

        # Cria um Estoque com dez unidades por produto.
        self.estoque = Estoque()

        # Prepara pedido de Ana: dois Cadernos e uma Camiseta, total de 8000 centavos.
        self.tipo, self.pedido = self.principal.criar("Ana", [("1", 2), ("2", 1)])

        # Guarda o ID para consultar o mesmo pedido ao longo do cenário.
        self.id = self.pedido["pedido_id"]

    # Auxiliar para efetuar a primeira reserva do pedido padrão.
    def reservar(self):

        # Chama a regra diretamente e seleciona o primeiro evento da lista retornada.
        return self.estoque.tratar(self.tipo, self.pedido)[0]

    # Cenário completo: criação, reserva, aprovação e envio.
    def test_fluxo_aprovado_ate_envio(self):

        # Reserva os itens e recebe pedido.estoque_ok.
        tipo, dados = self.reservar()

        # Atualiza o Principal com a confirmação de estoque, sem usar rede neste teste.
        self.principal.tratar(tipo, dados)

        # Probabilidade 1 garante aprovação; [0] extrai o evento produzido.
        tipo, dados = Pagamento(1).tratar(tipo, dados)[0]

        # Atualiza o Principal com pagamento.aprovado.
        self.principal.tratar(tipo, dados)

        # Cria um modelo de Entrega para observar a nota gerada.
        entrega = Entrega()

        # Processa a aprovação e obtém pedido.enviado.
        tipo, dados = entrega.tratar(tipo, dados)[0]

        # Aplica a confirmação de envio ao pedido no Principal.
        self.principal.tratar(tipo, dados)

        # Verifica que o estado final observado é enviado.
        self.assertEqual(self.principal.pedidos[self.id]["status"], "enviado")

        # Verifica desconto exato das unidades pedidas e preservação do produto 3.
        self.assertEqual(self.estoque.saldos, {"1": 8, "2": 9, "3": 10})

        # Confere o total de R$ 80,00 no registro da nota simulada.
        self.assertEqual(entrega.notas[self.id]["total_centavos"], 8000)

    # Cenário em que só parte dos produtos teria estoque suficiente.
    def test_sem_estoque_nao_reserva_nenhum_item(self):

        # Produto 1 tem saldo, mas as onze unidades do produto 2 excedem seu saldo.
        tipo, dados = self.principal.criar("Ana", [("1", 1), ("2", 11)])

        # Executa a tentativa e captura estoque.indisponivel.
        falha = self.estoque.tratar(tipo, dados)[0]

        # O * desempacota (tipo, dados) nos dois argumentos; Principal gera exclusão.
        exclusao = self.principal.tratar(*falha)[0]

        # Entrega a exclusão ao Estoque para completar o fluxo local simulado.
        self.estoque.tratar(*exclusao)

        # Verifica que nem mesmo o produto com saldo foi reservado parcialmente.
        self.assertEqual(self.estoque.saldos, {"1": 10, "2": 10, "3": 10})

        # Confere que o Principal terminou com o pedido excluído.
        self.assertEqual(self.principal.pedidos[dados["pedido_id"]]["status"], "excluido")

    # Cenário de recusa com exclusão repetida para testar devolução única.
    def test_recusa_devolve_reserva_uma_vez(self):

        # Reserva os itens antes de decidir o pagamento.
        reserva = self.reservar()

        # Probabilidade 0 garante recusa.
        recusa = Pagamento(0).tratar(*reserva)[0]

        # O Principal transforma a recusa em pedido.excluido.
        exclusao = self.principal.tratar(*recusa)[0]

        # Primeira exclusão devolve as quantidades reservadas.
        self.estoque.tratar(*exclusao)

        # Segunda entrega da mesma exclusão não deve devolver novamente.
        self.estoque.tratar(*exclusao)

        # Verifica que o saldo voltou a dez, sem ultrapassá-lo.
        self.assertEqual(self.estoque.saldos, {"1": 10, "2": 10, "3": 10})

        # Recusa repetida não gera nova exclusão no Principal.
        self.assertEqual(self.principal.tratar(*recusa), [])

    # Simula chegada da exclusão ao Estoque antes da criação.
    def test_exclusao_antes_da_criacao(self):

        # Marca o pedido excluído no Principal e captura o evento.
        exclusao = self.principal.excluir(self.id)[0]

        # Entrega primeiro a exclusão ao Estoque, ainda sem reserva.
        self.estoque.tratar(*exclusao)

        # Uma criação atrasada desse ID deve ser ignorada, sem evento de reserva.
        self.assertEqual(self.estoque.tratar(self.tipo, self.pedido), [])

        # O saldo do produto permanece no valor inicial.
        self.assertEqual(self.estoque.saldos["1"], 10)

    # Valida proteção por pedido_id separadamente do filtro de event_id da mensageria.
    def test_repeticoes_por_pedido_nao_duplicam_efeitos(self):

        # Faz a primeira reserva normalmente.
        reserva = self.reservar()

        # Repetir a criação não produz outra reserva ou evento.
        self.assertEqual(self.estoque.tratar(self.tipo, self.pedido), [])

        # Cria um Pagamento com aprovação garantida.
        pagamento = Pagamento(1)

        # Processa a primeira decisão e guarda o evento aprovado.
        aprovado = pagamento.tratar(*reserva)[0]

        # Segunda tentativa para o mesmo pedido não produz decisão adicional.
        self.assertEqual(pagamento.tratar(*reserva), [])

        # Cria uma Entrega para testar a repetição da aprovação.
        entrega = Entrega()

        # Processa a primeira aprovação e gera nota.
        entrega.tratar(*aprovado)

        # Aprovação repetida não gera outro evento de envio.
        self.assertEqual(entrega.tratar(*aprovado), [])

        # Confirma que existe exatamente um registro de nota.
        self.assertEqual(len(entrega.notas), 1)

    # Garante que eventos atrasados não fazem um pedido enviado retroceder.
    def test_eventos_atrasados_nao_regridem_enviado(self):

        # Coloca o pedido diretamente em enviado para isolar esta regra.
        self.principal.tratar("pedido.enviado", {"pedido_id": self.id})

        # Percorre confirmações intermediárias e falhas que poderiam chegar atrasadas.
        for tipo in ("pagamento.aprovado", "pedido.estoque_ok", "pagamento.recusado", "estoque.indisponivel"):

            # Cada evento atrasado deve resultar em lista vazia de saídas.
            self.assertEqual(self.principal.tratar(tipo, {"pedido_id": self.id}), [])

            # Após cada evento, confere que o estado enviado permanece.
            self.assertEqual(self.principal.pedidos[self.id]["status"], "enviado")

    # Valida a escolha de exclusão lógica inclusive após o envio.
    def test_excluido_nao_reativa_e_exclusao_manual_e_logica(self):

        # Prepara um pedido que já está enviado.
        self.principal.tratar("pedido.enviado", {"pedido_id": self.id})

        # A primeira exclusão manual ainda é permitida e produz um único evento.
        self.assertEqual(len(self.principal.excluir(self.id)), 1)

        # Repetir a exclusão não produz evento adicional.
        self.assertEqual(self.principal.excluir(self.id), [])

        # Simula uma confirmação de envio que chegou após a exclusão.
        self.principal.tratar("pedido.enviado", {"pedido_id": self.id})

        # O estado final deve continuar excluído, sem reativação.
        self.assertEqual(self.principal.pedidos[self.id]["status"], "excluido")

    # Valida filtro por nome de cliente, que não equivale a autenticação.
    def test_cliente_so_consulta_e_exclui_os_proprios_pedidos(self):

        # Bruno não deve listar o pedido criado para Ana no setUp.
        self.assertEqual(self.principal.listar("Bruno"), [])

        # O bloco deve lançar ValueError; se não lançar, o teste falha.
        with self.assertRaises(ValueError):

            # Tenta excluir o pedido de Ana usando o nome Bruno.
            self.principal.excluir(self.id, cliente="Bruno")

    # Valida entradas recusadas e agrupamento de produtos repetidos.
    def test_entradas_invalidas_e_produtos_repetidos(self):

        # Casos: pedido vazio, zero, negativo, ID desconhecido e booleano como quantidade.
        for itens in ([], [("1", 0)], [("1", -1)], [("9", 1)], [("1", True)]):

            # Cada caso deve falhar por validação.
            with self.assertRaises(ValueError):

                # Tenta criar o pedido com a seleção inválida desta iteração.
                self.principal.criar("Ana", itens)

        # Duas entradas válidas do produto 1, com quantidades 2 e 3; _ ignora o tipo.
        _, dados = self.principal.criar("Ana", [("1", 2), ("1", 3)])

        # Espera um item agrupado com cinco unidades.
        self.assertEqual(dados["itens"][0]["quantidade"], 5)

        # Confere 5 vezes 1500 centavos, ou R$ 75,00.
        self.assertEqual(dados["total_centavos"], 7500)

    # Garante que preço modificado não cause uma reserva de estoque.
    def test_preco_adulterado_nao_altera_estoque(self):

        # Adultera diretamente o preço unitário para um centavo.
        self.pedido["itens"][0]["preco_unitario_centavos"] = 1

        # A regra deve identificar a divergência do catálogo e lançar ValueError.
        with self.assertRaises(ValueError):

            # Tenta reservar com os dados adulterados.
            self.estoque.tratar(self.tipo, self.pedido)

        # Confere que o saldo não foi alterado pela entrada recusada.
        self.assertEqual(self.estoque.saldos["1"], 10)

    # Valida IDs de produto com tipos inválidos, incluindo objetos não hashable.
    def test_identificador_de_produto_invalido_e_rejeitado_sem_reserva(self):

        # Tenta lista, dicionário, None e inteiro no lugar de um ID string.
        for produto_id in ([], {}, None, 1):

            # subTest identifica qual entrada falhou sem misturar os casos no relatório.
            with self.subTest(produto_id=produto_id):

                # Substitui o ID do primeiro item pela entrada inválida atual.
                self.pedido["itens"][0]["produto_id"] = produto_id

                # A falha esperada é ValueError, tratável pelo consumidor.
                with self.assertRaises(ValueError):

                    # Executa a validação/reserva com esse item malformado.
                    self.estoque.tratar(self.tipo, self.pedido)

                # Todos os saldos precisam permanecer intactos.
                self.assertEqual(self.estoque.saldos, {"1": 10, "2": 10, "3": 10})

                # Nenhuma reserva pode ter sido registrada.
                self.assertEqual(self.estoque.reservas, {})

    # Valida que um ID de pedido malformado não altera o estado conhecido.
    def test_identificador_de_pedido_invalido_nao_altera_o_principal(self):

        # Casos não textuais ou texto vazio.
        for pedido_id in ([], {}, None, "", 1):

            # Identifica separadamente cada variação da entrada no relatório.
            with self.subTest(pedido_id=pedido_id):

                # Exige uma rejeição de validação.
                with self.assertRaises(ValueError):

                    # Simula pedido.enviado com ID inválido.
                    self.principal.tratar("pedido.enviado", {"pedido_id": pedido_id})

                # O pedido válido original deve continuar no estado criado.
                self.assertEqual(self.principal.pedidos[self.id]["status"], "criado")


# Permite executar este arquivo como programa de teste.
if __name__ == "__main__":

    # Inicia a descoberta dos métodos de teste deste módulo.
    unittest.main()
