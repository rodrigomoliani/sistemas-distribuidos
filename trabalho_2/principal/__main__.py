import threading

import pika

from comum.catalogo import CATALOGO, dinheiro
from comum.mensageria import Publicador, consumir
from principal.modelo import Principal


def main():
    modelo = Principal()
    parar, pronto = threading.Event(), threading.Event()
    falhas = []
    publicador = Publicador("principal")

    def receber():
        try:
            consumir("principal", modelo.tratar, parar, pronto)
        except Exception as erro:
            falhas.append(erro)
            print("FALHA no consumidor. Pressione Enter e reinicie a sessão limpa.", flush=True)
            parar.set()
            pronto.set()

    thread = threading.Thread(target=receber, name="eventos-principal", daemon=True)
    thread.start()
    try:
        if not pronto.wait(15) or falhas:
            raise RuntimeError("Não foi possível iniciar o consumidor.")
        cliente = input("Cliente: ").strip()
        if not cliente:
            raise ValueError("Informe um nome de cliente.")
        while not parar.is_set():
            print("\n1 Produtos | 2 Criar pedido | 3 Excluir pedido | 4 Meus pedidos | 0 Sair", flush=True)
            opcao = input("> ").strip()
            if parar.is_set():
                break
            try:
                if opcao == "0":
                    break
                if opcao == "1":
                    for codigo, produto in CATALOGO.items():
                        print(f"{codigo}: {produto['nome']} | categoria {produto['categoria']} | {dinheiro(produto['preco_centavos'])}")
                    print("Disponibilidade conferida pelo Estoque após criar o pedido.")
                elif opcao == "2":
                    entrada = input("Itens produto:quantidade separados por vírgula (ex.: 1:2,2:1): ")
                    selecao = []
                    for trecho in entrada.split(","):
                        codigo, quantidade = trecho.strip().split(":")
                        selecao.append((codigo.strip(), int(quantidade)))
                    with modelo.lock:
                        tipo, dados = modelo.criar(cliente, selecao)
                        publicador.publicar(tipo, dados)
                    print(f"CRIADO {dados['pedido_id']}", flush=True)
                elif opcao == "3":
                    pedido_id = input("ID do pedido: ").strip()
                    with modelo.lock:
                        saidas = modelo.excluir(pedido_id, cliente=cliente)
                        for tipo, dados in saidas:
                            publicador.publicar(tipo, dados)
                    print("Pedido excluído." if saidas else "Pedido já estava excluído.", flush=True)
                elif opcao == "4":
                    pedidos = modelo.listar(cliente)
                    for pedido in pedidos:
                        dados = pedido["dados"]
                        print(f"{dados['pedido_id']} | {pedido['status']} | {dinheiro(dados['total_centavos'])} | {pedido['motivo']}")
                    if not pedidos:
                        print("Nenhum pedido.")
                else:
                    print("Opção inválida.")
            except ValueError as erro:
                print(f"Entrada inválida: {erro}", flush=True)
    finally:
        parar.set()
        thread.join(timeout=5)
        publicador.fechar()
    if falhas:
        raise RuntimeError("Consumidor interrompido.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nPrincipal encerrado.")
    except (ValueError, RuntimeError, OSError, pika.exceptions.AMQPError) as erro:
        print(f"FALHA Principal: {type(erro).__name__}. Verifique entrada, RabbitMQ e chaves; reinicie a sessão limpa.", flush=True)
        raise SystemExit(1)
