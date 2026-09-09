from Crypto.PublicKey import RSA

from comum.seguranca import RAIZ, SERVICOS


def main():
    publicas = {}
    for servico in SERVICOS:
        pasta = RAIZ / servico / "chaves"
        pasta.mkdir(parents=True, exist_ok=True)
        privada = pasta / "privada.pem"
        if not privada.exists():
            privada.write_bytes(RSA.generate(2048).export_key())
        chave = RSA.import_key(privada.read_bytes())
        if not chave.has_private() or chave.size_in_bits() < 2048:
            raise ValueError(f"Chave privada inválida em {servico}.")
        publicas[servico] = chave.public_key().export_key()
    for destinatario in (*SERVICOS, "consumidores"):
        pasta = RAIZ / destinatario / "chaves" / "publicas"
        pasta.mkdir(parents=True, exist_ok=True)
        for produtor, chave in publicas.items():
            if destinatario != "consumidores" or produtor == "promocoes":
                (pasta / f"{produtor}.pem").write_bytes(chave)
    print("Chaves prontas. Chaves privadas existentes foram preservadas.", flush=True)


if __name__ == "__main__":
    main()
