from comum.mensageria import executar
from estoque.modelo import Estoque

if __name__ == "__main__":
    executar("estoque", Estoque().tratar)
