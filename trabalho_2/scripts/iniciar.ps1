# Inicializador da demonstração: prepara RabbitMQ e abre os sete terminais.
# Execute após encerrar TODOS os serviços da sessão anterior.
# Os comandos de Docker preparam a infraestrutura; os eventos da aplicação usam AMQP.

# Declara os parâmetros opcionais aceitos pelo script.
param(

    # Probabilidade entre 0 e 1, com padrão 0.5; double aceita frações.
    [ValidateRange(0, 1)][double]$ProbAprovacao = 0.5,

    # Intervalo das promoções em segundos, de 0.1 a 3600, com padrão 5.
    [ValidateRange(0.1, 3600)][double]$IntervaloPromocoes = 5
)

# Faz erros dos cmdlets interromperem o script; programas externos também
# precisam da verificação explícita de LASTEXITCODE feita abaixo.
$ErrorActionPreference = 'Stop'

# PSScriptRoot é a pasta scripts; sua pasta pai é a raiz do trabalho.
$taskDir = Split-Path -Parent $PSScriptRoot

# Define a raiz como diretório atual para encontrar compose.yaml e módulos Python.
# LiteralPath trata espaços e caracteres do caminho literalmente.
Set-Location -LiteralPath $taskDir

# Monta o caminho do Python do ambiente virtual do trabalho.
$taskPython = Join-Path $taskDir '.venv\Scripts\python.exe'

# Verifica se o executável esperado existe antes de iniciar a infraestrutura.
if (-not (Test-Path -LiteralPath $taskPython)) {

    # Interrompe com orientação de instalação quando falta o ambiente virtual.
    throw 'Crie .venv e instale requirements.txt conforme o README.'
}

# Sobe o broker em segundo plano (-d) e espera o healthcheck (--wait).
# Este comando prepara o contêiner; não publica pedidos ou promoções.
docker compose up -d --wait

# Se o programa docker falhou, não continua abrindo os serviços.
if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar RabbitMQ. Verifique Docker Desktop.' }

# O operador & executa o Python pelo caminho guardado. -m inicia um módulo.
# Prepara chaves locais, preservando privadas já existentes.
& $taskPython -m scripts.gerar_chaves

# Interrompe se a preparação de chaves falhar.
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar chaves.' }

# [AMQP VIA PYTHON] Declara a topologia e limpa mensagens da sessão anterior.
# O script Python verifica consumidores ativos antes de executar queue_purge.
& $taskPython -m scripts.preparar_filas --limpar

# Interrompe se houver falha ou consumidores de uma sessão anterior.
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar filas. Encerre a sessão anterior.' }

# Exporta a probabilidade para os processos filhos. InvariantCulture usa ponto
# decimal, como Python espera, independentemente da configuração regional.
$env:PROB_APROVACAO = $ProbAprovacao.ToString([Globalization.CultureInfo]::InvariantCulture)

# Exporta o intervalo das promoções usando também ponto decimal.
$env:INTERVALO_PROMOCOES = $IntervaloPromocoes.ToString([Globalization.CultureInfo]::InvariantCulture)

# Solicita UTF-8 ao Python para exibir corretamente textos com acentos.
$env:PYTHONUTF8 = '1'

# Percorre os sete nomes; cada iteração abre um processo em terminal próprio.
foreach ($taskService in @('estoque', 'pagamento', 'entrega', 'c1', 'c2', 'promocoes', 'principal')) {

    # NoProfile evita perfis pessoais; NoExit mantém o terminal aberto após sair.
    # ExecutionPolicy Bypass vale para esse processo; File indica o script a executar.
    $taskArgs = @('-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File',

        # Protege o caminho do script com aspas e passa o nome do serviço escolhido.
        ('"' + (Join-Path $PSScriptRoot 'terminal.ps1') + '"'), '-Servico', $taskService)
    # Janelas visíveis são os terminais interativos da demonstração.

    # Abre um terminal visível para interação na demonstração; Out-Null descarta
    # a saída do comando. Não aguarda prontidão de cada consumidor neste laço.
    Start-Process powershell.exe -ArgumentList $taskArgs -WorkingDirectory $taskDir -WindowStyle Normal | Out-Null
}

# Indica que os terminais foram iniciados; mensagens PRONTO em cada um
# informam a preparação efetiva de seus serviços.
Write-Host 'Sete terminais iniciados. Use o menu Principal. Encerre TODOS antes de iniciar outra sessão.'
