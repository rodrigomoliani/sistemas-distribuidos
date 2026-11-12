"""Teste de integração ponta a ponta com sete processos e RabbitMQ dedicado."""

import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

import httpx

from comum.config import RAIZ
from comum.mensageria import EXCHANGE, FILAS, conectar, declarar_topologia
from comum.processos import encerrar
from comum.seguranca import Assinador

API = "http://127.0.0.1:8000"
MOCK = "http://127.0.0.1:8003"


def aguardar(obter, criterio, limite=30):
    """Executa polling sobre uma função `obter` até que `criterio` retorne True ou ocorra timeout."""
    fim, ultimo = time.monotonic() + limite, None
    while time.monotonic() < fim:
        try:
            ultimo = obter()
            if criterio(ultimo):
                return ultimo
        except (httpx.HTTPError, sqlite3.Error):
            pass
        time.sleep(0.2)
    raise AssertionError(f"Tempo esgotado; último resultado: {ultimo}")


def get(caminho):
    """Auxiliar para requisições GET na API Principal com validação de status HTTP."""
    r = httpx.get(API + caminho, timeout=5)
    r.raise_for_status()
    return r.json()


def main():
    # 1. Validação prévia de conexões e portas locais
    conexao = conectar()
    canal = conexao.channel()
    declarar_topologia(canal)
    for s in FILAS:
        fila = canal.queue_declare(queue=f"trabalho3.{s}", passive=True).method
        if fila.consumer_count or fila.message_count:
            conexao.close()
            raise SystemExit("Use broker/vhost dedicado vazio, sem consumidores. O teste não limpa filas existentes.")
    conexao.close()

    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js não encontrado")

    for porta in (8000, 8001, 8002, 8003, 8080):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                raise SystemExit(f"Porta {porta} ocupada; encerre os serviços.")

    resultado = RAIZ / "test-results"
    resultado.mkdir(exist_ok=True)

    processos, logs = [], []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    # 2. Execução dos testes com isolamento de banco em diretório temporário
    with tempfile.TemporaryDirectory(prefix="sd3-integracao-") as temp:
        pasta = Path(temp)
        ambiente = {
            **os.environ,
            "PYTHONUTF8": "1",
            "DATA_DIR": str(pasta),
            "EMAIL_MODO": "arquivo",
            "INTERVALO_PROMOCOES": "1",
            "ESTOQUE_URL": "http://127.0.0.1:8001",
            "MOCK_URL": MOCK,
            "MOCK_PUBLIC_URL": MOCK,
            "WEBHOOK_URL": "http://127.0.0.1:8002/webhook",
        }

        def banco(servico, sql):
            with sqlite3.connect(pasta / f"{servico}.sqlite3") as con:
                return con.execute(sql).fetchall()

        def criar(q=1, produto="1", cliente=None):
            r = httpx.post(
                API + "/pedidos",
                json={
                    "cliente": cliente or cid,
                    "nome": "Ana",
                    "itens": [{"produto_id": produto, "quantidade": q}],
                },
                timeout=5,
            )
            assert r.status_code == 202, r.text
            return r.json()

        def consultar(p):
            return get(f"/pedidos/{p['pedido_id']}?cliente={p['cliente']}")

        def pagar(p, status):
            checkout = aguardar(lambda: consultar(p), lambda x: x.get("checkout_url"))
            cob = checkout["checkout_url"].split("/")[-1]
            r = httpx.post(f"{MOCK}/cobrancas/{cob}/decisao", json={"status": status}, timeout=10)
            assert r.status_code == 200, r.text
            return cob

        try:
            # Inicialização de todos os serviços
            for servico in ("estoque", "pagamento", "entrega", "promocoes", "mock_pagamento", "principal", "frontend"):
                log = (resultado / f"{servico}.log").open("w", encoding="utf-8")
                logs.append(log)
                cmd = [node, "frontend/server.mjs"] if servico == "frontend" else [sys.executable, "-u", "-m", servico]
                proc = subprocess.Popen(
                    cmd,
                    cwd=RAIZ,
                    env=ambiente,
                    stdout=log,
                    stderr=log,
                    creationflags=flags,
                )
                processos.append(proc)

            # Aguarda inicialização e healthcheck dos serviços
            for porta in (8000, 8001, 8002):
                aguardar(lambda p=porta: httpx.get(f"http://127.0.0.1:{p}/saude").json(), lambda d: d.get("rabbitmq"))
            aguardar(lambda: httpx.get(MOCK + "/saude").status_code, lambda x: x == 200)
            aguardar(lambda: httpx.get("http://127.0.0.1:8080").status_code, lambda x: x == 200)

            assert all(p.poll() is None for p in processos)
            assert len(get("/produtos")) == 3
            assert httpx.get(API + "/openapi.json").status_code == 200
            print("OK sete processos, catálogo REST e OpenAPI", flush=True)

            # Teste de fluxo completo com SSE
            cid = str(uuid4())
            notificacoes, sse_erros = [], []

            def ler_sse():
                try:
                    with httpx.stream("GET", API + "/eventos?cliente=" + cid, timeout=35) as r:
                        assert r.headers["content-type"].startswith("text/event-stream")
                        for linha in r.iter_lines():
                            if linha.startswith("data: "):
                                dado = json.loads(linha[6:])
                                notificacoes.append(dado)
                                if dado["tipo"] == "pedido.enviado":
                                    break
                except Exception as erro:
                    sse_erros.append(str(erro))

            reader = threading.Thread(target=ler_sse, daemon=True)
            reader.start()

            p = criar(2)
            cob = pagar(p, "APROVADO")
            final = aguardar(lambda: consultar(p), lambda x: x["estado"] == "Pedido Enviado")
            assert final["nota_id"]
            reader.join(timeout=10)

            assert not reader.is_alive() and not sse_erros, sse_erros
            assert {d["tipo"] for d in notificacoes} >= {"pedido.estoque_ok", "pagamento.aprovado", "pedido.enviado"}
            assert get("/produtos")[0]["quantidade"] == 8

            # Webhook idempotente e restrição de cancelamento
            assert httpx.post(f"{MOCK}/cobrancas/{cob}/decisao", json={"status": "APROVADO"}).status_code == 200
            assert len(banco("entrega", "SELECT * FROM notas")) == 1
            assert httpx.delete(f"{API}/pedidos/{p['pedido_id']}?cliente={cid}").status_code == 409
            print("OK aprovação, checkout, webhook idempotente, SSE e nota", flush=True)

            # Retomada SSE via Last-Event-ID e isolamento de clientes
            with httpx.stream(
                "GET",
                API + "/eventos?cliente=" + cid,
                headers={"Last-Event-ID": str(final["historico"][-2]["id"])},
                timeout=5,
            ) as r:
                for linha in r.iter_lines():
                    if linha.startswith("id: "):
                        assert int(linha[4:]) == final["historico"][-1]["id"]
                        break

            outro = str(uuid4())
            assert get("/pedidos?cliente=" + outro) == []
            assert httpx.get(f"{API}/pedidos/{p['pedido_id']}?cliente={outro}").status_code == 404
            print("OK retomada SSE e isolamento de pedidos", flush=True)

            # Pagamento recusado e estorno de estoque
            recusado = criar(1, "2")
            pagar(recusado, "RECUSADO")
            aguardar(lambda: consultar(recusado), lambda x: x["estado"] == "Pagamento Recusado")
            aguardar(lambda: get("/produtos")[1]["quantidade"], lambda x: x == 10)
            print("OK recusa e devolução do estoque", flush=True)

            # Estoque insuficiente e cancelamento voluntário
            faltante = criar(11, "3")
            aguardar(lambda: consultar(faltante), lambda x: x["estado"] == "Estoque Indisponível")
            assert get("/produtos")[2]["quantidade"] == 10

            cancelado = criar(1, "3")
            assert httpx.delete(f"{API}/pedidos/{cancelado['pedido_id']}?cliente={cid}").status_code == 200
            aguardar(
                lambda: banco("estoque", f"SELECT estado FROM reservas WHERE pedido_id='{cancelado['pedido_id']}'"),
                lambda x: x and x[0][0] == "excluido",
            )
            assert get("/produtos")[2]["quantidade"] == 10
            print("OK indisponibilidade e cancelamento", flush=True)

            # Interesses promocionais
            r = httpx.put(
                API + "/interesses",
                json={"cliente": cid, "email": "ana@example.com", "categorias": ["A", "B", "C"]},
            )
            assert r.status_code == 202
            aguardar(lambda: banco("promocoes", "SELECT * FROM envios"), bool)
            assert httpx.delete(API + "/interesses?cliente=" + cid).status_code == 202
            aguardar(lambda: banco("promocoes", "SELECT categorias FROM interesses"), lambda x: x and x[0][0] == "[]")
            print("OK promoções, e-mail de demonstração e cancelamento", flush=True)

            # Webhook sem token / validação de entrada
            assert httpx.post("http://127.0.0.1:8002/webhook", json={"status": "APROVADO"}).status_code == 401
            assert httpx.post(
                API + "/pedidos",
                json={"cliente": cid, "nome": "Ana", "itens": [{"produto_id": "1", "quantidade": -1}]},
            ).status_code == 422

            # Adulteração de mensagem AMQP (assinatura RSA inválida)
            conexao = conectar()
            canal = conexao.channel()
            dados = {k: p[k] for k in ("pedido_id", "cliente", "nome", "itens", "total_centavos")}
            dados["pedido_id"] = str(uuid4())
            corpo = json.loads(Assinador.carregar("principal").assinar("pedido.criado", dados))
            corpo["data"]["itens"][0]["quantidade"] = 999  # Adulteração sem recalcular assinatura

            canal.basic_publish(exchange=EXCHANGE, routing_key="pedido.criado", body=json.dumps(corpo))
            conexao.close()

            aguardar(lambda: (resultado / "estoque.log").read_text(encoding="utf-8"), lambda x: "DESCARTADO" in x)

            # Continuidade do consumidor após descarte
            novo = criar(1)
            pagar(novo, "APROVADO")
            aguardar(lambda: consultar(novo), lambda x: x["estado"] == "Pedido Enviado")
            assert get("/produtos")[0]["quantidade"] == 7
            print("OK adulteração rejeitada, webhook protegido e consumidor continua", flush=True)

            # Reinício e persistência de dados do Estoque
            encerrar([processos[0]])
            processos[0] = subprocess.Popen(
                [sys.executable, "-u", "-m", "estoque"],
                cwd=RAIZ,
                env=ambiente,
                stdout=logs[0],
                stderr=logs[0],
                creationflags=flags,
            )
            aguardar(lambda: get("/produtos"), lambda x: x[0]["quantidade"] == 7)
            print("OK persistência após reinício do Estoque", flush=True)

            (resultado / "resultado.json").write_text(
                json.dumps(
                    {
                        "resultado": "aprovado",
                        "cenarios": 8,
                        "email": "arquivo; Resend não acionado",
                        "processos": 7,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print("INTEGRAÇÃO APROVADA", flush=True)

        finally:
            encerrar(processos)
            for log in logs:
                log.close()


if __name__ == "__main__":
    main()
