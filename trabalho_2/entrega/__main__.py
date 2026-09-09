from comum.mensageria import executar
from entrega.modelo import Entrega

if __name__ == "__main__":
    executar("entrega", Entrega().tratar)
