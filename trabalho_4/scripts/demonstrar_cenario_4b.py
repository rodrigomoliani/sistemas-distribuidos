"""Demonstração automatizada do Cenário 4B (Truncamento de Log por Divergência).

Conforme o PDF (Pág. 3):
"Enviar uma escrita para o líder (N1), fazê-lo gravar localmente, mas derrubá-lo
imediatamente (simulando crash) antes da replicação. Aguardar a eleição de um novo
líder (N2, em um novo termo), realizar uma nova escrita com sucesso e, ao religar N1,
demonstrar que ele muda para Seguidor, trunca (deleta) a entrada não comitada e
ressincroniza o log correto via FetchRequest."
"""

import json
from pathlib import Path
import subprocess
import sys
import time

import grpc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from comum.config import CLIENT_PEERS
from comum.proto import cluster_pb2, cluster_pb2_grpc


def print_banner(msg: str):
    print("\n" + "=" * 78)
    print(f"  {msg}")
    print("=" * 78)


def obter_lider():
    for nid, addr in CLIENT_PEERS.items():
        try:
            c = grpc.insecure_channel(addr)
            s = cluster_pb2_grpc.ClientServiceStub(c)
            resp = s.GetStatus(cluster_pb2.StatusRequest(), timeout=1.0)
            c.close()
            if resp.role == "LÍDER":
                return resp.node_id, resp.current_term, addr
        except Exception:
            pass
    return None, None, None


def ler_arquivo_log(node_id: int):
    caminho = RAIZ / "dados" / f"no{node_id}" / "log.json"
    if caminho.exists():
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def executar_cenario_4b():
    print_banner("CENÁRIO 4B — TRUNCAMENTO POR DIVERGÊNCIA (UTFPR)")

    # 1. Identifica o Líder N1 atual
    n1_id, n1_term, n1_addr = obter_lider()
    print(f"[*] Líder inicial detectado: Nó {n1_id} (Termo {n1_term}) em {n1_addr}")
    assert n1_id is not None, "Nenhum líder ativo encontrado!"

    outros = [nid for nid in CLIENT_PEERS.keys() if nid != n1_id]
    print(f"[*] Pausando réplicas {outros} para simular que N{n1_id} grava local sem quórum...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "pause"] + [f"no{i}" for i in outros], cwd=RAIZ, check=True)

    # 2. Envia gravação para N1 (que gravará no log mas não conseguirá quórum)
    print(f"[*] Enviando escrita 'dado_orfao=valor_perdido' para Nó {n1_id}...")
    try:
        c = grpc.insecure_channel(n1_addr)
        s = cluster_pb2_grpc.ClientServiceStub(c)
        s.Write(cluster_pb2.WriteRequest(key="dado_orfao", value="valor_perdido"), timeout=1.5)
        c.close()
    except Exception:
        pass  # Timeout esperado pois não há quórum

    # 3. Derruba N1 simulando crash
    print(f"[*] Derrubando o líder N{n1_id} (simulando crash antes da replicação)...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "stop", f"no{n1_id}"], cwd=RAIZ, check=True)

    # Inspeciona o log em disco de N1 no host
    log_n1 = ler_arquivo_log(n1_id)
    print(f"[!] Log em disco de Nó {n1_id} após a queda:")
    for e in log_n1:
        print(f"    • Index {e['index']} (Termo {e['term']}): {e['key']} = '{e['value']}'")

    # 4. Despausa as outras réplicas para elegerem N2 em um novo termo
    print("\n[*] Despausando as outras réplicas para disparar nova eleição...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "unpause"] + [f"no{i}" for i in outros], cwd=RAIZ, check=True)

    print("[*] Aguardando eleição de novo líder (3 segundos)...")
    time.sleep(3.0)

    n2_id, n2_term, n2_addr = obter_lider()
    print(f"[+] Novo Líder Eleito: Nó {n2_id} (Termo {n2_term})")
    assert n2_id is not None and n2_id != n1_id, "Novo líder não assumiu!"
    assert n2_term > n1_term, "O termo deveria ser maior que o anterior!"

    # 5. Realiza uma nova escrita válida no novo líder N2
    print(f"[*] Gravando 'dado_valido=comitado_com_sucesso' no novo líder Nó {n2_id}...")
    c = grpc.insecure_channel(n2_addr)
    s = cluster_pb2_grpc.ClientServiceStub(c)
    resp = s.Write(cluster_pb2.WriteRequest(key="dado_valido", value="comitado_com_sucesso"), timeout=3.0)
    c.close()
    assert resp.success, f"Falha na escrita no novo líder: {resp.error}"
    print(f"[+] Escrita confirmada pelo líder Nó {n2_id}! Index: {resp.index}, Termo: {resp.term}")

    # 6. Religa N1 e demonstra o truncamento automático
    print(f"\n[*] Religa o antigo líder Nó {n1_id}...")
    subprocess.run(["docker", "compose", "-f", "compose.yaml", "start", f"no{n1_id}"], cwd=RAIZ, check=True)

    print("[*] Aguardando Nó {n1_id} sincronizar via FetchRequest e truncar entrada divergente (2.5 segundos)...")
    time.sleep(2.5)

    # Inspeciona o log em disco de N1 após ressincronização
    log_n1_recup = ler_arquivo_log(n1_id)
    print(f"\n[!] Log em disco de Nó {n1_id} APÓS o truncamento e sincronização com N{n2_id}:")
    for e in log_n1_recup:
        print(f"    • Index {e['index']} (Termo {e['term']}): {e['key']} = '{e['value']}'")

    chaves_n1 = [e["key"] for e in log_n1_recup]
    assert "dado_orfao" not in chaves_n1, "ERRO: A chave divergente 'dado_orfao' não foi truncada!"
    assert "dado_valido" in chaves_n1, "ERRO: A chave oficial 'dado_valido' não foi sincronizada!"

    print("\n[+] SUCESSO: A entrada divergente 'dado_orfao' foi TRUNCADA (deletada) com êxito!")
    print("[+] O log de Nó {n1_id} agora está perfeitamente alinhado com o Líder Nó {n2_id}.")
    print_banner("CENÁRIO 4B FINALIZADO COM 100% DE SUCESSO!")


if __name__ == "__main__":
    executar_cenario_4b()

