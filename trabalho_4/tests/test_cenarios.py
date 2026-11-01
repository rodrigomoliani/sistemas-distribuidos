"""Testes automatizados cobrindo os cenários obrigatórios da disciplina (UTFPR)."""

from pathlib import Path
import shutil
import tempfile
import time
import unittest

import grpc

from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc
from no.monitor_quorum import MonitorQuorum
from no.eleicao import GerenciadorEleicao


class TestRegrasConsenso(unittest.TestCase):
    """Testes unitários e funcionais das regras de Quórum, Votação e Replicação Pull."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cenarios_test_"))
        self.storage = PersistenciaNo(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_regra_voto_log_mais_atualizado(self):
        """Valida que o nó só concede voto a quem tem log igual ou mais atualizado."""
        # Configura nó local com log até index 2, termo 1
        self.storage.anexar_entrada(1, "x", "1")
        self.storage.anexar_entrada(1, "y", "2")
        self.storage.atualizar_termo(1, voted_for=None)

        eleicao = GerenciadorEleicao(
            node_id=1,
            storage=self.storage,
            on_assumir_lideranca=lambda: None,
            on_perder_lideranca=lambda: None,
        )

        # Candidato com termo menor -> Rejeitado
        req1 = cluster_pb2.VoteRequest(
            candidate_id=2, term=0, last_log_index=2, last_log_term=1
        )
        resp1 = eleicao.processar_request_vote(req1)
        self.assertFalse(resp1.vote_granted)

        # Candidato com mesmo termo mas log mais atrasado (index 1 < 2) -> Rejeitado
        req2 = cluster_pb2.VoteRequest(
            candidate_id=2, term=1, last_log_index=1, last_log_term=1
        )
        resp2 = eleicao.processar_request_vote(req2)
        self.assertFalse(resp2.vote_granted)

        # Candidato com termo 2 e log igual (index 2, term 1) -> Aceito
        req3 = cluster_pb2.VoteRequest(
            candidate_id=2, term=2, last_log_index=2, last_log_term=1
        )
        resp3 = eleicao.processar_request_vote(req3)
        self.assertTrue(resp3.vote_granted)

        # Segundo candidato no mesmo termo 2 -> Rejeitado (regra de voto único por termo)
        req4 = cluster_pb2.VoteRequest(
            candidate_id=3, term=2, last_log_index=3, last_log_term=1
        )
        resp4 = eleicao.processar_request_vote(req4)
        self.assertFalse(resp4.vote_granted)

    def test_monitor_quorum_e_bloqueio_cenario_3(self):
        """Valida a detecção de perda de quórum pelo monitor do líder (Cenário 3 do PDF)."""
        monitor = MonitorQuorum(node_id=1)
        monitor.resetar_para_nova_lideranca({1, 2, 3, 4})

        # Inicialmente todos ativos
        self.assertTrue(monitor.tem_quorum())

        # Simula atividade recente apenas do Nó 2 (Nó 3 e Nó 4 silenciosos)
        monitor.last_fetch_time[2] = time.time()
        monitor.last_fetch_time[3] = time.time() - 2.0  # Expirado
        monitor.last_fetch_time[4] = time.time() - 2.0  # Expirado

        # Total ativos: Líder (1) + Nó 2 = 2 nós (< 3 nós)
        self.assertFalse(monitor.tem_quorum())
        self.assertEqual(monitor.obter_replicas_ativas(), [2])

        # Nó 3 envia Fetch -> Quórum recuperado (1 + 2 + 3 = 3 nós)
        monitor.registrar_fetch(3, match_idx=1)
        self.assertTrue(monitor.tem_quorum())

    def test_calculo_avanco_commit_por_quorum(self):
        """Valida que o commit só avança quando a maioria (>=3 nós) confirma o índice."""
        monitor = MonitorQuorum(node_id=1)
        monitor.resetar_para_nova_lideranca({1, 2, 3, 4})

        # Cria entradas no log do líder
        e1 = self.storage.anexar_entrada(1, "a", "10")  # index 1
        e2 = self.storage.anexar_entrada(1, "b", "20")  # index 2
        e3 = self.storage.anexar_entrada(1, "c", "30")  # index 3

        # Apenas Nó 2 replicou até índice 1
        monitor.registrar_fetch(2, match_idx=1)
        monitor.registrar_fetch(3, match_idx=0)
        monitor.registrar_fetch(4, match_idx=0)

        # Líder (1) + Nó 2 = 2 nós (< 3) -> Commit não deve avançar
        novo_commit = monitor.calcular_novo_commit(
            self.storage.log, commit_atual=0, termo_atual=1, ultimo_log_idx=3
        )
        self.assertEqual(novo_commit, 0)

        # Nó 3 também replica até o índice 2
        monitor.registrar_fetch(3, match_idx=2)
        # Agora para o índice 1: Líder, Nó 2 e Nó 3 possuem (total 3 nós >= Quórum)
        novo_commit = monitor.calcular_novo_commit(
            self.storage.log, commit_atual=0, termo_atual=1, ultimo_log_idx=3
        )
        self.assertEqual(novo_commit, 1)

        # Nó 4 também replica até o índice 2
        monitor.registrar_fetch(4, match_idx=2)
        # Para o índice 2: Líder, Nó 3 e Nó 4 possuem (total 3 nós >= Quórum)
        novo_commit = monitor.calcular_novo_commit(
            self.storage.log, commit_atual=1, termo_atual=1, ultimo_log_idx=3
        )
        self.assertEqual(novo_commit, 2)


if __name__ == "__main__":
    unittest.main()

