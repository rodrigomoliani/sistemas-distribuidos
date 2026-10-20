import json

from comum.banco import json_texto
from comum.catalogo import CATALOGO, ESTOQUE_INICIAL, validar_pedido


class Estoque:
    """Reserva atômica e devolução de produtos usando o SQLite próprio do Estoque."""

    def __init__(self, banco):
        self.banco = banco
        banco.schema("""
            CREATE TABLE IF NOT EXISTS produtos (
                id TEXT PRIMARY KEY, nome TEXT, categoria TEXT,
                preco_centavos INTEGER, quantidade INTEGER CHECK(quantidade >= 0));
            CREATE TABLE IF NOT EXISTS reservas (
                pedido_id TEXT PRIMARY KEY, itens TEXT, estado TEXT);
        """)

        # Inicializa o catálogo de produtos se ainda não existirem
        with banco.transacao() as con:
            for pid, p in CATALOGO.items():
                con.execute(
                    "INSERT OR IGNORE INTO produtos VALUES (?,?,?,?,?)",
                    (pid, p["nome"], p["categoria"], p["preco_centavos"], ESTOQUE_INICIAL),
                )

    def produtos(self):
        """Devolve o catálogo com saldos disponíveis."""
        return [dict(p) for p in self.banco.ler("SELECT * FROM produtos ORDER BY id")]

    def tratar(self, con, tipo, dados):
        """Reserva produtos atomicamente ou devolve reserva após cancelamento."""
        pid = dados.get("pedido_id")
        if not isinstance(pid, str) or not pid:
            raise ValueError("pedido_id inválido")

        anterior = con.execute("SELECT * FROM reservas WHERE pedido_id=?", (pid,)).fetchone()

        # Devolução idempotente da reserva em cancelamento
        if tipo == "pedido.excluido":
            if anterior and anterior["estado"] == "reservado":
                for item in json.loads(anterior["itens"]):
                    con.execute(
                        "UPDATE produtos SET quantidade=quantidade+? WHERE id=?",
                        (item["quantidade"], item["produto_id"]),
                    )

            con.execute(
                "INSERT INTO reservas VALUES (?,?,?) ON CONFLICT(pedido_id) DO UPDATE SET estado='excluido'",
                (pid, "[]", "excluido"),
            )
            return []

        validar_pedido(dados)

        if anterior:
            return []

        # Verifica disponibilidade de todos os itens (all-or-nothing)
        for item in dados["itens"]:
            p = con.execute("SELECT * FROM produtos WHERE id=?", (item["produto_id"],)).fetchone()
            if not p or p["quantidade"] < item["quantidade"]:
                con.execute("INSERT INTO reservas VALUES (?,?,?)", (pid, "[]", "indisponivel"))
                return [("estoque.indisponivel", {"pedido_id": pid, "motivo": "Estoque insuficiente"})]

            if p["preco_centavos"] != item["preco_unitario_centavos"]:
                raise ValueError("Preço diverge do estoque")

        # Baixa as quantidades reservadas
        for item in dados["itens"]:
            con.execute(
                "UPDATE produtos SET quantidade=quantidade-? WHERE id=?",
                (item["quantidade"], item["produto_id"]),
            )

        con.execute(
            "INSERT INTO reservas VALUES (?,?,?)",
            (pid, json_texto(dados["itens"]), "reservado"),
        )

        return [("pedido.estoque_ok", dados)]
