import json
import unittest

from Crypto.PublicKey import RSA

from comum.seguranca import Assinador, serializar


class SegurancaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.principal = RSA.generate(2048)
        cls.estoque = RSA.generate(2048)

    def setUp(self):
        publicas = {"principal": self.principal.public_key(), "estoque": self.estoque.public_key()}
        self.emissor = Assinador("principal", self.principal, publicas)
        self.receptor = Assinador("estoque", self.estoque, publicas)
        self.corpo = self.emissor.assinar("pedido.criado", {"pedido_id": "123", "cliente": "João"})

    def test_assinatura_valida_e_json_reordenado(self):
        dados = json.loads(self.corpo)
        corpo = json.dumps(dict(reversed(list(dados.items()))), ensure_ascii=False, indent=2).encode()
        self.assertEqual(self.receptor.verificar(corpo, "pedido.criado")["data"]["cliente"], "João")

    def test_conteudo_adulterado(self):
        dados = json.loads(self.corpo)
        dados["data"]["cliente"] = "Outro"
        with self.assertRaises(ValueError):
            self.receptor.verificar(serializar(dados), "pedido.criado")

    def test_chave_errada(self):
        self.receptor.publicas["principal"] = self.estoque.public_key()
        with self.assertRaises(ValueError):
            self.receptor.verificar(self.corpo, "pedido.criado")

    def test_evento_roteado_com_chave_diferente(self):
        with self.assertRaises(ValueError):
            self.receptor.verificar(self.corpo, "pedido.excluido")

    def test_produtor_nao_pode_publicar_evento_de_outro(self):
        with self.assertRaises(ValueError):
            self.emissor.assinar("pagamento.aprovado", {})

    def test_envelopes_invalidos(self):
        for corpo in (b"[]", b"null", b"{}", b"not json", b"\xff"):
            with self.assertRaises(ValueError):
                self.receptor.verificar(corpo, "pedido.criado")
        dados = json.loads(self.corpo)
        dados["Signature"] = "%%%"
        with self.assertRaises(ValueError):
            self.receptor.verificar(serializar(dados), "pedido.criado")


if __name__ == "__main__":
    unittest.main()
