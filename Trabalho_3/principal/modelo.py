# Estado e histórico dos pedidos no Gateway, com proteção contra eventos atrasados.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import json_texto

# Prepara nomes de estados para cada evento recebido para esta etapa.
ESTADOS = {

    # Define o campo pedido.estoque_ok desta estrutura de dados.
    "pedido.estoque_ok": "Estoque Confirmado",

    # Define o campo estoque.indisponivel desta estrutura de dados.
    "estoque.indisponivel": "Estoque Indisponível",

    # Define o campo pagamento.aprovado desta estrutura de dados.
    "pagamento.aprovado": "Pagamento Aprovado",

    # Define o campo pagamento.recusado desta estrutura de dados.
    "pagamento.recusado": "Pagamento Recusado",

    # Define o campo pedido.enviado desta estrutura de dados.
    "pedido.enviado": "Pedido Enviado",

    # Define o campo pagamento.checkout_criado desta estrutura de dados.
    "pagamento.checkout_criado": "Aguardando Pagamento",

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
}

# Prepara prioridade dos estados para evitar regressões para esta etapa.
ORDEM = {

    # Define o campo Pedido Criado desta estrutura de dados.
    "Pedido Criado": 0,

    # Define o campo Estoque Confirmado desta estrutura de dados.
    "Estoque Confirmado": 1,

    # Define o campo Aguardando Pagamento desta estrutura de dados.
    "Aguardando Pagamento": 2,

    # Define o campo Pagamento Aprovado desta estrutura de dados.
    "Pagamento Aprovado": 3,

    # Define o campo Pedido Enviado desta estrutura de dados.
    "Pedido Enviado": 4,

    # Define o campo Estoque Indisponível desta estrutura de dados.
    "Estoque Indisponível": 5,

    # Define o campo Pagamento Recusado desta estrutura de dados.
    "Pagamento Recusado": 5,

    # Define o campo Pedido Cancelado desta estrutura de dados.
    "Pedido Cancelado": 5,

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
}

# Mantém estado, histórico de pedidos e interesses no Gateway.
class Principal:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, banco):

        # Guarda o banco exclusivo do serviço ou cria um banco isolado para o teste.
        self.banco = banco

        # Executa banco.schema para concluir esta etapa do processamento.
        banco.schema((

            # Preserva o espaço e as quebras de linha originais do texto SQL.
            '\n'

            # Cria a tabela pedidos somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS pedidos (\n'

            # Define as colunas e restrições SQL: id TEXT PRIMARY KEY, cliente TEXT, dados TEXT, estado TEXT,.
            '                id TEXT PRIMARY KEY, cliente TEXT, dados TEXT, estado TEXT,\n'

            # Define as colunas e restrições SQL: checkout_url TEXT, nota_id TEXT, encerrado INTEGER DEFAULT 0).
            '                checkout_url TEXT, nota_id TEXT, encerrado INTEGER DEFAULT 0);\n'

            # Cria a tabela historico somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS historico (\n'

            # Define as colunas e restrições SQL: id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id TEXT, cliente TEXT,.
            '                id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id TEXT, cliente TEXT,\n'

            # Define as colunas e restrições SQL: tipo TEXT, dados TEXT, criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),.
            "                tipo TEXT, dados TEXT, criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),\n"

            # Define as colunas e restrições SQL: UNIQUE(pedido_id, tipo)).
            '                UNIQUE(pedido_id, tipo));\n'

            # Cria a tabela interesses somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS interesses (\n'

            # Define as colunas e restrições SQL: cliente TEXT PRIMARY KEY, email TEXT, categorias TEXT, versao INTEGER).
            '                cliente TEXT PRIMARY KEY, email TEXT, categorias TEXT, versao INTEGER);\n'

            # Fornece este valor textual à chamada ou coleção em construção.
            '        '

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ))

    # Adiciona uma mudança de pedido ao histórico, sem duplicar o mesmo tipo de evento.
    def registrar(self, con, pid, tipo, extras=None):

        # Prepara p para esta etapa.
        p = con.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()

        # Prepara envelope verificado para esta etapa.
        evento = {

            # Define o campo pedido_id desta estrutura de dados.
            "pedido_id": pid,

            # Define o campo estado desta estrutura de dados.
            "estado": p["estado"],

            # Define o campo tipo desta estrutura de dados.
            "tipo": tipo,

            # Define o campo checkout_url desta estrutura de dados.
            "checkout_url": p["checkout_url"],

            # Define o campo nota_id desta estrutura de dados.
            "nota_id": p["nota_id"],

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            **(extras or {}),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

        # Insere o registro em historico; conflitos são tratados conforme a instrução.
        con.execute(

            # Insere o registro em historico; conflitos são tratados conforme a instrução.
            "INSERT OR IGNORE INTO historico(pedido_id,cliente,tipo,dados) VALUES (?,?,?,?)",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (pid, p["cliente"], tipo, json_texto(evento)),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Consulta o estado persistido; no Mock devolve apenas os dados públicos da cobrança.
    def consultar(self, cliente, pid=None):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        where, parametros = "cliente=?", [cliente]

        # Confere a condição pid antes de executar este bloco.
        if pid:

            # Continua a expressão que prepara os dados desta operação.
            where += " AND id=?"

            # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
            parametros.append(pid)

        # Prepara resultado da consulta para esta etapa.
        saida = []

        # Percorre self.banco.ler(f'SELECT * FROM pedidos WHERE {where} ORDER BY rowid DESC', parametros) para processar cada p.
        for p in self.banco.ler(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            f"SELECT * FROM pedidos WHERE {where} ORDER BY rowid DESC", parametros

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ):

            # Prepara mudanças registradas do pedido para esta etapa.
            historico = [

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                {**json.loads(h["dados"]), "id": h["id"], "criado_em": h["criado_em"]}

                # Aplica esta iteração ou condição à expressão que está sendo construída.
                for h in self.banco.ler(

                    # Fornece este valor textual à chamada ou coleção em construção.
                    "SELECT * FROM historico WHERE pedido_id=? ORDER BY id", (p["id"],)

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ]

            # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
            saida.append(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                {

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    **json.loads(p["dados"]),

                    # Define o campo estado desta estrutura de dados.
                    "estado": p["estado"],

                    # Define o campo checkout_url desta estrutura de dados.
                    "checkout_url": p["checkout_url"],

                    # Define o campo nota_id desta estrutura de dados.
                    "nota_id": p["nota_id"],

                    # Define o campo historico desta estrutura de dados.
                    "historico": historico,

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                }

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return saida

    # Aplica estados monotônicos e publica exclusão após falta de estoque ou recusa.
    def tratar(self, con, tipo, dados):

        # Prepara identificador usado nesta operação para esta etapa.
        pid = dados.get("pedido_id")

        # Confere a condição not isinstance(pid, str) or not pid antes de executar este bloco.
        if not isinstance(pid, str) or not pid:

            # Interrompe a operação com erro: pedido_id inválido.
            raise ValueError("pedido_id inválido")

        # Prepara p para esta etapa.
        p = con.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()

        # Confere a condição not p or p['encerrado'] antes de executar este bloco.
        if not p or p["encerrado"]:

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Prepara estado correspondente ao evento para esta etapa.
        estado = ESTADOS[tipo]

        # Confere a condição tipo == 'pagamento.checkout_criado' antes de executar este bloco.
        if tipo == "pagamento.checkout_criado":

            # Prepara url para esta etapa.
            url = dados.get("checkout_url")

            # Confere a condição not isinstance(url, str) or not url.startswith(('http://', 'https://')) antes de executar este bloco.
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):

                # Interrompe a operação com erro: Checkout inválido.
                raise ValueError("Checkout inválido")

            # Atualiza os campos de pedidos apenas nos registros selecionados pelo WHERE.
            con.execute("UPDATE pedidos SET checkout_url=? WHERE id=?", (url, pid))

        # Confere a condição tipo == 'pedido.enviado' antes de executar este bloco.
        if tipo == "pedido.enviado":

            # Atualiza os campos de pedidos apenas nos registros selecionados pelo WHERE.
            con.execute(

                # Fornece este valor textual à chamada ou coleção em construção.
                "UPDATE pedidos SET nota_id=? WHERE id=?", (dados["nota_id"], pid)

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Confere a condição ORDEM[estado] > ORDEM[p['estado']] antes de executar este bloco.
        if ORDEM[estado] > ORDEM[p["estado"]]:

            # Atualiza os campos de pedidos apenas nos registros selecionados pelo WHERE.
            con.execute("UPDATE pedidos SET estado=? WHERE id=?", (estado, pid))

        # Grava a mudança do pedido no histórico que será enviado pelo SSE.
        self.registrar(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            con, pid, tipo, {"notificacao": estado, "motivo": dados.get("motivo")}

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a condição tipo in ('estoque.indisponivel', 'pagamento.recusado') antes de executar este bloco.
        if tipo in ("estoque.indisponivel", "pagamento.recusado"):

            # Atualiza os campos de pedidos apenas nos registros selecionados pelo WHERE.
            con.execute("UPDATE pedidos SET encerrado=1 WHERE id=?", (pid,))

            # Devolve os eventos que o worker assinará e gravará na outbox da mesma transação.
            return [("pedido.excluido", {"pedido_id": pid, "motivo": estado})]

        # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
        return []
