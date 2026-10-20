import json
import logging
import os
import random
import time
from uuid import NAMESPACE_URL, uuid5
import httpx

from comum.banco import Banco
from comum.catalogo import CATALOGO, dinheiro
from comum.mensageria import Trabalhador
from promocoes.email import Email
from promocoes.modelo import Promocoes

log = logging.getLogger(__name__)


def disparar(banco, email):
    """Sorteia uma oferta e a envia somente aos clientes interessados naquela categoria."""
    produto = random.choice(list(CATALOGO.values()))
    desconto = random.choice([10, 20, 30])
    assunto = f"Oferta de {produto['nome']}: {desconto}% de desconto"
    texto = (
        f"Categoria {produto['categoria']}. De {dinheiro(produto['preco_centavos'])} por "
        f"{dinheiro(produto['preco_centavos'] * (100 - desconto) // 100)}. Oferta demonstrativa."
    )

    campanha = f"{int(time.time() // 60)}:{produto['nome']}:{desconto}"

    for row in banco.ler("SELECT * FROM interesses"):
        if produto["categoria"] not in json.loads(row["categorias"]):
            continue

        envio_id = str(uuid5(NAMESPACE_URL, f"{campanha}:{row['cliente']}:{row['versao']}"))

        with banco.transacao() as con:
            atual = con.execute("SELECT * FROM interesses WHERE cliente=?", (row["cliente"],)).fetchone()
            if (
                atual["versao"] != row["versao"]
                or produto["categoria"] not in json.loads(atual["categorias"])
            ):
                continue

            if con.execute("SELECT 1 FROM envios WHERE id=?", (envio_id,)).fetchone():
                continue

            try:
                email.enviar(row["email"], assunto, texto, envio_id)
            except httpx.HTTPError:
                log.exception("Falha no provedor de e-mail; cadastro preservado")
                continue

            con.execute(
                "INSERT INTO envios(id,email,assunto,texto,modo) VALUES (?,?,?,?,?)",
                (envio_id, row["email"], assunto, texto, email.modo),
            )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    intervalo = float(os.environ.get("INTERVALO_PROMOCOES", "30"))
    if not 1 <= intervalo < float("inf"):
        raise ValueError("INTERVALO_PROMOCOES deve ser finito e >= 1")

    email = Email()
    banco = Banco("promocoes")
    modelo = Promocoes(banco)
    worker = Trabalhador("promocoes", banco, modelo.tratar)
    worker.iniciar()

    proximo = time.monotonic() + intervalo
    try:
        while True:
            time.sleep(0.2)
            if time.monotonic() >= proximo:
                if worker.pronto.is_set():
                    disparar(banco, email)
                proximo = time.monotonic() + intervalo
    except KeyboardInterrupt:
        pass
    finally:
        worker.fechar()
        if not worker.thread.is_alive():
            banco.fechar()


if __name__ == "__main__":
    main()
