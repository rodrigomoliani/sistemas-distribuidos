"""Script automatizado para demonstração dos cenários obrigatórios de avaliação (UTFPR)."""

import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import grpc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from comum.config import CLIENT_PEERS, HEARTBEAT_TIMEOUT
from comum.proto import cluster_pb2, cluster_pb2_grpc


def print_etapa(titulo: str):
    print("\n" + "=" * 78)
    print(f"  {titulo}")
    print("=" * 78)


def obter_lider_atual():
    """Identifica quem é o líder do cluster e qual o termo atual."""
    for nid, addr in CLIENT_PEERS.items():
        try:
            canal = grpc.insecure_channel(addr)
            stub = cluster_pb2_grpc.ClientServiceStub(canal)
            resp = stub.GetStatus(cluster_pb2.StatusRequest(), timeout=1.0)
            canal.close()
            if resp.role == "LÍDER":
                return resp.node_id, resp.current_term, addr
        except Exception:
            pass
    return None, None, None


def esperar_lider(termo_minimo=0, timeout=12):
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        lider = obter_lider_atual()
        if lider[0] is not None and lider[1] >= termo_minimo:
            return lider
        time.sleep(0.2)
    raise RuntimeError("Nenhum líder encontrado no prazo")


def verificar_leitura(nid, chave, valor, timeout=8):
    fim = time.monotonic() + timeout
    ultimo_erro = None
    while time.monotonic() < fim:
        try:
            with grpc.insecure_channel(CLIENT_PEERS[nid]) as canal:
                resposta = cluster_pb2_grpc.ClientServiceStub(canal).Read(
                    cluster_pb2.ReadRequest(key=chave), timeout=0.5
                )
            if resposta.found and resposta.value == valor:
                print(f"    Nó {nid}: '{chave}' = '{valor}' (commit {resposta.commit_index})")
                return
            ultimo_erro = f"valor recebido: {resposta.value!r}"
        except grpc.RpcError as err:
            ultimo_erro = str(err)
        time.sleep(0.2)
    raise AssertionError(f"Nó {nid} não sincronizou {chave}: {ultimo_erro}")


def escrever_com_quorum(chave, valor, timeout=20):
    fim = time.monotonic() + timeout
    ultimo_erro = "líder indisponível"
    while time.monotonic() < fim:
        lider, _, addr = obter_lider_atual()
        if lider is not None:
            try:
                with grpc.insecure_channel(addr) as canal:
                    resp = cluster_pb2_grpc.ClientServiceStub(canal).Write(
                        cluster_pb2.WriteRequest(key=chave, value=valor), timeout=4
                    )
                if resp.success:
                    return resp
                ultimo_erro = resp.error
            except grpc.RpcError as err:
                ultimo_erro = str(err)
        time.sleep(0.2)
    raise RuntimeError(f"Não foi possível gravar após recuperação: {ultimo_erro}")


def _testar_cenarios(parados):
    print_etapa("INICIANDO VALIDAÇÃO DOS CENÁRIOS DO TRABALHO 4 (UTFPR)")
    sufixo = uuid.uuid4().hex
    chave_inicial = f"disciplina_{sufixo}"
    chave_recuperada = f"recuperado_{sufixo}"

    # ----------------------------------------------------
    # Cenário 1: Escrita Normal e Leitura Distribuída
    # ----------------------------------------------------
    print_etapa("Cenário 1: Escrita no Líder e Leitura em Todas as Réplicas")
    lider_id, termo, addr = esperar_lider()
    print(f"[*] Líder detectado: Nó {lider_id} (Termo {termo}) em {addr}")

    canal = grpc.insecure_channel(addr)
    stub = cluster_pb2_grpc.ClientServiceStub(canal)
    req = cluster_pb2.WriteRequest(key=chave_inicial, value="sistemas_distribuidos")
    resp = stub.Write(req, timeout=4.0)
    canal.close()

    assert resp.success, f"Falha na escrita: {resp.error}"
    print(f"[+] Escrita com sucesso! Index: {resp.index}, Termo: {resp.term}")

    print("[*] Conferindo leitura em todos os nós:")
    for nid in CLIENT_PEERS:
        verificar_leitura(nid, chave_inicial, "sistemas_distribuidos")

    # ----------------------------------------------------
    # Cenário 2: Eleição Automática por Queda do Líder
    # ----------------------------------------------------
    print_etapa("Cenário 2: Eleição Automática por Queda do Líder")
    print(f"[*] Derrubando o líder atual (Nó {lider_id})...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "stop", f"no{lider_id}"], cwd=RAIZ, check=True)
    parados.add(lider_id)

    print("[*] Aguardando election timeout das réplicas (3 segundos)...")
    novo_lider, novo_termo, novo_addr = esperar_lider(termo + 1)
    print(f"[+] Novo Líder Eleito: Nó {novo_lider} (Termo {novo_termo})")
    assert novo_lider is not None, "Nenhum líder foi eleito após a queda!"
    assert novo_termo > termo, f"O termo deveria ter avançado ({novo_termo} <= {termo})"

    # ----------------------------------------------------
    # Cenário 3: Bloqueio por Perda de Quórum
    # ----------------------------------------------------
    print_etapa("Cenário 3: Bloqueio por Perda de Quórum (Sem Quórum, Sem Escrita)")
    # Derruba mais um seguidor para restar apenas 2 nós ativos (< 3 nós)
    alvo_queda = [nid for nid in CLIENT_PEERS.keys() if nid not in (lider_id, novo_lider)][0]
    print(f"[*] Derrubando seguidor (Nó {alvo_queda}) para quebrar o quórum (restarão apenas 2 nós)...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "stop", f"no{alvo_queda}"], cwd=RAIZ, check=True)
    parados.add(alvo_queda)

    time.sleep(HEARTBEAT_TIMEOUT + 0.7)
    print(f"[*] Tentando gravar no líder (Nó {novo_lider}) sem quórum...")
    c = grpc.insecure_channel(novo_addr)
    s = cluster_pb2_grpc.ClientServiceStub(c)
    resp_bloq = s.Write(cluster_pb2.WriteRequest(key="sem_quorum", value="deve_falhar"), timeout=2.0)
    c.close()

    print(f"[*] Resposta do líder: Success={resp_bloq.success}, Erro='{resp_bloq.error}'")
    assert not resp_bloq.success, "A escrita deveria ter sido rejeitada por falta de quórum!"
    print("[+] SUCESSO: O líder bloqueou a escrita por perda de quórum!")

    # ----------------------------------------------------
    # Cenário 4A: Recuperação e Sincronização via Pull
    # ----------------------------------------------------
    print_etapa("Cenário 4A: Religamento de Nós e Recuperação via FetchRequest")
    print(f"[*] Religando apenas no{lider_id}; no{alvo_queda} permanece desligado...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "start", f"no{lider_id}"], cwd=RAIZ, check=True)
    parados.remove(lider_id)

    print("[*] Aguardando nós sincronizarem via Pull (2 segundos)...")
    time.sleep(2.0)

    # A escrita ocorre enquanto a réplica atrasada continua desligada.
    resp_ok = escrever_com_quorum(chave_recuperada, "sim")
    print(f"[+] Nova escrita realizada com quórum restabelecido! Index: {resp_ok.index}")

    print(f"[*] Religando a réplica atrasada no{alvo_queda}...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "start", f"no{alvo_queda}"], cwd=RAIZ, check=True)
    parados.remove(alvo_queda)
    print("[*] Verificando que todos os 4 nós sincronizaram os dados:")
    for nid in CLIENT_PEERS:
        verificar_leitura(nid, chave_recuperada, "sim")

    print_etapa("CENÁRIOS 1, 2, 3 E 4A VALIDADOS COM SUCESSO")


def testar_cenarios():
    parados = set()
    try:
        _testar_cenarios(parados)
    finally:
        if parados:
            subprocess.run(["docker", "compose", "-f", "compose.yaml", "start",
                            *(f"no{nid}" for nid in sorted(parados))], cwd=RAIZ, check=True)


if __name__ == "__main__":
    testar_cenarios()

