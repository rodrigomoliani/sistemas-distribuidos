# Criação de cobranças por REST e aplicação idempotente dos resultados de webhook.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa requisições HTTP aos serviços REST e às APIs externas.
import httpx

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import json_texto

# Importa catálogo inicial, valores em centavos e validação de itens e totais.
from comum.catalogo import validar_pedido

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import MOCK_URL, WEBHOOK_SECRET, WEBHOOK_URL

# Mantém cobranças e decisões de pagamento no banco do serviço.
class Pagamento:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, banco):

        # Guarda o banco exclusivo do serviço ou cria um banco isolado para o teste.
        self.banco = banco

        # Executa banco.schema para concluir esta etapa do processamento.
        banco.schema((

            # Preserva o espaço e as quebras de linha originais do texto SQL.
            '\n'

            # Cria a tabela cobrancas somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS cobrancas (\n'

            # Define as colunas e restrições SQL: pedido_id TEXT PRIMARY KEY, id TEXT UNIQUE, dados TEXT, checkout_url TEXT, estado TEXT).
            '                pedido_id TEXT PRIMARY KEY, id TEXT UNIQUE, dados TEXT, checkout_url TEXT, estado TEXT);\n'

            # Cria a tabela cancelados somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS cancelados (pedido_id TEXT PRIMARY KEY);\n'

            # Fornece este valor textual à chamada ou coleção em construção.
            '        '

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ))

    # Cancela cobranças pendentes ou solicita a URL de checkout após a reserva.
    def tratar(self, con, tipo, dados):

        # Prepara identificador usado nesta operação para esta etapa.
        pid = dados.get("pedido_id")

        # Confere a condição not isinstance(pid, str) or not pid antes de executar este bloco.
        if not isinstance(pid, str) or not pid:

            # Interrompe a operação com erro: pedido_id inválido.
            raise ValueError("pedido_id inválido")

        # Trata o cancelamento antes da criação para impedir uma reserva ou cobrança tardia.
        if tipo == "pedido.excluido":

            # Insere o registro em cancelados; conflitos são tratados conforme a instrução.
            con.execute("INSERT OR IGNORE INTO cancelados VALUES (?)", (pid,))

            # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
            con.execute(

                # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
                "UPDATE cobrancas SET estado='CANCELADO' WHERE pedido_id=? AND estado='PENDENTE'",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (pid,),

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Confere identificação, itens, quantidades, preços e total antes de aplicar uma regra.
        validar_pedido(dados)

        # Confere a condição con.execute('SELECT 1 FROM cancelados WHERE pedido_id=?', (pid,)).fetchone() antes de executar este bloco.
        if con.execute("SELECT 1 FROM cancelados WHERE pedido_id=?", (pid,)).fetchone():

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Confere a condição con.execute('SELECT 1 FROM cobrancas WHERE pedido_id=?', (pid,)).fetchone() antes de executar este bloco.
        if con.execute("SELECT 1 FROM cobrancas WHERE pedido_id=?", (pid,)).fetchone():

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # pedido_id é a chave de idempotência no provedor; uma repetição não gera outra cobrança.

        # Prepara r para esta etapa.
        r = httpx.post(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            f"{MOCK_URL}/cobrancas",

            # Limita a duração da operação para que uma falha de rede não bloqueie indefinidamente.
            timeout=5,

            # Define os headers HTTP de formato, cache ou autenticação desta requisição.
            headers={"X-API-Key": WEBHOOK_SECRET},

            # Envia estes dados como corpo JSON da requisição HTTP.
            json={

                # Define o campo pedido_id desta estrutura de dados.
                "pedido_id": pid,

                # Define o campo total_centavos desta estrutura de dados.
                "total_centavos": dados["total_centavos"],

                # Define o campo webhook_url desta estrutura de dados.
                "webhook_url": WEBHOOK_URL,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            },

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Transforma respostas HTTP de erro em exceções, evitando tratar falha como sucesso.
        r.raise_for_status()

        # Prepara resposta de criação da cobrança para esta etapa.
        cobranca = r.json()

        # Insere o registro em cobrancas; conflitos são tratados conforme a instrução.
        con.execute(

            # Insere o registro em cobrancas; conflitos são tratados conforme a instrução.
            "INSERT INTO cobrancas VALUES (?,?,?,?,?)",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                pid,

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                cobranca["id"],

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                json_texto(dados),

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                cobranca["checkout_url"],

                # Fornece este valor textual à chamada ou coleção em construção.
                "PENDENTE",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Devolve os eventos que o worker assinará e gravará na outbox da mesma transação.
        return [

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (

                # Fornece este valor textual à chamada ou coleção em construção.
                "pagamento.checkout_criado",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                {"pedido_id": pid, "checkout_url": cobranca["checkout_url"]},

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ]

    # Aplica uma decisão de pagamento, validando valor, cobrança e repetições do resultado.
    def resultado(self, con, entrada):

        # Prepara c para esta etapa.
        c = con.execute(

            # Consulta registros de cobrancas; '?' recebe parâmetros separados do SQL.
            "SELECT * FROM cobrancas WHERE id=? AND pedido_id=?",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (entrada.cobranca_id, str(entrada.pedido_id)),

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        ).fetchone()

        # Confere a condição not c antes de executar este bloco.
        if not c:

            # Interrompe a operação com erro: Cobrança desconhecida.
            raise ValueError("Cobrança desconhecida")

        # Prepara dados da operação para esta etapa.
        dados = json.loads(c["dados"])

        # Confere a condição entrada.total_centavos != dados['total_centavos'] antes de executar este bloco.
        if entrada.total_centavos != dados["total_centavos"]:

            # Interrompe a operação com erro: Valor incorreto.
            raise ValueError("Valor incorreto")

        # Confere a condição c['estado'] == entrada.status antes de executar este bloco.
        if c["estado"] == entrada.status:

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Confere a condição c['estado'] != 'PENDENTE' antes de executar este bloco.
        if c["estado"] != "PENDENTE":

            # Interrompe a operação com erro: Cobrança encerrada com outro estado.
            raise ValueError("Cobrança encerrada com outro estado")

        # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
        con.execute(

            # Atualiza os campos de cobrancas apenas nos registros selecionados pelo WHERE.
            "UPDATE cobrancas SET estado=? WHERE id=?",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (entrada.status, entrada.cobranca_id),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Prepara tipo para esta etapa.
        tipo = (

            # Fornece este valor textual à chamada ou coleção em construção.
            "pagamento.aprovado"

            # Aplica esta iteração ou condição à expressão que está sendo construída.
            if entrada.status == "APROVADO"

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            else "pagamento.recusado"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Devolve os eventos que o worker assinará e gravará na outbox da mesma transação.
        return [(tipo, dados)]
