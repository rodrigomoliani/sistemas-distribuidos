param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('principal', 'estoque', 'pagamento', 'entrega', 'promocoes', 'c1', 'c2')]
    [string]$Servico
)
$taskDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskDir
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$Host.UI.RawUI.WindowTitle = "Trabalho 2 - $Servico"
$taskPython = Join-Path $taskDir '.venv\Scripts\python.exe'
if ($Servico -in @('c1', 'c2')) {
    & $taskPython -u -m consumidores $Servico
} else {
    & $taskPython -u -m $Servico
}
