"""Gerenciador de eleição de líder e temporizadores aleatórios (estilo Raft)."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import random
import threading
import time
from typing import Callable, Dict, Optional

import grpc

from comum.config import (
    CLUSTER_SIZE,
    ELECTION_TIMEOUT_MAX,
    ELECTION_TIMEOUT_MIN,
    NODE_ID,
    PEERS,
    QUORUM_SIZE,
)
from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc

logger = logging.getLogger(f"No{NODE_ID}.Eleicao")


class GerenciadorEleicao:
    """Controla os papéis do nó (SEGUIDOR, CANDIDATO, LÍDER),

    temporizadores aleatórios de eleição e o protocolo RequestVote.
    """

    def __init__(
        self,
        node_id: int,
        storage: PersistenciaNo,
        on_assumir_lideranca: Callable[[], None],
        on_perder_lideranca: Callable[[], None],
    ):
        self.node_id = node_id
        self.storage = storage
        self.on_assumir_lideranca = on_assumir_lideranca
        self.on_perder_lideranca = on_perder_lideranca

        self.lock = threading.RLock()
        self.role: str = "SEGUIDOR"
        self.leader_id: Optional[int] = None

        self.proxima_eleicao: float = 0.0
        self.resetar_timer_eleicao()

        self._ativo = True
        self._thread_timer = threading.Thread(target=self._loop_timer_eleicao, daemon=True)

    def iniciar(self):
        """Inicia a thread do temporizador de eleição."""
        self._thread_timer.start()

    def parar(self):
        """Para a thread do temporizador."""
        self._ativo = False

    def resetar_timer_eleicao(self):
        """Reinicia o temporizador com jitter aleatório (1.5s a 3.0s)."""
        with self.lock:
            intervalo = random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)
            self.proxima_eleicao = time.time() + intervalo

    def _loop_timer_eleicao(self):
        """Monitora continuamente o vencimento do temporizador de eleição."""
        while self._ativo:
            time.sleep(0.05)
            with self.lock:
                if not self._ativo:
                    break
                # Se for líder, não executa eleição
                if self.role == "LÍDER":
                    continue

                if time.time() >= self.proxima_eleicao:
                    self._iniciar_eleicao()

    def _iniciar_eleicao(self):
        """Transita para Candidato, incrementa termo e requisita votos em paralelo."""
        self.role = "CANDIDATO"
        self.leader_id = None
        novo_termo = self.storage.current_term + 1
        self.storage.atualizar_termo(novo_termo, voted_for=self.node_id)
        self.resetar_timer_eleicao()

        logger.info(
            f"Election timeout! Iniciando eleição para o Termo {novo_termo} (Candidato: Nó {self.node_id})"
        )

        termo_eleicao = novo_termo
        last_idx, last_term = self.storage.ultimo_indice_e_termo()

        # Dispara coleta de votos em background para não bloquear o lock
        threading.Thread(
            target=self._coletar_votos,
            args=(termo_eleicao, last_idx, last_term),
            daemon=True,
        ).start()

    def _coletar_votos(self, termo: int, last_idx: int, last_term: int):
        """Envia RequestVote em paralelo para todos os outros nós."""
        votos_concedidos = 1  # Voto em si mesmo
        peers_alvo = [p for p in PEERS.keys() if p != self.node_id]

        def pedir_voto(peer_id: int):
            endereco = PEERS[peer_id]
            canal = grpc.insecure_channel(endereco)
            stub = cluster_pb2_grpc.RaftInternalServiceStub(canal)
            req = cluster_pb2.VoteRequest(
                candidate_id=self.node_id,
                term=termo,
                last_log_index=last_idx,
                last_log_term=last_term,
            )
            try:
                resp = stub.RequestVote(req, timeout=0.8)
                return peer_id, resp
            except Exception:
                return peer_id, None
            finally:
                canal.close()

        with ThreadPoolExecutor(max_workers=len(peers_alvo)) as executor:
            futuros = [executor.submit(pedir_voto, pid) for pid in peers_alvo]
            for futuro in as_completed(futuros):
                peer_id, resp = futuro.result()
                if resp is None:
                    continue

                with self.lock:
                    # Se receber resposta com termo superior, recua para seguidor
                    if resp.term > self.storage.current_term:
                        logger.info(
                            f"Termo maior recebido de Nó {peer_id} (T:{resp.term} > T:{self.storage.current_term}). Recuando para SEGUIDOR."
                        )
                        self.storage.atualizar_termo(resp.term, voted_for=None)
                        if self.role != "SEGUIDOR":
                            self.role = "SEGUIDOR"
                            self.on_perder_lideranca()
                        self.resetar_timer_eleicao()
                        return

                    # Se a eleição ainda for válida para este mandato e o voto foi concedido
                    if (
                        self.role == "CANDIDATO"
                        and self.storage.current_term == termo
                        and resp.vote_granted
                    ):
                        votos_concedidos += 1
                        logger.info(
                            f"Voto concedido por Nó {peer_id} para Termo {termo} ({votos_concedidos}/{QUORUM_SIZE} votos)"
                        )

                        # Se atingiu o quórum absoluto (>= 3 nós), assume a liderança!
                        if votos_concedidos >= QUORUM_SIZE:
                            self.role = "LÍDER"
                            self.leader_id = self.node_id
                            logger.info(
                                f"*** QUÓRUM ATINGIDO ({votos_concedidos}/{CLUSTER_SIZE} votos)! Nó {self.node_id} é o novo LÍDER do Termo {termo} ***"
                            )
                            self.on_assumir_lideranca()
                            return

    def processar_request_vote(self, req: cluster_pb2.VoteRequest) -> cluster_pb2.VoteResponse:
        """Processa a solicitação de voto de outro candidato."""
        with self.lock:
            # 1. Se termo da requisição for maior, atualiza imediatamente e vira seguidor
            if req.term > self.storage.current_term:
                logger.info(
                    f"Atualizando termo: T:{self.storage.current_term} -> T:{req.term} a pedido do Candidato {req.candidate_id}"
                )
                self.storage.atualizar_termo(req.term, voted_for=None)
                if self.role != "SEGUIDOR":
                    self.role = "SEGUIDOR"
                    self.on_perder_lideranca()
                self.leader_id = None
                self.resetar_timer_eleicao()

            # 2. Se termo da requisição for estritamente menor, rejeita
            if req.term < self.storage.current_term:
                return cluster_pb2.VoteResponse(
                    voter_id=self.node_id,
                    term=self.storage.current_term,
                    vote_granted=False,
                )

            # 3. Regra de voto único por termo
            meta = self.storage.obter_metadados()
            voto_disponivel = meta["voted_for"] is None or meta["voted_for"] == req.candidate_id

            # 4. Regra do log mais atualizado (Raft log up-to-date)
            local_idx, local_term = self.storage.ultimo_indice_e_termo()
            log_mais_atualizado = (req.last_log_term > local_term) or (
                req.last_log_term == local_term and req.last_log_index >= local_idx
            )

            if voto_disponivel and log_mais_atualizado:
                self.storage.registrar_voto(req.candidate_id)
                self.resetar_timer_eleicao()
                logger.info(
                    f"Voto CONCEDIDO ao Candidato {req.candidate_id} para o Termo {req.term}"
                )
                return cluster_pb2.VoteResponse(
                    voter_id=self.node_id,
                    term=self.storage.current_term,
                    vote_granted=True,
                )
            else:
                motivo = "já votou em outro candidato" if not voto_disponivel else "log local é mais recente"
                logger.info(
                    f"Voto RECUSADO ao Candidato {req.candidate_id} para o Termo {req.term} ({motivo})"
                )
                return cluster_pb2.VoteResponse(
                    voter_id=self.node_id,
                    term=self.storage.current_term,
                    vote_granted=False,
                )

    def reconhecer_lider(self, leader_id: int, term: int):
        """Reconhece a autoridade de um líder e reseta o temporizador de eleição."""
        with self.lock:
            if term > self.storage.current_term:
                self.storage.atualizar_termo(term, voted_for=None)
                if self.role != "SEGUIDOR":
                    self.role = "SEGUIDOR"
                    self.on_perder_lideranca()
            elif term == self.storage.current_term and self.role == "CANDIDATO":
                self.role = "SEGUIDOR"
                self.on_perder_lideranca()

            self.leader_id = leader_id
            self.resetar_timer_eleicao()

