import json
import sqlite3
import threading
from contextlib import contextmanager

from comum.config import DADOS


def json_texto(valor):
    """Serializa dados em JSON compacto, preservando caracteres UTF-8."""
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


class Banco:
    """Gerenciador SQLite do microsserviço com suporte a transações atômicas e outbox/inbox."""

    def __init__(self, servico, caminho=None):
        arquivo = caminho or DADOS / f"{servico}.sqlite3"
        if str(arquivo) != ":memory:":
            from pathlib import Path
            Path(arquivo).parent.mkdir(parents=True, exist_ok=True)

        self.lock = threading.RLock()
        self.con = sqlite3.connect(
            str(arquivo), check_same_thread=False, isolation_level=None
        )
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA busy_timeout=5000")

        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS inbox (event_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, corpo BLOB NOT NULL);
        """)

    @contextmanager
    def transacao(self):
        """Gerenciador de contexto para transação SQLite atômica (BEGIN IMMEDIATE / COMMIT / ROLLBACK)."""
        with self.lock:
            self.con.execute("BEGIN IMMEDIATE")
            try:
                yield self.con
                self.con.execute("COMMIT")
            except BaseException:
                self.con.execute("ROLLBACK")
                raise

    def ler(self, sql, parametros=()):
        """Executa consulta protegida por lock e retorna todas as linhas."""
        with self.lock:
            return self.con.execute(sql, parametros).fetchall()

    def schema(self, sql):
        """Executa scripts de criação de tabelas e esquemas."""
        with self.lock:
            self.con.executescript(sql)

    def fechar(self):
        """Encerra a conexão com o banco de dados."""
        with self.lock:
            self.con.close()


def emitir(con, assinador, tipo, dados):
    """Assina digitalmente o evento e o grava na outbox na transação corrente."""
    con.execute(
        "INSERT INTO outbox(tipo, corpo) VALUES (?, ?)",
        (tipo, assinador.assinar(tipo, dados)),
    )
