# Assinatura RSA dos eventos: prova origem e integridade, sem cifrar o conteúdo.

# Importa representação textual dos bytes da assinatura no envelope JSON.
import base64

# Importa exceções de decodificação binária, incluindo Base64 inválido.
import binascii

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa caminhos de arquivo portáveis por meio de Path.
from pathlib import Path

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import uuid4

# Importa resumo SHA-256 utilizado pela assinatura RSA.
from Crypto.Hash import SHA256

# Importa geração e leitura de chaves RSA em formato PEM.
from Crypto.PublicKey import RSA

# Importa assinatura e verificação RSA no padrão PKCS#1 v1.5.
from Crypto.Signature import pkcs1_15

# Prepara pasta raiz do trabalho para esta etapa.
RAIZ = Path(__file__).resolve().parents[1]

# Prepara serviços que possuem chave privada para esta etapa.
SERVICOS = ("principal", "estoque", "pagamento", "entrega", "promocoes")

# Prepara mapa de serviços autorizados a assinar cada evento para esta etapa.
PRODUTORES = {

    # Define o campo pedido.criado desta estrutura de dados.
    "pedido.criado": "principal",

    # Define o campo pedido.excluido desta estrutura de dados.
    "pedido.excluido": "principal",

    # Define o campo interesse.promocao desta estrutura de dados.
    "interesse.promocao": "principal",

    # Define o campo pedido.estoque_ok desta estrutura de dados.
    "pedido.estoque_ok": "estoque",

    # Define o campo estoque.indisponivel desta estrutura de dados.
    "estoque.indisponivel": "estoque",

    # Define o campo pagamento.aprovado desta estrutura de dados.
    "pagamento.aprovado": "pagamento",

    # Define o campo pagamento.recusado desta estrutura de dados.
    "pagamento.recusado": "pagamento",

    # Define o campo pagamento.checkout_criado desta estrutura de dados.
    "pagamento.checkout_criado": "pagamento",

    # Define o campo pedido.enviado desta estrutura de dados.
    "pedido.enviado": "entrega",

    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
    **{f"promocao.categoria.{c}": "promocoes" for c in "ABC"},

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
}

# Produz os mesmos bytes JSON para assinar e verificar: ordem e separadores fixos.
def serializar(conteudo):

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return json.dumps(

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        conteudo,

        # Define o argumento ou campo sort_keys desta operação.
        sort_keys=True,

        # Define o argumento ou campo separators desta operação.
        separators=(",", ":"),

        # Define o argumento ou campo ensure_ascii desta operação.
        ensure_ascii=False,

        # Define o argumento ou campo allow_nan desta operação.
        allow_nan=False,

    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
    ).encode("utf-8")

# Reúne a política de autorização, as chaves e as operações RSA.
class Assinador:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, produtor, privada, publicas):

        # Guarda o nome do serviço responsável pela assinatura dos eventos.
        self.produtor = produtor

        # Guarda a chave privada usada somente para assinar eventos deste produtor.
        self.privada = privada

        # Guarda as chaves públicas usadas para conferir eventos recebidos.
        self.publicas = publicas

    # Permite chamar este método na classe, sem construir uma instância antes.
    @classmethod

    # Lê a privada do serviço e as públicas locais; falha se as chaves necessárias estiverem ausentes.
    def carregar(cls, servico):

        # Prepara diretório de arquivos para esta etapa.
        pasta = (

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            RAIZ / ("consumidores" if servico in ("c1", "c2") else servico) / "chaves"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Prepara chave privada RSA para esta etapa.
            privada = (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                RSA.import_key((pasta / "privada.pem").read_bytes())

                # Aplica esta iteração ou condição à expressão que está sendo construída.
                if servico in SERVICOS

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                else None

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Prepara chaves públicas dos produtores para esta etapa.
            publicas = {

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                p.stem: RSA.import_key(p.read_bytes())

                # Aplica esta iteração ou condição à expressão que está sendo construída.
                for p in (pasta / "publicas").glob("*.pem")

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            }

            # Prepara produtores cujas chaves precisam estar presentes para esta etapa.
            exigidas = set(SERVICOS) if servico in SERVICOS else {"promocoes"}

            # Confere a condição not exigidas.issubset(publicas) antes de executar este bloco.
            if not exigidas.issubset(publicas):

                # Interrompe a operação com erro: Faltam chaves públicas.
                raise FileNotFoundError("Faltam chaves públicas.")

        # Trata (OSError, ValueError) sem confundir falha com resultado válido.
        except (OSError, ValueError) as erro:

            # Interrompe a operação com erro: Prepare as chaves: python -m scripts.gerar_chaves.
            raise RuntimeError(

                # Fornece este valor textual à chamada ou coleção em construção.
                "Prepare as chaves: python -m scripts.gerar_chaves"

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ) from erro

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return cls(servico, privada, publicas)

    # Cria o envelope e assina seu conteúdo com a chave privada do produtor autorizado.
    def assinar(self, tipo, dados):

        # Confere a condição PRODUTORES.get(tipo) != self.produtor or self.privada is None antes de executar este bloco.
        if PRODUTORES.get(tipo) != self.produtor or self.privada is None:

            # Interrompe a operação com erro: Produtor não autorizado para este evento.
            raise ValueError("Produtor não autorizado para este evento.")

        # Prepara envelope JSON do evento para esta etapa.
        envelope = {

            # Define o campo event_id desta estrutura de dados.
            "event_id": str(uuid4()),

            # Define o campo producer desta estrutura de dados.
            "producer": self.produtor,

            # Define o campo event_type desta estrutura de dados.
            "event_type": tipo,

            # Define o campo data desta estrutura de dados.
            "data": dados,

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

        # Prepara assinatura criptográfica para esta etapa.
        assinatura = pkcs1_15.new(self.privada).sign(SHA256.new(serializar(envelope)))

        # Acrescenta a assinatura em Base64 após assinar o envelope sem esse campo.
        envelope["Signature"] = base64.b64encode(assinatura).decode("ascii")

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return serializar(envelope)

    # Rejeita envelope, produtor, routing key ou assinatura inválidos antes da lógica de negócio.
    def verificar(self, corpo, routing_key):

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Prepara envelope JSON do evento para esta etapa.
            envelope = json.loads(corpo)

            # Prepara campos obrigatórios do envelope para esta etapa.
            campos = {"event_id", "producer", "event_type", "data", "Signature"}

            # Confere a condição not isinstance(envelope, dict) or set(envelope) != campos antes de executar este bloco.
            if not isinstance(envelope, dict) or set(envelope) != campos:

                # Interrompe a operação com erro: Envelope inválido.
                raise ValueError("Envelope inválido.")

            # Confere a condição not isinstance(envelope['event_id'], str) or not envelope['event_id'] antes de executar este bloco.
            if not isinstance(envelope["event_id"], str) or not envelope["event_id"]:

                # Interrompe a operação com erro: event_id inválido.
                raise ValueError("event_id inválido.")

            # Confere a condição not isinstance(envelope['data'], dict) antes de executar este bloco.
            if not isinstance(envelope["data"], dict):

                # Interrompe a operação com erro: Dados inválidos.
                raise ValueError("Dados inválidos.")

            # Prepara serviço produtor para esta etapa.
            produtor = envelope["producer"]

            # Confere a condição envelope['event_type'] != routing_key or PRODUTORES.get(routing_key) != produtor antes de executar este bloco.
            if (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                envelope["event_type"] != routing_key

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                or PRODUTORES.get(routing_key) != produtor

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ):

                # Interrompe a operação com erro: Produtor ou routing key incorretos.
                raise ValueError("Produtor ou routing key incorretos.")

            # Prepara assinatura criptográfica para esta etapa.
            assinatura = base64.b64decode(envelope["Signature"], validate=True)

            # Prepara conteúdo coberto pela assinatura para esta etapa.
            conteudo = {k: v for k, v in envelope.items() if k != "Signature"}

            # Executa pkcs1_15.new(self.publicas[produtor]).verify para concluir esta etapa do processamento.
            pkcs1_15.new(self.publicas[produtor]).verify(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                SHA256.new(serializar(conteudo)), assinatura

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return envelope

        # Trata (ValueError, TypeError, KeyError, UnicodeError, binascii.Error) sem confundir falha com resultado válido.
        except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error) as erro:

            # Interrompe a operação com erro: Evento rejeitado: assinatura, produtor ou envelope inválido.
            raise ValueError(

                # Fornece este valor textual à chamada ou coleção em construção.
                "Evento rejeitado: assinatura, produtor ou envelope inválido."

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ) from erro
