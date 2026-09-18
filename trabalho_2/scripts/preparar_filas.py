# Prepara a topologia AMQP e, opcionalmente, limpa mensagens da sessão anterior.
# Execute --limpar somente após encerrar TODOS os processos, inclusive Promoções.
# A verificação de consumidores não detecta um produtor que continua publicando.

# Lê a opção --limpar passada no terminal.
import argparse

# Reutiliza nomes de filas, conexão e declarações, evitando topologias divergentes.
from comum.mensageria import FILAS, conectar, declarar_topologia


# Por padrão só declara a topologia; limpar=True também descarta mensagens pendentes.
def preparar(limpar=False):

    # [AMQP VIA COMUM] Abre uma conexão com o broker usando conectar.
    conexao = conectar()

    # Garante tentativa de fechar a conexão ao terminar ou falhar.
    try:

        # [AMQP: CANAL] Abre um canal lógico na conexão.
        canal = conexao.channel()

        # [AMQP VIA COMUM] Declara as duas exchanges, seis filas e bindings.
        declarar_topologia(canal)

        # Só entra no caminho de descarte quando a limpeza foi solicitada.
        if limpar:
            # Confere todas as filas antes de remover qualquer mensagem.

            # [AMQP: CONSULTA] Declaração passiva consulta cada fila sem criá-la.
            # consumer_count informa consumidores ativos; any para ao encontrar algum.
            # A conferência vem antes do primeiro purge, mas não é uma trava contra
            # processos novos que iniciem entre essa consulta e a limpeza.
            if any(canal.queue_declare(queue=fila, passive=True).method.consumer_count for fila in FILAS):

                # Bloqueia a limpeza se detectar consumidor ativo em uma fila.
                raise RuntimeError("Encerre todos os processos antes de limpar as filas.")

            # Percorre os nomes das seis filas da aplicação.
            for fila in FILAS:

                # [AMQP: LIMPEZA] queue_purge descarta as mensagens prontas dessa fila.
                # Não remove a fila nem as bindings. Operação usada só em sessões paradas.
                canal.queue_purge(queue=fila)

        # Registra a preparação e informa se a limpeza foi solicitada.
        print("Topologia pronta: duas exchanges e seis filas." + (" Filas limpas." if limpar else ""))

    # Executa também quando ocorre exceção dentro do bloco.
    finally:

        # Consulta o estado local antes de tentar fechar.
        if conexao.is_open:

            # [AMQP: FECHAMENTO] Encerra a conexão de preparação.
            conexao.close()


# Executa o parser somente ao iniciar como programa.
if __name__ == "__main__":

    # Cria o parser de argumentos do terminal.
    parser = argparse.ArgumentParser()

    # store_true transforma a presença de --limpar em True; ausência em False.
    parser.add_argument("--limpar", action="store_true", help="Limpar somente com todos os processos parados")

    # Interpreta os argumentos e chama a preparação com a escolha recebida.
    preparar(parser.parse_args().limpar)
