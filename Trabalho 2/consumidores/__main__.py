# Uma implementação, dois processos: python -m consumidores c1 ou c2.
# Cada nome usa sua própria fila e recebe os eventos selecionados pelas bindings.

# Interpreta o argumento informado no terminal.
import argparse

# Importa o laço de consumo que verifica assinaturas e confirma as mensagens.
from comum.mensageria import executar


# Prepara o consumidor de promoções escolhido pelo usuário.
def main():

    # Cria o interpretador dos argumentos e sua descrição de ajuda.
    parser = argparse.ArgumentParser(description="Consumidor de promoções")

    # Exige um argumento posicional com valor c1 ou c2, rejeitando outros nomes.
    parser.add_argument("consumidor", choices=["c1", "c2"])

    # Lê a escolha que determinará a fila e os arquivos de chave pública.
    nome = parser.parse_args().consumidor

    # Callback de negócio local, chamado pela mensageria após verificar a assinatura.
    # A função acessa nome da função externa (closure) para identificar o consumidor.
    def tratar(tipo, dados):

        # Imprime a promoção recebida e o nome do consumidor no terminal.
        print(f"PROMOCAO {nome} {tipo} {dados}", flush=True)

        # Lista vazia informa que não há evento a publicar em resposta.
        return []

    # [AMQP VIA COMUM] Abre a conexão e consome promocoes.c1 ou promocoes.c2.
    # As bindings em comum/mensageria.py fazem a seleção no broker;
    # este callback não precisa filtrar categorias por conta própria.
    executar(nome, tratar)


# Inicia o programa quando usado como módulo executável.
if __name__ == "__main__":

    # Executa a preparação e entra no laço consumidor.
    main()
