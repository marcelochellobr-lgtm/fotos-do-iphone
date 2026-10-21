@echo off
rem Opcional. Cria um atalho "Fotos do iPhone" (com icone) na sua Area de Trabalho,
rem apontando para o "Abrir Fotos do iPhone.bat" desta pasta. Nao mexe em mais nada.
rem Para desfazer, basta apagar o atalho.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $l = $w.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Fotos do iPhone.lnk'); $l.TargetPath = '%~dp0Abrir Fotos do iPhone.bat'; $l.WorkingDirectory = '%~dp0'; $l.IconLocation = '%~dp0app\icone.ico'; $l.WindowStyle = 7; $l.Save()"
echo.
echo Pronto: o atalho "Fotos do iPhone" esta na sua Area de Trabalho.
echo.
pause
