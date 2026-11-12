# Entrada de python -m principal: menu na thread principal e consumo em outra thread.
# Cada thread usa sua própria conexão Pika. O lock protege o modelo compartilhado.
# [AMQP VIA COMUM] indica chamadas que delegam rede a comum/mensageria.py.

# Cria a thread consumidora e os sinais locais Event.
import threading

# Usado para reconhecer exceções de comunicação AMQP no encerramento.
import pika

# Catálogo para exibição local e formatação de valores em reais.
from comum.catalogo import CATALOGO, dinheiro

# Publicador envia eventos; consumir registra e atende o consumidor no RabbitMQ.
from comum.mensageria import Publicador, consumir

# Modelo mantém os pedidos e suas regras na memória deste processo.
from principal.modelo import Principal


# Coordena interface, publicação e consumo do serviço Principal.
def main():

    # Instancia os pedidos e o RLock compartilhados entre menu e consumidor.
    modelo = Principal()

    # parar solicita encerramento; pronto informa inicialização do consumidor.
    # São sinais locais de threads, não eventos publicados no RabbitMQ.
    parar, pronto = threading.Event(), threading.Event()

    # Lista em memória para comunicar uma falha do consumidor à thread do menu.
    falhas = []

    # [AMQP VIA COMUM] Carrega chaves, abre conexão/canal e declara a topologia.
    # Esta instância será usada só pela thread principal para publicações do menu.
    publicador = Publicador("principal")

    # Alvo da thread consumidora, sem parâmetros. Não é o callback de quatro
    # argumentos do Pika, que está dentro de comum.mensageria.consumir.
    def receber():

        # Captura falhas para sinalizar ao menu, em vez de perdê-las na outra thread.
        try:

            # [AMQP VIA COMUM] Abre outra conexão e consome a fila principal.
            # modelo.tratar é passado sem parênteses: o callback o chamará a cada evento.
            # Não chama outro microsserviço diretamente.
            consumir("principal", modelo.tratar, parar, pronto)

        # Qualquer exceção comum do consumidor exige reinício da sessão.
        except Exception as erro:

            # Guarda a falha para a thread principal perceber que o consumo terminou.
            falhas.append(erro)

            # input pode estar bloqueado; o usuário pressiona Enter para o menu voltar.
            print("FALHA no consumidor. Pressione Enter e reinicie a sessão limpa.", flush=True)

            # Aciona o sinal de parada usado pelo laço do menu.
            parar.set()

            # Libera também quem estiver esperando inicialização para detectar a falha.
            pronto.set()

    # Prepara a thread sem iniciá-la. target recebe a função, name identifica-a;
    # daemon permite que ela não impeça a saída do processo se continuar ativa.
    thread = threading.Thread(target=receber, name="eventos-principal", daemon=True)

    # Começa a executar receber em paralelo ao menu, dentro do mesmo processo.
    thread.start()

    # O finally garante a tentativa de encerramento dos recursos ao sair.
    try:

        # Espera até 15 segundos por prontidão e verifica se houve falha na inicialização.
        if not pronto.wait(15) or falhas:

            # Não abre o menu se o consumidor não estiver pronto.
            raise RuntimeError("Não foi possível iniciar o consumidor.")

        # Lê e limpa o nome do cliente no terminal; não consulta um serviço de usuários.
        cliente = input("Cliente: ").strip()

        # Recusa nome vazio, inclusive uma entrada que continha somente espaços.
        if not cliente:

            # Erro de entrada encerra esta inicialização do Principal.
            raise ValueError("Informe um nome de cliente.")

        # Repete o menu enquanto o consumidor não tiver solicitado parada.
        while not parar.is_set():

            # Mostra as opções locais da interface de terminal.
            print("\n1 Produtos | 2 Criar pedido | 3 Excluir pedido | 4 Meus pedidos | 0 Sair", flush=True)

            # Espera a opção apenas nesta thread; a outra continua recebendo eventos.
            opcao = input("> ").strip()

            # Após input retornar, confere se o consumidor falhou enquanto o usuário digitava.
            if parar.is_set():

                # Sai do laço para finalizar os recursos.
                break

            # Erros de preenchimento serão exibidos sem derrubar o menu.
            try:

                # A opção zero representa saída solicitada pelo usuário.
                if opcao == "0":

                    # Encerra o laço do menu, passando pelo finally.
                    break

                # Seleciona a exibição dos produtos.
                if opcao == "1":

                    # Percorre IDs e dados do catálogo local, sem consultar o Estoque.
                    for codigo, produto in CATALOGO.items():

                        # Imprime nome, categoria e preço convertido de centavos para texto.
                        print(f"{codigo}: {produto['nome']} | categoria {produto['categoria']} | {dinheiro(produto['preco_centavos'])}")

                    # Explica que saldo disponível só é conferido no fluxo assíncrono do pedido.
                    print("Disponibilidade conferida pelo Estoque após criar o pedido.")

                # Seleciona a criação de um pedido.
                elif opcao == "2":

                    # Recebe texto com pares ID:quantidade separados por vírgula.
                    entrada = input("Itens produto:quantidade separados por vírgula (ex.: 1:2,2:1): ")

                    # Lista auxiliar para os pares que serão validados pelo modelo.
                    selecao = []

                    # Divide o texto em trechos, um para cada produto informado.
                    for trecho in entrada.split(","):

                        # Remove espaços externos e separa cada trecho no caractere dois-pontos.
                        codigo, quantidade = trecho.strip().split(":")

                        # Normaliza o ID e converte a quantidade para inteiro; formato inválido gera ValueError.
                        selecao.append((codigo.strip(), int(quantidade)))

                    # Protege a criação e o envio contra alterações concorrentes do consumidor.
                    # É um lock local; não torna a alteração e a publicação uma transação distribuída.
                    with modelo.lock:

                        # Cria o pedido em memória e recebe o par (tipo, dados) a publicar.
                        tipo, dados = modelo.criar(cliente, selecao)

                        # [AMQP VIA COMUM: CRIAÇÃO] Assina e publica pedido.criado.
                        # O envio efetivo ocorre em canal.basic_publish de comum/mensageria.py.
                        publicador.publicar(tipo, dados)

                    # Exibe o ID após a publicação retornar; isso não significa pagamento aprovado.
                    print(f"CRIADO {dados['pedido_id']}", flush=True)

                # Seleciona a exclusão lógica de um pedido.
                elif opcao == "3":

                    # Lê o ID completo que foi mostrado na criação ou consulta.
                    pedido_id = input("ID do pedido: ").strip()

                    # Protege a exclusão e suas publicações de alterações da outra thread.
                    with modelo.lock:

                        # Marca o pedido como excluído, limitando a ação ao cliente deste menu.
                        saidas = modelo.excluir(pedido_id, cliente=cliente)

                        # Percorre a lista de saídas: na repetição ela é vazia.
                        for tipo, dados in saidas:

                            # [AMQP VIA COMUM: EXCLUSÃO] Envia pedido.excluido para o Estoque.
                            # A devolução acontece quando o outro processo consumir, não nesta linha localmente.
                            publicador.publicar(tipo, dados)

                    # Distingue exclusão nova de uma solicitação já atendida.
                    print("Pedido excluído." if saidas else "Pedido já estava excluído.", flush=True)

                # Seleciona a consulta de pedidos.
                elif opcao == "4":

                    # Lê uma cópia dos pedidos locais do cliente; não faz GET nem RPC.
                    pedidos = modelo.listar(cliente)

                    # Percorre os pedidos retornados pelo modelo.
                    for pedido in pedidos:

                        # Extrai o dicionário dos dados originais do pedido.
                        dados = pedido["dados"]

                        # Exibe ID, estado conhecido, total formatado e eventual motivo de exclusão.
                        print(f"{dados['pedido_id']} | {pedido['status']} | {dinheiro(dados['total_centavos'])} | {pedido['motivo']}")

                    # Detecta quando o filtro não encontrou pedidos deste cliente.
                    if not pedidos:

                        # Mostra que ainda não existe pedido para esse nome nesta sessão.
                        print("Nenhum pedido.")

                # Caminho das opções diferentes de zero a quatro.
                else:

                    # Informa opção desconhecida sem encerrar o programa.
                    print("Opção inválida.")

            # Captura falhas de conversão e validação da operação escolhida.
            except ValueError as erro:

                # Mostra o problema e volta ao menu na próxima iteração.
                print(f"Entrada inválida: {erro}", flush=True)

    # Executa tanto em saída normal quanto em exceção dentro do bloco protegido.
    finally:

        # Pede ao consumidor que termine seu laço de processamento.
        parar.set()

        # Espera no máximo cinco segundos pela thread; join não mata a thread à força.
        thread.join(timeout=5)

        # [AMQP VIA COMUM] Fecha a conexão do publicador da thread principal.
        publicador.fechar()

    # Verifica se o encerramento ocorreu por falha do consumidor.
    if falhas:

        # Propaga uma falha para o tratamento externo sinalizar saída com erro.
        raise RuntimeError("Consumidor interrompido.")


# Executa o programa ao usar python -m principal; importar não abre o menu.
if __name__ == "__main__":

    # Centraliza as formas de encerramento da entrada do programa.
    try:

        # Inicia a função que prepara e executa o serviço.
        main()

    # Ctrl+C ou fechamento da entrada do terminal são saídas previstas.
    except (KeyboardInterrupt, EOFError):

        # Imprime a informação de encerramento normal/interrompido pelo usuário.
        print("\nPrincipal encerrado.")

    # Agrupa problemas de entrada, preparação de chaves, sistema e RabbitMQ.
    except (ValueError, RuntimeError, OSError, pika.exceptions.AMQPError) as erro:

        # Exibe o tipo da falha e a orientação de reinício, sem imprimir credenciais.
        print(f"FALHA Principal: {type(erro).__name__}. Verifique entrada, RabbitMQ e chaves; reinicie a sessão limpa.", flush=True)

        # Encerra com código 1 para indicar falha ao terminal.
        raise SystemExit(1)
