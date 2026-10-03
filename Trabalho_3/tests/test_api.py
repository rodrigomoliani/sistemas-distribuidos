# Testes dos contratos HTTP, com transporte AMQP isolado e SQLite em memória.

# Importa estrutura de testes, asserções e execução automática dos casos.
import unittest

# Importa objetos simples que simulam respostas e componentes nos testes.
from types import SimpleNamespace

# Importa substituições temporárias de dependências, sem acesso a serviços reais.
from unittest.mock import patch

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import uuid4

# Importa cliente HTTP de testes que executa a aplicação sem servidor de rede.
from fastapi.testclient import TestClient

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import Banco

# Importa assinaturas RSA e política de produtores autorizados.
from comum.seguranca import Assinador

# Importa os componentes de principal.api.
from principal.api import app

# Importa os componentes de pagamento.api.
from pagamento.api import app as pagamento_app

# Importa os componentes de mock_pagamento.api.
from mock_pagamento.api import app as mock_app

# Simula a interface do worker nos testes HTTP, sem conexão ao RabbitMQ.
class WorkerTeste:

    # Continua a expressão que prepara os dados desta operação.
    """Isola transporte nos testes HTTP; integração usa o worker real."""

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, servico, banco, tratar):

        # Carrega ou armazena o assinador RSA do serviço que publica estes eventos.
        self.assinador = Assinador.carregar(servico)

        # Mantém o sinal de conexão pronta; no teste usa um dublê sempre disponível.
        self.pronto = SimpleNamespace(is_set=lambda: True)

        # Prepara a thread dona da conexão AMQP; no teste simula uma thread já parada.
        self.thread = SimpleNamespace(is_alive=lambda: False)

    # Inicia a thread do worker; no dublê de teste, mantém a interface sem criar uma thread.
    def iniciar(self):

        # Não executa outra ação: o encerramento ou a simulação já foi tratado pelo contexto.
        pass

    # Define a operação fechar.
    def fechar(self):

        # Não executa outra ação: o encerramento ou a simulação já foi tratado pelo contexto.
        pass

# Agrupa os testes relacionados a API.
class API(unittest.TestCase):

    # Prepara recursos novos e isolados antes de cada teste.
    def setUp(self):

        # Prepara a substituição dos bancos reais por SQLite em memória.
        self.banco_patch = patch(

            # Fornece este valor textual à chamada ou coleção em construção.
            "comum.web.Banco", side_effect=lambda s: Banco(s, ":memory:")

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Prepara a substituição do worker AMQP por um dublê de teste.
        self.worker_patch = patch("comum.web.Trabalhador", WorkerTeste)

        # Inicia a thread ou ativa a substituição temporária preparada para o teste.
        self.banco_patch.start()

        # Inicia a thread ou ativa a substituição temporária preparada para o teste.
        self.worker_patch.start()

        # Cria o cliente HTTP de teste para executar as rotas do Gateway.
        self.client = TestClient(app)

        # Inicia o lifespan do cliente de testes para preparar banco e worker simulados.
        self.client.__enter__()

        # Gera um UUID de cliente exclusivo deste teste.
        self.cid = str(uuid4())

    # Libera recursos e desfaz substituições após cada teste.
    def tearDown(self):

        # Finaliza o lifespan do cliente de testes e libera os recursos da aplicação.
        self.client.__exit__(None, None, None)

        # Desfaz a substituição temporária, restaurando a dependência original.
        self.worker_patch.stop()

        # Desfaz a substituição temporária, restaurando a dependência original.
        self.banco_patch.stop()

    # Testa o cenário de cria pedido preco vem do estoque.
    def test_cria_pedido_preco_vem_do_estoque(self):

        # Prepara catálogo consultado no serviço de Estoque para esta etapa.
        catalogo = [

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            {"id": "1", "nome": "Caderno", "preco_centavos": 1500, "quantidade": 10}

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ]

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch("principal.api.obter_produtos", return_value=catalogo):

            # Prepara r para esta etapa.
            r = self.client.post(

                # Fornece este valor textual à chamada ou coleção em construção.
                "/pedidos",

                # Envia estes dados como corpo JSON da requisição HTTP.
                json={

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": self.cid,

                    # Define o campo nome desta estrutura de dados.
                    "nome": "Ana",

                    # Define o campo itens desta estrutura de dados.
                    "itens": [

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        {"produto_id": "1", "quantidade": 2},

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        {"produto_id": "1", "quantidade": 1},

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    ],

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(r.status_code, 202)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(r.json()["total_centavos"], 4500)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(r.json()["itens"]), 1)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(app.state.banco.ler("SELECT * FROM outbox")), 1)

        # Prepara consulta ou cliente diferente para esta etapa.
        outro = self.client.get("/pedidos", params={"cliente": str(uuid4())})

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(outro.json(), [])

    # Testa o cenário de rejeita quantidade booleana e cliente invalido.
    def test_rejeita_quantidade_booleana_e_cliente_invalido(self):

        # Percorre (True, 0, -1, '2') para processar cada quantidade.
        for quantidade in (True, 0, -1, "2"):

            # Prepara r para esta etapa.
            r = self.client.post(

                # Fornece este valor textual à chamada ou coleção em construção.
                "/pedidos",

                # Envia estes dados como corpo JSON da requisição HTTP.
                json={

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": self.cid,

                    # Define o campo nome desta estrutura de dados.
                    "nome": "Ana",

                    # Define o campo itens desta estrutura de dados.
                    "itens": [{"produto_id": "1", "quantidade": quantidade}],

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
            self.assertEqual(r.status_code, 422)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(self.client.get("/pedidos?cliente=ana").status_code, 422)

    # Testa o cenário de interesse cancelamento eventos assinados.
    def test_interesse_cancelamento_eventos_assinados(self):

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.client.put(

                # Fornece este valor textual à chamada ou coleção em construção.
                "/interesses",

                # Envia estes dados como corpo JSON da requisição HTTP.
                json={

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": self.cid,

                    # Define o campo email desta estrutura de dados.
                    "email": "ana@example.com",

                    # Define o campo categorias desta estrutura de dados.
                    "categorias": ["A", "B"],

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ).status_code,

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            202,

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.client.delete("/interesses?cliente=" + self.cid).status_code, 202

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Prepara eventos para esta etapa.
        eventos = app.state.banco.ler("SELECT * FROM outbox")

        # Prepara verificador das assinaturas para esta etapa.
        verificador = app.state.worker.assinador

        # Prepara dados da operação para esta etapa.
        dados = [verificador.verificar(r["corpo"], r["tipo"])["data"] for r in eventos]

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(dados[1]["categorias"], [])

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(dados[1]["versao"], 2)

    # Testa o cenário de documentacao e sse header invalido.
    def test_documentacao_e_sse_header_invalido(self):

        # Prepara rotas publicadas na especificação OpenAPI para esta etapa.
        paths = self.client.get("/openapi.json").json()["paths"]

        # Confere que o elemento esperado está presente no resultado.
        self.assertIn("/eventos", paths)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.client.get(

                # Fornece este valor textual à chamada ou coleção em construção.
                "/eventos?cliente=" + self.cid, headers={"Last-Event-ID": "abc"}

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ).status_code,

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            400,

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

# Agrupa os testes relacionados a WebhookAPI.
class WebhookAPI(unittest.TestCase):

    # Testa o cenário de webhook sem assinatura.
    def test_webhook_sem_assinatura(self):

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch(

            # Fornece este valor textual à chamada ou coleção em construção.
            "comum.web.Banco", side_effect=lambda s: Banco(s, ":memory:")

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ), patch("comum.web.Trabalhador", WorkerTeste):

            # Abre o contexto TestClient(pagamento_app) e garante sua finalização ao sair do bloco.
            with TestClient(pagamento_app) as cliente:

                # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
                self.assertEqual(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    cliente.post("/webhook", json={"status": "APROVADO"}).status_code,

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    401,

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

    # Testa o cenário de mock restringe webhook e chave.
    def test_mock_restringe_webhook_e_chave(self):

        # Importa configurações compartilhadas, como URLs e caminho dos dados.
        from comum.config import WEBHOOK_SECRET

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch(

            # Fornece este valor textual à chamada ou coleção em construção.
            "mock_pagamento.api.Banco", side_effect=lambda s: Banco(s, ":memory:")

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ):

            # Abre o contexto TestClient(mock_app) e garante sua finalização ao sair do bloco.
            with TestClient(mock_app) as cliente:

                # Prepara dados da operação para esta etapa.
                dados = {

                    # Define o campo pedido_id desta estrutura de dados.
                    "pedido_id": str(uuid4()),

                    # Define o campo total_centavos desta estrutura de dados.
                    "total_centavos": 1500,

                    # Define o campo webhook_url desta estrutura de dados.
                    "webhook_url": "http://localhost:9999/roubar",

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                }

                # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
                self.assertEqual(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    cliente.post("/cobrancas", json=dados).status_code, 401

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

                # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
                self.assertEqual(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    cliente.post(

                        # Fornece este valor textual à chamada ou coleção em construção.
                        "/cobrancas", json=dados, headers={"X-API-Key": WEBHOOK_SECRET}

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    ).status_code,

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    422,

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )
