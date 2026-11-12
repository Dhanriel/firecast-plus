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
rem um ajudante de uma versao anterior ainda aberto continuaria rodando o codigo antigo: fecha (o atalho abre o novo)
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*Firecast Plus.pyw*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul
if not exist "%APPDATA%\Firecast\Plugins" mkdir "%APPDATA%\Firecast\Plugins"
rem o download nao leva arquivos do Firecast: o instalar.ps1 completa o plugin com o SDK e o som do Firecast deste PC
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" -Base "dist\momotoro.firecast.plus.rpk" -Destino "%APPDATA%\Firecast\Plugins\momotoro.firecast.plus.rpk" >nul || (
  echo Falha ao montar o plugin. O Firecast 8 esta instalado neste PC?
  pause & exit /b 1
)
echo Plugin instalado. Abra o Firecast e digite /fc numa mesa.
echo.
echo O ajudante ^(opcional^) faz funcionar: skins, piscar na barra de tarefas e atualizacao das skins.
choice /C SN /M "Criar o atalho 'Firecast Plus' na area de trabalho (usa Python 3; se faltar, ofereco instalar)"
if errorlevel 2 goto fim
rem "python" pode ser so o atalho da Microsoft Store, que nao roda nada: testa de verdade
set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PY goto atalho
echo O Python 3 nao esta instalado neste PC.
choice /C SN /M "Baixar e instalar o Python 3.12 agora (python.org, uns 25 MB, so para o seu usuario)"
if errorlevel 2 goto fim
echo Baixando o Python 3.12 do python.org...
rem so roda o instalador se ele tiver a assinatura digital valida da Python Software Foundation
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $f=Join-Path $env:TEMP 'python-3.12.10-amd64.exe'; Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $f; $a=Get-AuthenticodeSignature $f; if ($a.Status -ne 'Valid' -or $a.SignerCertificate.Subject -notlike '*Python Software Foundation*') { Remove-Item $f; throw 'assinatura invalida' }" || (
  echo Falha ao baixar ou conferir o Python. Instale pelo python.org e rode este instalador de novo.
  goto fim
)
echo Instalando o Python, pode levar um minuto...
"%TEMP%\python-3.12.10-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 || (
  echo Falha ao instalar o Python.
  goto fim
)
del "%TEMP%\python-3.12.10-amd64.exe" >nul 2>nul
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo O Python foi instalado, mas nao achei %PY%. Rode este instalador de novo.
  goto fim
)
:atalho
"%PY%" -I fcplus.py atalho
echo Use o atalho 'Firecast Plus' para abrir o Firecast daqui em diante.
:fim
pause
