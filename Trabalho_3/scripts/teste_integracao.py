# Validação com processos reais e RabbitMQ dedicado; usa bancos temporários e não envia e-mails reais.

# Continua a expressão que prepara os dados desta operação.
"""Teste completo com sete processos e RabbitMQ dedicado, sem mocks de AMQP."""

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa localização do executável Node.js no PATH.
import shutil

# Importa verificação das portas locais antes de iniciar os serviços de teste.
import socket

# Importa acesso ao banco relacional SQLite, mantido pelo próprio serviço.
import sqlite3

# Importa criação e controle dos processos locais iniciados pelo projeto.
import subprocess

# Importa caminho do interpretador Python que está executando este script.
import sys

# Importa diretórios temporários usados para isolar os bancos dos testes.
import tempfile

# Importa threads, locks e sinais usados para coordenar acesso concorrente.
import threading

# Importa relógios, timestamps e pausas do agendamento e dos testes.
import time

# Importa caminhos de arquivo portáveis por meio de Path.
from pathlib import Path

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import uuid4

# Importa requisições HTTP aos serviços REST e às APIs externas.
import httpx

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import RAIZ

# Importa worker AMQP, topologia do RabbitMQ e criação de conexões.
from comum.mensageria import EXCHANGE, FILAS, conectar, declarar_topologia

# Importa encerramento da árvore dos subprocessos iniciados pelo projeto.
from comum.processos import encerrar

# Importa assinaturas RSA e política de produtores autorizados.
from comum.seguranca import Assinador

# Prepara API para esta etapa.
API = "http://127.0.0.1:8000"

# Prepara MOCK para esta etapa.
MOCK = "http://127.0.0.1:8003"

# Repete uma consulta até cumprir o critério, ou falha quando o prazo termina.
def aguardar(obter, criterio, limite=30):

    # Prepara os recursos indicados para serem usados juntos nesta etapa.
    fim, ultimo = time.monotonic() + limite, None

    # Repete o bloco enquanto time.monotonic() < fim permitir continuar.
    while time.monotonic() < fim:

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Prepara último resultado consultado para esta etapa.
            ultimo = obter()

            # Confere a condição criterio(ultimo) antes de executar este bloco.
            if criterio(ultimo):

                # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
                return ultimo

        # Trata (httpx.HTTPError, sqlite3.Error) sem confundir falha com resultado válido.
        except (httpx.HTTPError, sqlite3.Error):

            # Não executa outra ação: o encerramento ou a simulação já foi tratado pelo contexto.
            pass

        # Pausa o ciclo pelo intervalo indicado, evitando ocupar a CPU em espera contínua.
        time.sleep(0.2)

    # Interrompe a operação com erro: Tempo esgotado; último resultado: .
    raise AssertionError(f"Tempo esgotado; último resultado: {ultimo}")

# Consulta o Gateway por HTTP e exige uma resposta de sucesso antes de ler o JSON.
def get(caminho):

    # Prepara r para esta etapa.
    r = httpx.get(API + caminho, timeout=5)

    # Transforma respostas HTTP de erro em exceções, evitando tratar falha como sucesso.
    r.raise_for_status()

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return r.json()

# Executa os cenários reais de integração em bancos temporários e finaliza seus subprocessos.
def main():

    # Prepara conexão AMQP para esta etapa.
    conexao = conectar()

    # Prepara canal AMQP para esta etapa.
    canal = conexao.channel()

    # Cria exchange, filas duráveis e bindings exatos de cada microsserviço.
    declarar_topologia(canal)

    # Percorre FILAS para processar cada s.
    for s in FILAS:

        # Prepara fila do microsserviço para esta etapa.
        fila = canal.queue_declare(queue=f"trabalho3.{s}", passive=True).method

        # Confere a condição fila.consumer_count or fila.message_count antes de executar este bloco.
        if fila.consumer_count or fila.message_count:

            # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
            conexao.close()

            # Interrompe a operação com erro: Use broker/vhost dedicado vazio, sem consumidores. O teste não limpa filas existentes.
            raise SystemExit(

                # Fornece este valor textual à chamada ou coleção em construção.
                "Use broker/vhost dedicado vazio, sem consumidores. O teste não limpa filas existentes."

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

    # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
    conexao.close()

    # Prepara caminho do executável Node.js para esta etapa.
    node = shutil.which("node")

    # Confere a condição not node antes de executar este bloco.
    if not node:

        # Interrompe a operação com erro: Node.js não encontrado.
        raise SystemExit("Node.js não encontrado")

    # Percorre (8000, 8001, 8002, 8003, 8080) para processar cada porta.
    for porta in (8000, 8001, 8002, 8003, 8080):

        # Abre o contexto socket.socket() e garante sua finalização ao sair do bloco.
        with socket.socket() as s:

            # Confere a condição s.connect_ex(('127.0.0.1', porta)) == 0 antes de executar este bloco.
            if s.connect_ex(("127.0.0.1", porta)) == 0:

                # Interrompe a operação com erro:  ocupada; encerre os serviços.
                raise SystemExit(f"Porta {porta} ocupada; encerre os serviços.")

    # Prepara pasta de evidências da integração para esta etapa.
    resultado = RAIZ / "test-results"

    # Executa resultado.mkdir para concluir esta etapa do processamento.
    resultado.mkdir(exist_ok=True)

    # Prepara os recursos indicados para serem usados juntos nesta etapa.
    processos, logs = [], []

    # Prepara opções específicas de criação no Windows para esta etapa.
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    # Abre o contexto tempfile.TemporaryDirectory(prefix='sd3-integracao-') e garante sua finalização ao sair do bloco.
    with tempfile.TemporaryDirectory(prefix="sd3-integracao-") as temp:

        # Prepara diretório de arquivos para esta etapa.
        pasta = Path(temp)

        # Prepara ambiente dos subprocessos para esta etapa.
        ambiente = {

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            **os.environ,

            # Define o campo PYTHONUTF8 desta estrutura de dados.
            "PYTHONUTF8": "1",

            # Define o campo DATA_DIR desta estrutura de dados.
            "DATA_DIR": str(pasta),

            # Define o campo EMAIL_MODO desta estrutura de dados.
            "EMAIL_MODO": "arquivo",

            # Define o campo INTERVALO_PROMOCOES desta estrutura de dados.
            "INTERVALO_PROMOCOES": "1",

            # Define o campo ESTOQUE_URL desta estrutura de dados.
            "ESTOQUE_URL": "http://127.0.0.1:8001",

            # Define o campo MOCK_URL desta estrutura de dados.
            "MOCK_URL": MOCK,

            # Define o campo MOCK_PUBLIC_URL desta estrutura de dados.
            "MOCK_PUBLIC_URL": MOCK,

            # Define o campo WEBHOOK_URL desta estrutura de dados.
            "WEBHOOK_URL": "http://127.0.0.1:8002/webhook",

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

        # Lê o banco temporário de um serviço para verificar os efeitos do teste de integração.
        def banco(servico, sql):

            # Abre o contexto sqlite3.connect(pasta / f'{servico}.sqlite3') e garante sua finalização ao sair do bloco.
            with sqlite3.connect(pasta / f"{servico}.sqlite3") as con:

                # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
                return con.execute(sql).fetchall()

        # Cria ou reutiliza a cobrança do pedido com autenticação e URL de webhook permitida.
        def criar(q=1, produto="1", cliente=None):

            # Prepara r para esta etapa.
            r = httpx.post(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                API + "/pedidos",

                # Envia estes dados como corpo JSON da requisição HTTP.
                json={

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": cliente or cid,

                    # Define o campo nome desta estrutura de dados.
                    "nome": "Ana",

                    # Define o campo itens desta estrutura de dados.
                    "itens": [{"produto_id": produto, "quantidade": q}],

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

                # Limita a duração da operação para que uma falha de rede não bloqueie indefinidamente.
                timeout=5,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert r.status_code == 202, r.text

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return r.json()

        # Consulta o estado persistido; no Mock devolve apenas os dados públicos da cobrança.
        def consultar(p):

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return get(f"/pedidos/{p['pedido_id']}?cliente={p['cliente']}")

        # Aguarda a URL de checkout e escolhe um resultado no provedor simulado.
        def pagar(p, status):

            # Prepara checkout para esta etapa.
            checkout = aguardar(lambda: consultar(p), lambda x: x.get("checkout_url"))

            # Prepara cob para esta etapa.
            cob = checkout["checkout_url"].split("/")[-1]

            # Prepara r para esta etapa.
            r = httpx.post(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                f"{MOCK}/cobrancas/{cob}/decisao", json={"status": status}, timeout=10

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert r.status_code == 200, r.text

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return cob

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Percorre ('estoque', 'pagamento', 'entrega', 'promocoes', 'mock_pagamento', 'principal', 'frontend') para processar cada servico.
            for servico in (

                # Fornece este valor textual à chamada ou coleção em construção.
                "estoque",

                # Fornece este valor textual à chamada ou coleção em construção.
                "pagamento",

                # Fornece este valor textual à chamada ou coleção em construção.
                "entrega",

                # Fornece este valor textual à chamada ou coleção em construção.
                "promocoes",

                # Fornece este valor textual à chamada ou coleção em construção.
                "mock_pagamento",

                # Fornece este valor textual à chamada ou coleção em construção.
                "principal",

                # Fornece este valor textual à chamada ou coleção em construção.
                "frontend",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ):

                # Prepara logger ou arquivo de log para esta etapa.
                log = (resultado / f"{servico}.log").open("w", encoding="utf-8")

                # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
                logs.append(log)

                # Prepara comando de inicialização do serviço para esta etapa.
                cmd = (

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    [node, "frontend/server.mjs"]

                    # Aplica esta iteração ou condição à expressão que está sendo construída.
                    if servico == "frontend"

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    else [sys.executable, "-u", "-m", servico]

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

                # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
                processos.append(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    subprocess.Popen(

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        cmd,

                        # Define o argumento ou campo cwd desta operação.
                        cwd=RAIZ,

                        # Define o argumento ou campo env desta operação.
                        env=ambiente,

                        # Redireciona a saída padrão do serviço para seu arquivo de log.
                        stdout=log,

                        # Redireciona também as falhas do serviço para o mesmo arquivo de log.
                        stderr=log,

                        # Evita abrir uma janela visível para o subprocesso no Windows.
                        creationflags=flags,

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    )

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

            # Percorre (8000, 8001, 8002) para processar cada porta.
            for porta in (8000, 8001, 8002):

                # Executa aguardar para concluir esta etapa do processamento.
                aguardar(

                    # Define o argumento ou campo lambda desta operação.
                    lambda: httpx.get(f"http://127.0.0.1:{porta}/saude").json(),

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    lambda d: d.get("rabbitmq"),

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(lambda: httpx.get(MOCK + "/saude").status_code, lambda x: x == 200)

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: httpx.get("http://127.0.0.1:8080").status_code,

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                lambda x: x == 200,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert all(p.poll() is None for p in processos)

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert len(get("/produtos")) == 3

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert httpx.get(API + "/openapi.json").status_code == 200

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK sete processos, catálogo REST e OpenAPI", flush=True)

            # Prepara identificador utilizado na cobrança ou no cliente de teste para esta etapa.
            cid = str(uuid4())

            # Prepara os recursos indicados para serem usados juntos nesta etapa.
            notificacoes, sse_erros = [], []

            # Lê o stream SSE real e coleta as notificações até o evento de envio.
            def ler_sse():

                # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
                try:

                    # Abre o contexto httpx.stream('GET', API + '/eventos?cliente=' + cid, timeout=35) e garante sua finalização ao sair do bloco.
                    with httpx.stream(

                        # Fornece este valor textual à chamada ou coleção em construção.
                        "GET", API + "/eventos?cliente=" + cid, timeout=35

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    ) as r:

                        # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
                        assert r.headers["content-type"].startswith("text/event-stream")

                        # Percorre r.iter_lines() para processar cada linha.
                        for linha in r.iter_lines():

                            # Confere a condição linha.startswith('data: ') antes de executar este bloco.
                            if linha.startswith("data: "):

                                # Prepara dado para esta etapa.
                                dado = json.loads(linha[6:])

                                # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
                                notificacoes.append(dado)

                                # Confere a condição dado['tipo'] == 'pedido.enviado' antes de executar este bloco.
                                if dado["tipo"] == "pedido.enviado":

                                    # Encerra o ciclo porque o resultado necessário já foi alcançado.
                                    break

                # Trata Exception sem confundir falha com resultado válido.
                except Exception as erro:

                    # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
                    sse_erros.append(str(erro))

            # Prepara thread que acompanha SSE para esta etapa.
            reader = threading.Thread(target=ler_sse, daemon=True)

            # Inicia a thread ou ativa a substituição temporária preparada para o teste.
            reader.start()

            # Prepara p para esta etapa.
            p = criar(2)

            # Prepara cob para esta etapa.
            cob = pagar(p, "APROVADO")

            # Prepara pedido após concluir a entrega para esta etapa.
            final = aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: consultar(p), lambda x: x["estado"] == "Pedido Enviado"

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert final["nota_id"]

            # Aguarda a thread terminar até o prazo indicado.
            reader.join(timeout=10)

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert not reader.is_alive() and not sse_erros, sse_erros

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert {d["tipo"] for d in notificacoes} >= {

                # Fornece este valor textual à chamada ou coleção em construção.
                "pedido.estoque_ok",

                # Fornece este valor textual à chamada ou coleção em construção.
                "pagamento.aprovado",

                # Fornece este valor textual à chamada ou coleção em construção.
                "pedido.enviado",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            }

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert get("/produtos")[0]["quantidade"] == 8

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                httpx.post(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    f"{MOCK}/cobrancas/{cob}/decisao", json={"status": "APROVADO"}

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ).status_code

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                == 200

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert len(banco("entrega", "SELECT * FROM notas")) == 1

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                httpx.delete(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    f"{API}/pedidos/{p['pedido_id']}?cliente={cid}"

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ).status_code

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                == 409

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK aprovação, checkout, webhook idempotente, SSE e nota", flush=True)

            # Abre o contexto httpx.stream('GET', API + '/eventos?cliente=' + cid, headers={'Last-Event-ID': str(final['historico'][-2]['id'])}, timeout=5) e garante sua finalização ao sair do bloco.
            with httpx.stream(

                # Fornece este valor textual à chamada ou coleção em construção.
                "GET",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                API + "/eventos?cliente=" + cid,

                # Define os headers HTTP de formato, cache ou autenticação desta requisição.
                headers={"Last-Event-ID": str(final["historico"][-2]["id"])},

                # Limita a duração da operação para que uma falha de rede não bloqueie indefinidamente.
                timeout=5,

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ) as r:

                # Percorre r.iter_lines() para processar cada linha.
                for linha in r.iter_lines():

                    # Confere a condição linha.startswith('id: ') antes de executar este bloco.
                    if linha.startswith("id: "):

                        # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
                        assert int(linha[4:]) == final["historico"][-1]["id"]

                        # Encerra o ciclo porque o resultado necessário já foi alcançado.
                        break

            # Prepara consulta ou cliente diferente para esta etapa.
            outro = str(uuid4())

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert get("/pedidos?cliente=" + outro) == []

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                httpx.get(f"{API}/pedidos/{p['pedido_id']}?cliente={outro}").status_code

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                == 404

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK retomada SSE e isolamento de pedidos", flush=True)

            # Prepara pedido do cenário de recusa para esta etapa.
            recusado = criar(1, "2")

            # Executa pagar para concluir esta etapa do processamento.
            pagar(recusado, "RECUSADO")

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: consultar(recusado),

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                lambda x: x["estado"] == "Pagamento Recusado",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(lambda: get("/produtos")[1]["quantidade"], lambda x: x == 10)

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK recusa e devolução do estoque", flush=True)

            # Prepara pedido acima do estoque para esta etapa.
            faltante = criar(11, "3")

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: consultar(faltante),

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                lambda x: x["estado"] == "Estoque Indisponível",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert get("/produtos")[2]["quantidade"] == 10

            # Prepara pedido do cenário de cancelamento para esta etapa.
            cancelado = criar(1, "3")

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                httpx.delete(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    f"{API}/pedidos/{cancelado['pedido_id']}?cliente={cid}"

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ).status_code

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                == 200

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: banco(

                    # Fornece este valor textual à chamada ou coleção em construção.
                    "estoque",

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    f"SELECT estado FROM reservas WHERE pedido_id='{cancelado['pedido_id']}'",

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                ),

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                lambda x: x and x[0][0] == "excluido",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert get("/produtos")[2]["quantidade"] == 10

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK indisponibilidade e cancelamento", flush=True)

            # Prepara r para esta etapa.
            r = httpx.put(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                API + "/interesses",

                # Envia estes dados como corpo JSON da requisição HTTP.
                json={

                    # Define o campo cliente desta estrutura de dados.
                    "cliente": cid,

                    # Define o campo email desta estrutura de dados.
                    "email": "ana@example.com",

                    # Define o campo categorias desta estrutura de dados.
                    "categorias": ["A", "B", "C"],

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                },

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert r.status_code == 202

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(lambda: banco("promocoes", "SELECT * FROM envios"), bool)

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert httpx.delete(API + "/interesses?cliente=" + cid).status_code == 202

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: banco("promocoes", "SELECT categorias FROM interesses"),

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                lambda x: x and x[0][0] == "[]",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK promoções, e-mail de demonstração e cancelamento", flush=True)

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                httpx.post(

                    # Fornece este valor textual à chamada ou coleção em construção.
                    "http://127.0.0.1:8002/webhook", json={"status": "APROVADO"}

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ).status_code

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                == 401

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                httpx.post(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    API + "/pedidos",

                    # Envia estes dados como corpo JSON da requisição HTTP.
                    json={

                        # Define o campo cliente desta estrutura de dados.
                        "cliente": cid,

                        # Define o campo nome desta estrutura de dados.
                        "nome": "Ana",

                        # Define o campo itens desta estrutura de dados.
                        "itens": [{"produto_id": "1", "quantidade": -1}],

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    },

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ).status_code

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                == 422

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Prepara conexão AMQP para esta etapa.
            conexao = conectar()

            # Prepara canal AMQP para esta etapa.
            canal = conexao.channel()

            # Prepara dados da operação para esta etapa.
            dados = {

                # Define o argumento ou campo k desta operação.
                k: p[k]

                # Aplica esta iteração ou condição à expressão que está sendo construída.
                for k in ("pedido_id", "cliente", "nome", "itens", "total_centavos")

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            }

            # Atualiza dados['pedido_id'] com o valor usado por este cenário.
            dados["pedido_id"] = str(uuid4())

            # Prepara corpo serializado original para esta etapa.
            corpo = json.loads(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                Assinador.carregar("principal").assinar("pedido.criado", dados)

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Atualiza corpo['data']['itens'][0]['quantidade'] com o valor usado por este cenário.
            corpo["data"]["itens"][0]["quantidade"] = 999

            # Publica o envelope assinado com a routing key do evento; a mensagem é persistente.
            canal.basic_publish(

                # Define o argumento ou campo exchange desta operação.
                exchange=EXCHANGE, routing_key="pedido.criado", body=json.dumps(corpo)

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
            conexao.close()

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(

                # Define o argumento ou campo lambda desta operação.
                lambda: (resultado / "estoque.log").read_text(encoding="utf-8"),

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                lambda x: "DESCARTADO" in x,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Prepara pedido válido após uma mensagem adulterada para esta etapa.
            novo = criar(1)

            # Executa pagar para concluir esta etapa do processamento.
            pagar(novo, "APROVADO")

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(lambda: consultar(novo), lambda x: x["estado"] == "Pedido Enviado")

            # Verifica que o resultado atende à condição esperada; falha a integração se não atender.
            assert get("/produtos")[0]["quantidade"] == 7

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print(

                # Fornece este valor textual à chamada ou coleção em construção.
                "OK adulteração rejeitada, webhook protegido e consumidor continua",

                # Define o argumento ou campo flush desta operação.
                flush=True,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Encerra os processos informados e seus filhos no Windows, aguardando a liberação dos recursos.
            encerrar([processos[0]])

            # Substitui a referência do subprocesso pelo serviço reiniciado no teste.
            processos[0] = subprocess.Popen(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                [sys.executable, "-u", "-m", "estoque"],

                # Define o argumento ou campo cwd desta operação.
                cwd=RAIZ,

                # Define o argumento ou campo env desta operação.
                env=ambiente,

                # Redireciona a saída padrão do serviço para seu arquivo de log.
                stdout=logs[0],

                # Redireciona também as falhas do serviço para o mesmo arquivo de log.
                stderr=logs[0],

                # Evita abrir uma janela visível para o subprocesso no Windows.
                creationflags=flags,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Executa aguardar para concluir esta etapa do processamento.
            aguardar(lambda: get("/produtos"), lambda x: x[0]["quantidade"] == 7)

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("OK persistência após reinício do Estoque", flush=True)

            # Salva a evidência textual do resultado usando UTF-8.
            (resultado / "resultado.json").write_text(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                json.dumps(

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    {

                        # Define o campo resultado desta estrutura de dados.
                        "resultado": "aprovado",

                        # Define o campo cenarios desta estrutura de dados.
                        "cenarios": 8,

                        # Define o campo email desta estrutura de dados.
                        "email": "arquivo; Resend não acionado",

                        # Define o campo processos desta estrutura de dados.
                        "processos": 7,

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    },

                    # Define o argumento ou campo indent desta operação.
                    indent=2,

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                ),

                # Define o argumento ou campo encoding desta operação.
                encoding="utf-8",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print("INTEGRAÇÃO APROVADA", flush=True)

        # Libera os recursos mesmo se ocorrer uma falha ou interrupção.
        finally:

            # Encerra os processos informados e seus filhos no Windows, aguardando a liberação dos recursos.
            encerrar(processos)

            # Percorre logs para processar cada log.
            for log in logs:

                # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
                log.close()

# Executa a entrada do serviço somente quando este módulo é iniciado diretamente.
if __name__ == "__main__":

    # Executa main para concluir esta etapa do processamento.
    main()
