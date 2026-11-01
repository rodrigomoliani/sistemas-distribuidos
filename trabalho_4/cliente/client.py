"""Cliente CLI interativo com suporte a redirecionamento automático ao líder e leituras distribuídas."""

import argparse
from pathlib import Path
import sys
import time

import grpc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from comum.config import CLIENT_PEERS, CLUSTER_SIZE
from comum.proto import cluster_pb2, cluster_pb2_grpc


class ClienteCluster:
    def __init__(self, peers=CLIENT_PEERS):
        self.peers = peers

    def obter_status(self):
        """Consulta o status de cada um dos nós do cluster."""
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

    def escrever(self, chave: str, valor: str, node_id: int = 1, max_tentativas: int = 3):
        """Envia gravação para um nó; se não for líder, segue o redirecionamento."""
        addr = self.peers.get(node_id)
        if not addr:
            print(f"Erro: Nó {node_id} não configurado.")
            return False

        alvo_atual = addr
        alvo_id = node_id

        for tentativa in range(max_tentativas):
            print(f"[*] Tentando gravar [{chave}={valor}] no Nó {alvo_id} ({alvo_atual})...")
            try:
                canal = grpc.insecure_channel(alvo_atual)
                stub = cluster_pb2_grpc.ClientServiceStub(canal)
                req = cluster_pb2.WriteRequest(key=chave, value=valor)
                resp = stub.Write(req, timeout=4.0)
                canal.close()

                if resp.success:
                    print(
                        f"\033[92m[SUCESSO]\033[0m Gravado com êxito pelo Líder (Nó {resp.leader_id})! "
                        f"Index: {resp.index}, Termo: {resp.term}"
                    )
                    return True

                # Redirecionamento recebido
                if resp.leader_address:
                    print(
                        f"\033[93m[REDIRECIONAMENTO]\033[0m {resp.error} Redirecionando para o Líder em {resp.leader_address}..."
                    )
                    alvo_atual = resp.leader_address
                    alvo_id = resp.leader_id
                    time.sleep(0.2)
                    continue
                else:
                    print(f"\033[91m[FALHA]\033[0m {resp.error}")
                    return False

            except grpc.RpcError as err:
                print(f"\033[91m[ERRO DE CONEXÃO]\033[0m Falha ao contatar {alvo_atual}: {err.details() if hasattr(err, 'details') else err}")
                # Tenta próximo nó disponível
                alvo_id = (alvo_id % CLUSTER_SIZE) + 1
                alvo_atual = self.peers.get(alvo_id, "")
                time.sleep(0.5)

        print(f"\033[91m[ERRO]\033[0m Não foi possível concluir a gravação após {max_tentativas} tentativas.")
        return False

    def ler(self, chave: str, node_id: int = 1):
        """Consulta leitura de dados comitados em um nó específico."""
        addr = self.peers.get(node_id)
        if not addr:
            print(f"Erro: Nó {node_id} não encontrado.")
            return None

        try:
            canal = grpc.insecure_channel(addr)
            stub = cluster_pb2_grpc.ClientServiceStub(canal)
            req = cluster_pb2.ReadRequest(key=chave)
            resp = stub.Read(req, timeout=1.5)
            canal.close()

            if resp.found:
                print(
                    f"\033[92m[LEITURA OK]\033[0m Nó {resp.node_id} ({resp.role}, T:{resp.term}): "
                    f"'{resp.key}' = '{resp.value}' (CommitIndex: {resp.commit_index})"
                )
                return resp.value
            else:
                print(
                    f"\033[93m[CHAVE NÃO ENCONTRADA]\033[0m Nó {resp.node_id} ({resp.role}, CommitIndex: {resp.commit_index}): "
                    f"Chave '{chave}' não existe ou ainda não foi comitada."
                )
                return None
        except Exception as err:
            print(f"\033[91m[ERRO]\033[0m Falha ao consultar Nó {node_id} ({addr}): {err}")
            return None

    def ler_todas_replicas(self, chave: str):
        """Lê a mesma chave em todas as 4 réplicas para comprovar a consistência distribuída."""
        print(f"\n[*] Consultando chave '{chave}' em todos os nós do cluster:")
        for nid in sorted(self.peers.keys()):
            self.ler(chave, node_id=nid)
        print()


def main():
    parser = argparse.ArgumentParser(description="Cliente Raft/Pull UTFPR")
    subparsers = parser.add_subparsers(dest="comando")

    # Subcomando status
    subparsers.add_parser("status", help="Exibe status de todos os nós do cluster")

    # Subcomando write
    write_p = subparsers.add_parser("write", help="Escreve uma chave e valor no cluster")
    write_p.add_argument("chave", help="Nome da chave")
    write_p.add_argument("valor", help="Valor a ser armazenado")
    write_p.add_argument("--node", type=int, default=1, help="Nó inicial a ser contatado (padrão: 1)")

    # Subcomando read
    read_p = subparsers.add_parser("read", help="Lê uma chave de um nó específico ou de todos")
    read_p.add_argument("chave", help="Nome da chave")
    read_p.add_argument("--node", type=int, default=None, help="Nó específico a ser consultado (1..4)")
    read_p.add_argument("--todos", action="store_true", help="Consulta em todos os nós do cluster")

    args = parser.parse_args()
    cliente = ClienteCluster()

    if args.comando == "status":
        cliente.obter_status()
    elif args.comando == "write":
        cliente.escrever(args.chave, args.valor, node_id=args.node)
    elif args.comando == "read":
        if args.todos or args.node is None:
            cliente.ler_todas_replicas(args.chave)
        else:
            cliente.ler(args.chave, node_id=args.node)
    else:
        # Modo Interativo
        print("=== Cliente Interativo Cluster Raft/Pull (UTFPR) ===")
        print("Comandos disponíveis: status | write <k> <v> | read <k> [node_id] | exit")
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
                    cliente.obter_status()
                elif cmd == "write" and len(partes) >= 3:
                    cliente.escrever(partes[1], " ".join(partes[2:]))
                elif cmd == "read" and len(partes) >= 2:
                    nid = int(partes[2]) if len(partes) >= 3 else None
                    if nid:
                        cliente.ler(partes[1], node_id=nid)
                    else:
                        cliente.ler_todas_replicas(partes[1])
                else:
                    print("Comando inválido. Exemplos: 'write x 10', 'read x', 'status'")
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    main()
