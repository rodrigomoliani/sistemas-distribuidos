"""Camada de persistência em disco para nós do cluster Raft/Pull.

Persiste atômica e individualmente:
1. metadados.json: current_term, voted_for, commit_index
2. log.json: lista sequencial de entradas de log [index, term, key, value]
3. banco_comitado.json: estado consolidado da máquina de estados (apenas dados comitados)
"""

import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple


class PersistenciaNo:
    """Gerenciador de armazenamento em disco de um nó com gravações atômicas (fsync)."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

        self.arq_metadados = self.data_dir / "metadados.json"
        self.arq_log = self.data_dir / "log.json"
        self.arq_banco = self.data_dir / "banco_comitado.json"

        # Estado em memória espelhado em disco
        self.current_term: int = 0
        self.voted_for: Optional[int] = None
        self.commit_index: int = 0
        self.log: List[Dict[str, Any]] = []
        self.banco_comitado: Dict[str, str] = {}

        self._carregar_ou_inicializar()

    # ==========================================================
    # Escrita Atômica
    # ==========================================================

    def _gravar_arquivo_atomico(self, caminho: Path, dados: Any) -> None:
        """Grava dados em arquivo temporário com fsync e renomeia atomicamente."""
        caminho_str = str(caminho)
        conteudo = json.dumps(dados, indent=2, ensure_ascii=False)
        with tempfile.NamedTemporaryFile("w", dir=self.data_dir, delete=False, encoding="utf-8") as temp:
            temp.write(conteudo)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = temp.name

        os.replace(temp_path, caminho_str)

    def _carregar_ou_inicializar(self) -> None:
        """Carrega o estado existente do disco ou inicializa estruturas vazias."""
        with self.lock:
            # 1. Metadados
            if self.arq_metadados.exists():
                try:
                    meta = json.loads(self.arq_metadados.read_text(encoding="utf-8"))
                    self.current_term = int(meta.get("current_term", 0))
                    self.voted_for = meta.get("voted_for")
                    self.commit_index = int(meta.get("commit_index", 0))
                except Exception as err:
                    raise RuntimeError(f"Não foi possível carregar metadados: {err}") from err
            else:
                self._persistir_metadados_sem_lock()

            # 2. Log de Operações
            if self.arq_log.exists():
                try:
                    self.log = json.loads(self.arq_log.read_text(encoding="utf-8"))
                except Exception as err:
                    raise RuntimeError(f"Não foi possível carregar log: {err}") from err
            else:
                self._persistir_log_sem_lock()

            # 3. Banco Comitado
            if self.arq_banco.exists():
                try:
                    self.banco_comitado = json.loads(self.arq_banco.read_text(encoding="utf-8"))
                except Exception as err:
                    print(f"[Storage] Aviso ao carregar banco comitado: {err}")
                    self.banco_comitado = {}
            else:
                self._persistir_banco_sem_lock()

            # O log e o commit persistido são a fonte de verdade após um crash.
            # Reconstruir evita que uma atualização parcial dos arquivos exponha
            # dados acima do commit ou perca uma atualização já confirmada.
            if self.commit_index > len(self.log):
                raise ValueError("commit_index persistido ultrapassa o log local")
            banco_recuperado = {}
            for entrada in self.log:
                if int(entrada["index"]) <= self.commit_index:
                    banco_recuperado[entrada["key"]] = entrada["value"]
            if banco_recuperado != self.banco_comitado:
                self.banco_comitado = banco_recuperado
                self._persistir_banco_sem_lock()

    def _persistir_metadados_sem_lock(self) -> None:
        self._gravar_arquivo_atomico(
            self.arq_metadados,
            {
                "current_term": self.current_term,
                "voted_for": self.voted_for,
                "commit_index": self.commit_index,
            },
        )

    def _persistir_log_sem_lock(self) -> None:
        self._gravar_arquivo_atomico(self.arq_log, self.log)

    def _persistir_banco_sem_lock(self) -> None:
        self._gravar_arquivo_atomico(self.arq_banco, self.banco_comitado)

    # ==========================================================
    # Operações de Metadados (Termo e Voto)
    # ==========================================================

    def obter_metadados(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "current_term": self.current_term,
                "voted_for": self.voted_for,
                "commit_index": self.commit_index,
            }

    def atualizar_termo(self, novo_termo: int, voted_for: Optional[int] = None) -> None:
        """Atualiza o termo atual e opcionalmente reseta/define o voto concedido."""
        with self.lock:
            if novo_termo > self.current_term:
                self.current_term = novo_termo
                self.voted_for = voted_for
                self._persistir_metadados_sem_lock()

    def registrar_voto(self, candidate_id: int) -> None:
        """Registra voto concedido para o termo atual."""
        with self.lock:
            self.voted_for = candidate_id
            self._persistir_metadados_sem_lock()

    # ==========================================================
    # Operações do Log
    # ==========================================================

    def ultimo_indice_e_termo(self) -> Tuple[int, int]:
        """Retorna (last_log_index, last_log_term). Se log vazio, retorna (0, 0)."""
        with self.lock:
            if not self.log:
                return 0, 0
            ultimo = self.log[-1]
            return int(ultimo["index"]), int(ultimo["term"])

    def obter_entrada(self, index: int) -> Optional[Dict[str, Any]]:
        """Busca uma entrada específica pelo índice sequencial (1-based)."""
        with self.lock:
            if 1 <= index <= len(self.log):
                entrada = self.log[index - 1]
                if entrada["index"] == index:
                    return dict(entrada)
            # Busca linear como fallback de segurança
            for entrada in self.log:
                if entrada["index"] == index:
                    return dict(entrada)
            return None

    def obter_entradas_a_partir_de(self, start_index: int) -> List[Dict[str, Any]]:
        """Retorna todas as entradas com index >= start_index."""
        with self.lock:
            return [dict(e) for e in self.log if e["index"] >= start_index]

    def anexar_entrada(self, term: int, key: str, value: str) -> Dict[str, Any]:
        """Adiciona uma nova entrada no topo do log (usado pelo líder em novas escritas)."""
        with self.lock:
            last_idx, _ = self.ultimo_indice_e_termo()
            nova_entrada = {
                "index": last_idx + 1,
                "term": term,
                "key": key,
                "value": value,
            }
            self.log.append(nova_entrada)
            self._persistir_log_sem_lock()
            return dict(nova_entrada)

    def truncar_a_partir_de(self, index: int) -> int:
        """Deleta todas as entradas com index >= index (Resolução de divergência).

        Retorna a quantidade de entradas removidas.
        """
        with self.lock:
            if index <= self.commit_index:
                raise ValueError("Não é permitido truncar entradas já comitadas")
            tamanho_original = len(self.log)
            self.log = [e for e in self.log if e["index"] < index]
            removidos = tamanho_original - len(self.log)
            if removidos > 0:
                self._persistir_log_sem_lock()
            return removidos

    def sincronizar_entradas_do_lider(
        self, prev_log_index: int, prev_log_term: int, novas_entradas: List[Dict[str, Any]]
    ) -> Tuple[bool, int]:
        """Aplica a regra de consistência do log (Raft log matching).

        Retorna (sucesso, conflict_index_ou_last_index).
        Se sucesso=False, conflict_index indica onde houve divergência.
        """
        with self.lock:
            last_idx, last_term = self.ultimo_indice_e_termo()

            # 1. Se prev_log_index > last_idx, réplica está desatualizada (faltam dados intermediários)
            if prev_log_index > last_idx:
                return False, last_idx + 1

            # 2. Se prev_log_index > 0, deve existir entrada correspondente com mesmo termo
            if prev_log_index > 0:
                entrada_local = self.obter_entrada(prev_log_index)
                if not entrada_local or entrada_local["term"] != prev_log_term:
                    # Conflito detectado: recua para o ponto conflitante
                    return False, max(1, prev_log_index)

            # 3. Consistência satisfeita até prev_log_index. Inserir ou corrigir novas entradas
            alterado = False
            for entrada in novas_entradas:
                idx = int(entrada["index"])
                termo = int(entrada["term"])

                entrada_existente = self.obter_entrada(idx)
                if entrada_existente:
                    if entrada_existente["term"] != termo:
                        # Divergência encontrada! Trunca o log a partir daqui
                        self.truncar_a_partir_de(idx)
                        self.log.append(dict(entrada))
                        alterado = True
                else:
                    self.log.append(dict(entrada))
                    alterado = True

            if alterado:
                self._persistir_log_sem_lock()

            novo_ultimo_idx, _ = self.ultimo_indice_e_termo()
            return True, novo_ultimo_idx

    # ==========================================================
    # Operações do Banco Comitado (State Machine)
    # ==========================================================

    def avancar_commit(self, novo_commit_index: int) -> List[Dict[str, Any]]:
        """Aplica entradas do log com self.commit_index < index <= novo_commit_index no banco comitado."""
        with self.lock:
            if novo_commit_index <= self.commit_index:
                return []

            aplicadas = []
            for entrada in self.log:
                idx = int(entrada["index"])
                if self.commit_index < idx <= novo_commit_index:
                    self.banco_comitado[entrada["key"]] = entrada["value"]
                    aplicadas.append(dict(entrada))

            self.commit_index = novo_commit_index
            self._persistir_metadados_sem_lock()
            self._persistir_banco_sem_lock()
            return aplicadas

    def ler_comitado(self, key: str) -> Optional[str]:
        """Consulta valor da chave exclusivamente no banco comitado (Cenário 5: isolamento)."""
        with self.lock:
            return self.banco_comitado.get(key)

    def obter_todos_comitados(self) -> Dict[str, str]:
        with self.lock:
            return dict(self.banco_comitado)

