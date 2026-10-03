# Testes de categorias e do contrato Resend; nenhuma chamada real é enviada ao provedor.

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa estrutura de testes, asserções e execução automática dos casos.
import unittest

# Importa objetos simples que simulam respostas e componentes nos testes.
from types import SimpleNamespace

# Importa substituições temporárias de dependências, sem acesso a serviços reais.
from unittest.mock import patch

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import uuid4

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import Banco

# Importa catálogo inicial, valores em centavos e validação de itens e totais.
from comum.catalogo import CATALOGO

# Importa os componentes de promocoes.__main__.
from promocoes.__main__ import disparar

# Importa os componentes de promocoes.email.
from promocoes.email import Email

# Importa modelo com as regras de negócio do microsserviço promocoes.
from promocoes.modelo import Promocoes

# Agrupa os testes relacionados a EmailPromocoes.
class EmailPromocoes(unittest.TestCase):

    # Testa o cenário de categorias e cancelamento.
    def test_categorias_e_cancelamento(self):

        # Prepara banco para esta etapa.
        banco = Banco("teste", ":memory:")

        # Prepara modelo de regras do serviço para esta etapa.
        modelo = Promocoes(banco)

        # Prepara identificador utilizado na cobrança ou no cliente de teste para esta etapa.
        cid = str(uuid4())

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with banco.transacao() as con:

            # Executa modelo.tratar para concluir esta etapa do processamento.
            modelo.tratar(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                con,

                # Fornece este valor textual à chamada ou coleção em construção.
                "interesse.promocao",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                {

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": cid,

                    # Define o campo email desta estrutura de dados.
                    "email": "ana@example.com",

                    # Define o campo categorias desta estrutura de dados.
                    "categorias": ["A"],

                    # Define o campo versao desta estrutura de dados.
                    "versao": 1,

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Prepara adaptador ou endereço de e-mail para esta etapa.
        email = SimpleNamespace(modo="arquivo", enviar=lambda *args: None)

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch("promocoes.__main__.random.choice", side_effect=[CATALOGO["2"], 10]):

            # Executa disparar para concluir esta etapa do processamento.
            disparar(banco, email)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(banco.ler("SELECT * FROM envios")), 0)

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch("promocoes.__main__.random.choice", side_effect=[CATALOGO["1"], 10]):

            # Executa disparar para concluir esta etapa do processamento.
            disparar(banco, email)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(banco.ler("SELECT * FROM envios")), 1)

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with banco.transacao() as con:

            # Executa modelo.tratar para concluir esta etapa do processamento.
            modelo.tratar(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                con,

                # Fornece este valor textual à chamada ou coleção em construção.
                "interesse.promocao",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                {

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": cid,

                    # Define o campo email desta estrutura de dados.
                    "email": "ana@example.com",

                    # Define o campo categorias desta estrutura de dados.
                    "categorias": [],

                    # Define o campo versao desta estrutura de dados.
                    "versao": 2,

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch("promocoes.__main__.random.choice", side_effect=[CATALOGO["1"], 20]):

            # Executa disparar para concluir esta etapa do processamento.
            disparar(banco, email)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(banco.ler("SELECT * FROM envios")), 1)

        # Libera o recurso do serviço depois do processamento.
        banco.fechar()

    # Testa o cenário de resend contrato http sem envio real.
    def test_resend_contrato_http_sem_envio_real(self):

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch.dict(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            os.environ,

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            {

                # Define o campo EMAIL_MODO desta estrutura de dados.
                "EMAIL_MODO": "resend",

                # Define o campo RESEND_API_KEY desta estrutura de dados.
                "RESEND_API_KEY": "chave-teste",

                # Define o campo EMAIL_FROM desta estrutura de dados.
                "EMAIL_FROM": "teste@example.com",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            },

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ):

            # Prepara adaptador ou endereço de e-mail para esta etapa.
            email = Email()

        # Prepara resposta recebida ou simulada para esta etapa.
        resposta = SimpleNamespace(raise_for_status=lambda: None)

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch("promocoes.email.httpx.post", return_value=resposta) as chamada:

            # Dispara a mensagem pelo adaptador de e-mail selecionado.
            email.enviar("ana@example.com", "Oferta", "Texto", "campanha-1")

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(chamada.call_args.args, ("https://api.resend.com/emails",))

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            chamada.call_args.kwargs["headers"]["Idempotency-Key"], "campanha-1"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(chamada.call_args.kwargs["json"]["to"], ["ana@example.com"])

    # Testa o cenário de resend sem chave falha explicitamente.
    def test_resend_sem_chave_falha_explicitamente(self):

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch.dict(os.environ, {"EMAIL_MODO": "resend", "RESEND_API_KEY": ""}):

            # Exige que este bloco levante a exceção esperada pelo teste.
            with self.assertRaises(ValueError):

                # Executa Email para concluir esta etapa do processamento.
                Email()
