import os

from comum.mensageria import executar
from pagamento.modelo import Pagamento

if __name__ == "__main__":
    try:
        modelo = Pagamento(float(os.environ.get("PROB_APROVACAO", "0.5")))
    except ValueError as erro:
        raise SystemExit(str(erro))
    executar("pagamento", modelo.tratar)
