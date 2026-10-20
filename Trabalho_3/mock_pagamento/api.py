from contextlib import asynccontextmanager
import hmac
from pathlib import Path
import time
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from comum.banco import Banco, json_texto
from comum.config import MOCK_PUBLIC_URL, WEBHOOK_SECRET, WEBHOOK_URL
from comum.webhook import assinar_webhook


@asynccontextmanager
async def lifespan(app):
    app.state.banco = Banco("mock_pagamento")
    app.state.banco.schema("""
        CREATE TABLE IF NOT EXISTS cobrancas (
            id TEXT PRIMARY KEY, pedido_id TEXT UNIQUE, total_centavos INTEGER,
            webhook_url TEXT, estado TEXT, entregue INTEGER DEFAULT 0);
    """)
    yield
    app.state.banco.fechar()


app = FastAPI(title="Mock externo de pagamento", lifespan=lifespan)


class NovaCobranca(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pedido_id: UUID
    total_centavos: int = Field(strict=True, gt=0)
    webhook_url: HttpUrl


class Decisao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["APROVADO", "RECUSADO"]


def obter(cid):
    rows = app.state.banco.ler("SELECT * FROM cobrancas WHERE id=?", (str(cid),))
    if not rows:
        raise HTTPException(404, "Cobrança não encontrada")
    return dict(rows[0])


@app.get("/saude")
def saude():
    return {"servico": "mock_pagamento"}


@app.post("/cobrancas", status_code=201)
def criar(entrada: NovaCobranca, x_api_key: str = Header(default="")):
    """Cria uma nova cobrança ou devolve a URL da cobrança existente."""
    if not hmac.compare_digest(x_api_key, WEBHOOK_SECRET):
        raise HTTPException(401, "Credencial inválida")

    if str(entrada.webhook_url) != WEBHOOK_URL:
        raise HTTPException(422, "Webhook não permitido")

    with app.state.banco.transacao() as con:
        c = con.execute("SELECT * FROM cobrancas WHERE pedido_id=?", (str(entrada.pedido_id),)).fetchone()
        if c:
            if c["total_centavos"] != entrada.total_centavos or c["webhook_url"] != str(entrada.webhook_url):
                raise HTTPException(409, "Pedido já possui outra cobrança")
            cid = c["id"]
        else:
            cid = str(uuid4())
            con.execute(
                "INSERT INTO cobrancas(id,pedido_id,total_centavos,webhook_url,estado) VALUES (?,?,?,?,?)",
                (cid, str(entrada.pedido_id), entrada.total_centavos, str(entrada.webhook_url), "PENDENTE"),
            )

    return {"id": cid, "checkout_url": f"{MOCK_PUBLIC_URL}/checkout/{cid}"}


@app.get("/cobrancas/{cobranca_id}")
def consultar(cobranca_id: UUID):
    """Consulta dados públicos da cobrança para exibição na tela de checkout."""
    c = obter(cobranca_id)
    return {k: c[k] for k in ("id", "pedido_id", "total_centavos", "estado", "entregue")}


@app.get("/checkout/{cobranca_id}", response_class=HTMLResponse)
def checkout(cobranca_id: UUID):
    """Serve a página HTML de checkout para o navegador."""
    obter(cobranca_id)
    return HTMLResponse((Path(__file__).parent / "checkout.html").read_text(encoding="utf-8"))


@app.post("/cobrancas/{cobranca_id}/decisao")
async def decidir(cobranca_id: UUID, entrada: Decisao):
    """Registra a escolha do usuário e dispara o Webhook assinado para o MS Pagamento."""
    with app.state.banco.transacao() as con:
        c = obter(cobranca_id)
        if c["estado"] not in ("PENDENTE", entrada.status):
            raise HTTPException(409, "Outra decisão já foi registrada")

        con.execute("UPDATE cobrancas SET estado=? WHERE id=?", (entrada.status, str(cobranca_id)))

        if c["entregue"]:
            return {"recebido": True, "status": entrada.status}

    corpo = json_texto({
        "cobranca_id": str(cobranca_id),
        "pedido_id": c["pedido_id"],
        "total_centavos": c["total_centavos"],
        "status": entrada.status,
    }).encode()

    timestamp = str(int(time.time()))

    try:
        async with httpx.AsyncClient(timeout=8) as cliente:
            r = await cliente.post(
                c["webhook_url"],
                content=corpo,
                headers={
                    "Content-Type": "application/json",
                    "X-Timestamp": timestamp,
                    "X-Signature": assinar_webhook(corpo, timestamp),
                },
            )
            r.raise_for_status()
    except httpx.HTTPError as erro:
        raise HTTPException(
            502,
            "Webhook não confirmado. Repita a mesma decisão para reenviar; o pedido pode ter sido cancelado.",
        ) from erro

    with app.state.banco.transacao() as con:
        con.execute("UPDATE cobrancas SET entregue=1 WHERE id=?", (str(cobranca_id),))

    return {"recebido": True, "status": entrada.status}
