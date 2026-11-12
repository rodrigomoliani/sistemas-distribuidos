# Este módulo concentra o transporte dos eventos pelo protocolo AMQP.
# Para apresentar a comunicação com o RabbitMQ, procure as marcações [AMQP].
# Definir funções, montar dicionários, assinar e validar mensagens são ações
# locais: as chamadas de rede aparecem explicitamente nos comentários abaixo.

# Permite ler a variável de ambiente com o endereço do broker.
import os

# Fornece Event, um sinal para coordenar threads dentro do mesmo processo.
import threading

# Biblioteca cliente usada para conversar com o RabbitMQ por AMQP.
import pika

# Classe responsável pela assinatura e verificação local das mensagens.
from comum.seguranca import Assinador

# Nomes exatos das exchanges; produtores e consumidores usam os mesmos nomes.
ECOMMERCE = "eCommerce"
PROMOCOES = "Promoções"

# Mapa local: cada fila tem uma exchange e uma lista de binding keys.
# Este dicionário não cria nada no broker; declarar_topologia faz as operações.
FILAS = {
    # O Principal acompanha reserva, recusa de estoque, pagamento e envio.
    "principal": (ECOMMERCE, [
        # Resultados possíveis da tentativa de reserva.
        "pedido.estoque_ok", "estoque.indisponivel",
        # Resultados do pagamento e confirmação da Entrega.
        "pagamento.aprovado", "pagamento.recusado", "pedido.enviado",
    ]),

    # Estoque reserva na criação e devolve eventual reserva na exclusão.
    "estoque": (ECOMMERCE, ["pedido.criado", "pedido.excluido"]),

    # Pagamento só começa após a confirmação da reserva.
    "pagamento": (ECOMMERCE, ["pedido.estoque_ok"]),

    # Entrega começa após a aprovação do pagamento.
    "entrega": (ECOMMERCE, ["pagamento.aprovado"]),

    # C1 tem duas inscrições exatas, para categorias A e B.
    "promocoes.c1": (PROMOCOES, ["promocao.categoria.A", "promocao.categoria.B"]),

    # Na exchange topic, * corresponde a uma palavra: recebe A/B/C e qualquer
    # outra categoria de uma palavra que corresponda a este padrão.
    "promocoes.c2": (PROMOCOES, ["promocao.categoria.*"]),
}


# Define a abertura da conexão; o corpo só roda quando conectar() é chamada.
def conectar():
    # Apenas monta a configuração. os.environ.get lê uma variável local;
    # esse "get" não é um método HTTP nem uma requisição REST.
    parametros = pika.URLParameters(
        # Se não houver variável, usa guest/guest, localhost, porta AMQP 5672
        # e virtual host "/", representado por %2F na URL.
        os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
    )

    # Configura heartbeat como zero nesta demonstração. O publicador do
    # terminal pode ficar ocioso enquanto input() espera o usuário digitar.
    parametros.heartbeat = 0

    # Limita a dez segundos a espera quando o broker bloqueia a conexão
    # por falta de recursos; não é um prazo para processar um pedido.
    parametros.blocked_connection_timeout = 10

    # Limita a espera do socket durante a abertura da conexão TCP.
    parametros.socket_timeout = 5

    # [AMQP: CONEXÃO] Esta chamada abre o transporte e negocia a sessão
    # com o RabbitMQ. Retorna a conexão que o serviço usará.
    return pika.BlockingConnection(parametros)


# Recebe um canal aberto e declara exchanges, filas e suas ligações.
def declarar_topologia(canal):
    # [AMQP: EXCHANGE] direct exige correspondência exata entre routing key
    # e binding key. durable=False não solicita manter a exchange após
    # reiniciar o broker. Declaração repetida deve ter propriedades iguais.
    canal.exchange_declare(exchange=ECOMMERCE, exchange_type="direct", durable=False)

    # [AMQP: EXCHANGE] topic permite padrões nas bindings, como o * de C2.
    canal.exchange_declare(exchange=PROMOCOES, exchange_type="topic", durable=False)

    # Desempacota cada entrada do mapa em nome da fila, exchange e bindings.
    for fila, (exchange, bindings) in FILAS.items():
        # [AMQP: FILA] Cria a fila ou verifica uma existente compatível.
        # durable=False: não sobrevive ao reinício do broker.
        # exclusive=False: não é exclusiva desta conexão.
        # auto_delete=False: não desaparece quando sai o último consumidor.
        canal.queue_declare(queue=fila, durable=False, exclusive=False, auto_delete=False)

        # Uma fila pode ter interesse em vários eventos, com várias bindings.
        for chave in bindings:
            # [AMQP: BINDING] Liga a fila à exchange com a chave de seleção.
            # Uma mesma chave em filas diferentes leva uma cópia a cada fila
            # correspondente; consumidores da mesma fila dividem as entregas.
            canal.queue_bind(queue=fila, exchange=exchange, routing_key=chave)


# Agrupa assinatura, conexão e canal para publicações fora do callback,
# como as feitas pelo menu do Principal e pelo serviço de Promoções.
class Publicador:
    """Conexão usada somente pela thread que criou esta instância."""

    # Executa ao criar Publicador(servico). self é a instância atual;
    # servico indica a identidade e as chaves usadas na assinatura.
    def __init__(self, servico):
        # Lê as chaves do disco, sem consultar outros serviços pela rede.
        self.assinador = Assinador.carregar(servico)

        # A chamada delega a abertura da conexão à função conectar.
        self.conexao = conectar()

        # [AMQP: CANAL] Abre um canal lógico na conexão TCP existente;
        # não cria uma conexão TCP separada para cada operação.
        self.canal = self.conexao.channel()

        # Declara as estruturas no broker antes da primeira publicação.
        declarar_topologia(self.canal)

        # [AMQP: CONFIRMAÇÕES] Ativa publisher confirms neste canal.
        # Confirmação do broker não significa que um consumidor já tratou
        # o evento nem que o pedido inteiro foi concluído.
        self.canal.confirm_delivery()

    # tipo é o nome do evento; dados é o conteúdo de negócio da mensagem.
    def publicar(self, tipo, dados):
        # Operação local: produz o envelope assinado e serializado em bytes.
        corpo = self.assinador.assinar(tipo, dados)

        # Delega o envio à função que chama basic_publish abaixo.
        publicar_corpo(self.canal, tipo, corpo)

    # Permite encerrar explicitamente o publicador quando ele não for mais usado.
    def fechar(self):
        # Consulta o estado local; is_open não publica nem consulta uma fila.
        if self.conexao.is_open:
            # [AMQP: FECHAMENTO] Encerra a conexão e seus canais.
            self.conexao.close()


# Recebe bytes já assinados; a responsabilidade aqui é encaminhá-los ao broker.
def publicar_corpo(canal, tipo, corpo):
    # Escolha local da exchange pelo prefixo do nome do evento.
    exchange = PROMOCOES if tipo.startswith("promocao.") else ECOMMERCE

    # [AMQP: ENVIO] Esta é a chamada que efetivamente publica a mensagem.
    # Com confirms ativados, Pika aguarda confirmação do broker e pode
    # lançar uma exceção se houver falha ou se a mensagem não tiver destino.
    canal.basic_publish(
        # A exchange roteia a mensagem; não chamamos diretamente outro serviço.
        exchange=exchange,

        # Nome do evento que o broker compara com as binding keys.
        routing_key=tipo,

        # Bytes do JSON, já incluindo o campo Signature.
        body=corpo,

        # Pede devolução caso nenhuma fila corresponda ao roteamento.
        # Com confirms, Pika sinaliza esse caso como erro de publicação.
        mandatory=True,

        # BasicProperties apenas constrói metadados localmente.
        # basic_publish envia esses metadados junto com o corpo.
        properties=pika.BasicProperties(
            # Informa o formato; não converte nem valida o JSON.
            content_type="application/json",

            # 1 significa mensagem transitória: não solicita persistência.
            delivery_mode=1,
        ),
    )

    # Saída local no terminal; flush=True evita esperar pelo buffer de saída.
    print(f"PUBLICADO {tipo}", flush=True)


# servico escolhe fila/chaves. tratar é a função de negócio passada pelo
# chamador. parar e pronto são sinais opcionais entre threads locais.
def consumir(servico, tratar, parar=None, pronto=None):
    # Carrega chaves para verificar entradas e assinar eventuais saídas.
    assinador = Assinador.carregar(servico)

    # C1/C2 usam filas prefixadas; os demais serviços usam o próprio nome.
    fila = f"promocoes.{servico}" if servico in ("c1", "c2") else servico

    # Reutiliza o sinal recebido ou cria um Event inicialmente não acionado.
    parar = parar or threading.Event()

    # Guarda IDs já concluídos nesta execução. É memória local e não persiste:
    # reiniciar o processo perde esta proteção contra eventos repetidos.
    vistos = set()

    # Abre uma conexão própria, usada na thread que executa este consumidor.
    conexao = conectar()

    # O finally abaixo fará o fechamento ao sair deste bloco.
    try:
        # [AMQP: CANAL] Abre o canal para receber e publicar eventos de saída.
        canal = conexao.channel()

        # Declara filas e ligações antes de iniciar o consumo.
        declarar_topologia(canal)

        # [AMQP: CONFIRMAÇÕES] Ativa confirmação das publicações de saída.
        canal.confirm_delivery()

        # [AMQP: PREFETCH] No máximo uma entrega ainda sem ack por consumidor.
        # Não limita a capacidade da fila nem estabelece um intervalo de tempo.
        canal.basic_qos(prefetch_count=1)

        # CALLBACK: função entregue ao Pika para ser chamada quando uma
        # mensagem chegar. O RabbitMQ entrega bytes; quem chama esta função
        # Python é o Pika, dentro deste processo.
        # ch: canal; metodo: routing_key e delivery_tag da entrega;
        # propriedades: metadados da mensagem, não usados aqui; corpo: bytes.
        def receber(ch, metodo, propriedades, corpo):
            # Erros de validação serão tratados como entrada inválida.
            try:
                # Verifica localmente assinatura, envelope, produtor autorizado
                # e correspondência entre tipo do evento e routing key.
                evento = assinador.verificar(corpo, metodo.routing_key)

                # Se o ID já foi concluído, pula o negócio, mas ainda dá ack.
                if evento["event_id"] not in vistos:
                    # Chamada LOCAL da função recebida no parâmetro tratar.
                    # Executa a regra do serviço e retorna pares (tipo, dados)
                    # para publicação. Não faz uma chamada remota por HTTP.
                    saidas = tratar(evento["event_type"], evento["data"])

                    # Pode haver nenhuma, uma ou várias mensagens de saída.
                    for tipo, dados in saidas:
                        # Assina localmente e delega o envio AMQP ao publicador,
                        # usando o mesmo canal deste consumidor.
                        publicar_corpo(ch, tipo, assinador.assinar(tipo, dados))

                    # Marca o ID após tratar e publicar todas as saídas.
                    # Isso não torna estado local e publicação uma transação;
                    # uma falha parcial exige reiniciar a sessão limpa.
                    vistos.add(evento["event_id"])

            # Abrange ValueError da assinatura e das regras de validação.
            except ValueError as erro:
                # Registra localmente qual evento foi recusado e por quê.
                print(f"DESCARTADO {metodo.routing_key}: {erro}", flush=True)

                # [AMQP: REJEIÇÃO] Informa que esta entrega foi rejeitada.
                # delivery_tag identifica a entrega neste canal, não o pedido.
                # requeue=False impede devolvê-la à fila; sem dead-letter
                # configurada neste projeto, a mensagem é descartada.
                ch.basic_reject(delivery_tag=metodo.delivery_tag, requeue=False)

                # Sai do callback para não dar ack à entrega rejeitada.
                return

            # [AMQP: ACK] Confirma o tratamento desta entrega ao broker,
            # inclusive para duplicatas já vistas. Ele pode removê-la da fila.
            # Falhas de conexão/publicação saem antes daqui, sem confirmar
            # a entrada. Este ack é diferente de um publisher confirm.
            ch.basic_ack(delivery_tag=metodo.delivery_tag)

        # [AMQP: INSCRIÇÃO] Registra o consumidor e associa seu callback.
        # receber sem parênteses passa a função; receber() a executaria agora.
        # auto_ack=False exige confirmação ou rejeição explícita no callback.
        canal.basic_consume(queue=fila, on_message_callback=receber, auto_ack=False)

        # Informa no terminal que a inscrição do consumidor já foi criada.
        print(f"PRONTO {servico} fila={fila}", flush=True)

        # Só sinaliza prontidão se o chamador tiver fornecido um Event.
        if pronto:
            # Sinal local entre threads; não é um evento enviado ao RabbitMQ.
            pronto.set()

        # Mantém o atendimento enquanto ninguém acionar a parada.
        while not parar.is_set():
            # [AMQP: PROCESSAMENTO DE I/O] Atende a conexão e despacha entregas
            # para receber. time_limit permite voltar ao laço periodicamente
            # para verificar parar; não limita a duração de um callback.
            conexao.process_data_events(time_limit=0.5)

    # Executa na saída normal ou durante a propagação de uma exceção.
    finally:
        # Verifica o estado local para não fechar uma conexão já fechada.
        if conexao.is_open:
            # [AMQP: FECHAMENTO] Libera a conexão deste consumidor.
            conexao.close()


# Entrada comum dos serviços que ficam consumindo eventos no terminal.
def executar(servico, tratar):
    # Centraliza o tratamento das falhas esperadas durante a execução.
    try:
        # Permanece no consumo até interrupção, parada ou erro.
        consumir(servico, tratar)

    # Ctrl+C gera KeyboardInterrupt; permite encerrar sem traceback neste caso.
    except KeyboardInterrupt:
        # consumir já executa seu finally; não há outra ação neste bloco.
        pass

    # Trata erros de sistema, preparação de chaves e comunicação AMQP.
    except (OSError, RuntimeError, pika.exceptions.AMQPError) as erro:
        # Exibe apenas o tipo de falha, sem imprimir credenciais da conexão.
        # Não há recuperação distribuída: a orientação é reiniciar a sessão.
        print(f"FALHA {servico}: {type(erro).__name__}. Verifique RabbitMQ/chaves e reinicie a sessão limpa.", flush=True)

        # Código de saída 1 informa ao terminal que o processo falhou.
        raise SystemExit(1)
