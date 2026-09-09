from copy import deepcopy

from comum.catalogo import CATALOGO, ESTOQUE_INICIAL, validar_pedido


class Estoque:
    def __init__(self):
        self.saldos = {p: ESTOQUE_INICIAL for p in CATALOGO}
        self.reservas = {}
        self.criados = set()
        self.excluidos = set()

    def tratar(self, tipo, dados):
        pedido_id = dados.get("pedido_id")
        if not isinstance(pedido_id, str) or not pedido_id:
            raise ValueError("pedido_id ausente.")
        if tipo == "pedido.excluido":
            if pedido_id not in self.excluidos:
                self.excluidos.add(pedido_id)
                reserva = self.reservas.pop(pedido_id, {})
                for produto_id, quantidade in reserva.items():
                    self.saldos[produto_id] += quantidade
                print(f"DEVOLUCAO {pedido_id} {reserva} SALDOS {self.saldos}", flush=True)
            return []
        validar_pedido(dados)
        if pedido_id in self.criados or pedido_id in self.excluidos:
            return []
        self.criados.add(pedido_id)
        reserva = {i["produto_id"]: i["quantidade"] for i in dados["itens"]}
        if any(self.saldos[p] < q for p, q in reserva.items()):
            return [("estoque.indisponivel", {"pedido_id": pedido_id, "motivo": "Estoque insuficiente"})]
        for produto_id, quantidade in reserva.items():
            self.saldos[produto_id] -= quantidade
        self.reservas[pedido_id] = reserva
        print(f"RESERVA {pedido_id} {reserva} SALDOS {self.saldos}", flush=True)
        return [("pedido.estoque_ok", deepcopy(dados))]
