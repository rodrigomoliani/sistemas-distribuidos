"""Testes unitários automatizados para o Cliente gRPC (Redirecionamento e Leitura)."""

from concurrent import futures
from pathlib import Path
import shutil
import tempfile
import unittest

import grpc

from cliente.client import ClienteCluster
from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc
from no.servidor import ServidorNo


class TestClienteCluster(unittest.TestCase):
    def setUp(self):
        self.temp_dir1 = Path(tempfile.mkdtemp(prefix="client_test_no1_"))
        self.temp_dir2 = Path(tempfile.mkdtemp(prefix="client_test_no2_"))

        self.servidor1 = ServidorNo(data_dir=self.temp_dir1)
        self.servidor2 = ServidorNo(data_dir=self.temp_dir2)

        self.porta1 = 59201
        self.porta2 = 59202

        # Nó 1 será Seguidor com líder apontando para Nó 2
        self.servidor1.eleicao.role = "SEGUIDOR"
        self.servidor1.eleicao.leader_id = 2

        # Nó 2 será Líder
        self.servidor2.eleicao.role = "LÍDER"
        self.servidor2.eleicao.leader_id = 2

        self.servidor1.iniciar(porta=self.porta1, host="127.0.0.1")
        self.servidor2.iniciar(porta=self.porta2, host="127.0.0.1")

        self.peers_teste = {
            1: f"127.0.0.1:{self.porta1}",
            2: f"127.0.0.1:{self.porta2}",
        }
        self.cliente = ClienteCluster(peers=self.peers_teste)

    def tearDown(self):
        self.servidor1.parar()
        self.servidor2.parar()
        shutil.rmtree(self.temp_dir1, ignore_errors=True)
        shutil.rmtree(self.temp_dir2, ignore_errors=True)

    def test_leitura_em_qualquer_no(self):
        """Valida que o cliente consegue ler dados diretamente de qualquer nó."""
        # Insere dado comitado no Nó 1
        self.servidor1.storage.anexar_entrada(1, "curso", "sistemas")
        self.servidor1.storage.avancar_commit(1)

        val = self.cliente.ler("curso", node_id=1)
        self.assertEqual(val, "sistemas")

        # Chave inexistente retorna None
        val_inexistente = self.cliente.ler("nao_existe", node_id=1)
        self.assertIsNone(val_inexistente)

    def test_status_consulta_todos_nos(self):
        """Valida que a chamada de status não levanta exceções e consulta os nós."""
        try:
            self.cliente.status()
        except Exception as e:
            self.fail(f"cliente.status() falhou com exceção: {e}")


if __name__ == "__main__":
    unittest.main()

