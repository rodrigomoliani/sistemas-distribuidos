"""Testes unitários de integridade de mensagens RSA e webhooks HMAC."""

import json
import time
import unittest

from Crypto.PublicKey import RSA

from comum.seguranca import Assinador
from comum.webhook import assinar_webhook, verificar_webhook


class Seguranca(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chave = RSA.generate(2048)
        cls.a = Assinador("principal", cls.chave, {"principal": cls.chave.public_key()})

    def test_assinatura_valida(self):
        corpo = self.a.assinar("interesse.promocao", {"email": "ana@example.com"})
        self.assertEqual(self.a.verificar(corpo, "interesse.promocao")["producer"], "principal")

    def test_adulteracao_rejeitada(self):
        corpo = json.loads(self.a.assinar("pedido.criado", {"total_centavos": 1500}))
        corpo["data"]["total_centavos"] = 1
        with self.assertRaises(ValueError):
            self.a.verificar(json.dumps(corpo), "pedido.criado")

    def test_routing_incorreto(self):
        with self.assertRaises(ValueError):
            self.a.verificar(self.a.assinar("pedido.criado", {}), "pedido.excluido")

    def test_produtor_nao_autorizado(self):
        with self.assertRaises(ValueError):
            self.a.assinar("pagamento.aprovado", {})

    def test_envelopes_malformados(self):
        for corpo in (b"null", b"[]", b"{", b'{"data":{}}'):
            with self.subTest(corpo=corpo), self.assertRaises(ValueError):
                self.a.verificar(corpo, "pedido.criado")

    def test_webhook_integridade_e_expiracao(self):
        corpo = b'{"status":"APROVADO"}'
        ts = str(int(time.time()))
        sig = assinar_webhook(corpo, ts)
        self.assertTrue(verificar_webhook(corpo, ts, sig))
        self.assertFalse(verificar_webhook(b'{"status":"RECUSADO"}', ts, sig))

        velho = str(int(time.time()) - 301)
        self.assertFalse(verificar_webhook(corpo, velho, assinar_webhook(corpo, velho)))


if __name__ == "__main__":
    unittest.main()
