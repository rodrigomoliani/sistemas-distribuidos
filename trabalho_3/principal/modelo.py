import json

from comum.banco import json_texto

ESTADOS = {
    "pedido.estoque_ok": "Estoque Confirmado",
    "estoque.indisponivel": "Estoque Indisponível",
    "pagamento.aprovado": "Pagamento Aprovado",
    "pagamento.recusado": "Pagamento Recusado",
    "pedido.enviado": "Pedido Enviado",
    "pagamento.checkout_criado": "Aguardando Pagamento",
}

# Ordem dos estados para evitar regressões monotônicas
ORDEM = {
    "Pedido Criado": 0,
    "Estoque Confirmado": 1,
    "Aguardando Pagamento": 2,
    "Pagamento Aprovado": 3,
    "Pedido Enviado": 4,
    "Estoque Indisponível": 5,
    "Pagamento Recusado": 5,
    "Pedido Cancelado": 5,
}


class Principal:
    """Mantém estado, histórico de pedidos e interesses no Gateway."""

    def __init__(self, banco):
        self.banco = banco
        banco.schema("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id TEXT PRIMARY KEY, cliente TEXT, dados TEXT, estado TEXT,
                checkout_url TEXT, nota_id TEXT, encerrado INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id TEXT, cliente TEXT,
                tipo TEXT, dados TEXT, criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                UNIQUE(pedido_id, tipo));
            CREATE TABLE IF NOT EXISTS interesses (
                cliente TEXT PRIMARY KEY, email TEXT, categorias TEXT, versao INTEGER);
        """)

    def registrar(self, con, pid, tipo, extras=None):
        """Adiciona uma mudança de pedido ao histórico que alimenta o SSE."""
        p = con.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()
        evento = {
            "pedido_id": pid,
            "estado": p["estado"],
            "tipo": tipo,
            "checkout_url": p["checkout_url"],
            "nota_id": p["nota_id"],
            **(extras or {}),
        }
        con.execute(
            "INSERT OR IGNORE INTO historico(pedido_id,cliente,tipo,dados) VALUES (?,?,?,?)",
            (pid, p["cliente"], tipo, json_texto(evento)),
        )

    def consultar(self, cliente, pid=None):
        """Consulta pedidos e seus respectivos históricos filtrados por cliente."""
        where, parametros = "cliente=?", [cliente]
        if pid:
            where += " AND id=?"
            parametros.append(pid)

        saida = []
        for p in self.banco.ler(f"SELECT * FROM pedidos WHERE {where} ORDER BY rowid DESC", parametros):
            historico = [
                {**json.loads(h["dados"]), "id": h["id"], "criado_em": h["criado_em"]}
                for h in self.banco.ler(
                    "SELECT * FROM historico WHERE pedido_id=? ORDER BY id", (p["id"],)
                )
            ]
            saida.append({
                **json.loads(p["dados"]),
                "estado": p["estado"],
                "checkout_url": p["checkout_url"],
                "nota_id": p["nota_id"],
                "historico": historico,
            })
        return saida

    def tratar(self, con, tipo, dados):
        """Aplica transições de estado dos eventos consumidos e notifica o histórico SSE."""
        pid = dados.get("pedido_id")
        if not isinstance(pid, str) or not pid:
            raise ValueError("pedido_id inválido")

        p = con.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()
        if not p or p["encerrado"]:
            return []

        estado = ESTADOS[tipo]

        if tipo == "pagamento.checkout_criado":
            url = dados.get("checkout_url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError("Checkout inválido")
            con.execute("UPDATE pedidos SET checkout_url=? WHERE id=?", (url, pid))

        if tipo == "pedido.enviado":
            con.execute("UPDATE pedidos SET nota_id=? WHERE id=?", (dados["nota_id"], pid))

        # Atualiza o estado respeitando a ordem monotônica
        if ORDEM[estado] > ORDEM[p["estado"]]:
            con.execute("UPDATE pedidos SET estado=? WHERE id=?", (estado, pid))

        self.registrar(con, pid, tipo, {"notificacao": estado, "motivo": dados.get("motivo")})

        if tipo in ("estoque.indisponivel", "pagamento.recusado"):
            con.execute("UPDATE pedidos SET encerrado=1 WHERE id=?", (pid,))
            return [("pedido.excluido", {"pedido_id": pid, "motivo": estado})]

        return []
