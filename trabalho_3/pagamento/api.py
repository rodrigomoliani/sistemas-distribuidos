from typing import Literal
from uuid import UUID

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from comum.banco import emitir
from comum.web import criar_app
from comum.webhook import verificar_webhook
from pagamento.modelo import Pagamento

app = criar_app("pagamento", Pagamento)


class Resultado(BaseModel):
    """Payload esperado no webhook do provedor de pagamento."""
    model_config = ConfigDict(extra="forbid")

    pedido_id: UUID
    cobranca_id: str = Field(min_length=1)
    total_centavos: int = Field(strict=True, gt=0)
    status: Literal["APROVADO", "RECUSADO"]


@app.post("/webhook", tags=["Pagamento"])
async def webhook(
    request: Request,
    x_timestamp: str = Header(default=""),
    x_signature: str = Header(default=""),
):
    """Autentica o webhook HMAC e grava o resultado e evento AMQP atomicamente."""
    corpo = await request.body()
    if not verificar_webhook(corpo, x_timestamp, x_signature):
        raise HTTPException(401, "Assinatura do webhook inválida ou expirada")

    try:
        entrada = Resultado.model_validate_json(corpo)
    except ValidationError:
        raise HTTPException(422, "Formato de webhook inválido")

    try:
        with app.state.banco.transacao() as con:
            for tipo, dados in app.state.modelo.resultado(con, entrada):
                emitir(con, app.state.worker.assinador, tipo, dados)
    except ValueError as erro:
        raise HTTPException(409, str(erro)) from erro

    return {"recebido": True, "status": entrada.status}
