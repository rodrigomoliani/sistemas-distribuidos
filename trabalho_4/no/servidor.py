"""Servidor gRPC base do nó do cluster."""

from concurrent import futures
import logging
import signal
import sys
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(f"No{NODE_ID}")


class RaftInternalServicer(cluster_pb2_grpc.RaftInternalServiceServicer):
    """Implementa o serviço gRPC de comunicação interna do Raft."""

    def __init__(self, servidor: "ServidorNo"):
        self.servidor = servidor

    def RequestVote(self, request, context):
        # Stub para a Parte 1/2: será integrado com a máquina de estados nas Partes 3/4
        with self.servidor.lock:
            meta = self.servidor.storage.obter_metadados()
            return cluster_pb2.VoteResponse(
                voter_id=NODE_ID,
                term=meta["current_term"],
                vote_granted=False,
            )

    def Fetch(self, request, context):
        # Stub para a Parte 1/2: será integrado com a replicação Pull nas Partes 3/4
        with self.servidor.lock:
            meta = self.servidor.storage.obter_metadados()
            return cluster_pb2.FetchResponse(
                leader_id=self.servidor.leader_id or -1,
                leader_term=meta["current_term"],
                success=False,
                conflict_index=0,
                leader_commit=meta["commit_index"],
                entries=[],
            )


class ClientServicer(cluster_pb2_grpc.ClientServiceServicer):
    """Implementa o serviço gRPC para atendimento a clientes."""

    def __init__(self, servidor: "ServidorNo"):
        self.servidor = servidor

    def GetStatus(self, request, context):
        with self.servidor.lock:
            meta = self.servidor.storage.obter_metadados()
            last_idx, last_term = self.servidor.storage.ultimo_indice_e_termo()
            leader_addr = CLIENT_PEERS.get(self.servidor.leader_id, "") if self.servidor.leader_id else ""
            banco = self.servidor.storage.obter_todos_comitados()

            return cluster_pb2.StatusResponse(
                node_id=NODE_ID,
                role=self.servidor.role,
                current_term=meta["current_term"],
                voted_for=meta["voted_for"] if meta["voted_for"] is not None else -1,
                commit_index=meta["commit_index"],
                last_log_index=last_idx,
                last_log_term=last_term,
                leader_id=self.servidor.leader_id or -1,
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
                    role=self.servidor.role,
                    term=meta["current_term"],
                )
            return cluster_pb2.ReadResponse(
                found=False,
                key=request.key,
                value="",
                commit_index=meta["commit_index"],
                node_id=NODE_ID,
                role=self.servidor.role,
                term=meta["current_term"],
            )

    def Write(self, request, context):
        """Gravação com redirecionamento ao líder."""
        with self.servidor.lock:
            if self.servidor.role != "LÍDER":
                leader_addr = CLIENT_PEERS.get(self.servidor.leader_id, "") if self.servidor.leader_id else ""
                return cluster_pb2.WriteResponse(
                    success=False,
                    leader_id=self.servidor.leader_id or -1,
                    leader_address=leader_addr,
                    error=f"Nó {NODE_ID} é {self.servidor.role}. Redirecione para o líder.",
                )

            # Implementação completa com replicação Pull e Quórum será integrada na Parte 4
            return cluster_pb2.WriteResponse(
                success=False,
                leader_id=NODE_ID,
                error="Cluster ainda em modo de inicialização/eleição.",
            )


class ServidorNo:
    """Instância do nó do cluster, coordenando storage e servidor gRPC."""

    def __init__(self, data_dir=DATA_DIR):
        self.lock = threading.RLock()
        self.storage = PersistenciaNo(data_dir)
        self.role: str = "SEGUIDOR"
        self.leader_id: Optional[int] = None
        self.server: Optional[grpc.Server] = None
        self._parar_evento = threading.Event()

    def banner_status(self) -> str:
        meta = self.storage.obter_metadados()
        last_idx, last_term = self.storage.ultimo_indice_e_termo()
        return (
            f"[Nó {NODE_ID} | Papel: {self.role} | Termo: {meta['current_term']} | "
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
        logger.info(self.banner_status())

    def parar(self):
        logger.info(f"Encerrando Nó {NODE_ID}...")
        self._parar_evento.set()
        if self.server:
            self.server.stop(grace=1)
        logger.info(f"Nó {NODE_ID} encerrado.")

    def esperar(self):
        try:
            while not self._parar_evento.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.parar()

