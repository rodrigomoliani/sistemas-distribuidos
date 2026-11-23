import json
import httpx

from comum.banco import json_texto
from comum.catalogo import validar_pedido
from comum.config import MOCK_URL, WEBHOOK_SECRET, WEBHOOK_URL


class Pagamento:
    """Mantém cobranças e decisões de pagamento no banco do serviço."""

    def __init__(self, banco):
        self.banco = banco
        banco.schema("""
            CREATE TABLE IF NOT EXISTS cobrancas (
                pedido_id TEXT PRIMARY KEY, id TEXT UNIQUE, dados TEXT, checkout_url TEXT, estado TEXT);
            CREATE TABLE IF NOT EXISTS cancelados (pedido_id TEXT PRIMARY KEY);
        """)

    def tratar(self, con, tipo, dados):
        """Cancela cobranças pendentes ou solicita a URL de checkout após a reserva."""
        pid = dados.get("pedido_id")
        if not isinstance(pid, str) or not pid:
            raise ValueError("pedido_id inválido")

        # Trata cancelamento antes ou durante a cobrança
        if tipo == "pedido.excluido":
            con.execute("INSERT OR IGNORE INTO cancelados VALUES (?)", (pid,))
            con.execute(
                "UPDATE cobrancas SET estado='CANCELADO' WHERE pedido_id=? AND estado='PENDENTE'",
                (pid,),
            )
            return []

        validar_pedido(dados)

        if con.execute("SELECT 1 FROM cancelados WHERE pedido_id=?", (pid,)).fetchone():
            return []

        if con.execute("SELECT 1 FROM cobrancas WHERE pedido_id=?", (pid,)).fetchone():
            return []

        # Solicita criação de cobrança no Mock de Pagamento
        r = httpx.post(
            f"{MOCK_URL}/cobrancas",
            timeout=5,
            headers={"X-API-Key": WEBHOOK_SECRET},
            json={
                "pedido_id": pid,
                "total_centavos": dados["total_centavos"],
                "webhook_url": WEBHOOK_URL,
            },
        )
        r.raise_for_status()
        cobranca = r.json()

        con.execute(
            "INSERT INTO cobrancas VALUES (?,?,?,?,?)",
            (pid, cobranca["id"], json_texto(dados), cobranca["checkout_url"], "PENDENTE"),
        )

        return [
            (
                "pagamento.checkout_criado",
                {"pedido_id": pid, "checkout_url": cobranca["checkout_url"]},
            )
        ]

    def resultado(self, con, entrada):
        """Aplica uma decisão de pagamento (APROVADO/RECUSADO) recebida via webhook."""
        c = con.execute(
            "SELECT * FROM cobrancas WHERE id=? AND pedido_id=?",
            (entrada.cobranca_id, str(entrada.pedido_id)),
        ).fetchone()

        if not c:
            raise ValueError("Cobrança desconhecida")

        dados = json.loads(c["dados"])
        if entrada.total_centavos != dados["total_centavos"]:
            raise ValueError("Valor incorreto")

        # Repetições com o mesmo status são idempotentes
        if c["estado"] == entrada.status:
            return []

        if c["estado"] != "PENDENTE":
            raise ValueError("Cobrança encerrada com outro estado")

        con.execute("UPDATE cobrancas SET estado=? WHERE id=?", (entrada.status, entrada.cobranca_id))

        tipo = "pagamento.aprovado" if entrada.status == "APROVADO" else "pagamento.recusado"
        return [(tipo, dados)]
