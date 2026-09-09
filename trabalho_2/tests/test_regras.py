import unittest

from entrega.modelo import Entrega
from estoque.modelo import Estoque
from pagamento.modelo import Pagamento
from principal.modelo import Principal


class RegrasTest(unittest.TestCase):
    def setUp(self):
        self.principal = Principal()
        self.estoque = Estoque()
        self.tipo, self.pedido = self.principal.criar("Ana", [("1", 2), ("2", 1)])
        self.id = self.pedido["pedido_id"]

    def reservar(self):
        return self.estoque.tratar(self.tipo, self.pedido)[0]

    def test_fluxo_aprovado_ate_envio(self):
        tipo, dados = self.reservar()
        self.principal.tratar(tipo, dados)
        tipo, dados = Pagamento(1).tratar(tipo, dados)[0]
        self.principal.tratar(tipo, dados)
        entrega = Entrega()
        tipo, dados = entrega.tratar(tipo, dados)[0]
        self.principal.tratar(tipo, dados)
        self.assertEqual(self.principal.pedidos[self.id]["status"], "enviado")
        self.assertEqual(self.estoque.saldos, {"1": 8, "2": 9, "3": 10})
        self.assertEqual(entrega.notas[self.id]["total_centavos"], 8000)

    def test_sem_estoque_nao_reserva_nenhum_item(self):
        tipo, dados = self.principal.criar("Ana", [("1", 1), ("2", 11)])
        falha = self.estoque.tratar(tipo, dados)[0]
        exclusao = self.principal.tratar(*falha)[0]
        self.estoque.tratar(*exclusao)
        self.assertEqual(self.estoque.saldos, {"1": 10, "2": 10, "3": 10})
        self.assertEqual(self.principal.pedidos[dados["pedido_id"]]["status"], "excluido")

    def test_recusa_devolve_reserva_uma_vez(self):
        reserva = self.reservar()
        recusa = Pagamento(0).tratar(*reserva)[0]
        exclusao = self.principal.tratar(*recusa)[0]
        self.estoque.tratar(*exclusao)
        self.estoque.tratar(*exclusao)
        self.assertEqual(self.estoque.saldos, {"1": 10, "2": 10, "3": 10})
        self.assertEqual(self.principal.tratar(*recusa), [])

    def test_exclusao_antes_da_criacao(self):
        exclusao = self.principal.excluir(self.id)[0]
        self.estoque.tratar(*exclusao)
        self.assertEqual(self.estoque.tratar(self.tipo, self.pedido), [])
        self.assertEqual(self.estoque.saldos["1"], 10)

    def test_repeticoes_por_pedido_nao_duplicam_efeitos(self):
        reserva = self.reservar()
        self.assertEqual(self.estoque.tratar(self.tipo, self.pedido), [])
        pagamento = Pagamento(1)
        aprovado = pagamento.tratar(*reserva)[0]
        self.assertEqual(pagamento.tratar(*reserva), [])
        entrega = Entrega()
        entrega.tratar(*aprovado)
        self.assertEqual(entrega.tratar(*aprovado), [])
        self.assertEqual(len(entrega.notas), 1)

    def test_eventos_atrasados_nao_regridem_enviado(self):
        self.principal.tratar("pedido.enviado", {"pedido_id": self.id})
        for tipo in ("pagamento.aprovado", "pedido.estoque_ok", "pagamento.recusado", "estoque.indisponivel"):
            self.assertEqual(self.principal.tratar(tipo, {"pedido_id": self.id}), [])
            self.assertEqual(self.principal.pedidos[self.id]["status"], "enviado")

    def test_excluido_nao_reativa_e_exclusao_manual_e_logica(self):
        self.principal.tratar("pedido.enviado", {"pedido_id": self.id})
        self.assertEqual(len(self.principal.excluir(self.id)), 1)
        self.assertEqual(self.principal.excluir(self.id), [])
        self.principal.tratar("pedido.enviado", {"pedido_id": self.id})
        self.assertEqual(self.principal.pedidos[self.id]["status"], "excluido")

    def test_cliente_so_consulta_e_exclui_os_proprios_pedidos(self):
        self.assertEqual(self.principal.listar("Bruno"), [])
        with self.assertRaises(ValueError):
            self.principal.excluir(self.id, cliente="Bruno")

    def test_entradas_invalidas_e_produtos_repetidos(self):
        for itens in ([], [("1", 0)], [("1", -1)], [("9", 1)], [("1", True)]):
            with self.assertRaises(ValueError):
                self.principal.criar("Ana", itens)
        _, dados = self.principal.criar("Ana", [("1", 2), ("1", 3)])
        self.assertEqual(dados["itens"][0]["quantidade"], 5)
        self.assertEqual(dados["total_centavos"], 7500)

    def test_preco_adulterado_nao_altera_estoque(self):
        self.pedido["itens"][0]["preco_unitario_centavos"] = 1
        with self.assertRaises(ValueError):
            self.estoque.tratar(self.tipo, self.pedido)
        self.assertEqual(self.estoque.saldos["1"], 10)


if __name__ == "__main__":
    unittest.main()
