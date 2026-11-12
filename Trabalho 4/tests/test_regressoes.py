"""Regressões de quórum, recuperação após crash e isolamento no fluxo Fetch."""
from concurrent import futures
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import grpc

from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc
from no.eleicao import GerenciadorEleicao
from no.monitor_quorum import MonitorQuorum
from no.replicacao_pull import ReplicadorPull
from no.servidor import ClientServicer, ServidorNo


class TestRegressoes(unittest.TestCase):
    def test_fetch_divergente_nao_confirma_quorum(self):
        with tempfile.TemporaryDirectory() as pasta:
            storage = PersistenciaNo(Path(pasta))
            storage.atualizar_termo(2)
            storage.anexar_entrada(2, "chave", "valor")
            eleicao = GerenciadorEleicao(1, storage, lambda: None, lambda: None)
            eleicao.role = "LÍDER"
            monitor = MonitorQuorum(1)
            monitor.resetar_para_nova_lideranca({1, 2, 3, 4})
            pull = ReplicadorPull(1, storage, eleicao, monitor)
            conflito = cluster_pb2.FetchRequest(replica_id=2, replica_term=2, prev_log_index=1, prev_log_term=1)
            self.assertFalse(pull.atender_fetch(conflito).success)
            valido = cluster_pb2.FetchRequest(replica_id=3, replica_term=2, prev_log_index=1, prev_log_term=2)
            self.assertTrue(pull.atender_fetch(valido).success)
            self.assertEqual(storage.commit_index, 0)
            self.assertIsNone(storage.ler_comitado("chave"))
            valido.replica_id = 4
            pull.atender_fetch(valido)
            self.assertEqual(storage.commit_index, 1)

    def test_recuperacao_crash_entre_arquivos(self):
        with tempfile.TemporaryDirectory() as pasta:
            storage = PersistenciaNo(Path(pasta))
            storage.anexar_entrada(1, "chave", "valor")
            with patch.object(storage, "_persistir_banco_sem_lock", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    storage.avancar_commit(1)
            recuperado = PersistenciaNo(Path(pasta))
            self.assertEqual(recuperado.commit_index, 1)
            self.assertEqual(recuperado.ler_comitado("chave"), "valor")
            # Também corrige banco adiantado em relação ao commit persistido.
            recuperado.arq_metadados.write_text('{"current_term": 1, "voted_for": null, "commit_index": 0}', encoding="utf-8")
            recuperado = PersistenciaNo(Path(pasta))
            self.assertIsNone(recuperado.ler_comitado("chave"))

    def test_cenario_5_fetch_e_leitura_grpc(self):
        class LiderSimulado(cluster_pb2_grpc.RaftInternalServiceServicer):
            commit = 0

            def Fetch(self, request, context):
                entradas = [] if request.prev_log_index else [cluster_pb2.LogEntry(index=1, term=1, key="isolado", value="valor")]
                return cluster_pb2.FetchResponse(leader_id=2, leader_term=1, success=True, leader_commit=self.commit, entries=entradas)

        with tempfile.TemporaryDirectory() as pasta:
            lider = LiderSimulado()
            servidor_lider = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
            cluster_pb2_grpc.add_RaftInternalServiceServicer_to_server(lider, servidor_lider)
            porta_lider = servidor_lider.add_insecure_port("127.0.0.1:0")
            servidor_lider.start()
            replica = ServidorNo(data_dir=Path(pasta))
            replica.storage.atualizar_termo(1)
            replica.eleicao.leader_id = 2
            servidor_cliente = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
            cluster_pb2_grpc.add_ClientServiceServicer_to_server(ClientServicer(replica), servidor_cliente)
            porta_cliente = servidor_cliente.add_insecure_port("127.0.0.1:0")
            servidor_cliente.start()
            try:
                with patch.dict("no.replicacao_pull.PEERS", {2: f"127.0.0.1:{porta_lider}"}):
                    replica.replicador_pull._executar_fetch_para_lider(2)
                    self.assertIsNotNone(replica.storage.obter_entrada(1))
                    with grpc.insecure_channel(f"127.0.0.1:{porta_cliente}") as canal:
                        stub = cluster_pb2_grpc.ClientServiceStub(canal)
                        self.assertFalse(stub.Read(cluster_pb2.ReadRequest(key="isolado"), timeout=1).found)
                        lider.commit = 1
                        replica.replicador_pull._executar_fetch_para_lider(2)
                        resposta = stub.Read(cluster_pb2.ReadRequest(key="isolado"), timeout=1)
                        self.assertTrue(resposta.found)
                        self.assertEqual(resposta.value, "valor")
            finally:
                servidor_cliente.stop(0).wait()
                servidor_lider.stop(0).wait()


if __name__ == "__main__":
    unittest.main(verbosity=2)
