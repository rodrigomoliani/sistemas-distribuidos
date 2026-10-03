# Reserva atômica e devolução única de produtos, usando o SQLite do Estoque.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import json_texto

# Importa catálogo inicial, valores em centavos e validação de itens e totais.
from comum.catalogo import CATALOGO, ESTOQUE_INICIAL, validar_pedido

# Mantém produtos e reservas no banco próprio do Estoque.
class Estoque:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, banco):

        # Guarda o banco exclusivo do serviço ou cria um banco isolado para o teste.
        self.banco = banco

        # Executa banco.schema para concluir esta etapa do processamento.
        banco.schema((

            # Preserva o espaço e as quebras de linha originais do texto SQL.
            '\n'

            # Cria a tabela produtos somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS produtos (\n'

            # Define as colunas e restrições SQL: id TEXT PRIMARY KEY, nome TEXT, categoria TEXT,.
            '                id TEXT PRIMARY KEY, nome TEXT, categoria TEXT,\n'

            # Define as colunas e restrições SQL: preco_centavos INTEGER, quantidade INTEGER CHECK(quantidade >= 0)).
            '                preco_centavos INTEGER, quantidade INTEGER CHECK(quantidade >= 0));\n'

            # Cria a tabela reservas somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS reservas (\n'

            # Define as colunas e restrições SQL: pedido_id TEXT PRIMARY KEY, itens TEXT, estado TEXT).
            '                pedido_id TEXT PRIMARY KEY, itens TEXT, estado TEXT);\n'

            # Fornece este valor textual à chamada ou coleção em construção.
            '        '

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ))

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with banco.transacao() as con:

            # Percorre CATALOGO.items() para processar cada (pid, p).
            for pid, p in CATALOGO.items():

                # Insere o registro em produtos; conflitos são tratados conforme a instrução.
                con.execute(

                    # Insere o registro em produtos; conflitos são tratados conforme a instrução.
                    "INSERT OR IGNORE INTO produtos VALUES (?,?,?,?,?)",

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    (

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        pid,

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        p["nome"],

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        p["categoria"],

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        p["preco_centavos"],

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        ESTOQUE_INICIAL,

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    ),

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

    # Devolve o catálogo do serviço de Estoque ou encaminha sua consulta REST no Gateway.
    def produtos(self):

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return [dict(p) for p in self.banco.ler("SELECT * FROM produtos ORDER BY id")]

    # Reserva os itens de um pedido ou devolve uma reserva registrada, sem repetir efeitos.
    def tratar(self, con, tipo, dados):

        # Prepara identificador usado nesta operação para esta etapa.
        pid = dados.get("pedido_id")

        # Confere a condição not isinstance(pid, str) or not pid antes de executar este bloco.
        if not isinstance(pid, str) or not pid:

            # Interrompe a operação com erro: pedido_id inválido.
            raise ValueError("pedido_id inválido")

        # Prepara registro existente para esta etapa.
        anterior = con.execute(

            # Fornece este valor textual à chamada ou coleção em construção.
            "SELECT * FROM reservas WHERE pedido_id=?", (pid,)

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ).fetchone()

        # Trata o cancelamento antes da criação para impedir uma reserva ou cobrança tardia.
        if tipo == "pedido.excluido":

            # Confere a condição anterior and anterior['estado'] == 'reservado' antes de executar este bloco.
            if anterior and anterior["estado"] == "reservado":

                # Percorre json.loads(anterior['itens']) para processar cada item.
                for item in json.loads(anterior["itens"]):

                    # Atualiza os campos de produtos apenas nos registros selecionados pelo WHERE.
                    con.execute(

                        # Atualiza os campos de produtos apenas nos registros selecionados pelo WHERE.
                        "UPDATE produtos SET quantidade=quantidade+? WHERE id=?",

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        (item["quantidade"], item["produto_id"]),

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    )

            # Insere o registro em reservas; conflitos são tratados conforme a instrução.
            con.execute(

                # Insere o registro em reservas; conflitos são tratados conforme a instrução.
                "INSERT INTO reservas VALUES (?,?,?) ON CONFLICT(pedido_id) DO UPDATE SET estado='excluido'",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (pid, "[]", "excluido"),

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Confere identificação, itens, quantidades, preços e total antes de aplicar uma regra.
        validar_pedido(dados)

        # Confere a condição anterior antes de executar este bloco.
        if anterior:

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Percorre dados['itens'] para processar cada item.
        for item in dados["itens"]:

            # Prepara p para esta etapa.
            p = con.execute(

                # Fornece este valor textual à chamada ou coleção em construção.
                "SELECT * FROM produtos WHERE id=?", (item["produto_id"],)

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ).fetchone()

            # Confere a condição not p or p['quantidade'] < item['quantidade'] antes de executar este bloco.
            if not p or p["quantidade"] < item["quantidade"]:

                # Insere o registro em reservas; conflitos são tratados conforme a instrução.
                con.execute(

                    # Fornece este valor textual à chamada ou coleção em construção.
                    "INSERT INTO reservas VALUES (?,?,?)", (pid, "[]", "indisponivel")

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

                # Devolve os eventos que o worker assinará e gravará na outbox da mesma transação.
                return [

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    (

                        # Fornece este valor textual à chamada ou coleção em construção.
                        "estoque.indisponivel",

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        {"pedido_id": pid, "motivo": "Estoque insuficiente"},

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    )

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                ]

            # Confere a condição p['preco_centavos'] != item['preco_unitario_centavos'] antes de executar este bloco.
            if p["preco_centavos"] != item["preco_unitario_centavos"]:

                # Interrompe a operação com erro: Preço diverge do estoque.
                raise ValueError("Preço diverge do estoque")

        # Percorre dados['itens'] para processar cada item.
        for item in dados["itens"]:

            # Atualiza os campos de produtos apenas nos registros selecionados pelo WHERE.
            con.execute(

                # Atualiza os campos de produtos apenas nos registros selecionados pelo WHERE.
                "UPDATE produtos SET quantidade=quantidade-? WHERE id=?",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (item["quantidade"], item["produto_id"]),

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Insere o registro em reservas; conflitos são tratados conforme a instrução.
        con.execute(

            # Insere o registro em reservas; conflitos são tratados conforme a instrução.
            "INSERT INTO reservas VALUES (?,?,?)",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (pid, json_texto(dados["itens"]), "reservado"),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Devolve os eventos que o worker assinará e gravará na outbox da mesma transação.
        return [("pedido.estoque_ok", dados)]
