"""Mecanismo de replicação no modelo Pull (Fetch-based) e controle de commit por quórum."""

import logging
import threading
import time
from typing import Optional

import grpc

from comum.config import FETCH_INTERVAL, NODE_ID, PEERS
from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc
from no.eleicao import GerenciadorEleicao
from no.monitor_quorum import MonitorQuorum

logger = logging.getLogger(f"No{NODE_ID}.Pull")


class ReplicadorPull:
    """Gerencia a busca ativa periódica de logs nas réplicas (FetchRequest)

    e o processamento de fetches no líder para replicação e avanço de commit.
    """

    def __init__(
        self,
        node_id: int,
        storage: PersistenciaNo,
        eleicao: GerenciadorEleicao,
        monitor_quorum: MonitorQuorum,
    ):
        self.node_id = node_id
        self.storage = storage
        self.eleicao = eleicao
        self.monitor_quorum = monitor_quorum

        self.lock = threading.RLock()
        self.commit_cond = threading.Condition(self.lock)

        self._ativo = True
        self._thread_fetch = threading.Thread(target=self._loop_fetch, daemon=True)

    def iniciar(self):
        self._thread_fetch.start()

    def parar(self):
        self._ativo = False
        with self.lock:
            self.commit_cond.notify_all()

    # ==========================================================
    # Loop de Fetch Ativo da Réplica (Seguidor)
    # ==========================================================

    def _loop_fetch(self):
        """Loop periódico do seguidor buscando ativamente novas entradas no líder."""
        while self._ativo:
            time.sleep(FETCH_INTERVAL)

            if not self._ativo:
                break

            # Apenas seguidores buscam dados
            with self.eleicao.lock:
                role = self.eleicao.role
                leader_id = self.eleicao.leader_id

            if role != "SEGUIDOR":
                continue

            # Se não conhece o líder, tenta descobrir entre os pares
            if leader_id is None:
                self._descobrir_lider()
                continue

            # Executa o FetchRequest para o líder conhecido
            self._executar_fetch_para_lider(leader_id)

    def _descobrir_lider(self):
        """Sonda pares do cluster para descobrir quem é o líder atual."""
        for peer_id, addr in PEERS.items():
            if peer_id == self.node_id:
                continue
            try:
                canal = grpc.insecure_channel(addr)
                stub = cluster_pb2_grpc.ClientServiceStub(canal)
                resp = stub.GetStatus(cluster_pb2.StatusRequest(), timeout=0.3)
                canal.close()
                if resp.role == "LÍDER" and resp.current_term >= self.storage.current_term:
                    self.eleicao.reconhecer_lider(resp.node_id, resp.current_term)
                    return
            except Exception:
                pass

    def _executar_fetch_para_lider(self, leader_id: int):
        """Dispara FetchRequest ao líder e processa retorno e índice de commit."""
        endereco = PEERS.get(leader_id)
        if not endereco:
            return

        with self.storage.lock:
            meta = self.storage.obter_metadados()
            termo_local = meta["current_term"]
            prev_idx, prev_term = self.storage.ultimo_indice_e_termo()

        canal = grpc.insecure_channel(endereco)
        stub = cluster_pb2_grpc.RaftInternalServiceStub(canal)
        req = cluster_pb2.FetchRequest(
            replica_id=self.node_id,
            replica_term=termo_local,
            prev_log_index=prev_idx,
            prev_log_term=prev_term,
        )

        try:
            resp = stub.Fetch(req, timeout=0.5)
        except Exception:
            # Falha de comunicação com o líder (líder pode ter caído)
            canal.close()
            return
        finally:
            canal.close()

        with self.storage.lock, self.eleicao.lock:
            # Se o líder tem termo estritamente maior, atualiza
            if resp.leader_term > self.storage.current_term:
                self.eleicao.reconhecer_lider(resp.leader_id, resp.leader_term)
                return

            if resp.leader_id > 0 and resp.leader_term == self.storage.current_term:
                # Heartbeat bem-sucedido: reseta o temporizador de eleição
                self.eleicao.reconhecer_lider(resp.leader_id, resp.leader_term)

                if resp.success:
                    # 1. Aplica novos logs recebidos
                    if resp.entries:
                        novas = [
                            {
                                "index": int(e.index),
                                "term": int(e.term),
                                "key": e.key,
                                "value": e.value,
                            }
                            for e in resp.entries
                        ]
                        sucesso_sync, _ = self.storage.sincronizar_entradas_do_lider(
                            prev_idx, prev_term, novas
                        )
                        if not sucesso_sync:
                            logger.warning("Falha na sincronização local de entradas do líder.")

                    # 2. Aplica avanço do índice de commit no banco consolidado
                    if resp.leader_commit > self.storage.commit_index:
                        ultimo_idx, _ = self.storage.ultimo_indice_e_termo()
                        commit_alvo = min(resp.leader_commit, ultimo_idx)
                        if commit_alvo > self.storage.commit_index:
                            aplicadas = self.storage.avancar_commit(commit_alvo)
                            if aplicadas:
                                logger.info(
                                    f"Commit avançado para {commit_alvo} ({len(aplicadas)} entradas aplicadas no banco local)"
                                )

                else:
                    # Divergência detectada pelo líder: trunca log a partir do ponto de conflito
                    if resp.conflict_index > 0:
                        logger.warning(
                            f"Divergência de log detectada! Truncando a partir do índice {resp.conflict_index}"
                        )
                        self.storage.truncar_a_partir_de(resp.conflict_index)

    # ==========================================================
    # Atendimento de Fetch no Líder
    # ==========================================================

    def atender_fetch(self, req: cluster_pb2.FetchRequest) -> cluster_pb2.FetchResponse:
        """Processa requisições de Fetch enviadas pelas réplicas para o Líder."""
        with self.storage.lock, self.eleicao.lock:
            # Se a réplica tiver termo maior, o líder se rebaixa imediatamente
            if req.replica_term > self.storage.current_term:
                logger.info(
                    f"Réplica {req.replica_id} possui termo maior (T:{req.replica_term} > T:{self.storage.current_term}). Rebaixando para SEGUIDOR."
                )
                self.storage.atualizar_termo(req.replica_term, voted_for=None)
                self.eleicao.role = "SEGUIDOR"
                self.eleicao.on_perder_lideranca()
                return cluster_pb2.FetchResponse(
                    leader_id=-1,
                    leader_term=self.storage.current_term,
                    success=False,
                    conflict_index=0,
                    leader_commit=self.storage.commit_index,
                    entries=[],
                )

            # Se este nó não for o líder atual
            if self.eleicao.role != "LÍDER":
                return cluster_pb2.FetchResponse(
                    leader_id=self.eleicao.leader_id or -1,
                    leader_term=self.storage.current_term,
                    success=False,
                    conflict_index=0,
                    leader_commit=self.storage.commit_index,
                    entries=[],
                )

            # Registra atividade da réplica no monitor de quórum
            self.monitor_quorum.registrar_fetch(req.replica_id, req.prev_log_index)

            last_idx, last_term = self.storage.ultimo_indice_e_termo()

            # Valida consistência de log até prev_log_index
            # 1. Se prev_log_index for maior que o último log do líder
            if req.prev_log_index > last_idx:
                return cluster_pb2.FetchResponse(
                    leader_id=self.node_id,
                    leader_term=self.storage.current_term,
                    success=False,
                    conflict_index=last_idx + 1,
                    leader_commit=self.storage.commit_index,
                    entries=[],
                )

            # 2. Se prev_log_index > 0, deve existir entrada com o mesmo termo
            if req.prev_log_index > 0:
                entrada_lider = self.storage.obter_entrada(req.prev_log_index)
                if not entrada_lider or int(entrada_lider["term"]) != req.prev_log_term:
                    # Conflito de log! Informa para a réplica recuar
                    return cluster_pb2.FetchResponse(
                        leader_id=self.node_id,
                        leader_term=self.storage.current_term,
                        success=False,
                        conflict_index=max(1, req.prev_log_index),
                        leader_commit=self.storage.commit_index,
                        entries=[],
                    )

            # Log consistente até prev_log_index!
            self.monitor_quorum.registrar_fetch(req.replica_id, req.prev_log_index)

            # Busca novas entradas para enviar à réplica
            entradas_enviar = self.storage.obter_entradas_a_partir_de(req.prev_log_index + 1)
            entries_proto = [
                cluster_pb2.LogEntry(
                    index=int(e["index"]),
                    term=int(e["term"]),
                    key=e["key"],
                    value=e["value"],
                )
                for e in entradas_enviar
            ]

            # Recalcula commit com base no progresso das réplicas
            novo_commit = self.monitor_quorum.calcular_novo_commit(
                self.storage.log,
                self.storage.commit_index,
                self.storage.current_term,
                last_idx,
            )

            if novo_commit > self.storage.commit_index:
                self.storage.avancar_commit(novo_commit)
                logger.info(f"Líder avançou commit_index para {novo_commit} por quórum.")
                with self.commit_cond:
                    self.commit_cond.notify_all()

            return cluster_pb2.FetchResponse(
                leader_id=self.node_id,
                leader_term=self.storage.current_term,
                success=True,
                conflict_index=0,
                leader_commit=self.storage.commit_index,
                entries=entries_proto,
            )

    # ==========================================================
    # Atendimento de Gravações do Cliente no Líder
    # ==========================================================

    def executar_escrita_cliente(self, key: str, value: str, timeout: float = 3.0):
        """Grava no log local e aguarda confirmação de quórum para commit."""
        with self.lock:
            # 1. Verifica se continua sendo líder
            if self.eleicao.role != "LÍDER":
                return False, 0, 0, "Nó não é o líder atual."

            # 2. Regra Sem Quórum, Sem Escrita: rejeita imediatamente se não houver réplicas ativas
            if not self.monitor_quorum.tem_quorum():
                total_ativos = 1 + len(self.monitor_quorum.obter_replicas_ativas())
                msg = f"Cluster sem quórum de réplicas ativas ({total_ativos}/4 nós ativos). Escrita bloqueada."
                logger.warning(msg)
                return False, 0, 0, msg

            # 3. Grava no log local
            termo = self.storage.current_term
            entrada = self.storage.anexar_entrada(termo, key, value)
            target_idx = entrada["index"]
            logger.info(
                f"Nova escrita aceita pelo líder: [{key}={value}] atribuída a Index:{target_idx}, Termo:{termo}. Aguardando quórum de replicação..."
            )

        # 4. Aguarda quórum replicar e avançar o commit_index
        fim = time.time() + timeout
        while time.time() < fim:
            with self.lock:
                if self.storage.commit_index >= target_idx:
                    logger.info(f"Escrita [Index:{target_idx}] comitada com sucesso!")
                    return True, target_idx, termo, ""
                if self.eleicao.role != "LÍDER":
                    return False, target_idx, termo, "Liderança perdida antes do commit."
                if not self.monitor_quorum.tem_quorum():
                    return False, target_idx, termo, "Perda de quórum durante a replicação."

            time.sleep(0.05)

        return False, target_idx, termo, "Timeout aguardando confirmação do quórum."
