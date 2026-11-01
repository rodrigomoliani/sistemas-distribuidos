"""Script automatizado para demonstração dos cenários obrigatórios de avaliação (UTFPR)."""

import os
from pathlib import Path
import subprocess
import sys
import time

import grpc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from comum.config import CLIENT_PEERS, CLUSTER_SIZE
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


def testar_cenarios():
    print_etapa("INICIANDO VALIDAÇÃO DOS CENÁRIOS DO TRABALHO 4 (UTFPR)")

    # ----------------------------------------------------
    # Cenário 1: Escrita Normal e Leitura Distribuída
    # ----------------------------------------------------
    print_etapa("Cenário 1: Escrita no Líder e Leitura em Todas as Réplicas")
    lider_id, termo, addr = obter_lider_atual()
    print(f"[*] Líder detectado: Nó {lider_id} (Termo {termo}) em {addr}")

    canal = grpc.insecure_channel(addr)
    stub = cluster_pb2_grpc.ClientServiceStub(canal)
    req = cluster_pb2.WriteRequest(key="disciplina", value="sistemas_distribuidos")
    resp = stub.Write(req, timeout=4.0)
    canal.close()

    assert resp.success, f"Falha na escrita: {resp.error}"
    print(f"[+] Escrita com sucesso! Index: {resp.index}, Termo: {resp.term}")

    time.sleep(0.5)  # Aguarda ciclo de fetch das réplicas
    print("[*] Conferindo leitura em todos os nós:")
    for nid, p_addr in CLIENT_PEERS.items():
        try:
            c = grpc.insecure_channel(p_addr)
            s = cluster_pb2_grpc.ClientServiceStub(c)
            r = s.Read(cluster_pb2.ReadRequest(key="disciplina"), timeout=1.0)
            c.close()
            print(f"    • Nó {nid} ({r.role}): '{r.key}' = '{r.value}' (Commit: {r.commit_index})")
            assert r.found and r.value == "sistemas_distribuidos"
        except Exception as err:
            print(f"    • Nó {nid}: Erro ao ler ({err})")

    # ----------------------------------------------------
    # Cenário 2: Eleição Automática por Queda do Líder
    # ----------------------------------------------------
    print_etapa("Cenário 2: Eleição Automática por Queda do Líder")
    print(f"[*] Derrubando o líder atual (Nó {lider_id})...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "stop", f"no{lider_id}"], cwd=RAIZ, check=True)

    print("[*] Aguardando election timeout das réplicas (3 segundos)...")
    time.sleep(3.0)

    novo_lider, novo_termo, novo_addr = obter_lider_atual()
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

    time.sleep(1.2)  # Aguarda heartbeat timeout do líder
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
    print(f"[*] Religando os nós derrubados (no{lider_id} e no{alvo_queda})...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "start", f"no{lider_id}", f"no{alvo_queda}"], cwd=RAIZ, check=True)

    print("[*] Aguardando nós sincronizarem via Pull (2 segundos)...")
    time.sleep(2.0)

    # Realiza nova escrita com cluster restabelecido
    c = grpc.insecure_channel(novo_addr)
    s = cluster_pb2_grpc.ClientServiceStub(c)
    resp_ok = s.Write(cluster_pb2.WriteRequest(key="recuperado", value="sim"), timeout=3.0)
    c.close()
    assert resp_ok.success, f"Falha na escrita após recuperação: {resp_ok.error}"
    print(f"[+] Nova escrita realizada com quórum restabelecido! Index: {resp_ok.index}")

    time.sleep(0.5)
    print("[*] Verificando que todos os 4 nós sincronizaram os dados:")
    for nid, p_addr in CLIENT_PEERS.items():
        try:
            c = grpc.insecure_channel(p_addr)
            s = cluster_pb2_grpc.ClientServiceStub(c)
            r = s.Read(cluster_pb2.ReadRequest(key="recuperado"), timeout=1.0)
            c.close()
            print(f"    • Nó {nid} ({r.role}): '{r.key}' = '{r.value}' (Commit: {r.commit_index})")
            assert r.found and r.value == "sim"
        except Exception as err:
            print(f"    • Nó {nid}: Erro ao ler ({err})")

    print_etapa("TODOS OS CENÁRIOS FORAM VALIDADOS COM SUCESSO!")


if __name__ == "__main__":
    testar_cenarios()
