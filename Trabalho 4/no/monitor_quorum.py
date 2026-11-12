"""Monitor de quórum e inatividade de réplicas para o Líder Raft/Pull."""

import time
import threading
from typing import Dict, List, Set
from comum.config import HEARTBEAT_TIMEOUT, QUORUM_SIZE, CLUSTER_SIZE


class MonitorQuorum:
    """Rastreia réplicas ativas via Heartbeat Timeout e calcula o avanço do commit por quórum."""

    def __init__(self, node_id: int):
        self.node_id = node_id
        self.lock = threading.RLock()

        # Rastreamento de atividade por réplica: replica_id -> timestamp do último FetchRequest
        self.last_fetch_time: Dict[int, float] = {}

        # Rastreamento do último índice replicado com sucesso: replica_id -> match_index
        self.match_index: Dict[int, int] = {}

    def resetar_para_nova_lideranca(self, peers_ids: Set[int]):
        """Inicializa métricas ao assumir a liderança."""
        with self.lock:
            agora = time.time()
            self.last_fetch_time = {p: agora for p in peers_ids if p != self.node_id}
            self.match_index = {p: 0 for p in peers_ids if p != self.node_id}

    def registrar_fetch(self, replica_id: int, match_idx: int | None = None) -> None:
        """Registra atividade e índice correspondente reportado no FetchRequest."""
        with self.lock:
            self.last_fetch_time[replica_id] = time.time()
            if match_idx is not None:
                self.match_index[replica_id] = match_idx

    def obter_replicas_ativas(self) -> List[int]:
        """Retorna a lista de IDs de réplicas que enviaram Fetch dentro do Heartbeat Timeout."""
        with self.lock:
            agora = time.time()
            return [
                replica_id
                for replica_id, ultimo_fetch in self.last_fetch_time.items()
                if (agora - ultimo_fetch) <= HEARTBEAT_TIMEOUT
            ]

    def tem_quorum(self) -> bool:
        """Verifica se há quórum absoluto de nós ativos (Líder + réplicas ativas >= 3)."""
        with self.lock:
            # O líder sempre conta como 1 nó ativo
            total_ativos = 1 + len(self.obter_replicas_ativas())
            return total_ativos >= QUORUM_SIZE

    def calcular_novo_commit(
        self,
        log_entries: List[Dict],
        commit_atual: int,
        termo_atual: int,
        ultimo_log_idx: int,
    ) -> int:
        """Calcula o maior índice N > commit_atual tal que uma maioria de nós

        (quórum >= 3) tenha match_index >= N e log[N].term == termo_atual.
        """
        with self.lock:
            if ultimo_log_idx <= commit_atual:
                return commit_atual

            novo_commit = commit_atual

            # Analisa índices sequencialmente de commit_atual + 1 até ultimo_log_idx
            for n in range(commit_atual + 1, ultimo_log_idx + 1):
                # Procura a entrada no log para checar o termo
                entrada_n = None
                for entrada in log_entries:
                    if int(entrada["index"]) == n:
                        entrada_n = entrada
                        break

                if not entrada_n:
                    continue

                # Regra do Raft: só comita diretamente entradas do termo atual
                if int(entrada_n["term"]) != termo_atual:
                    continue

                # Conta quantos nós possuem o log até pelo menos o índice N
                # 1. O próprio líder já possui
                contagem = 1
                for replica_id, match_idx in self.match_index.items():
                    if match_idx >= n:
                        contagem += 1

                # Se a contagem atingir o quórum (>= 3 nós), pode comitar até N
                if contagem >= QUORUM_SIZE:
                    novo_commit = n

            return novo_commit

