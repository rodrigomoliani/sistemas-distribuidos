@REM Oculta a repetição dos comandos; as mensagens dos programas continuam visíveis.
@echo off

REM Muda a unidade e a pasta para o local deste arquivo; as aspas aceitam caminhos com espaços.
cd /d "%~dp0"

REM Executa o inicializador sem o perfil pessoal e libera scripts apenas neste processo PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar.ps1"

REM Mantém a janela aberta para permitir a leitura do resultado ou de eventuais erros.
pause
