param(
    [ValidateRange(0, 1)][double]$ProbAprovacao = 0.5,
    [ValidateRange(0.1, 3600)][double]$IntervaloPromocoes = 5
)
$ErrorActionPreference = 'Stop'
$taskDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskDir
$taskPython = Join-Path $taskDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Crie .venv e instale requirements.txt conforme o README.'
}
docker compose up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Falha ao iniciar RabbitMQ. Verifique Docker Desktop.' }
& $taskPython -m scripts.gerar_chaves
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar chaves.' }
& $taskPython -m scripts.preparar_filas --limpar
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar filas. Encerre a sessão anterior.' }
$env:PROB_APROVACAO = $ProbAprovacao.ToString([Globalization.CultureInfo]::InvariantCulture)
$env:INTERVALO_PROMOCOES = $IntervaloPromocoes.ToString([Globalization.CultureInfo]::InvariantCulture)
$env:PYTHONUTF8 = '1'
foreach ($taskService in @('estoque', 'pagamento', 'entrega', 'c1', 'c2', 'promocoes', 'principal')) {
    $taskArgs = @('-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File',
        ('"' + (Join-Path $PSScriptRoot 'terminal.ps1') + '"'), '-Servico', $taskService)
    # Janelas visíveis são os terminais interativos da demonstração.
    Start-Process powershell.exe -ArgumentList $taskArgs -WorkingDirectory $taskDir -WindowStyle Normal | Out-Null
}
Write-Host 'Sete terminais iniciados. Use o menu Principal. Encerre TODOS antes de iniciar outra sessão.'
