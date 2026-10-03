# Inscrições em promoções: versões crescentes impedem que um evento antigo reative o cadastro.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import UUID

# Importa validação de endereço de e-mail sem consultar a entrega no domínio.
from email_validator import EmailNotValidError, validate_email

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import json_texto

# Persiste interesses e o registro de mensagens promocionais.
class Promocoes:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, banco):

        # Guarda o banco exclusivo do serviço ou cria um banco isolado para o teste.
        self.banco = banco

        # Executa banco.schema para concluir esta etapa do processamento.
        banco.schema((

            # Preserva o espaço e as quebras de linha originais do texto SQL.
            '\n'

            # Cria a tabela interesses somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS interesses (\n'

            # Define as colunas e restrições SQL: cliente TEXT PRIMARY KEY, email TEXT, categorias TEXT, versao INTEGER).
            '                cliente TEXT PRIMARY KEY, email TEXT, categorias TEXT, versao INTEGER);\n'

            # Cria a tabela envios somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS envios (\n'

            # Define as colunas e restrições SQL: id TEXT PRIMARY KEY, email TEXT, assunto TEXT, texto TEXT,.
            '                id TEXT PRIMARY KEY, email TEXT, assunto TEXT, texto TEXT,\n'

            # Define as colunas e restrições SQL: modo TEXT, enviado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))).
            "                modo TEXT, enviado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));\n"

            # Fornece este valor textual à chamada ou coleção em construção.
            '        '

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ))

    # Valida o cadastro e aceita apenas uma versão mais recente dos interesses.
    def tratar(self, con, tipo, dados):

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Prepara cliente HTTP ou identificador do consumidor para esta etapa.
            cliente = str(UUID(dados["cliente"]))

            # Prepara adaptador ou endereço de e-mail para esta etapa.
            email = validate_email(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                dados["email"], check_deliverability=False

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            ).normalized

            # Prepara categorias do evento de inscrição para esta etapa.
            cats = dados["categorias"]

            # Prepara versão crescente do cadastro para esta etapa.
            versao = dados["versao"]

            # Confere a condição not isinstance(cats, list) or not all((isinstance(c, str) and c in 'ABC' and (len(c) == 1) for c in cats)) antes de executar este bloco.
            if not isinstance(cats, list) or not all(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                isinstance(c, str) and c in "ABC" and len(c) == 1 for c in cats

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ):

                # Interrompe a operação com erro: Categorias inválidas.
                raise ValueError("Categorias inválidas")

            # Confere a condição type(versao) is not int or versao < 1 antes de executar este bloco.
            if type(versao) is not int or versao < 1:

                # Interrompe a operação com erro: Versão inválida.
                raise ValueError("Versão inválida")

        # Trata (KeyError, TypeError, AttributeError, EmailNotValidError) sem confundir falha com resultado válido.
        except (KeyError, TypeError, AttributeError, EmailNotValidError) as erro:

            # Interrompe a operação com erro: Interesse inválido.
            raise ValueError("Interesse inválido") from erro

        # Insere o registro em interesses; conflitos são tratados conforme a instrução.
        con.execute(

            # Insere o registro em interesses; conflitos são tratados conforme a instrução.
            "INSERT INTO interesses VALUES (?,?,?,?) ON CONFLICT(cliente) DO UPDATE SET "

            # Fornece este valor textual à chamada ou coleção em construção.
            "email=excluded.email,categorias=excluded.categorias,versao=excluded.versao "

            # Aceita a atualização somente quando a versão recebida é mais recente que a persistida.
            "WHERE excluded.versao > interesses.versao",

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            (cliente, email, json_texto(sorted(set(cats))), versao),

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
        return []
