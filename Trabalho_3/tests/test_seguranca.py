# Testes de autenticidade, integridade, autorização dos produtores e validade do webhook.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa relógios, timestamps e pausas do agendamento e dos testes.
import time

# Importa estrutura de testes, asserções e execução automática dos casos.
import unittest

# Importa geração e leitura de chaves RSA em formato PEM.
from Crypto.PublicKey import RSA

# Importa assinaturas RSA e política de produtores autorizados.
from comum.seguranca import Assinador

# Importa assinatura e verificação do webhook externo.
from comum.webhook import assinar_webhook, verificar_webhook

# Agrupa os testes relacionados a Seguranca.
class Seguranca(unittest.TestCase):

    # Permite chamar este método na classe, sem construir uma instância antes.
    @classmethod

    # Prepara uma chave RSA de teste uma única vez para a classe.
    def setUpClass(cls):

        # Prepara cls.chave para esta etapa.
        cls.chave = RSA.generate(2048)

        # Prepara cls.a para esta etapa.
        cls.a = Assinador("principal", cls.chave, {"principal": cls.chave.public_key()})

    # Testa o cenário de assinatura valida.
    def test_assinatura_valida(self):

        # Prepara corpo serializado original para esta etapa.
        corpo = self.a.assinar("interesse.promocao", {"email": "ana@example.com"})

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.a.verificar(corpo, "interesse.promocao")["producer"], "principal"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Testa o cenário de adulteracao rejeitada.
    def test_adulteracao_rejeitada(self):

        # Prepara corpo serializado original para esta etapa.
        corpo = json.loads(self.a.assinar("pedido.criado", {"total_centavos": 1500}))

        # Atualiza corpo['data']['total_centavos'] com o valor usado por este cenário.
        corpo["data"]["total_centavos"] = 1

        # Exige que este bloco levante a exceção esperada pelo teste.
        with self.assertRaises(ValueError):

            # Executa self.a.verificar para concluir esta etapa do processamento.
            self.a.verificar(json.dumps(corpo), "pedido.criado")

    # Testa o cenário de routing incorreto.
    def test_routing_incorreto(self):

        # Exige que este bloco levante a exceção esperada pelo teste.
        with self.assertRaises(ValueError):

            # Executa self.a.verificar para concluir esta etapa do processamento.
            self.a.verificar(self.a.assinar("pedido.criado", {}), "pedido.excluido")

    # Testa o cenário de produtor nao autorizado.
    def test_produtor_nao_autorizado(self):

        # Exige que este bloco levante a exceção esperada pelo teste.
        with self.assertRaises(ValueError):

            # Executa self.a.assinar para concluir esta etapa do processamento.
            self.a.assinar("pagamento.aprovado", {})

    # Testa o cenário de envelopes malformados.
    def test_envelopes_malformados(self):

        # Percorre (b'null', b'[]', b'{', b'{"data":{}}') para processar cada corpo.
        for corpo in (b"null", b"[]", b"{", b'{"data":{}}'):

            # Abre o contexto self.subTest(corpo=corpo) e garante sua finalização ao sair do bloco.
            with self.subTest(corpo=corpo), self.assertRaises(ValueError):

                # Executa self.a.verificar para concluir esta etapa do processamento.
                self.a.verificar(corpo, "pedido.criado")

    # Testa o cenário de webhook integridade e expiracao.
    def test_webhook_integridade_e_expiracao(self):

        # Prepara corpo serializado original para esta etapa.
        corpo = b'{"status":"APROVADO"}'

        # Prepara ts para esta etapa.
        ts = str(int(time.time()))

        # Prepara sig para esta etapa.
        sig = assinar_webhook(corpo, ts)

        # Exige que a condição verificada pelo teste seja verdadeira.
        self.assertTrue(verificar_webhook(corpo, ts, sig))

        # Exige que a condição verificada pelo teste seja falsa.
        self.assertFalse(verificar_webhook(b'{"status":"RECUSADO"}', ts, sig))

        # Prepara timestamp fora da janela permitida para esta etapa.
        velho = str(int(time.time()) - 301)

        # Exige que a condição verificada pelo teste seja falsa.
        self.assertFalse(verificar_webhook(corpo, velho, assinar_webhook(corpo, velho)))
