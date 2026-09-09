import os
import random
import time

import pika

from comum.catalogo import CATALOGO
from comum.mensageria import Publicador


def main():
    intervalo = float(os.environ.get("INTERVALO_PROMOCOES", "5"))
    if not 0 < intervalo < float("inf"):
        raise ValueError("INTERVALO_PROMOCOES deve ser positivo e finito.")
    publicador = Publicador("promocoes")
    try:
        print("PRONTO promocoes", flush=True)
        while True:
            produto_id = random.choice(list(CATALOGO))
            produto = CATALOGO[produto_id]
            desconto = random.choice([10, 20, 30])
            dados = {"produto_id": produto_id, **produto, "desconto_percentual": desconto,
                     "preco_promocional_centavos": produto["preco_centavos"] * (100 - desconto) // 100}
            publicador.publicar(f"promocao.categoria.{produto['categoria']}", dados)
            time.sleep(intervalo)
    finally:
        publicador.fechar()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (ValueError, RuntimeError, OSError, pika.exceptions.AMQPError) as erro:
        raise SystemExit(f"FALHA Promoções: {type(erro).__name__}. Verifique configuração, RabbitMQ e chaves.")
