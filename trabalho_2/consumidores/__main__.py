import argparse

from comum.mensageria import executar


def main():
    parser = argparse.ArgumentParser(description="Consumidor de promoções")
    parser.add_argument("consumidor", choices=["c1", "c2"])
    nome = parser.parse_args().consumidor

    def tratar(tipo, dados):
        print(f"PROMOCAO {nome} {tipo} {dados}", flush=True)
        return []

    executar(nome, tratar)


if __name__ == "__main__":
    main()
