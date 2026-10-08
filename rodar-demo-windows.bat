@echo off
REM Roda o portal em modo DEMONSTRACAO no Windows.
REM Dados de teste, Bling simulado - nenhum pedido vai para o Bling de verdade.
REM Use: dois cliques neste arquivo.
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Portal The Bulldog - demonstracao

echo.
echo === Portal The Bulldog - demonstracao ===
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :temPython
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :temPython

echo Precisa do Python 3.10 ou mais novo.
echo Baixe em https://www.python.org/downloads/ - botao amarelo "Download Python".
echo IMPORTANTE: na primeira tela do instalador, marque "Add python.exe to PATH".
echo Depois de instalar, rode este arquivo de novo.
echo.
pause
exit /b 1

:temPython
if exist ".venv\Scripts\python.exe" goto :temVenv
echo Preparando o ambiente - so na primeira vez, leva 1 a 3 minutos...
%PY% -m venv .venv
if errorlevel 1 goto :erro

:temVenv
call ".venv\Scripts\activate.bat"
python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :erro

if exist ".env" goto :temEnv
python -m app.cli gen-keys > .env
if errorlevel 1 goto :erro
>>.env echo APP_ENV=development
>>.env echo DATABASE_URL=sqlite:///./demo.db
>>.env echo SEED_ADMIN_EMAIL=admin@demo.local
>>.env echo SEED_ADMIN_PASSWORD=bulldog123
>>.env echo SEED_DEMO_PASSWORD=bulldog123
>>.env echo APP_PROCESS_JOBS_INLINE=true

:temEnv
alembic upgrade head >nul
if errorlevel 1 goto :erro
python -m app.cli seed --demo --st-mode mock
if errorlevel 1 goto :erro

echo.
echo Pronto! Abrindo http://localhost:8000 no navegador.
echo.
echo   Admin - back-office:  admin@demo.local     senha bulldog123
echo   Vendedor:             vendedor@demo.local  senha bulldog123
echo   Cliente - PDV:        pdv@demo.local       senha bulldog123
echo.
echo Para encerrar: feche esta janela.
echo.

start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8000"
python -m uvicorn app.main:create_app --factory --port 8000
goto :fim

:erro
echo.
echo Deu erro em algum passo acima. Tire um print desta janela e me mande.
echo.
pause
exit /b 1

:fim
endlocal
