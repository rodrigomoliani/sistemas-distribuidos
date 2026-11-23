from Crypto.PublicKey import RSA
from comum.seguranca import RAIZ, SERVICOS


def main():
    """Gera pares de chaves RSA 2048-bit para cada microsserviço e distribui as chaves públicas."""
    publicas = {}

    for servico in SERVICOS:
        pasta = RAIZ / servico / "chaves"
        pasta.mkdir(parents=True, exist_ok=True)
        privada = pasta / "privada.pem"

        # Gera chave privada apenas se ainda não existir
        if not privada.exists():
            privada.write_bytes(RSA.generate(2048).export_key())

        chave = RSA.import_key(privada.read_bytes())
        if not chave.has_private() or chave.size_in_bits() < 2048:
            raise ValueError(f"Chave privada inválida em {servico}.")

        publicas[servico] = chave.public_key().export_key()

    # Distribui cópias das chaves públicas para cada serviço consumidor
    for destinatario in SERVICOS:
        pasta = RAIZ / destinatario / "chaves" / "publicas"
        pasta.mkdir(parents=True, exist_ok=True)
        for produtor, chave in publicas.items():
            (pasta / f"{produtor}.pem").write_bytes(chave)

    print("Chaves prontas. Chaves privadas existentes foram preservadas.", flush=True)


if __name__ == "__main__":
    main()
