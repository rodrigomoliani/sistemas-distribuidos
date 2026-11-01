"""Testes unitários de contratos HTTP da API REST (Gateway, Pagamento e Mock)."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from comum.banco import Banco
from comum.config import WEBHOOK_SECRET
from comum.seguranca import Assinador
from mock_pagamento.api import app as mock_app
from pagamento.api import app as pagamento_app
from principal.api import app


class WorkerTeste:
    """Isola o transporte AMQP nos testes de rotas HTTP; simula interface do Trabalhador."""

    def __init__(self, servico, banco, tratar):
        self.assinador = Assinador.carregar(servico)
        self.pronto = SimpleNamespace(is_set=lambda: True)
        self.thread = SimpleNamespace(is_alive=lambda: False)

    def iniciar(self):
        pass

    def fechar(self):
        pass


class API(unittest.TestCase):
    def setUp(self):
        self.banco_patch = patch("comum.web.Banco", side_effect=lambda s: Banco(s, ":memory:"))
        self.worker_patch = patch("comum.web.Trabalhador", WorkerTeste)
        self.banco_patch.start()
        self.worker_patch.start()

        self.client = TestClient(app)
        self.client.__enter__()
        self.cid = str(uuid4())

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.worker_patch.stop()
        self.banco_patch.stop()

    def test_cria_pedido_preco_vem_do_estoque(self):
        catalogo = [{"id": "1", "nome": "Caderno", "preco_centavos": 1500, "quantidade": 10}]
        with patch("principal.api.obter_produtos", return_value=catalogo):
            r = self.client.post(
                "/pedidos",
                json={
                    "cliente": self.cid,
                    "nome": "Ana",
                    "itens": [
                        {"produto_id": "1", "quantidade": 2},
                        {"produto_id": "1", "quantidade": 1},
                    ],
                },
            )

        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["total_centavos"], 4500)
        self.assertEqual(len(r.json()["itens"]), 1)
        self.assertEqual(len(app.state.banco.ler("SELECT * FROM outbox")), 1)

        outro = self.client.get("/pedidos", params={"cliente": str(uuid4())})
        self.assertEqual(outro.json(), [])

    def test_rejeita_quantidade_booleana_e_cliente_invalido(self):
        for quantidade in (True, 0, -1, "2"):
            r = self.client.post(
                "/pedidos",
                json={
                    "cliente": self.cid,
                    "nome": "Ana",
                    "itens": [{"produto_id": "1", "quantidade": quantidade}],
                },
            )
            self.assertEqual(r.status_code, 422)

        self.assertEqual(self.client.get("/pedidos?cliente=ana").status_code, 422)

    def test_interesse_cancelamento_eventos_assinados(self):
        self.assertEqual(
            self.client.put(
                "/interesses",
                json={"cliente": self.cid, "email": "ana@example.com", "categorias": ["A", "B"]},
            ).status_code,
            202,
        )
        self.assertEqual(self.client.delete("/interesses?cliente=" + self.cid).status_code, 202)

        eventos = app.state.banco.ler("SELECT * FROM outbox")
        verificador = app.state.worker.assinador
        dados = [verificador.verificar(r["corpo"], r["tipo"])["data"] for r in eventos]

        self.assertEqual(dados[1]["categorias"], [])
        self.assertEqual(dados[1]["versao"], 2)

    def test_documentacao_e_sse_header_invalido(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/eventos", paths)
        self.assertEqual(
            self.client.get("/eventos?cliente=" + self.cid, headers={"Last-Event-ID": "abc"}).status_code,
            400,
        )


class WebhookAPI(unittest.TestCase):
    def test_webhook_sem_assinatura(self):
        with patch("comum.web.Banco", side_effect=lambda s: Banco(s, ":memory:")), patch(
            "comum.web.Trabalhador", WorkerTeste
        ):
            with TestClient(pagamento_app) as cliente:
                self.assertEqual(cliente.post("/webhook", json={"status": "APROVADO"}).status_code, 401)

    def test_mock_restringe_webhook_e_chave(self):
        with patch("mock_pagamento.api.Banco", side_effect=lambda s: Banco(s, ":memory:")):
            with TestClient(mock_app) as cliente:
                dados = {
                    "pedido_id": str(uuid4()),
                    "total_centavos": 1500,
                    "webhook_url": "http://localhost:9999/roubar",
                }
                # Sem API Key
                self.assertEqual(cliente.post("/cobrancas", json=dados).status_code, 401)
                # Com API Key, mas URL de webhook não autorizada
                self.assertEqual(
                    cliente.post("/cobrancas", json=dados, headers={"X-API-Key": WEBHOOK_SECRET}).status_code,
                    422,
                )


if __name__ == "__main__":
    unittest.main()
