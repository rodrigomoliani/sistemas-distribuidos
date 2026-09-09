from copy import deepcopy
from uuid import uuid4

from comum.catalogo import validar_pedido


class Entrega:
    def __init__(self):
        self.notas = {}

    def tratar(self, tipo, dados):
        validar_pedido(dados)
        pedido_id = dados["pedido_id"]
        if pedido_id in self.notas:
            return []
        nota = {"numero": str(uuid4()), "pedido_id": pedido_id,
                "cliente": dados["cliente"], "total_centavos": dados["total_centavos"],
                "itens": deepcopy(dados["itens"])}
        self.notas[pedido_id] = nota
        print(f"NOTA_SIMULADA {nota} ENVIO_PREPARADO {pedido_id}", flush=True)
        return [("pedido.enviado", {"pedido_id": pedido_id, "nota_id": nota["numero"]})]
