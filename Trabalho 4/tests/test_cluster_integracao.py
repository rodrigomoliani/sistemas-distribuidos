"""Exercita quatro processos reais e gRPC em portas locais, sem Docker."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import grpc

from comum.proto import cluster_pb2, cluster_pb2_grpc

RAIZ = Path(__file__).resolve().parents[1]


class TestClusterIntegracao(unittest.TestCase):
    def test_eleicao_quorum_e_recuperacao(self):
        sockets = [socket.socket() for _ in range(4)]
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        enderecos = {i + 1: f"127.0.0.1:{sock.getsockname()[1]}" for i, sock in enumerate(sockets)}
        for sock in sockets:
            sock.close()
        processos = {}

        def iniciar(nid, pasta):
            env = os.environ.copy()
            env.update(NODE_ID=str(nid), NODE_HOST="127.0.0.1", NODE_PORT=enderecos[nid].split(":")[1],
                       DATA_DIR=str(Path(pasta) / str(nid)),
                       PEERS=",".join(f"{i}={addr}" for i, addr in enderecos.items()),
                       CLIENT_PEERS=",".join(f"{i}={addr}" for i, addr in enderecos.items()),
                       ELECTION_TIMEOUT_MIN="0.8", ELECTION_TIMEOUT_MAX="1.6", HEARTBEAT_TIMEOUT="0.6")
            processos[nid] = subprocess.Popen([sys.executable, "-m", "no"], cwd=RAIZ, env=env,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def parar(nid):
            processo = processos.pop(nid)
            processo.kill()
            processo.wait(timeout=5)

        def rpc(nid, metodo, mensagem, timeout=1):
            with grpc.insecure_channel(enderecos[nid]) as canal:
                return getattr(cluster_pb2_grpc.ClientServiceStub(canal), metodo)(mensagem, timeout=timeout)

        def esperar(acao, descricao, timeout=12):
            fim = time.monotonic() + timeout
            while time.monotonic() < fim:
                try:
                    valor = acao()
                    if valor:
                        return valor
                except grpc.RpcError:
                    pass
                time.sleep(0.1)
            self.fail(f"Timeout: {descricao}")

        def lider(termo_minimo=0):
            for nid in list(processos):
                try:
                    status = rpc(nid, "GetStatus", cluster_pb2.StatusRequest(), 0.3)
                    if status.role == "LÍDER" and status.current_term >= termo_minimo:
                        return nid, status.current_term
                except grpc.RpcError:
                    pass
            return None

        def leitura(nid, chave, valor):
            resp = rpc(nid, "Read", cluster_pb2.ReadRequest(key=chave))
            return resp.found and resp.value == valor

        with tempfile.TemporaryDirectory() as pasta:
            try:
                for nid in enderecos:
                    iniciar(nid, pasta)
                primeiro, termo = esperar(lider, "eleição inicial")
                esperar(lambda: all(rpc(n, "GetStatus", cluster_pb2.StatusRequest()).leader_id == primeiro
                                    for n in enderecos), "descoberta do líder")
                resp = rpc(primeiro, "Write", cluster_pb2.WriteRequest(key="primeira", value="ok"), 4)
                self.assertTrue(resp.success, resp.error)
                for nid in enderecos:
                    esperar(lambda nid=nid: leitura(nid, "primeira", "ok"), f"replicação no nó {nid}")
                parar(primeiro)
                segundo, _ = esperar(lambda: lider(termo + 1), "eleição após crash")
                ausente = next(n for n in processos if n != segundo)
                parar(ausente)
                time.sleep(1)
                resp = rpc(segundo, "Write", cluster_pb2.WriteRequest(key="sem_quorum", value="nao"), 4)
                self.assertFalse(resp.success)
                iniciar(primeiro, pasta)
                def escrever_com_quorum():
                    atual = lider(termo + 1)
                    if atual is None:
                        return False
                    resp = rpc(atual[0], "Write", cluster_pb2.WriteRequest(key="atrasada", value="ok"), 4)
                    return resp.success
                esperar(escrever_com_quorum, "escrita com quórum restabelecido", timeout=20)
                iniciar(ausente, pasta)
                esperar(lambda: leitura(ausente, "atrasada", "ok"), "sincronização da réplica atrasada")
            finally:
                for nid in list(processos):
                    parar(nid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
