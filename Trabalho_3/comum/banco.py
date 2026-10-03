# Persistência local de cada microsserviço. A mesma transação grava dados, inbox e outbox.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa acesso ao banco relacional SQLite, mantido pelo próprio serviço.
import sqlite3

# Importa threads, locks e sinais usados para coordenar acesso concorrente.
import threading

# Importa gerenciadores de contexto, responsáveis por iniciar e finalizar recursos.
from contextlib import contextmanager

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import DADOS

# Serializa dados em JSON compacto, preservando os acentos.
def json_texto(valor):

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))

# Encapsula a conexão SQLite e a coordenação entre threads do serviço.
class Banco:

    # Documenta a responsabilidade da classe; a string também fica disponível em Banco.__doc__.
    """SQLite próprio de cada serviço; transações incluem inbox/outbox."""

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, servico, caminho=None):

        # Prepara caminho do banco ou arquivo para esta etapa.
        arquivo = caminho or DADOS / f"{servico}.sqlite3"

        # Confere a condição str(arquivo) != ':memory:' antes de executar este bloco.
        if str(arquivo) != ":memory:":

            # Importa caminhos de arquivo portáveis por meio de Path.
            from pathlib import Path

            # Cria a pasta dos dados, incluindo diretórios superiores; não falha se já existir.
            Path(arquivo).parent.mkdir(parents=True, exist_ok=True)

        # Cria um lock reentrante para proteger a conexão SQLite entre threads.
        self.lock = threading.RLock()

        # Abre a conexão SQLite com transações gerenciadas explicitamente pelo código.
        self.con = sqlite3.connect(

            # Permite uso entre threads sob o lock e desativa transações implícitas para controlar COMMIT/ROLLBACK.
            str(arquivo), check_same_thread=False, isolation_level=None

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Permite acessar as colunas dos resultados pelo nome, usando sqlite3.Row.
        self.con.row_factory = sqlite3.Row

        # Ativa WAL para permitir consultas enquanto outra conexão grava alterações no SQLite.
        self.con.execute("PRAGMA journal_mode=WAL")

        # Aguarda até 5000 milissegundos se outro acesso mantiver o banco bloqueado.
        self.con.execute("PRAGMA busy_timeout=5000")

        # Cria a tabela inbox somente se ela ainda não existir.
        self.con.executescript((

            # Preserva o espaço e as quebras de linha originais do texto SQL.
            '\n'

            # Cria a tabela inbox somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS inbox (event_id TEXT PRIMARY KEY);\n'

            # Cria a tabela outbox somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS outbox (\n'

            # Define as colunas e restrições SQL: id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, corpo BLOB NOT NULL).
            '                id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, corpo BLOB NOT NULL);\n'

            # Fornece este valor textual à chamada ou coleção em construção.
            '        '

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ))

    # Transforma a função em gerenciador de contexto para cuidar de início e finalização.
    @contextmanager

    # Agrupa operações: confirma todas com COMMIT ou desfaz todas com ROLLBACK.
    def transacao(self):

        # Adquire o lock antes de acessar a conexão compartilhada entre threads.
        with self.lock:

            # Inicia a transação e obtém a reserva de escrita do SQLite.
            self.con.execute("BEGIN IMMEDIATE")

            # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
            try:

                # Empresta a conexão ao bloco 'with'; o código retoma aqui quando o bloco termina.
                yield self.con

                # Confirma todas as alterações feitas nesta transação.
                self.con.execute("COMMIT")

            # Trata BaseException sem confundir falha com resultado válido.
            except BaseException:

                # Desfaz as alterações porque a operação terminou com erro.
                self.con.execute("ROLLBACK")

                # Propaga a falha original depois de desfazer a transação.
                raise

    # Consulta o SQLite com proteção do lock e devolve todas as linhas encontradas.
    def ler(self, sql, parametros=()):

        # Adquire o lock antes de acessar a conexão compartilhada entre threads.
        with self.lock:

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return self.con.execute(sql, parametros).fetchall()

    # Cria as tabelas necessárias usando um conjunto de comandos SQL.
    def schema(self, sql):

        # Adquire o lock antes de acessar a conexão compartilhada entre threads.
        with self.lock:

            # Executa as instruções de criação de tabelas fornecidas pelo modelo do serviço.
            self.con.executescript(sql)

    # Fecha a conexão SQLite com acesso protegido pelo lock.
    def fechar(self):

        # Adquire o lock antes de acessar a conexão compartilhada entre threads.
        with self.lock:

            # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
            self.con.close()

# Assina o evento e o grava na outbox da transação atual, sem publicar por HTTP.
def emitir(con, assinador, tipo, dados):

    # Insere o registro em outbox; conflitos são tratados conforme a instrução.
    con.execute(

        # Insere o registro em outbox; conflitos são tratados conforme a instrução.
        "INSERT INTO outbox(tipo, corpo) VALUES (?, ?)",

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        (tipo, assinador.assinar(tipo, dados)),

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    )
