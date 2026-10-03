# API Gateway: comandos REST entram na outbox; resultados chegam por AMQP e saem por SSE.

# Importa esperas assíncronas do stream SSE sem bloquear o servidor HTTP.
import asyncio

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa anotações de tipos e conjuntos de valores aceitos pela API.
from typing import Annotated

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import UUID, uuid4

# Importa requisições HTTP aos serviços REST e às APIs externas.
import httpx

# Importa servidor HTTP, parâmetros de rotas e respostas de erro.
from fastapi import Header, HTTPException, Request

# Importa política CORS que permite ao frontend acessar o Gateway.
from fastapi.middleware.cors import CORSMiddleware

# Importa respostas HTTP de streaming ou conteúdo HTML.
from fastapi.responses import StreamingResponse

# Importa validação dos corpos JSON e dos tipos recebidos pela API.
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import emitir, json_texto

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import ESTOQUE_URL

# Importa fábrica que prepara o ciclo de vida da API e do seu worker AMQP.
from comum.web import criar_app

# Importa modelo com as regras de negócio do microsserviço principal.
from principal.modelo import Principal

# Prepara aplicação FastAPI para esta etapa.
app = criar_app("principal", Principal)

# Executa app.add_middleware para concluir esta etapa do processamento.
app.add_middleware(

    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
    CORSMiddleware,

    # Autoriza somente as origens locais do frontend a acessar o Gateway.
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],

    # Permite os métodos REST usados pela interface.
    allow_methods=["GET", "POST", "PUT", "DELETE"],

    # Permite JSON e o header de retomada do SSE nas requisições do frontend.
    allow_headers=["Content-Type", "Last-Event-ID"],

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
)

# Valida o ID do produto e exige quantidade inteira positiva.
class Item(BaseModel):

    # Rejeita campos extras no JSON para manter o contrato de entrada explícito.
    model_config = ConfigDict(extra="forbid")

    # Limita o tamanho do identificador textual do produto.
    produto_id: str = Field(min_length=1, max_length=40)

    # Aceita somente inteiro de 1 a 1000; bool e texto não são quantidades válidas.
    quantidade: int = Field(strict=True, ge=1, le=1000)

# Valida cliente, nome e lista de itens recebidos pelo Gateway.
class NovoPedido(BaseModel):

    # Rejeita campos extras no JSON para manter o contrato de entrada explícito.
    model_config = ConfigDict(extra="forbid")

    # Exige um UUID válido como identificador do cliente.
    cliente: UUID

    # Aceita nome não vazio com no máximo oitenta caracteres.
    nome: str = Field(min_length=1, max_length=80)

    # Exige uma lista com pelo menos um item e no máximo trinta entradas.
    itens: list[Item] = Field(min_length=1, max_length=30)

# Valida o e-mail e as categorias de interesse enviadas pelo frontend.
class Interesse(BaseModel):

    # Rejeita campos extras no JSON para manter o contrato de entrada explícito.
    model_config = ConfigDict(extra="forbid")

    # Exige um UUID válido como identificador do cliente.
    cliente: UUID

    # Exige um endereço de e-mail em formato válido.
    email: EmailStr

    # Recebe no máximo três categorias, depois verificadas contra A, B e C.
    categorias: list[str] = Field(max_length=3)

# Bloqueia novos comandos quando o worker do Gateway sabe que o RabbitMQ está indisponível.
def disponivel():

    # Confere se o Gateway tem conexão AMQP antes de aceitar o comando.
    if not app.state.worker.pronto.is_set():

        # Interrompe a operação com erro: RabbitMQ indisponível. Tente novamente em alguns segundos.
        raise HTTPException(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            503, "RabbitMQ indisponível. Tente novamente em alguns segundos."

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

# Consulta o catálogo por REST diretamente no Estoque, com timeout de cinco segundos.
async def obter_produtos():

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Abre o contexto httpx.AsyncClient(timeout=5) e garante sua finalização ao sair do bloco.
        async with httpx.AsyncClient(timeout=5) as cliente:

            # Prepara resposta recebida ou simulada para esta etapa.
            resposta = await cliente.get(f"{ESTOQUE_URL}/produtos")

            # Transforma respostas HTTP de erro em exceções, evitando tratar falha como sucesso.
            resposta.raise_for_status()

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return resposta.json()

    # Trata (httpx.HTTPError, ValueError) sem confundir falha com resultado válido.
    except (httpx.HTTPError, ValueError) as erro:

        # Interrompe a operação com erro: Serviço de estoque indisponível.
        raise HTTPException(503, "Serviço de estoque indisponível") from erro

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/produtos", tags=["Catálogo"])

# Devolve o catálogo do serviço de Estoque ou encaminha sua consulta REST no Gateway.
async def produtos():

    # Continua a expressão que prepara os dados desta operação.
    """Consulta REST diretamente ao MS Estoque; não usa catálogo local."""

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return await obter_produtos()

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.post("/pedidos", status_code=202, tags=["Pedidos"])

# Registra o pedido e o evento assinado de criação, devolvendo HTTP 202.
async def criar_pedido(entrada: NovoPedido):

    # Bloqueia novos comandos quando o worker do Gateway sabe que o RabbitMQ está indisponível.
    disponivel()

    # Confere a condição not entrada.nome.strip() antes de executar este bloco.
    if not entrada.nome.strip():

        # Interrompe a operação com erro: Informe o nome.
        raise HTTPException(422, "Informe o nome")

    # Prepara catálogo consultado no serviço de Estoque para esta etapa.
    catalogo = {p["id"]: p for p in await obter_produtos()}

    # Prepara quantidades agrupadas por produto para esta etapa.
    quantidades = {}

    # Percorre entrada.itens para processar cada i.
    for i in entrada.itens:

        # Confere a condição i.produto_id not in catalogo antes de executar este bloco.
        if i.produto_id not in catalogo:

            # Interrompe a operação com erro: Produto desconhecido.
            raise HTTPException(422, "Produto desconhecido")

        # Soma quantidades de linhas que se referem ao mesmo produto.
        quantidades[i.produto_id] = quantidades.get(i.produto_id, 0) + i.quantidade

    # Prepara itens do pedido para esta etapa.
    itens = [

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        {

            # Define o campo produto_id desta estrutura de dados.
            "produto_id": pid,

            # Define o campo quantidade desta estrutura de dados.
            "quantidade": q,

            # Define o campo nome desta estrutura de dados.
            "nome": catalogo[pid]["nome"],

            # Define o campo preco_unitario_centavos desta estrutura de dados.
            "preco_unitario_centavos": catalogo[pid]["preco_centavos"],

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

        # Aplica esta iteração ou condição à expressão que está sendo construída.
        for pid, q in quantidades.items()

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    ]

    # Prepara identificador usado nesta operação para esta etapa.
    pid = str(uuid4())

    # Prepara dados da operação para esta etapa.
    dados = {

        # Define o campo pedido_id desta estrutura de dados.
        "pedido_id": pid,

        # Define o campo cliente desta estrutura de dados.
        "cliente": str(entrada.cliente),

        # Define o campo nome desta estrutura de dados.
        "nome": entrada.nome.strip(),

        # Define o campo itens desta estrutura de dados.
        "itens": itens,

        # Define o campo total_centavos desta estrutura de dados.
        "total_centavos": sum(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            i["quantidade"] * i["preco_unitario_centavos"] for i in itens

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ),

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    }

    # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
    with app.state.banco.transacao() as con:

        # Insere o registro em pedidos; conflitos são tratados conforme a instrução.
        con.execute(

            # Insere o registro em pedidos; conflitos são tratados conforme a instrução.
            "INSERT INTO pedidos(id,cliente,dados,estado) VALUES (?,?,?,?)",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (pid, dados["cliente"], json_texto(dados), "Pedido Criado"),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Grava a mudança do pedido no histórico que será enviado pelo SSE.
        app.state.modelo.registrar(con, pid, "pedido.criado")

        # Assina o evento e o grava na outbox da transação atual, sem publicar por HTTP.
        emitir(con, app.state.worker.assinador, "pedido.criado", dados)

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return app.state.modelo.consultar(dados["cliente"], pid)[0]

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/pedidos", tags=["Pedidos"])

# Lista somente os pedidos associados ao identificador de cliente informado.
def pedidos(cliente: UUID):

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return app.state.modelo.consultar(str(cliente))

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/pedidos/{pedido_id}", tags=["Pedidos"])

# Consulta um pedido do cliente; nos testes, monta um pedido válido de demonstração.
def pedido(pedido_id: UUID, cliente: UUID):

    # Prepara encontrados para esta etapa.
    encontrados = app.state.modelo.consultar(str(cliente), str(pedido_id))

    # Confere a condição not encontrados antes de executar este bloco.
    if not encontrados:

        # Interrompe a operação com erro: Pedido não encontrado.
        raise HTTPException(404, "Pedido não encontrado")

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return encontrados[0]

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.delete("/pedidos/{pedido_id}", tags=["Pedidos"])

# Cancela um pedido ainda não pago e agenda a devolução da reserva por AMQP.
def excluir(pedido_id: UUID, cliente: UUID):

    # Bloqueia novos comandos quando o worker do Gateway sabe que o RabbitMQ está indisponível.
    disponivel()

    # Prepara identificador usado nesta operação para esta etapa.
    pid = str(pedido_id)

    # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
    with app.state.banco.transacao() as con:

        # Prepara p para esta etapa.
        p = con.execute(

            # Fornece este valor textual à chamada ou coleção em construção.
            "SELECT * FROM pedidos WHERE id=? AND cliente=?", (pid, str(cliente))

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ).fetchone()

        # Confere a condição not p antes de executar este bloco.
        if not p:

            # Interrompe a operação com erro: Pedido não encontrado.
            raise HTTPException(404, "Pedido não encontrado")

        # Confere a condição p['encerrado'] antes de executar este bloco.
        if p["encerrado"]:

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return {"estado": p["estado"]}

        # Confere a condição p['estado'] in ('Pagamento Aprovado', 'Pedido Enviado') antes de executar este bloco.
        if p["estado"] in ("Pagamento Aprovado", "Pedido Enviado"):

            # Interrompe a operação com erro: Pedido já pago; cancelamento não permitido.
            raise HTTPException(409, "Pedido já pago; cancelamento não permitido")

        # Atualiza os campos de pedidos apenas nos registros selecionados pelo WHERE.
        con.execute(

            # Atualiza os campos de pedidos apenas nos registros selecionados pelo WHERE.
            "UPDATE pedidos SET estado='Pedido Cancelado', encerrado=1 WHERE id=?",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (pid,),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Grava a mudança do pedido no histórico que será enviado pelo SSE.
        app.state.modelo.registrar(con, pid, "pedido.excluido")

        # Assina o evento e o grava na outbox da transação atual, sem publicar por HTTP.
        emitir(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            con,

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            app.state.worker.assinador,

            # Fornece este valor textual à chamada ou coleção em construção.
            "pedido.excluido",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            {"pedido_id": pid, "motivo": "Cliente cancelou"},

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {"estado": "Pedido Cancelado"}

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.put("/interesses", status_code=202, tags=["Promoções"])

# Salva e-mail e categorias, incrementa a versão e publica a atualização do interesse.
def interesse(entrada: Interesse):

    # Bloqueia novos comandos quando o worker do Gateway sabe que o RabbitMQ está indisponível.
    disponivel()

    # Prepara categorias selecionadas para esta etapa.
    categorias = sorted(set(entrada.categorias))

    # Confere a condição not set(categorias).issubset(set('ABC')) antes de executar este bloco.
    if not set(categorias).issubset(set("ABC")):

        # Interrompe a operação com erro: Categorias válidas: A, B e C.
        raise HTTPException(422, "Categorias válidas: A, B e C")

    # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
    with app.state.banco.transacao() as con:

        # Prepara registro existente para esta etapa.
        anterior = con.execute(

            # Fornece este valor textual à chamada ou coleção em construção.
            "SELECT versao FROM interesses WHERE cliente=?", (str(entrada.cliente),)

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ).fetchone()

        # Prepara versão crescente do cadastro para esta etapa.
        versao = anterior["versao"] + 1 if anterior else 1

        # Insere o registro em interesses; conflitos são tratados conforme a instrução.
        con.execute(

            # Insere o registro em interesses; conflitos são tratados conforme a instrução.
            "INSERT INTO interesses VALUES (?,?,?,?) ON CONFLICT(cliente) DO UPDATE SET "

            # Fornece este valor textual à chamada ou coleção em construção.
            "email=excluded.email,categorias=excluded.categorias,versao=excluded.versao",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (str(entrada.cliente), str(entrada.email), json_texto(categorias), versao),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Assina o evento e o grava na outbox da transação atual, sem publicar por HTTP.
        emitir(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            con,

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            app.state.worker.assinador,

            # Fornece este valor textual à chamada ou coleção em construção.
            "interesse.promocao",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            {

                # Define o campo cliente desta estrutura de dados.
                "cliente": str(entrada.cliente),

                # Define o campo email desta estrutura de dados.
                "email": str(entrada.email),

                # Define o campo categorias desta estrutura de dados.
                "categorias": categorias,

                # Define o campo versao desta estrutura de dados.
                "versao": versao,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            },

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {"mensagem": "Solicitação registrada", "categorias": categorias}

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/interesses", tags=["Promoções"])

# Devolve a inscrição do cliente ou um cadastro vazio quando não houver registro.
def consultar_interesse(cliente: UUID):

    # Prepara linhas encontradas no banco para esta etapa.
    rows = app.state.banco.ler(

        # Fornece este valor textual à chamada ou coleção em construção.
        "SELECT * FROM interesses WHERE cliente=?", (str(cliente),)

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return (

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        {"email": rows[0]["email"], "categorias": json.loads(rows[0]["categorias"])}

        # Aplica esta iteração ou condição à expressão que está sendo construída.
        if rows

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        else {"email": "", "categorias": []}

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.delete("/interesses", status_code=202, tags=["Promoções"])

# Reutiliza o registro de interesse com categorias vazias para cancelar a inscrição.
def cancelar_interesse(cliente: UUID):

    # Prepara linhas encontradas no banco para esta etapa.
    rows = app.state.banco.ler(

        # Fornece este valor textual à chamada ou coleção em construção.
        "SELECT * FROM interesses WHERE cliente=?", (str(cliente),)

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )

    # Confere a condição not rows antes de executar este bloco.
    if not rows:

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return {"mensagem": "Nenhuma inscrição ativa"}

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return interesse(Interesse(cliente=cliente, email=rows[0]["email"], categorias=[]))

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/eventos", tags=["Tempo real"], response_class=StreamingResponse)

# Abre o stream SSE do cliente e retoma o histórico após Last-Event-ID.
async def eventos(

    # Define o argumento ou campo request desta operação.
    request: Request,

    # Define o argumento ou campo cliente desta operação.
    cliente: UUID,

    # Recebe o header Last-Event-ID usado pelo navegador para retomar o SSE.
    last_event_id: Annotated[str | None, Header()] = None,

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
):

    # Continua a expressão que prepara os dados desta operação.
    """SSE com histórico persistido e retomada pelo header Last-Event-ID."""

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Prepara último ID de evento SSE enviado para esta etapa.
        cursor = max(0, int(last_event_id or 0))

    # Trata ValueError sem confundir falha com resultado válido.
    except ValueError:

        # Interrompe a operação com erro: Last-Event-ID inválido.
        raise HTTPException(400, "Last-Event-ID inválido")

    # Gera eventos SSE ordenados, com heartbeat e pausa assíncrona até a desconexão.
    async def stream():

        # Permite atualizar o cursor SSE definido na função externa.
        nonlocal cursor

        # Prepara ciclos SSE sem novidades para esta etapa.
        ociosos = 0

        # Entrega o próximo conteúdo ao consumidor do gerador, sem fechar o stream.
        yield "retry: 2000\n\n"

        # Mantém o SSE ativo somente enquanto o navegador estiver conectado.
        while not await request.is_disconnected():

            # Prepara linhas encontradas no banco para esta etapa.
            rows = app.state.banco.ler(

                # Consulta registros de historico; '?' recebe parâmetros separados do SQL.
                "SELECT * FROM historico WHERE cliente=? AND id>? ORDER BY id LIMIT 100",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (str(cliente), cursor),

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Percorre rows para processar cada h.
            for h in rows:

                # Prepara último ID de evento SSE enviado para esta etapa.
                cursor = h["id"]

                # Prepara dados da operação para esta etapa.
                dados = {**json.loads(h["dados"]), "criado_em": h["criado_em"]}

                # Entrega o próximo conteúdo ao consumidor do gerador, sem fechar o stream.
                yield f"id: {cursor}\nevent: pedido\ndata: {json_texto(dados)}\n\n"

            # Prepara ciclos SSE sem novidades para esta etapa.
            ociosos = 0 if rows else ociosos + 1

            # Envia heartbeat após vinte ciclos sem eventos, aproximadamente dez segundos.
            if ociosos >= 20:

                # Entrega o próximo conteúdo ao consumidor do gerador, sem fechar o stream.
                yield ": heartbeat\n\n"

                # Prepara ciclos SSE sem novidades para esta etapa.
                ociosos = 0

            # Pausa o ciclo pelo intervalo indicado, evitando ocupar a CPU em espera contínua.
            await asyncio.sleep(0.5)

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return StreamingResponse(

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        stream(),

        # Identifica a resposta como stream SSE para o EventSource do navegador.
        media_type="text/event-stream",

        # Define os headers HTTP de formato, cache ou autenticação desta requisição.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )
