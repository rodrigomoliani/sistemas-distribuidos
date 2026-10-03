# Inicialização local dos cinco serviços, Mock e frontend, com logs separados.

# Continua a expressão que prepara os dados desta operação.
"""Executa os serviços locais e encerra somente seus subprocessos."""

# Importa leitura das opções de linha de comando.
import argparse

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa localização do executável Node.js no PATH.
import shutil

# Importa criação e controle dos processos locais iniciados pelo projeto.
import subprocess

# Importa caminho do interpretador Python que está executando este script.
import sys

# Importa relógios, timestamps e pausas do agendamento e dos testes.
import time

# Importa abertura opcional da loja no navegador padrão.
import webbrowser

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import RAIZ

# Importa encerramento da árvore dos subprocessos iniciados pelo projeto.
from comum.processos import encerrar

# Inicia os sete subprocessos locais, observa falhas e encerra a sessão ao terminar.
def main():

    # Prepara leitor das opções de execução para esta etapa.
    parser = argparse.ArgumentParser()

    # Executa parser.add_argument para concluir esta etapa do processamento.
    parser.add_argument("--sem-navegador", action="store_true")

    # Prepara opções recebidas na linha de comando para esta etapa.
    args = parser.parse_args()

    # Prepara caminho do executável Node.js para esta etapa.
    node = shutil.which("node")

    # Confere a condição not node antes de executar este bloco.
    if not node:

        # Interrompe a operação com erro: Instale Node.js >= 20 para servir o frontend.
        raise SystemExit("Instale Node.js >= 20 para servir o frontend.")

    # Prepara processos iniciados por este script para esta etapa.
    processos = []

    # Prepara arquivos de log abertos para esta etapa.
    logs = []

    # Prepara diretório de arquivos para esta etapa.
    pasta = RAIZ / "dados" / "logs"

    # Executa pasta.mkdir para concluir esta etapa do processamento.
    pasta.mkdir(parents=True, exist_ok=True)

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Percorre ('estoque', 'mock_pagamento', 'pagamento', 'entrega', 'promocoes', 'principal', 'frontend') para processar cada servico.
        for servico in (

            # Fornece este valor textual à chamada ou coleção em construção.
            "estoque",

            # Fornece este valor textual à chamada ou coleção em construção.
            "mock_pagamento",

            # Fornece este valor textual à chamada ou coleção em construção.
            "pagamento",

            # Fornece este valor textual à chamada ou coleção em construção.
            "entrega",

            # Fornece este valor textual à chamada ou coleção em construção.
            "promocoes",

            # Fornece este valor textual à chamada ou coleção em construção.
            "principal",

            # Fornece este valor textual à chamada ou coleção em construção.
            "frontend",

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ):

            # Prepara logger ou arquivo de log para esta etapa.
            log = (pasta / f"{servico}.log").open("a", encoding="utf-8")

            # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
            logs.append(log)

            # Prepara comando do subprocesso para esta etapa.
            comando = (

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                [node, "frontend/server.mjs"]

                # Aplica esta iteração ou condição à expressão que está sendo construída.
                if servico == "frontend"

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                else [sys.executable, "-u", "-m", servico]

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

            # Prepara opções específicas de criação no Windows para esta etapa.
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            # Prepara ambiente dos subprocessos para esta etapa.
            ambiente = {**os.environ, "PYTHONUTF8": "1"}

            # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
            processos.append(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    servico,

                    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                    subprocess.Popen(

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        comando,

                        # Define o argumento ou campo cwd desta operação.
                        cwd=RAIZ,

                        # Define o argumento ou campo env desta operação.
                        env=ambiente,

                        # Redireciona a saída padrão do serviço para seu arquivo de log.
                        stdout=log,

                        # Redireciona também as falhas do serviço para o mesmo arquivo de log.
                        stderr=log,

                        # Evita abrir uma janela visível para o subprocesso no Windows.
                        creationflags=flags,

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    ),

                # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                )

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
        print("Loja: http://localhost:8080 | Swagger: http://localhost:8000/docs")

        # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
        print(f"Logs: {pasta}. Ctrl+C encerra todos os serviços locais.")

        # Pausa o ciclo pelo intervalo indicado, evitando ocupar a CPU em espera contínua.
        time.sleep(3)

        # Confere a condição not args.sem_navegador antes de executar este bloco.
        if not args.sem_navegador:

            # Abre o arquivo ou a página indicada, respeitando o modo de execução do script.
            webbrowser.open("http://localhost:8080")

        # Repete o bloco enquanto True permitir continuar.
        while True:

            # Percorre processos para processar cada (nome, processo).
            for nome, processo in processos:

                # Confere a condição processo.poll() is not None antes de executar este bloco.
                if processo.poll() is not None:

                    # Interrompe a operação com erro: .log.
                    raise RuntimeError(

                        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                        f"{nome} encerrou. Consulte {pasta / (nome + '.log')}"

                    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
                    )

            # Pausa o ciclo pelo intervalo indicado, evitando ocupar a CPU em espera contínua.
            time.sleep(1)

    # Trata KeyboardInterrupt sem confundir falha com resultado válido.
    except KeyboardInterrupt:

        # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
        print("Encerrando serviços…")

    # Libera os recursos mesmo se ocorrer uma falha ou interrupção.
    finally:

        # Encerra os processos informados e seus filhos no Windows, aguardando a liberação dos recursos.
        encerrar([processo for _, processo in processos])

        # Percorre logs para processar cada log.
        for log in logs:

            # Fecha a conexão, arquivo ou cliente indicado para liberar seus recursos.
            log.close()

# Executa a entrada do serviço somente quando este módulo é iniciado diretamente.
if __name__ == "__main__":

    # Executa main para concluir esta etapa do processamento.
    main()
