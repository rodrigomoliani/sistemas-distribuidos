# Script de inicialização do ambiente e dos microsserviços do Trabalho 3
param(
    [switch]$Local,
    [switch]$SemDocker,
    [switch]$SemNavegador
)

$ErrorActionPreference = 'Stop'
$raizTrabalho = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raizTrabalho

$pythonTrabalho = Join-Path $raizTrabalho '.venv\Scripts\python.exe'

# Criação do ambiente virtual se não existir
if (-not (Test-Path -LiteralPath $pythonTrabalho)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
    } else {
        throw 'Instale Python 3.12 e crie o ambiente .venv conforme o README.'
    }

    if ($LASTEXITCODE -ne 0) {
        throw 'Falha ao preparar ambiente Python.'
    }
}

# Instalação de dependências e geração de chaves RSA
& $pythonTrabalho -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao instalar dependências.'
}

& $pythonTrabalho -m scripts.gerar_chaves
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao gerar chaves.'
}

# Execução em modo Local
if ($Local) {
    if (-not $SemDocker) {
        docker compose up -d --wait rabbitmq
        if ($LASTEXITCODE -ne 0) {
            throw 'Abra o Docker Desktop ou use -Local -SemDocker com RabbitMQ externo.'
        }
        $env:RABBITMQ_URL = 'amqp://trabalho3:trabalho3@localhost:5673/%2F'
    }

    if ($SemNavegador) {
        & $pythonTrabalho -m scripts.servicos --sem-navegador
    } else {
        & $pythonTrabalho -m scripts.servicos
    }

    if ($LASTEXITCODE -ne 0) {
        throw 'Os serviços encerraram com erro. Consulte dados/logs.'
    }
} else {
    # Execução completa via Docker Compose
    if ($SemDocker) {
        throw '-SemDocker deve acompanhar -Local.'
    }

    docker compose up --build -d --wait
    if ($LASTEXITCODE -ne 0) {
        throw 'Falha ao iniciar. Confira Docker Desktop e docker compose logs.'
    }

    Write-Host 'Loja: http://localhost:8080 | Swagger: http://localhost:8000/docs'
    if (-not $SemNavegador) {
        Start-Process 'http://localhost:8080'
    }
}
