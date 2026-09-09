import random
from copy import deepcopy

from comum.catalogo import validar_pedido


class Pagamento:
    def __init__(self, probabilidade=0.5, sortear=None):
        if not 0 <= probabilidade <= 1:
            raise ValueError("PROB_APROVACAO deve estar entre 0 e 1.")
        self.probabilidade = probabilidade
        self.sortear = sortear or random.random
        self.processados = set()

    def tratar(self, tipo, dados):
        validar_pedido(dados)
        pedido_id = dados["pedido_id"]
        if pedido_id in self.processados:
            return []
        self.processados.add(pedido_id)
        aprovado = self.sortear() < self.probabilidade
        evento = "pagamento.aprovado" if aprovado else "pagamento.recusado"
        print(f"PAGAMENTO {pedido_id} {evento}", flush=True)
        return [(evento, deepcopy(dados))]
