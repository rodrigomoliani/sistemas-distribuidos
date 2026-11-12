# Testes locais de assinatura: não abrem conexão com RabbitMQ.
# As chaves são temporárias em memória; não leem nem substituem as chaves dos serviços.
# Cada teste confere uma propriedade do envelope, da autorização ou da assinatura.

# Permite decodificar e modificar JSON para preparar cenários de adulteração.
import json

# Fornece o executor dos testes e as verificações assert*.
import unittest

# Gera pares RSA reais, mas exclusivos desta execução de testes.
from Crypto.PublicKey import RSA

# Reutiliza a mesma assinatura e serialização empregadas pela aplicação.
from comum.seguranca import Assinador, serializar


# Conjunto de testes de segurança.
class SegurancaTest(unittest.TestCase):

    # Método de classe: preparação compartilhada antes de todos os testes da classe.
    @classmethod

    # Gera as chaves uma vez para evitar repetir uma operação relativamente custosa.
    def setUpClass(cls):

        # Par RSA de 2048 bits para representar o Principal.
        cls.principal = RSA.generate(2048)

        # Outro par independente para representar o Estoque.
        cls.estoque = RSA.generate(2048)

    # Recria assinadores e mensagem antes de cada caso, evitando alterações entre testes.
    def setUp(self):

        # Mapa com apenas as partes públicas das duas identidades do cenário.
        publicas = {"principal": self.principal.public_key(), "estoque": self.estoque.public_key()}

        # Emissor possui a privada do Principal para assinar pedido.criado.
        self.emissor = Assinador("principal", self.principal, publicas)

        # Receptor tem as públicas necessárias para verificar os eventos.
        self.receptor = Assinador("estoque", self.estoque, publicas)

        # Cria bytes assinados de um evento mínimo; este teste valida o envelope,
        # não a regra de negócio de um pedido completo. João também exercita UTF-8.
        self.corpo = self.emissor.assinar("pedido.criado", {"pedido_id": "123", "cliente": "João"})

    # Verifica que a ordem das chaves e o espaçamento JSON não invalidam a assinatura.
    def test_assinatura_valida_e_json_reordenado(self):

        # Converte o envelope assinado de bytes para dicionário.
        dados = json.loads(self.corpo)

        # Inverte a ordem das chaves externas e adiciona indentação ao JSON.
        # encode gera bytes UTF-8; a verificação usa a serialização padronizada.
        corpo = json.dumps(dict(reversed(list(dados.items()))), ensure_ascii=False, indent=2).encode()

        # Espera verificação bem-sucedida e preservação do cliente com acento.
        self.assertEqual(self.receptor.verificar(corpo, "pedido.criado")["data"]["cliente"], "João")

    # Simula alteração de dados depois de o produtor ter assinado.
    def test_conteudo_adulterado(self):

        # Lê o envelope válido para uma estrutura editável.
        dados = json.loads(self.corpo)

        # Altera o cliente sem gerar nova assinatura.
        dados["data"]["cliente"] = "Outro"

        # A verificação deve lançar ValueError, indicando recusa.
        with self.assertRaises(ValueError):

            # Serializa o envelope adulterado e tenta verificá-lo com a routing key original.
            self.receptor.verificar(serializar(dados), "pedido.criado")

    # Simula uma chave pública incorreta associada ao nome do produtor.
    def test_chave_errada(self):

        # Substitui a pública do Principal pela pública do Estoque neste receptor de teste.
        self.receptor.publicas["principal"] = self.estoque.public_key()

        # A assinatura original não pode ser validada por esse outro par de chaves.
        with self.assertRaises(ValueError):

            # Tenta verificar o mesmo corpo sem modificar seus dados.
            self.receptor.verificar(self.corpo, "pedido.criado")

    # Garante que o tipo assinado precisa coincidir com a routing key da entrega.
    def test_evento_roteado_com_chave_diferente(self):

        # Espera a rejeição do roteamento incompatível.
        with self.assertRaises(ValueError):

            # O corpo contém pedido.criado, mas simulamos entrega como pedido.excluido.
            self.receptor.verificar(self.corpo, "pedido.excluido")

    # Valida a autorização de cada produtor antes de assinar.
    def test_produtor_nao_pode_publicar_evento_de_outro(self):

        # A tentativa de emitir evento de outro serviço deve ser recusada.
        with self.assertRaises(ValueError):

            # Principal tenta produzir pagamento.aprovado, reservado ao Pagamento.
            self.emissor.assinar("pagamento.aprovado", {})

    # Valida rejeição de estruturas que não respeitam o contrato do envelope.
    def test_envelopes_invalidos(self):

        # Casos: lista, null, objeto sem campos, texto sem JSON e byte inválido em UTF-8.
        for corpo in (b"[]", b"null", b"{}", b"not json", b"\xff"):

            # Cada entrada deve gerar erro de validação.
            with self.assertRaises(ValueError):

                # Envia o corpo inválido à verificação local, sem broker.
                self.receptor.verificar(corpo, "pedido.criado")

        # Reabre um envelope válido para testar especificamente o campo Signature.
        dados = json.loads(self.corpo)

        # Troca a assinatura por texto que não é Base64 válido.
        dados["Signature"] = "%%%"

        # A falha de decodificação deve ser apresentada como ValueError.
        with self.assertRaises(ValueError):

            # Tenta validar o envelope com a assinatura malformada.
            self.receptor.verificar(serializar(dados), "pedido.criado")


# Permite iniciar os testes deste módulo diretamente.
if __name__ == "__main__":

    # Executa os métodos test_* usando unittest.
    unittest.main()
