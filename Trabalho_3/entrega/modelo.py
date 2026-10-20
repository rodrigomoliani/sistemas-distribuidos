from uuid import uuid4

from comum.banco import json_texto
from comum.catalogo import validar_pedido


class Entrega:
    """Emissão de nota fiscal simulada e despacho de pedidos aprovados."""

    def __init__(self, banco):
        self.banco = banco
        banco.schema("""
            CREATE TABLE IF NOT EXISTS notas (
                pedido_id TEXT PRIMARY KEY, numero TEXT, dados TEXT);
        """)

    def tratar(self, con, tipo, dados):
        """Registra uma única nota por pedido aprovado e produz o evento de envio."""
        validar_pedido(dados)
        pid = dados["pedido_id"]

        # Evita emissão duplicada de nota para o mesmo pedido
        if con.execute("SELECT 1 FROM notas WHERE pedido_id=?", (pid,)).fetchone():
            return []

        numero = str(uuid4())
        con.execute("INSERT INTO notas VALUES (?,?,?)", (pid, numero, json_texto(dados)))

        print(f"NOTA_SIMULADA {numero} PEDIDO_ENVIADO {pid}", flush=True)
        return [("pedido.enviado", {"pedido_id": pid, "nota_id": numero})]
