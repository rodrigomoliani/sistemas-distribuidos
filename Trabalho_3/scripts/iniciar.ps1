# Recebe as opções de execução local, broker externo e abertura automática do navegador.
param([switch]$Local, [switch]$SemDocker, [switch]$SemNavegador)

# Interrompe em erros do PowerShell; códigos de programas externos são verificados separadamente.
$ErrorActionPreference = 'Stop'

# Obtém a pasta do trabalho a partir da pasta deste script.
$raizTrabalho = Split-Path -Parent $PSScriptRoot

# Usa a pasta do trabalho como base dos caminhos relativos, mesmo quando ela contém espaços.
Set-Location -LiteralPath $raizTrabalho

# Localiza o Python do ambiente virtual exclusivo deste projeto.
$pythonTrabalho = Join-Path $raizTrabalho '.venv\Scripts\python.exe'

# Cria o ambiente virtual somente quando seu executável ainda não existe.
if (-not (Test-Path -LiteralPath $pythonTrabalho)) {

    # Prefere o launcher Python do Windows se ele estiver disponível.
    if (Get-Command py -ErrorAction SilentlyContinue) {

        # Cria o ambiente virtual com Python 3.12 e dependências isoladas.
        & py -3.12 -m venv .venv

    # Encerra o bloco condicional aberto acima.
    }

    # Usa o comando python como alternativa ao launcher py.
    elseif (Get-Command python -ErrorAction SilentlyContinue) {

        # Cria o ambiente virtual com Python 3.12 e dependências isoladas.
        & python -m venv .venv

    # Encerra o bloco condicional aberto acima.
    }

    # Inicia a alternativa executada quando a condição anterior não foi atendida.
    else {

        # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
        throw 'Instale Python 3.12 e crie o ambiente .venv conforme o README.'

    # Encerra o bloco condicional aberto acima.
    }

    # Verifica se o último programa externo terminou com um código de erro.
    if ($LASTEXITCODE -ne 0) {

        # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
        throw 'Falha ao preparar ambiente Python.'

    # Encerra o bloco condicional aberto acima.
    }

# Encerra o bloco condicional aberto acima.
}

# Instala no ambiente virtual as versões fixadas no requirements.txt.
& $pythonTrabalho -m pip install -r requirements.txt

# Verifica se o último programa externo terminou com um código de erro.
if ($LASTEXITCODE -ne 0) {

    # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
    throw 'Falha ao instalar dependências.'

# Encerra o bloco condicional aberto acima.
}

# Gera as chaves RSA ausentes e preserva as chaves já criadas.
& $pythonTrabalho -m scripts.gerar_chaves

# Verifica se o último programa externo terminou com um código de erro.
if ($LASTEXITCODE -ne 0) {

    # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
    throw 'Falha ao gerar chaves.'

# Encerra o bloco condicional aberto acima.
}

# Escolhe executar os processos Python e Node diretamente nesta máquina.
if ($Local) {

    # Inicia RabbitMQ pelo Docker quando um broker externo não foi solicitado.
    if (-not $SemDocker) {

        # Inicia somente o broker em segundo plano e aguarda seu healthcheck.
        docker compose up -d --wait rabbitmq

        # Verifica se o último programa externo terminou com um código de erro.
        if ($LASTEXITCODE -ne 0) {

            # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
            throw 'Abra o Docker Desktop ou use -Local -SemDocker com RabbitMQ externo.'

        # Encerra o bloco condicional aberto acima.
        }

        # Aponta os processos locais para a porta do RabbitMQ publicada pelo Compose.
        $env:RABBITMQ_URL = 'amqp://trabalho3:trabalho3@localhost:5673/%2F'

    # Encerra o bloco condicional aberto acima.
    }

    # Seleciona a execução que não abre automaticamente a página da loja.
    if ($SemNavegador) {

        # Inicia e acompanha os sete processos, sem abrir o navegador.
        & $pythonTrabalho -m scripts.servicos --sem-navegador

    # Encerra o bloco condicional aberto acima.
    }

    # Inicia a alternativa executada quando a condição anterior não foi atendida.
    else {

        # Inicia os sete processos e abre a loja após as APIs ficarem disponíveis.
        & $pythonTrabalho -m scripts.servicos

    # Encerra o bloco condicional aberto acima.
    }

    # Verifica se o último programa externo terminou com um código de erro.
    if ($LASTEXITCODE -ne 0) {

        # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
        throw 'Os serviços encerraram com erro. Consulte dados/logs.'

    # Encerra o bloco condicional aberto acima.
    }

# Encerra o bloco condicional aberto acima.
}

# Inicia a alternativa executada quando a condição anterior não foi atendida.
else {

    # Rejeita -SemDocker sem -Local porque esse modo depende do Compose.
    if ($SemDocker) {

        # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
        throw '-SemDocker deve acompanhar -Local.'

    # Encerra o bloco condicional aberto acima.
    }

    # Constrói as imagens, inicia todos os contêineres e aguarda sua disponibilidade inicial.
    docker compose up --build -d --wait

    # Verifica se o último programa externo terminou com um código de erro.
    if ($LASTEXITCODE -ne 0) {

        # Interrompe a inicialização e explica a causa da falha na mensagem abaixo.
        throw 'Falha ao iniciar. Confira Docker Desktop e docker compose logs.'

    # Encerra o bloco condicional aberto acima.
    }

    # Mostra os endereços da loja e da documentação interativa da API.
    Write-Host 'Loja: http://localhost:8080 | Swagger: http://localhost:8000/docs'

    # Abre a loja apenas quando a abertura automática não foi desativada.
    if (-not $SemNavegador) {

        # Entrega a URL da loja ao navegador padrão do Windows.
        Start-Process 'http://localhost:8080'

    # Encerra o bloco condicional aberto acima.
    }

# Encerra o bloco condicional aberto acima.
}
