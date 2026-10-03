# Provedor externo simulado: gera checkout e confirma a escolha no webhook do Pagamento.

# Importa assinatura com segredo compartilhado e comparação resistente a diferenças de tempo.
import hmac

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa relógios, timestamps e pausas do agendamento e dos testes.
import time

# Importa gerenciadores de contexto, responsáveis por iniciar e finalizar recursos.
from contextlib import asynccontextmanager

# Importa caminhos de arquivo portáveis por meio de Path.
from pathlib import Path

# Importa anotações de tipos e conjuntos de valores aceitos pela API.
from typing import Literal

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import UUID, uuid4

# Importa requisições HTTP aos serviços REST e às APIs externas.
import httpx

# Importa servidor HTTP, parâmetros de rotas e respostas de erro.
from fastapi import FastAPI, Header, HTTPException

# Importa respostas HTTP de streaming ou conteúdo HTML.
from fastapi.responses import HTMLResponse

# Importa validação dos corpos JSON e dos tipos recebidos pela API.
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import Banco, json_texto

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import MOCK_PUBLIC_URL, WEBHOOK_SECRET, WEBHOOK_URL

# Importa assinatura e verificação do webhook externo.
from comum.webhook import assinar_webhook

# Transforma a função em gerenciador de contexto para cuidar de início e finalização.
@asynccontextmanager

# Prepara os recursos na inicialização e os encerra após o servidor terminar.
async def lifespan(app):

    # Guarda o recurso no estado da aplicação para disponibilizá-lo às rotas HTTP.
    app.state.banco = Banco("mock_pagamento")

    # Executa app.state.banco.schema para concluir esta etapa do processamento.
    app.state.banco.schema((

        # Preserva o espaço e as quebras de linha originais do texto SQL.
        '\n'

        # Cria a tabela cobrancas somente se ela ainda não existir.
        '        CREATE TABLE IF NOT EXISTS cobrancas (\n'

        # Define as colunas e restrições SQL: id TEXT PRIMARY KEY, pedido_id TEXT UNIQUE, total_centavos INTEGER,.
        '            id TEXT PRIMARY KEY, pedido_id TEXT UNIQUE, total_centavos INTEGER,\n'

        # Define as colunas e restrições SQL: webhook_url TEXT, estado TEXT, entregue INTEGER DEFAULT 0).
        '            webhook_url TEXT, estado TEXT, entregue INTEGER DEFAULT 0);\n'

        # Fornece este valor textual à chamada ou coleção em construção.
        '    '

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    ))

    # Entrega o próximo conteúdo ao consumidor do gerador, sem fechar o stream.
    yield

    # Libera o recurso do serviço depois do processamento.
    app.state.banco.fechar()

# Prepara aplicação FastAPI para esta etapa.
app = FastAPI(title="Mock externo de pagamento", lifespan=lifespan)

# Valida pedido, valor em centavos e URL de callback enviados ao Mock.
class NovaCobranca(BaseModel):

    # Rejeita campos extras no JSON para manter o contrato de entrada explícito.
    model_config = ConfigDict(extra="forbid")

    # Exige um UUID válido para identificar o pedido.
    pedido_id: UUID

    # Exige valor monetário inteiro e estritamente positivo.
    total_centavos: int = Field(strict=True, gt=0)

    # Exige uma URL HTTP válida para retorno ao Pagamento.
    webhook_url: HttpUrl

# Restringe a escolha do checkout a APROVADO ou RECUSADO.
class Decisao(BaseModel):

    # Rejeita campos extras no JSON para manter o contrato de entrada explícito.
    model_config = ConfigDict(extra="forbid")

    # Aceita somente os estados APROVADO ou RECUSADO.
    status: Literal["APROVADO", "RECUSADO"]

# Busca a cobrança no banco do Mock e responde 404 se o ID não existir.
def obter(cid):

    # Prepara linhas encontradas no banco para esta etapa.
    rows = app.state.banco.ler("SELECT * FROM cobrancas WHERE id=?", (str(cid),))

    # Confere a condição not rows antes de executar este bloco.
    if not rows:

        # Interrompe a operação com erro: Cobrança não encontrada.
        raise HTTPException(404, "Cobrança não encontrada")

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return dict(rows[0])

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/saude")

# Informa que o serviço está ativo e, quando aplicável, se está conectado ao RabbitMQ.
def saude():

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {"servico": "mock_pagamento"}

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.post("/cobrancas", status_code=201)

# Cria ou reutiliza a cobrança do pedido com autenticação e URL de webhook permitida.
def criar(entrada: NovaCobranca, x_api_key: str = Header(default="")):

    # Confere a condição not hmac.compare_digest(x_api_key, WEBHOOK_SECRET) antes de executar este bloco.
    if not hmac.compare_digest(x_api_key, WEBHOOK_SECRET):

        # Interrompe a operação com erro: Credencial inválida.
        raise HTTPException(401, "Credencial inválida")

    # Neste mock, somente o webhook configurado é aceito.

    # Confere a condição str(entrada.webhook_url) != WEBHOOK_URL antes de executar este bloco.
    if str(entrada.webhook_url) != WEBHOOK_URL:

        # Interrompe a operação com erro: Webhook não permitido.
        raise HTTPException(422, "Webhook não permitido")

    # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
    with app.state.banco.transacao() as con:

        # Prepara c para esta etapa.
        c = con.execute(

            # Fornece este valor textual à chamada ou coleção em construção.
            "SELECT * FROM cobrancas WHERE pedido_id=?", (str(entrada.pedido_id),)

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ).fetchone()

        # Confere a condição c antes de executar este bloco.
        if c:

            # Confere a condição c['total_centavos'] != entrada.total_centavos or c['webhook_url'] != str(entrada.webhook_url) antes de executar este bloco.
            if c["total_centavos"] != entrada.total_centavos or c["webhook_url"] != str(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                entrada.webhook_url

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ):

                # Interrompe a operação com erro: Pedido já possui outra cobrança.
                raise HTTPException(409, "Pedido já possui outra cobrança")

            # Prepara identificador utilizado na cobrança ou no cliente de teste para esta etapa.
            cid = c["id"]

        # Executa a alternativa quando a condição anterior não foi satisfeita.
        else:

            # Prepara identificador utilizado na cobrança ou no cliente de teste para esta etapa.
            cid = str(uuid4())

            # Insere o registro em cobrancas; conflitos são tratados conforme a instrução.
            con.execute(

                # Insere o registro em cobrancas; conflitos são tratados conforme a instrução.
                "INSERT INTO cobrancas(id,pedido_id,total_centavos,webhook_url,estado) VALUES (?,?,?,?,?)",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    cid,

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    str(entrada.pedido_id),

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    entrada.total_centavos,

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    str(entrada.webhook_url),

                    # Fornece este valor textual à chamada ou coleção em construção.
                    "PENDENTE",

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                ),

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {"id": cid, "checkout_url": f"{MOCK_PUBLIC_URL}/checkout/{cid}"}

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/cobrancas/{cobranca_id}")

# Consulta o estado persistido; no Mock devolve apenas os dados públicos da cobrança.
def consultar(cobranca_id: UUID):

    # Prepara c para esta etapa.
    c = obter(cobranca_id)

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {

        # Define o argumento ou campo k desta operação.
        k: c[k] for k in ("id", "pedido_id", "total_centavos", "estado", "entregue")

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    }

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/checkout/{cobranca_id}", response_class=HTMLResponse)

# Entrega a página HTML de pagamento depois de conferir a existência da cobrança.
def checkout(cobranca_id: UUID):

    # Executa obter para concluir esta etapa do processamento.
    obter(cobranca_id)

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return HTMLResponse(

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        (Path(__file__).parent / "checkout.html").read_text(encoding="utf-8")

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.post("/cobrancas/{cobranca_id}/decisao")

# Persiste a escolha no Mock e envia seu resultado ao Pagamento por webhook assinado.
async def decidir(cobranca_id: UUID, entrada: Decisao):

    # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
    with app.state.banco.transacao() as con:

        # Prepara c para esta etapa.
        c = obter(cobranca_id)

        # Confere a condição c['estado'] not in ('PENDENTE', entrada.status) antes de executar este bloco.
        if c["estado"] not in ("PENDENTE", entrada.status):

            # Interrompe a operação com erro: Outra decisão já foi registrada.
            raise HTTPException(409, "Outra decisão já foi registrada")

        # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
        con.execute(

            # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
            "UPDATE cobrancas SET estado=? WHERE id=?",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (entrada.status, str(cobranca_id)),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Reconhece webhook já confirmado e evita reenviar o mesmo resultado.
        if c["entregue"]:

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return {"recebido": True, "status": entrada.status}

    # Prepara corpo serializado original para esta etapa.
    corpo = json_texto(

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        {

            # Define o campo cobranca_id desta estrutura de dados.
            "cobranca_id": str(cobranca_id),

            # Define o campo pedido_id desta estrutura de dados.
            "pedido_id": c["pedido_id"],

            # Define o campo total_centavos desta estrutura de dados.
            "total_centavos": c["total_centavos"],

            # Define o campo status desta estrutura de dados.
            "status": entrada.status,

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
    ).encode()

    # Prepara instante em segundos desde a época Unix para esta etapa.
    timestamp = str(int(time.time()))

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Abre o contexto httpx.AsyncClient(timeout=8) e garante sua finalização ao sair do bloco.
        async with httpx.AsyncClient(timeout=8) as cliente:

            # Prepara r para esta etapa.
            r = await cliente.post(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                c["webhook_url"],

                # Envia os bytes originais já assinados, sem reserializar o webhook.
                content=corpo,

                # Define os headers HTTP de formato, cache ou autenticação desta requisição.
                headers={

                    # Define o campo Content-Type desta estrutura de dados.
                    "Content-Type": "application/json",

                    # Define o campo X-Timestamp desta estrutura de dados.
                    "X-Timestamp": timestamp,

                    # Define o campo X-Signature desta estrutura de dados.
                    "X-Signature": assinar_webhook(corpo, timestamp),

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Transforma respostas HTTP de erro em exceções, evitando tratar falha como sucesso.
            r.raise_for_status()

    # Trata httpx.HTTPError sem confundir falha com resultado válido.
    except httpx.HTTPError as erro:

        # Interrompe a operação com erro: Webhook não confirmado. Repita a mesma decisão para reenviar; o pedido pode ter sido cancelado.
        raise HTTPException(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            502,

            # Fornece este valor textual à chamada ou coleção em construção.
            "Webhook não confirmado. Repita a mesma decisão para reenviar; o pedido pode ter sido cancelado.",

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ) from erro

    # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
    with app.state.banco.transacao() as con:

        # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
        con.execute("UPDATE cobrancas SET entregue=1 WHERE id=?", (str(cobranca_id),))

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {"recebido": True, "status": entrada.status}
