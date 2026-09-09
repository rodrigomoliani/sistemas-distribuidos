from copy import deepcopy
from threading import RLock
from uuid import uuid4

from comum.catalogo import montar_itens


class Principal:
    def __init__(self):
        self.pedidos = {}
        self.lock = RLock()

    def criar(self, cliente, selecao):
        if not cliente.strip():
            raise ValueError("Informe o cliente.")
        itens = montar_itens(selecao)
        dados = {"pedido_id": str(uuid4()), "cliente": cliente.strip(), "itens": itens,
                 "total_centavos": sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens)}
        with self.lock:
            self.pedidos[dados["pedido_id"]] = {"dados": dados, "status": "criado", "motivo": ""}
        return "pedido.criado", deepcopy(dados)

    def excluir(self, pedido_id, motivo="exclusão manual", cliente=None):
        with self.lock:
            pedido = self.pedidos.get(pedido_id)
            if pedido is None or (cliente is not None and pedido["dados"]["cliente"] != cliente):
                raise ValueError("Pedido não encontrado para este cliente.")
            if pedido["status"] == "excluido":
                return []
            pedido.update(status="excluido", motivo=motivo)
            return [("pedido.excluido", {"pedido_id": pedido_id, "motivo": motivo})]

    def tratar(self, tipo, dados):
        pedido_id = dados.get("pedido_id")
        with self.lock:
            pedido = self.pedidos.get(pedido_id)
            if pedido is None or pedido["status"] == "excluido":
                return []
            if tipo in ("estoque.indisponivel", "pagamento.recusado"):
                if pedido["status"] == "enviado":
                    return []
                saidas = self.excluir(pedido_id, tipo)
            else:
                estados = {"pedido.estoque_ok": "estoque_reservado",
                           "pagamento.aprovado": "pagamento_aprovado", "pedido.enviado": "enviado"}
                ordem = {"criado": 0, "estoque_reservado": 1, "pagamento_aprovado": 2, "enviado": 3}
                estado = estados[tipo]
                if ordem[estado] > ordem[pedido["status"]]:
                    pedido["status"] = estado
                saidas = []
            print(f"STATUS {pedido_id} {pedido['status']} {pedido['motivo']}", flush=True)
            return saidas

    def listar(self, cliente):
        with self.lock:
            return deepcopy([p for p in self.pedidos.values() if p["dados"]["cliente"] == cliente])
