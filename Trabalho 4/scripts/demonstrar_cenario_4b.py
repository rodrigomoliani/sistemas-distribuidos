"""Demonstra divergência real: escrita local sem commit, crash e correção por pull."""
import json
from pathlib import Path
import subprocess
import time
import uuid

import grpc

from comum.config import CLIENT_PEERS
from comum.proto import cluster_pb2, cluster_pb2_grpc
from scripts.testar_cenarios import esperar_lider, verificar_leitura

RAIZ = Path(__file__).resolve().parents[1]


def compose(*args):
    subprocess.run(["docker", "compose", "-f", "compose.yaml", *args], cwd=RAIZ, check=True)


def log_no(node_id):
    return json.loads((RAIZ / "dados" / f"no{node_id}" / "log.json").read_text(encoding="utf-8"))


def executar_cenario_4b():
    lider, termo, addr = esperar_lider()
    outros = [nid for nid in CLIENT_PEERS if nid != lider]
    chave_orfa = f"orfao_{uuid.uuid4().hex}"
    chave_valida = f"valido_{uuid.uuid4().hex}"
    pausados = False
    lider_parado = False
    canal = None
    try:
        with grpc.insecure_channel(addr) as c:
            status = cluster_pb2_grpc.ClientServiceStub(c).GetStatus(cluster_pb2.StatusRequest(), timeout=1)
        compose("pause", *(f"no{i}" for i in outros))
        pausados = True
        canal = grpc.insecure_channel(addr)
        stub = cluster_pb2_grpc.ClientServiceStub(canal)
        # A chamada assíncrona permite derrubar o líder assim que a gravação local aparecer.
        escrita = stub.Write.future(cluster_pb2.WriteRequest(key=chave_orfa, value="orfao"), timeout=4)
        fim = time.monotonic() + 3
        entrada = None
        while time.monotonic() < fim:
            entrada = next((e for e in log_no(lider) if e["key"] == chave_orfa), None)
            if entrada:
                break
            if escrita.done():
                raise RuntimeError(f"Escrita não chegou ao log: {escrita.result().error}")
            time.sleep(0.01)
        if entrada is None:
            raise RuntimeError("Escrita órfã não apareceu no log; cenário não demonstrado")
        status_apos = stub.GetStatus(cluster_pb2.StatusRequest(), timeout=1)
        if not (entrada["index"] > status_apos.commit_index >= status.commit_index):
            raise AssertionError("A entrada órfã já foi comitada")
        print(f"Entrada órfã no líder {lider}: índice {entrada['index']}, commit {status_apos.commit_index}")
        compose("kill", f"no{lider}")
        lider_parado = True
        compose("unpause", *(f"no{i}" for i in outros))
        pausados = False
        novo, novo_termo, novo_addr = esperar_lider(termo + 1)
        assert novo != lider
        with grpc.insecure_channel(novo_addr) as c:
            resp = cluster_pb2_grpc.ClientServiceStub(c).Write(
                cluster_pb2.WriteRequest(key=chave_valida, value="comitado"), timeout=4
            )
        assert resp.success, resp.error
        assert resp.index == entrada["index"], "A escrita nova não substituiu a posição órfã"
        compose("start", f"no{lider}")
        lider_parado = False
        verificar_leitura(lider, chave_valida, "comitado")
        with grpc.insecure_channel(addr) as c:
            stub = cluster_pb2_grpc.ClientServiceStub(c)
            estado = stub.GetStatus(cluster_pb2.StatusRequest(), timeout=1)
            leitura = stub.Read(cluster_pb2.ReadRequest(key=chave_orfa), timeout=1)
        log = log_no(lider)
        assert estado.role == "SEGUIDOR" and estado.current_term >= novo_termo
        assert not leitura.found and all(e["key"] != chave_orfa for e in log)
        assert any(e["key"] == chave_valida and e["index"] == entrada["index"] for e in log)
        print(f"Cenário 4B validado: nó {lider} tornou-se seguidor e substituiu a entrada órfã.")
    finally:
        if canal is not None:
            canal.close()
        if pausados:
            compose("unpause", *(f"no{i}" for i in outros))
        if lider_parado:
            compose("start", f"no{lider}")


if __name__ == "__main__":
    executar_cenario_4b()
