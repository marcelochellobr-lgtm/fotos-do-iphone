@echo off
rem Fotos do iPhone - liga o app.
rem Usa o Python que vem dentro desta pasta (nada e instalado no Windows) para rodar app\app.py.
rem O app abre no navegador. Fechar esta janela preta desliga o app.
title Fotos do iPhone (feche esta janela para encerrar o app)
cd /d "%~dp0"
"python\python.exe" "app\app.py"
if errorlevel 1 pause
