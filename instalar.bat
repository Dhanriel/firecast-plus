@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Firecast Plus: instalador ===
if not exist "dist\momotoro.firecast.plus.rpk" (
  echo Nao achei dist\momotoro.firecast.plus.rpk. Monte antes com: python fcplus.py plugin
  pause & exit /b 1
)
tasklist /FI "IMAGENAME eq Firecast.exe" /NH | find /I "Firecast.exe" >nul && (
  echo Feche o Firecast ^(inclusive o icone perto do relogio^) e rode de novo.
  pause & exit /b 1
)
if not exist "%APPDATA%\Firecast\Plugins" mkdir "%APPDATA%\Firecast\Plugins"
copy /Y "dist\momotoro.firecast.plus.rpk" "%APPDATA%\Firecast\Plugins\momotoro.firecast.plus.rpk" >nul || (
  echo Falha ao copiar o plugin.
  pause & exit /b 1
)
echo Plugin instalado. Abra o Firecast e digite /fc numa mesa.
echo.
echo O ajudante ^(opcional^) faz funcionar: cores do Firecast, piscar na barra de tarefas e reaplicar a skin apos atualizacoes.
choice /C SN /M "Criar o atalho 'Firecast Plus' na area de trabalho (precisa de Python 3)"
if errorlevel 2 goto fim
where python >nul 2>nul || (
  echo Python nao encontrado. Instale o Python 3 ^(python.org^) e rode este instalador de novo.
  goto fim
)
python -I fcplus.py atalho
echo Use o atalho 'Firecast Plus' para abrir o Firecast daqui em diante.
:fim
pause
