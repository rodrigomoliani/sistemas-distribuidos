import asyncio
import json
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from comum.banco import emitir, json_texto
from comum.config import ESTOQUE_URL
from comum.web import criar_app
from principal.modelo import Principal

app = criar_app("principal", Principal)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: str = Field(min_length=1, max_length=40)
    quantidade: int = Field(strict=True, ge=1, le=1000)


class NovoPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cliente: UUID
    nome: str = Field(min_length=1, max_length=80)
    itens: list[Item] = Field(min_length=1, max_length=30)


class Interesse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cliente: UUID
    email: EmailStr
    categorias: list[str] = Field(max_length=3)


def disponivel():
    """Bloqueia novos comandos quando o worker do Gateway sabe que o RabbitMQ está indisponível."""
    if not app.state.worker.pronto.is_set():
        raise HTTPException(503, "RabbitMQ indisponível. Tente novamente em alguns segundos.")


async def obter_produtos():
    """Consulta o catálogo por REST diretamente no MS Estoque."""
    try:
        async with httpx.AsyncClient(timeout=5) as cliente:
            resposta = await cliente.get(f"{ESTOQUE_URL}/produtos")
            resposta.raise_for_status()
            return resposta.json()
    except (httpx.HTTPError, ValueError) as erro:
        raise HTTPException(503, "Serviço de estoque indisponível") from erro


@app.get("/produtos", tags=["Catálogo"])
async def produtos():
    """Consulta REST diretamente ao MS Estoque; não usa catálogo local."""
    return await obter_produtos()


@app.post("/pedidos", status_code=202, tags=["Pedidos"])
async def criar_pedido(entrada: NovoPedido):
    """Registra pedido e publica pedido.criado no RabbitMQ, devolvendo HTTP 202."""
    disponivel()
    if not entrada.nome.strip():
        raise HTTPException(422, "Informe o nome")

    catalogo = {p["id"]: p for p in await obter_produtos()}
    quantidades = {}

    for i in entrada.itens:
        if i.produto_id not in catalogo:
            raise HTTPException(422, "Produto desconhecido")
        quantidades[i.produto_id] = quantidades.get(i.produto_id, 0) + i.quantidade

    itens = [
        {
            "produto_id": pid,
            "quantidade": q,
            "nome": catalogo[pid]["nome"],
            "preco_unitario_centavos": catalogo[pid]["preco_centavos"],
        }
        for pid, q in quantidades.items()
    ]

    pid = str(uuid4())
    dados = {
        "pedido_id": pid,
        "cliente": str(entrada.cliente),
        "nome": entrada.nome.strip(),
        "itens": itens,
        "total_centavos": sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens),
    }

    with app.state.banco.transacao() as con:
        con.execute(
            "INSERT INTO pedidos(id,cliente,dados,estado) VALUES (?,?,?,?)",
            (pid, dados["cliente"], json_texto(dados), "Pedido Criado"),
        )
        app.state.modelo.registrar(con, pid, "pedido.criado")
        emitir(con, app.state.worker.assinador, "pedido.criado", dados)

    return app.state.modelo.consultar(dados["cliente"], pid)[0]


@app.get("/pedidos", tags=["Pedidos"])
def pedidos(cliente: UUID):
    """Lista somente os pedidos associados ao cliente informado."""
    return app.state.modelo.consultar(str(cliente))


@app.get("/pedidos/{pedido_id}", tags=["Pedidos"])
def pedido(pedido_id: UUID, cliente: UUID):
    """Consulta um pedido específico do cliente com histórico."""
    encontrados = app.state.modelo.consultar(str(cliente), str(pedido_id))
    if not encontrados:
        raise HTTPException(404, "Pedido não encontrado")
    return encontrados[0]


@app.delete("/pedidos/{pedido_id}", tags=["Pedidos"])
def excluir(pedido_id: UUID, cliente: UUID):
    """Cancela um pedido não pago e agenda devolução de reserva via RabbitMQ."""
    disponivel()
    pid = str(pedido_id)

    with app.state.banco.transacao() as con:
        p = con.execute(
            "SELECT * FROM pedidos WHERE id=? AND cliente=?", (pid, str(cliente))
        ).fetchone()
        if not p:
            raise HTTPException(404, "Pedido não encontrado")

        if p["encerrado"]:
            return {"estado": p["estado"]}

        if p["estado"] in ("Pagamento Aprovado", "Pedido Enviado"):
            raise HTTPException(409, "Pedido já pago; cancelamento não permitido")

        con.execute("UPDATE pedidos SET estado='Pedido Cancelado', encerrado=1 WHERE id=?", (pid,))
        app.state.modelo.registrar(con, pid, "pedido.excluido")
        emitir(
            con,
            app.state.worker.assinador,
            "pedido.excluido",
            {"pedido_id": pid, "motivo": "Cliente cancelou"},
        )

    return {"estado": "Pedido Cancelado"}


@app.put("/interesses", status_code=202, tags=["Promoções"])
def interesse(entrada: Interesse):
    """Salva e-mail e categorias de interesse, e publica interesse.promocao."""
    disponivel()
    categorias = sorted(set(entrada.categorias))
    if not set(categorias).issubset(set("ABC")):
        raise HTTPException(422, "Categorias válidas: A, B e C")

    with app.state.banco.transacao() as con:
        anterior = con.execute(
            "SELECT versao FROM interesses WHERE cliente=?", (str(entrada.cliente),)
        ).fetchone()
        versao = anterior["versao"] + 1 if anterior else 1

        con.execute(
            "INSERT INTO interesses VALUES (?,?,?,?) ON CONFLICT(cliente) DO UPDATE SET "
            "email=excluded.email,categorias=excluded.categorias,versao=excluded.versao",
            (str(entrada.cliente), str(entrada.email), json_texto(categorias), versao),
        )
        emitir(
            con,
            app.state.worker.assinador,
            "interesse.promocao",
            {
                "cliente": str(entrada.cliente),
                "email": str(entrada.email),
                "categorias": categorias,
                "versao": versao,
            },
        )

    return {"mensagem": "Solicitação registrada", "categorias": categorias}


@app.get("/interesses", tags=["Promoções"])
def consultar_interesse(cliente: UUID):
    """Devolve a inscrição de promoções do cliente."""
    rows = app.state.banco.ler("SELECT * FROM interesses WHERE cliente=?", (str(cliente),))
    if rows:
        return {"email": rows[0]["email"], "categorias": json.loads(rows[0]["categorias"])}
    return {"email": "", "categorias": []}


@app.delete("/interesses", status_code=202, tags=["Promoções"])
def cancelar_interesse(cliente: UUID):
    """Cancela a inscrição de promoções do cliente."""
    rows = app.state.banco.ler("SELECT * FROM interesses WHERE cliente=?", (str(cliente),))
    if not rows:
        return {"mensagem": "Nenhuma inscrição ativa"}
    return interesse(Interesse(cliente=cliente, email=rows[0]["email"], categorias=[]))


@app.get("/eventos", tags=["Tempo real"], response_class=StreamingResponse)
async def eventos(
    request: Request,
    cliente: UUID,
    last_event_id: Annotated[str | None, Header()] = None,
):
    """Stream SSE do cliente com histórico persistido e reconexão pelo header Last-Event-ID."""
    try:
        cursor = max(0, int(last_event_id or 0))
    except ValueError:
        raise HTTPException(400, "Last-Event-ID inválido")

    async def stream():
        nonlocal cursor
        ociosos = 0
        yield "retry: 2000\n\n"

        while not await request.is_disconnected():
            rows = app.state.banco.ler(
                "SELECT * FROM historico WHERE cliente=? AND id>? ORDER BY id LIMIT 100",
                (str(cliente), cursor),
            )
            for h in rows:
                cursor = h["id"]
                dados = {**json.loads(h["dados"]), "criado_em": h["criado_em"]}
                yield f"id: {cursor}\nevent: pedido\ndata: {json_texto(dados)}\n\n"

            ociosos = 0 if rows else ociosos + 1
            if ociosos >= 20:
                yield ": heartbeat\n\n"
                ociosos = 0

            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
