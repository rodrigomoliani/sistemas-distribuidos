"""Servidor gRPC integrado do nó do cluster (Eleição Raft e Replicação Pull)."""

from concurrent import futures
import logging
import threading
import time
from typing import Optional

import grpc

from comum.config import (
    CLIENT_PEERS,
    DATA_DIR,
    NODE_HOST,
    NODE_ID,
    NODE_PORT,
    PEERS,
)
from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc
from no.eleicao import GerenciadorEleicao
from no.monitor_quorum import MonitorQuorum
from no.replicacao_pull import ReplicadorPull

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(f"No{NODE_ID}")


class RaftInternalServicer(cluster_pb2_grpc.RaftInternalServiceServicer):
    """Implementa o serviço gRPC de comunicação interna do cluster."""

    def __init__(self, servidor: "ServidorNo"):
        self.servidor = servidor

    def RequestVote(self, request, context):
        return self.servidor.eleicao.processar_request_vote(request)

    def Fetch(self, request, context):
        return self.servidor.replicador_pull.atender_fetch(request)


class ClientServicer(cluster_pb2_grpc.ClientServiceServicer):
    """Implementa o serviço gRPC para atendimento a clientes."""

    def __init__(self, servidor: "ServidorNo"):
        self.servidor = servidor

    def GetStatus(self, request, context):
        with self.servidor.lock:
            meta = self.servidor.storage.obter_metadados()
            last_idx, last_term = self.servidor.storage.ultimo_indice_e_termo()
            leader_id = self.servidor.eleicao.leader_id
            leader_addr = CLIENT_PEERS.get(leader_id, "") if leader_id else ""
            banco = self.servidor.storage.obter_todos_comitados()

            return cluster_pb2.StatusResponse(
                node_id=NODE_ID,
                role=self.servidor.eleicao.role,
                current_term=meta["current_term"],
                voted_for=meta["voted_for"] if meta["voted_for"] is not None else -1,
                commit_index=meta["commit_index"],
                last_log_index=last_idx,
                last_log_term=last_term,
                leader_id=leader_id or -1,
                leader_address=leader_addr,
                committed_keys_count=len(banco),
            )

    def Read(self, request, context):
        """Consulta leitura de dados comitados (disponível em qualquer nó)."""
        with self.servidor.lock:
            meta = self.servidor.storage.obter_metadados()
            valor = self.servidor.storage.ler_comitado(request.key)
            if valor is not None:
                return cluster_pb2.ReadResponse(
                    found=True,
                    key=request.key,
                    value=valor,
                    commit_index=meta["commit_index"],
                    node_id=NODE_ID,
                    role=self.servidor.eleicao.role,
                    term=meta["current_term"],
                )
            return cluster_pb2.ReadResponse(
                found=False,
                key=request.key,
                value="",
                commit_index=meta["commit_index"],
                node_id=NODE_ID,
                role=self.servidor.eleicao.role,
                term=meta["current_term"],
            )

    def Write(self, request, context):
        """Gravação com quórum e redirecionamento caso contate seguidor."""
        # Se não for o líder, informa redirecionamento imediato
        if self.servidor.eleicao.role != "LÍDER":
            leader_id = self.servidor.eleicao.leader_id
            leader_addr = CLIENT_PEERS.get(leader_id, "") if leader_id else ""
            return cluster_pb2.WriteResponse(
                success=False,
                leader_id=leader_id or -1,
                leader_address=leader_addr,
                error=f"Nó {NODE_ID} é {self.servidor.eleicao.role}. Redirecione para o líder.",
            )

        # Se for o líder, submete à replicação e aguarda quórum de commit
        sucesso, idx, termo, erro = self.servidor.replicador_pull.executar_escrita_cliente(
            request.key, request.value
        )
        return cluster_pb2.WriteResponse(
            success=sucesso,
            leader_id=NODE_ID,
            index=idx,
            term=termo,
            error=erro,
        )


class ServidorNo:
    """Instância completa do nó do cluster."""

    def __init__(self, data_dir=DATA_DIR):
        self.lock = threading.RLock()
        self.storage = PersistenciaNo(data_dir)
        self.monitor_quorum = MonitorQuorum(NODE_ID)

        self.eleicao = GerenciadorEleicao(
            node_id=NODE_ID,
            storage=self.storage,
            on_assumir_lideranca=self._on_assumir_lideranca,
            on_perder_lideranca=self._on_perder_lideranca,
        )

        self.replicador_pull = ReplicadorPull(
            node_id=NODE_ID,
            storage=self.storage,
            eleicao=self.eleicao,
            monitor_quorum=self.monitor_quorum,
        )

        self.server: Optional[grpc.Server] = None
        self._parar_evento = threading.Event()

    def _on_assumir_lideranca(self):
        logger.info(f">>> Nó {NODE_ID} assumiu o papel de LÍDER! <<<")
        self.monitor_quorum.resetar_para_nova_lideranca(set(PEERS.keys()))

    def _on_perder_lideranca(self):
        logger.info(f"Nó {NODE_ID} voltou para o papel de SEGUIDOR.")

    def banner_status(self) -> str:
        meta = self.storage.obter_metadados()
        last_idx, last_term = self.storage.ultimo_indice_e_termo()
        return (
            f"[Nó {NODE_ID} | Papel: {self.eleicao.role} | Termo: {meta['current_term']} | "
            f"CommitIndex: {meta['commit_index']} | LastLog: {last_idx} (T:{last_term})]"
        )

    def iniciar(self, porta: int = NODE_PORT, host: str = NODE_HOST):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        cluster_pb2_grpc.add_RaftInternalServiceServicer_to_server(
            RaftInternalServicer(self), self.server
        )
        cluster_pb2_grpc.add_ClientServiceServicer_to_server(
            ClientServicer(self), self.server
        )

        endereco = f"{host}:{porta}"
        self.server.add_insecure_port(endereco)
        self.server.start()
        logger.info(f"Servidor gRPC iniciado em {endereco}")

        # Inicia a eleição e o loop de replicação
        self.eleicao.iniciar()
        self.replicador_pull.iniciar()
        logger.info(self.banner_status())

    def parar(self):
        logger.info(f"Encerrando Nó {NODE_ID}...")
        self._parar_evento.set()
        self.eleicao.parar()
        self.replicador_pull.parar()
        if self.server:
            self.server.stop(grace=1)
        logger.info(f"Nó {NODE_ID} encerrado.")

    def esperar(self):
        try:
            while not self._parar_evento.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.parar()
