# Encerramento dos subprocessos que os scripts deste projeto iniciaram.

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa criação e controle dos processos locais iniciados pelo projeto.
import subprocess

# Encerra os processos informados e seus filhos no Windows, aguardando a liberação dos recursos.
def encerrar(processos):

    # Continua a expressão que prepara os dados desta operação.
    """Encerra também o interpretador filho do launcher de venv no Windows."""

    # Percorre reversed(processos) para processar cada processo.
    for processo in reversed(processos):

        # Confere a condição processo.poll() is not None antes de executar este bloco.
        if processo.poll() is not None:

            # Ignora este registro e segue para o próximo, sem executar o restante do ciclo.
            continue

        # Confere a condição os.name == 'nt' antes de executar este bloco.
        if os.name == "nt":

            # Executa subprocess.run para concluir esta etapa do processamento.
            subprocess.run(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                ["taskkill", "/PID", str(processo.pid), "/T", "/F"],

                # Redireciona a saída padrão do serviço para seu arquivo de log.
                stdout=subprocess.DEVNULL,

                # Redireciona também as falhas do serviço para o mesmo arquivo de log.
                stderr=subprocess.DEVNULL,

                # Evita abrir uma janela visível para o subprocesso no Windows.
                creationflags=subprocess.CREATE_NO_WINDOW,

                # Define o argumento ou campo check desta operação.
                check=False,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Executa a alternativa quando a condição anterior não foi satisfeita.
        else:

            # Executa processo.terminate para concluir esta etapa do processamento.
            processo.terminate()

    # Percorre processos para processar cada processo.
    for processo in processos:

        # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
        try:

            # Executa processo.wait para concluir esta etapa do processamento.
            processo.wait(timeout=10)

        # Trata subprocess.TimeoutExpired sem confundir falha com resultado válido.
        except subprocess.TimeoutExpired:

            # Executa processo.kill para concluir esta etapa do processamento.
            processo.kill()

            # Executa processo.wait para concluir esta etapa do processamento.
            processo.wait()
