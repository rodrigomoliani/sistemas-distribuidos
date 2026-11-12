# Produtor periódico de promoções. Não consome eventos e não altera o catálogo.
# O envio passa por Publicador, que assina e usa basic_publish na mensageria.

# Lê o intervalo configurado no ambiente local.
import os

# Fornece os sorteios de produto e percentual de desconto.
import random

# Permite pausar o laço entre publicações.
import time

# Permite reconhecer erros de transporte AMQP.
import pika

# Catálogo fixo local com produtos, categorias e preços.
from comum.catalogo import CATALOGO

# Classe que mantém conexão/canal e assinatura do produtor.
from comum.mensageria import Publicador


# Coordena a preparação e o laço de publicação.
def main():

    # Lê os segundos entre publicações; usa cinco quando não configurado.
    intervalo = float(os.environ.get("INTERVALO_PROMOCOES", "5"))

    # Exige valor positivo e finito; zero, negativos, infinito e NaN são recusados.
    if not 0 < intervalo < float("inf"):

        # Interrompe a inicialização se o intervalo não for adequado.
        raise ValueError("INTERVALO_PROMOCOES deve ser positivo e finito.")

    # [AMQP VIA COMUM] Abre conexão/canal e prepara as exchanges e filas.
    publicador = Publicador("promocoes")

    # Garante fechamento do publicador mesmo em interrupção ou erro.
    try:

        # Informa que o processo está pronto para publicar.
        print("PRONTO promocoes", flush=True)

        # Laço contínuo, encerrado por interrupção ou exceção.
        while True:

            # Transforma as chaves do catálogo em lista e sorteia um ID.
            produto_id = random.choice(list(CATALOGO))

            # Obtém os dados do produto escolhido na memória local.
            produto = CATALOGO[produto_id]

            # Escolhe um dos três percentuais de desconto da demonstração.
            desconto = random.choice([10, 20, 30])

            # Monta os dados: ID, campos do produto (expandido com **) e percentual.
            dados = {"produto_id": produto_id, **produto, "desconto_percentual": desconto,

                     # Calcula preço promocional em centavos; // mantém resultado inteiro.
                     # Esse preço é uma notificação, não modifica o preço usado para criar pedidos.
                     "preco_promocional_centavos": produto["preco_centavos"] * (100 - desconto) // 100}

            # [AMQP VIA COMUM: ENVIO] Publica com categoria na routing key.
            # Exemplo: promocao.categoria.C vai para C2, mas não para C1.
            # O envio efetivo é canal.basic_publish em comum/mensageria.py.
            publicador.publicar(f"promocao.categoria.{produto['categoria']}", dados)

            # Pausa esta thread pelo intervalo; não espera resposta dos consumidores.
            time.sleep(intervalo)

    # Executa ao sair do bloco protegido por qualquer motivo.
    finally:

        # [AMQP VIA COMUM] Encerra o canal/conexão do publicador.
        publicador.fechar()


# Permite iniciar com python -m promocoes.
if __name__ == "__main__":

    # Centraliza o tratamento do encerramento do programa.
    try:

        # Executa o produtor periódico.
        main()

    # Captura o Ctrl+C usado para parar a demonstração.
    except KeyboardInterrupt:

        # Não precisa de ação extra; o finally de main já fecha o publicador.
        pass

    # Trata erros de configuração, arquivos de chave e comunicação.
    except (ValueError, RuntimeError, OSError, pika.exceptions.AMQPError) as erro:

        # Encerra com erro e mostra seu tipo sem expor credenciais.
        raise SystemExit(f"FALHA Promoções: {type(erro).__name__}. Verifique configuração, RabbitMQ e chaves.")
