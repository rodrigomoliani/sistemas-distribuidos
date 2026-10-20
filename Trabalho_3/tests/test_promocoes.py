"""Testes unitários do microsserviço de promoções e envio de e-mails."""

import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from comum.banco import Banco
from comum.catalogo import CATALOGO
from promocoes.__main__ import disparar
from promocoes.email import Email
from promocoes.modelo import Promocoes


class EmailPromocoes(unittest.TestCase):
    def test_categorias_e_cancelamento(self):
        banco = Banco("teste", ":memory:")
        modelo = Promocoes(banco)
        cid = str(uuid4())

        # Registra interesse em categoria A
        with banco.transacao() as con:
            modelo.tratar(
                con,
                "interesse.promocao",
                {"cliente": cid, "email": "ana@example.com", "categorias": ["A"], "versao": 1},
            )

        email = SimpleNamespace(modo="arquivo", enviar=lambda *args: None)

        # Produto sem correspondência na categoria A não gera envio
        with patch("promocoes.__main__.random.choice", side_effect=[CATALOGO["2"], 10]):
            disparar(banco, email)
        self.assertEqual(len(banco.ler("SELECT * FROM envios")), 0)

        # Produto compatível com categoria A gera envio
        with patch("promocoes.__main__.random.choice", side_effect=[CATALOGO["1"], 10]):
            disparar(banco, email)
        self.assertEqual(len(banco.ler("SELECT * FROM envios")), 1)

        # Cancelamento de interesse (categorias vazias)
        with banco.transacao() as con:
            modelo.tratar(
                con,
                "interesse.promocao",
                {"cliente": cid, "email": "ana@example.com", "categorias": [], "versao": 2},
            )

        with patch("promocoes.__main__.random.choice", side_effect=[CATALOGO["1"], 20]):
            disparar(banco, email)
        self.assertEqual(len(banco.ler("SELECT * FROM envios")), 1)

        banco.fechar()

    def test_resend_contrato_http_sem_envio_real(self):
        with patch.dict(
            os.environ,
            {
                "EMAIL_MODO": "resend",
                "RESEND_API_KEY": "chave-teste",
                "EMAIL_FROM": "teste@example.com",
            },
        ):
            email = Email()

        resposta = SimpleNamespace(raise_for_status=lambda: None)
        with patch("promocoes.email.httpx.post", return_value=resposta) as chamada:
            email.enviar("ana@example.com", "Oferta", "Texto", "campanha-1")

        self.assertEqual(chamada.call_args.args, ("https://api.resend.com/emails",))
        self.assertEqual(chamada.call_args.kwargs["headers"]["Idempotency-Key"], "campanha-1")
        self.assertEqual(chamada.call_args.kwargs["json"]["to"], ["ana@example.com"])

    def test_resend_sem_chave_falha_explicitamente(self):
        with patch.dict(os.environ, {"EMAIL_MODO": "resend", "RESEND_API_KEY": ""}):
            with self.assertRaises(ValueError):
                Email()


if __name__ == "__main__":
    unittest.main()
