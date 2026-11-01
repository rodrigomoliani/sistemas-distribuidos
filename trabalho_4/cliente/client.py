"""Cliente do cluster de replicação gRPC (Modelo Pull e Eleição Raft).

Atende aos dois requisitos avaliados da professora (0,30 pts):
1. Gravação com Redirecionamento (0,15): Envia escrita ao líder; se contatar seguidor,
   recebe a indicação do líder e redireciona automaticamente.
2. Consulta nos nós do cluster (0,15): Realiza leituras de dados em qualquer um dos nós.
"""

import argparse
from pathlib import Path
import sys
import time
from typing import Optional

import grpc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from comum.config import CLIENT_PEERS, CLUSTER_SIZE
from comum.proto import cluster_pb2, cluster_pb2_grpc


class ClienteCluster:
    """Cliente para interação com o cluster Raft/Pull."""

    def __init__(self, peers=CLIENT_PEERS):
        self.peers = peers

    def status(self) -> None:
        """Exibe o estado consolidado dos 4 nós do cluster."""
        print("\n" + "=" * 78)
        print("                        ESTADO DO CLUSTER")
        print("=" * 78)
        print(f"{'Nó':<6} | {'Status':<9} | {'Papel':<10} | {'Termo':<6} | {'Commit':<7} | {'LastLog':<10} | {'Líder':<6}")
        print("-" * 78)

        for nid in sorted(self.peers.keys()):
            addr = self.peers[nid]
            try:
                canal = grpc.insecure_channel(addr)
                stub = cluster_pb2_grpc.ClientServiceStub(canal)
                resp = stub.GetStatus(cluster_pb2.StatusRequest(), timeout=1.5)
                canal.close()
                last_log = f"{resp.last_log_index} (T:{resp.last_log_term})"
                lider_str = f"Nó {resp.leader_id}" if resp.leader_id > 0 else "Nenhum"
                print(
                    f"No {resp.node_id:<3} | "
                    f"\033[92m{'ONLINE':<9}\033[0m | "
                    f"{resp.role:<10} | "
                    f"{resp.current_term:<6} | "
                    f"{resp.commit_index:<7} | "
                    f"{last_log:<10} | "
                    f"{lider_str:<6}"
                )
            except Exception:
                print(f"No {nid:<3} | \033[91m{'OFFLINE':<9}\033[0m | {'-':<10} | {'-':<6} | {'-':<7} | {'-':<10} | {'-':<6}")
        print("=" * 78 + "\n")

    def escrever(self, chave: str, valor: str, node_id: int = 1, max_tentativas: int = 3) -> bool:
        """Envia gravação para um nó; se for seguidor, segue o redirecionamento."""
        addr = self.peers.get(node_id)
        if not addr:
            print(f"\033[91m[ERRO]\033[0m Nó {node_id} não configurado.")
            return False

        alvo_addr = addr
        alvo_id = node_id

        for tentativa in range(1, max_tentativas + 1):
            print(f"[*] Tentativa {tentativa}: Enviando gravação [{chave}='{valor}'] para o Nó {alvo_id} ({alvo_addr})...")
            try:
                canal = grpc.insecure_channel(alvo_addr)
                stub = cluster_pb2_grpc.ClientServiceStub(canal)
                req = cluster_pb2.WriteRequest(key=chave, value=valor)
                resp = stub.Write(req, timeout=4.0)
                canal.close()

                # Escrita bem-sucedida pelo líder
                if resp.success:
                    print(
                        f"\033[92m[SUCESSO]\033[0m Gravação comitada pelo Líder (Nó {resp.leader_id})! "
                        f"Índice de Commit: {resp.index}, Termo: {resp.term}"
                    )
                    return True

                # Redirecionamento recebido de um seguidor/candidato
                if resp.leader_id and resp.leader_id in self.peers:
                    alvo_id = resp.leader_id
                    alvo_addr = self.peers[alvo_id]
                    print(
                        f"\033[93m[REDIRECIONAMENTO]\033[0m {resp.error} "
                        f"Redirecionando automaticamente para o Líder informado: Nó {alvo_id} ({alvo_addr})..."
                    )
                    time.sleep(0.2)
                    continue
                elif resp.leader_address:
                    alvo_addr = resp.leader_address
                    alvo_id = resp.leader_id
                    print(
                        f"\033[93m[REDIRECIONAMENTO]\033[0m {resp.error} "
                        f"Redirecionando automaticamente para o Líder informado: Nó {alvo_id} ({alvo_addr})..."
                    )
                    time.sleep(0.2)
                    continue
                else:
                    print(f"\033[91m[RECUSADO]\033[0m {resp.error}")
                    return False

            except grpc.RpcError as err:
                print(f"\033[91m[FALHA DE CONEXÃO]\033[0m Nó {alvo_id} ({alvo_addr}) inacessível.")
                # Tenta próximo nó se o atual caiu
                alvo_id = (alvo_id % CLUSTER_SIZE) + 1
                alvo_addr = self.peers.get(alvo_id, "")
                time.sleep(0.5)

        print(f"\033[91m[FALHA]\033[0m Não foi possível concluir a gravação após {max_tentativas} tentativas.")
        return False

    def ler(self, chave: str, node_id: int = 1) -> Optional[str]:
        """Consulta leitura de dados comitados em um nó específico do cluster."""
        addr = self.peers.get(node_id)
        if not addr:
            print(f"\033[91m[ERRO]\033[0m Nó {node_id} não encontrado.")
            return None

        try:
            canal = grpc.insecure_channel(addr)
            stub = cluster_pb2_grpc.ClientServiceStub(canal)
            req = cluster_pb2.ReadRequest(key=chave)
            resp = stub.Read(req, timeout=1.5)
            canal.close()

            if resp.found:
                print(
                    f"\033[92m[LEITURA OK]\033[0m Nó {resp.node_id} ({resp.role}, Termo: {resp.term}, CommitIndex: {resp.commit_index}): "
                    f"'{resp.key}' = '{resp.value}'"
                )
                return resp.value
            else:
                print(
                    f"\033[93m[CHAVE NÃO ENCONTRADA]\033[0m Nó {resp.node_id} ({resp.role}, CommitIndex: {resp.commit_index}): "
                    f"Chave '{chave}' não existe ou ainda não foi comitada no banco final."
                )
                return None
        except Exception as err:
            print(f"\033[91m[FALHA]\033[0m Erro ao consultar Nó {node_id} ({addr}): {err}")
            return None

    def ler_todas_replicas(self, chave: str) -> None:
        """Lê a mesma chave em todas as 4 réplicas para comprovar a consistência distribuída."""
        print(f"\n[*] Consultando chave '{chave}' em todos os 4 nós do cluster:")
        for nid in sorted(self.peers.keys()):
            self.ler(chave, node_id=nid)
        print()


def main():
    parser = argparse.ArgumentParser(description="Cliente Raft/Pull UTFPR")
    subparsers = parser.add_subparsers(dest="comando")

    # Comando status
    subparsers.add_parser("status", help="Exibe status de todos os nós do cluster")

    # Comando write
    p_write = subparsers.add_parser("write", help="Escreve uma chave e valor no cluster")
    p_write.add_argument("chave", help="Nome da chave")
    p_write.add_argument("valor", help="Valor a ser gravado")
    p_write.add_argument("--node", type=int, default=1, help="Nó inicial a ser contatado (padrão: 1)")

    # Comando read
    p_read = subparsers.add_parser("read", help="Lê uma chave de um nó específico ou de todos")
    p_read.add_argument("chave", help="Nome da chave")
    p_read.add_argument("--node", type=int, default=None, help="Nó específico (1..4)")
    p_read.add_argument("--todos", action="store_true", help="Consulta todos os 4 nós do cluster")

    args = parser.parse_args()
    cliente = ClienteCluster()

    if args.comando == "status":
        cliente.status()
    elif args.comando == "write":
        cliente.escrever(args.chave, args.valor, node_id=args.node)
    elif args.comando == "read":
        if args.todos or args.node is None:
            cliente.ler_todas_replicas(args.chave)
        else:
            cliente.ler(args.chave, node_id=args.node)
    else:
        # Modo Interativo Simples
        print("=== Cliente Interativo Cluster Raft/Pull (UTFPR) ===")
        print("Comandos: status | write <chave> <valor> [--node N] | read <chave> [--node N] | exit")
        while True:
            try:
                linha = input("\ncluster> ").strip()
                if not linha:
                    continue
                partes = linha.split()
                cmd = partes[0].lower()

                if cmd in ("exit", "quit"):
                    break
                elif cmd == "status":
                    cliente.status()
                elif cmd == "write" and len(partes) >= 3:
                    nid = 1
                    if "--node" in partes:
                        pos = partes.index("--node")
                        if pos + 1 < len(partes):
                            nid = int(partes[pos + 1])
                            partes = partes[:pos]
                    cliente.escrever(partes[1], " ".join(partes[2:]), node_id=nid)
                elif cmd == "read" and len(partes) >= 2:
                    if "--todos" in partes or len(partes) == 2:
                        cliente.ler_todas_replicas(partes[1])
                    else:
                        cliente.ler(partes[1], node_id=int(partes[2]))
                else:
                    print("Comando inválido. Exemplos: 'write x 10', 'read x', 'status'")
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    main()
