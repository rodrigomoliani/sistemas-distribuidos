# Recepção HTTP do webhook: autentica os bytes antes de validar e registrar o resultado.

# Importa anotações de tipos e conjuntos de valores aceitos pela API.
from typing import Literal

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import UUID

# Importa servidor HTTP, parâmetros de rotas e respostas de erro.
from fastapi import Header, HTTPException, Request

# Importa validação dos corpos JSON e dos tipos recebidos pela API.
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import emitir

# Importa fábrica que prepara o ciclo de vida da API e do seu worker AMQP.
from comum.web import criar_app

# Importa assinatura e verificação do webhook externo.
from comum.webhook import verificar_webhook

# Importa modelo com as regras de negócio do microsserviço pagamento.
from pagamento.modelo import Pagamento

# Prepara aplicação FastAPI para esta etapa.
app = criar_app("pagamento", Pagamento)

# Define os campos e os dois estados aceitos no corpo do webhook.
class Resultado(BaseModel):

    # Rejeita campos extras no JSON para manter o contrato de entrada explícito.
    model_config = ConfigDict(extra="forbid")

    # Exige um UUID válido para identificar o pedido.
    pedido_id: UUID

    # Exige um identificador não vazio para a cobrança.
    cobranca_id: str = Field(min_length=1)

    # Exige valor monetário inteiro e estritamente positivo.
    total_centavos: int = Field(strict=True, gt=0)

    # Aceita somente os estados APROVADO ou RECUSADO.
    status: Literal["APROVADO", "RECUSADO"]

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.post("/webhook", tags=["Pagamento"])

# Autentica o corpo HTTP e grava o resultado e o evento AMQP na mesma transação.
async def webhook(

    # Define o argumento ou campo request desta operação.
    request: Request,

    # Define o argumento ou campo x_timestamp desta operação.
    x_timestamp: str = Header(default=""),

    # Define o argumento ou campo x_signature desta operação.
    x_signature: str = Header(default=""),

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
):

    # Prepara corpo serializado original para esta etapa.
    corpo = await request.body()

    # Confere a condição not verificar_webhook(corpo, x_timestamp, x_signature) antes de executar este bloco.
    if not verificar_webhook(corpo, x_timestamp, x_signature):

        # Interrompe a operação com erro: Assinatura do webhook inválida ou expirada.
        raise HTTPException(401, "Assinatura do webhook inválida ou expirada")

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Prepara dados validados de entrada para esta etapa.
        entrada = Resultado.model_validate_json(corpo)

    # Trata ValidationError sem confundir falha com resultado válido.
    except ValidationError:

        # Interrompe a operação com erro: Formato de webhook inválido.
        raise HTTPException(422, "Formato de webhook inválido")

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with app.state.banco.transacao() as con:

            # Percorre app.state.modelo.resultado(con, entrada) para processar cada (tipo, dados).
            for tipo, dados in app.state.modelo.resultado(con, entrada):

                # Assina o evento e o grava na outbox da transação atual, sem publicar por HTTP.
                emitir(con, app.state.worker.assinador, tipo, dados)

    # Trata ValueError sem confundir falha com resultado válido.
    except ValueError as erro:

        # Interrompe a operação com erro: a operação não pode continuar.
        raise HTTPException(409, str(erro)) from erro

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {"recebido": True, "status": entrada.status}
