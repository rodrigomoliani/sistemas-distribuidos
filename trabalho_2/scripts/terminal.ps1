# Configura um terminal individual e inicia o módulo Python correspondente.
# É chamado pelo inicializador uma vez para cada processo da demonstração.

# Declara o argumento de seleção do serviço.
param(

    # Mandatory exige que o chamador forneça o nome.
    [Parameter(Mandatory = $true)]

    # Restringe o argumento aos cinco serviços e dois consumidores conhecidos.
    [ValidateSet('principal', 'estoque', 'pagamento', 'entrega', 'promocoes', 'c1', 'c2')]

    # Armazena o nome validado como string.
    [string]$Servico
)

# Obtém a raiz do trabalho a partir da localização deste script.
$taskDir = Split-Path -Parent $PSScriptRoot

# Usa a raiz como diretório de trabalho para resolver os módulos Python.
Set-Location -LiteralPath $taskDir

# Habilita o modo UTF-8 no processo Python iniciado abaixo.
$env:PYTHONUTF8 = '1'

# Configura a saída do console para representar corretamente os acentos.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

# Identifica o serviço no título da janela, facilitando a demonstração.
$Host.UI.RawUI.WindowTitle = "Trabalho 2 - $Servico"

# Resolve o executável Python do ambiente virtual local.
$taskPython = Join-Path $taskDir '.venv\Scripts\python.exe'

# C1 e C2 compartilham o mesmo módulo Python, com argumento diferente.
if ($Servico -in @('c1', 'c2')) {

    # & executa o Python; -u desativa buffer de saída; -m executa o módulo.
    # consumidores lê c1/c2 do argumento e seleciona sua fila RabbitMQ.
    & $taskPython -u -m consumidores $Servico

# Os outros nomes correspondem diretamente aos módulos de cada serviço.
} else {

    # Inicia principal, estoque, pagamento, entrega ou promocoes nesse terminal.
    # As conexões AMQP serão abertas pelo código Python do módulo.
    & $taskPython -u -m $Servico
}
