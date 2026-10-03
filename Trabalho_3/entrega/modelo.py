# Emissão de nota simulada e evento de despacho após pagamento aprovado.

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import uuid4

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import json_texto

# Importa catálogo inicial, valores em centavos e validação de itens e totais.
from comum.catalogo import validar_pedido

# Mantém notas simuladas e evita despacho repetido do mesmo pedido.
class Entrega:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self, banco):

        # Executa banco.schema para concluir esta etapa do processamento.
        banco.schema((

            # Preserva o espaço e as quebras de linha originais do texto SQL.
            '\n'

            # Cria a tabela notas somente se ela ainda não existir.
            '            CREATE TABLE IF NOT EXISTS notas (\n'

            # Define as colunas e restrições SQL: pedido_id TEXT PRIMARY KEY, numero TEXT, dados TEXT).
            '                pedido_id TEXT PRIMARY KEY, numero TEXT, dados TEXT);\n'

            # Fornece este valor textual à chamada ou coleção em construção.
            '        '

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ))

    # Registra uma única nota por pedido aprovado e produz o evento de envio.
    def tratar(self, con, tipo, dados):

        # Confere identificação, itens, quantidades, preços e total antes de aplicar uma regra.
        validar_pedido(dados)

        # Prepara identificador usado nesta operação para esta etapa.
        pid = dados["pedido_id"]

        # Confere a condição con.execute('SELECT 1 FROM notas WHERE pedido_id=?', (pid,)).fetchone() antes de executar este bloco.
        if con.execute("SELECT 1 FROM notas WHERE pedido_id=?", (pid,)).fetchone():

            # Termina sem novos eventos, evitando repetir efeitos ou processar uma operação encerrada.
            return []

        # Prepara número da nota simulada para esta etapa.
        numero = str(uuid4())

        # Insere o registro em notas; conflitos são tratados conforme a instrução.
        con.execute(

            # Fornece este valor textual à chamada ou coleção em construção.
            "INSERT INTO notas VALUES (?,?,?)", (pid, numero, json_texto(dados))

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
        print(f"NOTA_SIMULADA {numero} PEDIDO_ENVIADO {pid}", flush=True)

        # Devolve os eventos que o worker assinará e gravará na outbox da mesma transação.
        return [("pedido.enviado", {"pedido_id": pid, "nota_id": numero})]
