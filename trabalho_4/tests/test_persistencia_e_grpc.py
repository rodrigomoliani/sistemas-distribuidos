"""Testes automatizados da camada de persistência e comunicação gRPC base (Partes 1 e 2)."""

from pathlib import Path
import shutil
import tempfile
import time
import unittest

import grpc

from comum.persistencia import PersistenciaNo
from comum.proto import cluster_pb2, cluster_pb2_grpc
from no.servidor import ServidorNo


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="raft_test_"))
        self.storage = PersistenciaNo(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_persistencia_metadados(self):
        # Estado inicial
        meta = self.storage.obter_metadados()
        self.assertEqual(meta["current_term"], 0)
        self.assertIsNone(meta["voted_for"])
        self.assertEqual(meta["commit_index"], 0)

        # Atualiza termo
        self.storage.atualizar_termo(2)
        self.storage.registrar_voto(3)

        # Recarrega a partir do disco simulando reinício do processo (crash recovery)
        recuperado = PersistenciaNo(self.temp_dir)
        meta_recup = recuperado.obter_metadados()
        self.assertEqual(meta_recup["current_term"], 2)
        self.assertEqual(meta_recup["voted_for"], 3)

    def test_persistencia_log_e_recuperacao(self):
        # Insere entradas no log
        e1 = self.storage.anexar_entrada(1, "usuario", "carlos")
        e2 = self.storage.anexar_entrada(1, "curso", "engenharia")
        e3 = self.storage.anexar_entrada(2, "disciplina", "distribuidos")

        self.assertEqual(e1["index"], 1)
        self.assertEqual(e3["index"], 3)

        ultimo_idx, ultimo_termo = self.storage.ultimo_indice_e_termo()
        self.assertEqual(ultimo_idx, 3)
        self.assertEqual(ultimo_termo, 2)

        # Simula desligamento e religamento
        recuperado = PersistenciaNo(self.temp_dir)
        self.assertEqual(len(recuperado.log), 3)
        self.assertEqual(recuperado.obter_entrada(2)["value"], "engenharia")
        self.assertEqual(recuperado.ultimo_indice_e_termo(), (3, 2))

    def test_truncamento_de_log_cenario_4b(self):
        """Valida o truncamento de divergência (Cenário 4B do PDF)."""
        self.storage.anexar_entrada(1, "k1", "v1")
        self.storage.anexar_entrada(1, "k2", "v2_antigo")
        self.storage.anexar_entrada(1, "k3", "v3_antigo")

        # Trunca a partir do índice 2 para descartar entradas conflitantes
        removidos = self.storage.truncar_a_partir_de(2)
        self.assertEqual(removidos, 2)
        self.assertEqual(len(self.storage.log), 1)

        # Insere a nova entrada do novo líder (Termo 2)
        nova = self.storage.anexar_entrada(2, "k2", "v2_novo")
        self.assertEqual(nova["index"], 2)
        self.assertEqual(nova["term"], 2)

        # Verifica se a persistência em disco reflete o truncamento após reiniciar
        recuperado = PersistenciaNo(self.temp_dir)
        self.assertEqual(len(recuperado.log), 2)
        self.assertEqual(recuperado.obter_entrada(2)["value"], "v2_novo")

    def test_sincronizacao_log_matching(self):
        """Valida a regra de compatibilidade e correção de sufixos de log."""
        self.storage.anexar_entrada(1, "a", "1")

        # Tentativa com prev_log_index além do tamanho atual -> Rejeição
        sucesso, conflito = self.storage.sincronizar_entradas_do_lider(
            prev_log_index=5, prev_log_term=1, novas_entradas=[]
        )
        self.assertFalse(sucesso)
        self.assertEqual(conflito, 2)

        # Tentativa com prev_log_index existente mas termo divergente -> Rejeição
        sucesso, conflito = self.storage.sincronizar_entradas_do_lider(
            prev_log_index=1, prev_log_term=99, novas_entradas=[]
        )
        self.assertFalse(sucesso)
        self.assertEqual(conflito, 1)

        # Sincronização compatível com novas entradas do líder
        novas = [
            {"index": 2, "term": 1, "key": "b", "value": "2"},
            {"index": 3, "term": 1, "key": "c", "value": "3"},
        ]
        sucesso, ultimo = self.storage.sincronizar_entradas_do_lider(
            prev_log_index=1, prev_log_term=1, novas_entradas=novas
        )
        self.assertTrue(sucesso)
        self.assertEqual(ultimo, 3)

    def test_isolamento_dados_uncommitted_cenario_5(self):
        """Valida o Isolamento de Dados Uncommitted (Cenário 5 do PDF):

        Entradas no log permanecem invisíveis para leitura até serem comitadas.
        """
        self.storage.anexar_entrada(1, "saldo", "100")
        self.storage.anexar_entrada(1, "bonus", "50")

        # 1. Antes do commit, as chaves NÃO devem ser visíveis no banco comitado
        self.assertIsNone(self.storage.ler_comitado("saldo"))
        self.assertIsNone(self.storage.ler_comitado("bonus"))
        self.assertEqual(self.storage.obter_todos_comitados(), {})

        # 2. Avança commit para o índice 1 -> Apenas 'saldo' deve se tornar visível
        aplicadas = self.storage.avancar_commit(1)
        self.assertEqual(len(aplicadas), 1)
        self.assertEqual(self.storage.ler_comitado("saldo"), "100")
        self.assertIsNone(self.storage.ler_comitado("bonus"))

        # 3. Avança commit para o índice 2 -> Agora 'bonus' se torna visível
        self.storage.avancar_commit(2)
        self.assertEqual(self.storage.ler_comitado("bonus"), "50")

        # 4. Confirma que o banco comitado sobrevive ao reinício
        recuperado = PersistenciaNo(self.temp_dir)
        self.assertEqual(recuperado.ler_comitado("saldo"), "100")
        self.assertEqual(recuperado.ler_comitado("bonus"), "50")
        self.assertEqual(recuperado.commit_index, 2)


class TestGrpcServidorBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="raft_grpc_"))
        self.servidor = ServidorNo(data_dir=self.temp_dir)
        self.porta = 59123
        self.servidor.iniciar(porta=self.porta, host="127.0.0.1")
        self.canal = grpc.insecure_channel(f"127.0.0.1:{self.porta}")
        self.client_stub = cluster_pb2_grpc.ClientServiceStub(self.canal)

    def tearDown(self):
        self.canal.close()
        self.servidor.parar()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_status_e_leitura_via_grpc(self):
        # 1. Consulta status inicial
        status = self.client_stub.GetStatus(cluster_pb2.StatusRequest())
        self.assertEqual(status.role, "SEGUIDOR")
        self.assertEqual(status.commit_index, 0)
        self.assertEqual(status.last_log_index, 0)

        # 2. Leitura de chave inexistente
        resp_read = self.client_stub.Read(cluster_pb2.ReadRequest(key="foo"))
        self.assertFalse(resp_read.found)

        # 3. Simula dado gravado e comitado diretamente na persistência do nó
        self.servidor.storage.anexar_entrada(1, "status_cluster", "ativo")
        self.servidor.storage.avancar_commit(1)

        # 4. Leitura via gRPC do dado agora comitado
        resp_read2 = self.client_stub.Read(cluster_pb2.ReadRequest(key="status_cluster"))
        self.assertTrue(resp_read2.found)
        self.assertEqual(resp_read2.value, "ativo")
        self.assertEqual(resp_read2.commit_index, 1)


if __name__ == "__main__":
    unittest.main()

