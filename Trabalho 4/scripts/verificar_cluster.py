"""Verifica o status e conectividade gRPC de todos os nós do cluster."""

from pathlib import Path
import sys
import grpc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from comum.config import CLUSTER_SIZE
from comum.proto import cluster_pb2, cluster_pb2_grpc


def verificar_cluster():
    print("\n" + "=" * 78)
    print("            DIAGNÓSTICO DO CLUSTER RAFT / PULL (UTFPR)")
    print("=" * 78)
    print(f"{'Nó':<6} | {'Status':<9} | {'Papel':<10} | {'Termo':<6} | {'Commit':<7} | {'LastLog':<10} | {'Chaves':<7}")
    print("-" * 78)

    sucessos = 0
    for node_id in range(1, CLUSTER_SIZE + 1):
        porta = 50050 + node_id
        endereco = f"127.0.0.1:{porta}"

        canal = grpc.insecure_channel(endereco)
        stub = cluster_pb2_grpc.ClientServiceStub(canal)

        try:
            resp = stub.GetStatus(cluster_pb2.StatusRequest(), timeout=2.0)
            last_log_str = f"{resp.last_log_index} (T:{resp.last_log_term})"
            print(
                f"No {node_id:<3} | "
                f"\033[92m{'ONLINE':<9}\033[0m | "
                f"{resp.role:<10} | "
                f"{resp.current_term:<6} | "
                f"{resp.commit_index:<7} | "
                f"{last_log_str:<10} | "
                f"{resp.committed_keys_count:<7}"
            )
            sucessos += 1
        except grpc.RpcError as err:
            print(f"No {node_id:<3} | \033[91m{'OFFLINE':<9}\033[0m | {'-':<10} | {'-':<6} | {'-':<7} | {'-':<10} | {'-':<7} ({err.code().name if hasattr(err, 'code') else 'Erro'})")
        finally:
            canal.close()

    print("=" * 78)
    print(f"Total de nós respondendo via gRPC: {sucessos}/{CLUSTER_SIZE}")

    # Verifica os arquivos persistidos em disco no host
    print("\nArquivos de persistência em disco (Host):")
    dados_dir = RAIZ / "dados"
    for node_id in range(1, CLUSTER_SIZE + 1):
        pasta_no = dados_dir / f"no{node_id}"
        if pasta_no.exists():
            arquivos = [f.name for f in pasta_no.glob("*.json")]
            print(f"  • dados/no{node_id}/ -> {', '.join(sorted(arquivos)) if arquivos else '(vazio)'}")
        else:
            print(f"  • dados/no{node_id}/ -> (ainda não criado)")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    verificar_cluster()

