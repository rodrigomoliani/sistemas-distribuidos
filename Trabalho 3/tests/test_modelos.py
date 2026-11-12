"""Testes unitários das regras de negócio dos modelos (Estoque, Entrega, Pagamento, Principal, Promoções)."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from comum.banco import Banco, json_texto
from comum.catalogo import montar_itens
from entrega.modelo import Entrega
from estoque.modelo import Estoque
from pagamento.modelo import Pagamento
from principal.modelo import Principal
from promocoes.modelo import Promocoes


def pedido(q=2, produto="1"):
    """Gera um payload de pedido simulado para os testes."""
    itens = montar_itens([(produto, q)])
    return {
        "pedido_id": str(uuid4()),
        "cliente": str(uuid4()),
        "nome": "Ana",
        "itens": itens,
        "total_centavos": sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens),
    }


class Regras(unittest.TestCase):
    def setUp(self):
        self.banco = Banco("teste", ":memory:")

    def tearDown(self):
        self.banco.fechar()

    def tratar(self, modelo, tipo, dados):
        with self.banco.transacao() as con:
            return modelo.tratar(con, tipo, dados)

    def test_reserva_e_devolucao_unica(self):
        e, p = Estoque(self.banco), pedido()
        # Primeira reserva
        self.assertEqual(self.tratar(e, "pedido.criado", p)[0][0], "pedido.estoque_ok")
        # Idempotência da reserva
        self.tratar(e, "pedido.criado", p)
        self.assertEqual(e.produtos()[0]["quantidade"], 8)

        # Devolução idempotente
        self.tratar(e, "pedido.excluido", {"pedido_id": p["pedido_id"]})
        self.tratar(e, "pedido.excluido", {"pedido_id": p["pedido_id"]})
        self.assertEqual(e.produtos()[0]["quantidade"], 10)

    def test_sem_reserva_parcial(self):
        e, p = Estoque(self.banco), pedido()
        p["itens"] = montar_itens([("1", 1), ("2", 11)])
        p["total_centavos"] = sum(i["quantidade"] * i["preco_unitario_centavos"] for i in p["itens"])

        # Quando qualquer item falta no estoque, a reserva de nenhum deve ser feita
        self.assertEqual(self.tratar(e, "pedido.criado", p)[0][0], "estoque.indisponivel")
        self.assertEqual([prod["quantidade"] for prod in e.produtos()], [10, 10, 10])

    def test_exclusao_antes_da_criacao(self):
        e, p = Estoque(self.banco), pedido()
        # Se pedido.excluido chegar antes de pedido.criado por desordem de rede
        self.tratar(e, "pedido.excluido", {"pedido_id": p["pedido_id"]})
        self.assertEqual(self.tratar(e, "pedido.criado", p), [])
        self.assertEqual(e.produtos()[0]["quantidade"], 10)

    def test_persistencia_estoque(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "estoque.sqlite3"
            b = Banco("estoque", arquivo)
            e = Estoque(b)
            with b.transacao() as con:
                e.tratar(con, "pedido.criado", pedido())
            b.fechar()

            # Reabre e valida estoque preservado em disco
            b = Banco("estoque", arquivo)
            self.assertEqual(Estoque(b).produtos()[0]["quantidade"], 8)
            b.fechar()

    def test_preco_adulterado(self):
        e, p = Estoque(self.banco), pedido()
        p["total_centavos"] = 1
        with self.assertRaises(ValueError):
            self.tratar(e, "pedido.criado", p)
        self.assertEqual(e.produtos()[0]["quantidade"], 10)

    def test_nota_idempotente(self):
        e, p = Entrega(self.banco), pedido()
        self.assertEqual(self.tratar(e, "pagamento.aprovado", p)[0][0], "pedido.enviado")
        self.assertEqual(self.tratar(e, "pagamento.aprovado", p), [])
        self.assertEqual(len(self.banco.ler("SELECT * FROM notas")), 1)

    def criar_principal(self):
        modelo, p = Principal(self.banco), pedido()
        with self.banco.transacao() as con:
            con.execute(
                "INSERT INTO pedidos(id,cliente,dados,estado) VALUES (?,?,?,?)",
                (p["pedido_id"], p["cliente"], json_texto(p), "Pedido Criado"),
            )
        return modelo, p

    def test_eventos_atrasados_nao_regridem(self):
        m, p = self.criar_principal()
        self.tratar(m, "pedido.enviado", {"pedido_id": p["pedido_id"], "nota_id": "nf"})
        self.tratar(m, "pagamento.aprovado", p)
        self.tratar(m, "pedido.estoque_ok", p)

        r = m.consultar(p["cliente"])[0]
        self.assertEqual(r["estado"], "Pedido Enviado")
        self.assertEqual(len(r["historico"]), 3)

    def test_recusa_gera_exclusao(self):
        m, p = self.criar_principal()
        self.assertEqual(self.tratar(m, "pagamento.recusado", p)[0][0], "pedido.excluido")
        self.assertEqual(self.tratar(m, "pedido.enviado", {"pedido_id": p["pedido_id"], "nota_id": "nf"}), [])
        self.assertEqual(m.consultar(p["cliente"])[0]["estado"], "Pagamento Recusado")

    def test_interesse_cancelamento_e_evento_atrasado(self):
        m, cid = Promocoes(self.banco), str(uuid4())
        dados = {
            "cliente": cid,
            "email": "ana@example.com",
            "categorias": ["A", "B"],
            "versao": 1,
        }
        self.tratar(m, "interesse.promocao", dados)
        self.tratar(m, "interesse.promocao", {**dados, "categorias": [], "versao": 2})
        # Evento versão 1 atrasado deve ser ignorado em favor da versão 2
        self.tratar(m, "interesse.promocao", dados)

        self.assertEqual(json.loads(self.banco.ler("SELECT * FROM interesses")[0]["categorias"]), [])

    def test_checkout_idempotente_e_webhook(self):
        m, p = Pagamento(self.banco), pedido()
        resposta = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"id": "cob1", "checkout_url": "http://localhost:8003/checkout/cob1"},
        )
        with patch("pagamento.modelo.httpx.post", return_value=resposta) as chamada:
            self.tratar(m, "pedido.estoque_ok", p)
            self.tratar(m, "pedido.estoque_ok", p)
            chamada.assert_called_once()

        entrada = SimpleNamespace(
            cobranca_id="cob1",
            pedido_id=p["pedido_id"],
            total_centavos=p["total_centavos"],
            status="APROVADO",
        )
        with self.banco.transacao() as con:
            self.assertEqual(m.resultado(con, entrada)[0][0], "pagamento.aprovado")
            self.assertEqual(m.resultado(con, entrada), [])

            # Decisão conflitante após aprovação
            entrada.status = "RECUSADO"
            with self.assertRaises(ValueError):
                m.resultado(con, entrada)

    def test_transacao_desfaz_estado_e_outbox(self):
        with self.assertRaises(RuntimeError):
            with self.banco.transacao() as con:
                con.execute("INSERT INTO outbox(tipo,corpo) VALUES ('x','y')")
                raise RuntimeError("Falha simulada")

        self.assertEqual(self.banco.ler("SELECT * FROM outbox"), [])


if __name__ == "__main__":
    unittest.main()
