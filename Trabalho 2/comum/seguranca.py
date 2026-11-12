# Este módulo cuida da autenticidade e da integridade dos eventos.
# Tudo aqui é local: leitura de arquivos, serialização e operações criptográficas.
# Nenhuma função deste arquivo envia mensagens ao RabbitMQ.
# A assinatura permite verificar a origem e detectar alterações; não esconde
# o conteúdo. Base64 também não é criptografia de confidencialidade.

# Converte os bytes da assinatura em texto adequado para um campo JSON.
import base64

# Fornece a classe de erro usada quando uma codificação Base64 é inválida.
import binascii

# Converte entre objetos Python e sua representação textual JSON.
import json

# Representa caminhos de arquivos sem montar separadores manualmente.
from pathlib import Path

# Gera identificadores aleatórios para diferenciar eventos.
from uuid import uuid4

# Calcula o resumo SHA-256 usado pelo algoritmo de assinatura.
from Crypto.Hash import SHA256

# Importa chaves RSA armazenadas nos arquivos PEM do projeto.
from Crypto.PublicKey import RSA

# Implementa a assinatura RSA no padrão PKCS#1 v1.5 e sua verificação.
from Crypto.Signature import pkcs1_15

# __file__ é este arquivo; resolve() obtém seu caminho absoluto.
# parents[0] é comum; parents[1] é a pasta do trabalho. Assim, a busca
# por chaves não depende de construir um caminho absoluto fixo no código.
RAIZ = Path(__file__).resolve().parents[1]

# Serviços autorizados a produzir eventos. C1/C2 só consomem promoções
# e, por isso, não precisam de uma chave privada para assinar saídas.
SERVICOS = ("principal", "estoque", "pagamento", "entrega", "promocoes")

# Política local de autorização: qual serviço pode assinar cada evento.
# Uma assinatura matematicamente válida não basta se o serviço não estiver
# autorizado a emitir aquele tipo. O campo producer sozinho não prova origem.
PRODUTORES = {
    # Somente o Principal cria e exclui pedidos.
    "pedido.criado": "principal", "pedido.excluido": "principal",

    # Somente o Estoque informa o resultado da tentativa de reserva.
    "pedido.estoque_ok": "estoque", "estoque.indisponivel": "estoque",

    # Somente o Pagamento informa aprovação ou recusa.
    "pagamento.aprovado": "pagamento", "pagamento.recusado": "pagamento",

    # Somente a Entrega confirma o envio.
    "pedido.enviado": "entrega",

    # A compreensão gera três pares, um por letra A/B/C.
    # ** incorpora esses pares ao dicionário externo.
    **{f"promocao.categoria.{c}": "promocoes" for c in "ABC"},
}


# Padroniza os bytes usados tanto na assinatura quanto na verificação.
# Essa padronização é necessária: espaços ou ordem das chaves poderiam
# alterar o hash mesmo mantendo os mesmos valores de um objeto JSON.
def serializar(conteudo):
    # dumps transforma o objeto em texto JSON; encode transforma texto em bytes.
    return json.dumps(
        # Objeto Python a representar, por exemplo o envelope da mensagem.
        conteudo,

        # Ordena as chaves dos objetos; não altera a ordem dos itens das listas.
        sort_keys=True,

        # Remove os espaços opcionais entre itens e entre chave/valor.
        separators=(",", ":"),

        # Preserva caracteres como "ç" no texto, em vez de escapes ASCII.
        ensure_ascii=False,

        # Recusa NaN e infinito, que não são números válidos no padrão JSON.
        allow_nan=False,
    ).encode("utf-8")


# Mantém a identidade, a chave privada e as chaves públicas disponíveis.
# A confiança depende das chaves previamente distribuídas pelo projeto;
# não se aceita uma chave fornecida pela própria mensagem recebida.
class Assinador:
    # Construtor: recebe as chaves já carregadas, sem fazer comunicação de rede.
    def __init__(self, produtor, privada, publicas):
        # Nome da identidade usada no campo producer ao assinar.
        self.produtor = produtor

        # Chave privada deste serviço; None para consumidores que não assinam.
        self.privada = privada

        # Mapa nome do produtor -> chave pública usada para verificar sua assinatura.
        self.publicas = publicas

    # Permite chamar Assinador.carregar(servico) sem criar antes uma instância.
    # O primeiro argumento recebido será a classe (cls), em vez de self.
    @classmethod
    def carregar(cls, servico):
        # O operador / de Path junta trechos de um caminho, não faz divisão.
        # C1/C2 compartilham a pasta consumidores; cada produtor tem sua pasta.
        pasta = RAIZ / ("consumidores" if servico in ("c1", "c2") else servico) / "chaves"

        # Converte problemas de arquivo/chave em uma orientação de preparação.
        try:
            # read_bytes lê o arquivo local e import_key interpreta sua chave RSA.
            # Só os cinco produtores carregam privada.pem; C1/C2 recebem None.
            privada = RSA.import_key((pasta / "privada.pem").read_bytes()) if servico in SERVICOS else None

            # Compreensão de dicionário: importa cada chave pública encontrada.
            publicas = {
                # stem é o nome sem extensão: estoque.pem vira a chave "estoque".
                p.stem: RSA.import_key(p.read_bytes())

                # glob seleciona os arquivos PEM dentro da subpasta publicas.
                for p in (pasta / "publicas").glob("*.pem")
            }

            # Os produtores exigem as cinco chaves; C1/C2 só precisam da de Promoções.
            exigidas = set(SERVICOS) if servico in SERVICOS else {"promocoes"}

            # issubset verifica se todos os nomes exigidos existem no dicionário.
            if not exigidas.issubset(publicas):
                # Trata ausência de uma chave necessária como falha de preparação.
                raise FileNotFoundError("Faltam chaves públicas.")

        # OSError cobre erros de arquivo, inclusive FileNotFoundError;
        # ValueError pode indicar um conteúdo de chave que não pôde ser importado.
        except (OSError, ValueError) as erro:
            # from erro preserva a causa original para diagnóstico.
            raise RuntimeError("Prepare as chaves: python -m scripts.gerar_chaves") from erro

        # cls(...) chama o construtor acima e devolve o assinador pronto.
        return cls(servico, privada, publicas)

    # Cria um evento assinado. tipo é seu nome; dados contém o conteúdo de negócio.
    def assinar(self, tipo, dados):
        # get consulta um dicionário local, não uma API HTTP.
        # Recusa tipo desconhecido, produtor errado ou ausência de chave privada.
        if PRODUTORES.get(tipo) != self.produtor or self.privada is None:
            # Impede produzir uma mensagem em desacordo com a política local.
            raise ValueError("Produtor não autorizado para este evento.")

        # Monta primeiro o envelope SEM Signature: a assinatura não pode fazer
        # parte do próprio conteúdo a ser assinado.
        envelope = {
            # Identifica este evento, não o pedido. Um pedido pode gerar vários
            # eventos, cada um com event_id próprio, mas com o mesmo pedido_id.
            "event_id": str(uuid4()),

            # Identidade declarada do emissor, também protegida pela assinatura.
            "producer": self.produtor,

            # Tipo que será usado como routing key na publicação AMQP.
            "event_type": tipo,

            # Dados do evento, por exemplo pedido_id, itens, cliente e total.
            "data": dados,
        }

        # De dentro para fora: serializa o envelope, calcula SHA-256 e assina
        # esse resumo com RSA/PKCS#1 v1.5 usando a chave PRIVADA.
        # Só calcular um hash não autenticaria o emissor; a assinatura faz isso.
        assinatura = pkcs1_15.new(self.privada).sign(SHA256.new(serializar(envelope)))

        # Codifica os bytes em Base64 e converte para texto ASCII.
        # O nome Signature tem a maiúscula definida no contrato das mensagens.
        envelope["Signature"] = base64.b64encode(assinatura).decode("ascii")

        # Retorna os bytes do envelope completo. O envio fica em mensageria.py.
        return serializar(envelope)

    # Recebe o corpo entregue pelo Pika e a routing key observada na entrega.
    # Retorna o envelope validado ou lança ValueError para rejeitar a mensagem.
    def verificar(self, corpo, routing_key):
        # Centraliza falhas de formato, autorização e assinatura neste bloco.
        try:
            # Interpreta JSON recebido; ainda não significa que ele é confiável.
            envelope = json.loads(corpo)

            # Conjunto exato de campos permitidos no nível externo.
            campos = {"event_id", "producer", "event_type", "data", "Signature"}

            # Exige objeto/dicionário e rejeita campos ausentes ou extras.
            # O "or" para após a primeira condição verdadeira (curto-circuito).
            if not isinstance(envelope, dict) or set(envelope) != campos:
                # Interrompe a validação antes de acessar uma estrutura inválida.
                raise ValueError("Envelope inválido.")

            # Exige ID textual não vazio; não valida aqui a sintaxe de um UUID.
            if not isinstance(envelope["event_id"], str) or not envelope["event_id"]:
                # Impede usar um ID ausente ou de tipo inadequado.
                raise ValueError("event_id inválido.")

            # Confere somente a estrutura geral de data. A validação específica
            # de um pedido acontece nas regras de negócio e em catalogo.py.
            if not isinstance(envelope["data"], dict):
                # Recusa, por exemplo, uma lista ou string no lugar dos dados.
                raise ValueError("Dados inválidos.")

            # Guarda o nome declarado para consultar a política e a chave pública.
            produtor = envelope["producer"]

            # O tipo assinado precisa coincidir com a routing key real da entrega;
            # o produtor também precisa ser o autorizado para esse tipo.
            if envelope["event_type"] != routing_key or PRODUTORES.get(routing_key) != produtor:
                # Evita aceitar evento sob outro roteamento ou identidade indevida.
                raise ValueError("Produtor ou routing key incorretos.")

            # Recupera os bytes da assinatura. validate=True rejeita Base64 malformado;
            # decodificar Base64, por si só, ainda não valida a assinatura RSA.
            assinatura = base64.b64decode(envelope["Signature"], validate=True)

            # Reconstrói uma cópia sem Signature, igual ao conteúdo usado ao assinar.
            # k e v são chave e valor de cada campo; o envelope original é mantido.
            conteudo = {k: v for k, v in envelope.items() if k != "Signature"}

            # Verifica com a chave PÚBLICA local do produtor e o hash recalculado.
            # Sucesso não retorna True: verify termina normalmente; falha lança erro.
            # Alterar dados sem refazer uma assinatura válida é detectado aqui.
            pkcs1_15.new(self.publicas[produtor]).verify(SHA256.new(serializar(conteudo)), assinatura)

            # Só entrega o evento ao chamador depois de concluir todas as verificações.
            return envelope

        # Unifica erros de JSON/valores, tipos, chaves ausentes, Unicode e Base64.
        except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error) as erro:
            # mensageria.py captura este ValueError e envia basic_reject ao broker.
            # Aqui só propagamos a falha local, mantendo sua causa com "from erro".
            raise ValueError("Evento rejeitado: assinatura, produtor ou envelope inválido.") from erro
