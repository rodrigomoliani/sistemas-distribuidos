import signal
import sys
from no.servidor import ServidorNo


def main():
    servidor = ServidorNo()

    def signal_handler(sig, frame):
        servidor.parar()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    servidor.iniciar()
    servidor.esperar()


if __name__ == "__main__":
    main()

