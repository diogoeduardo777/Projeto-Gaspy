@echo off
setlocal
title Setup Gaspy-APBR - PC de casa
cd /d "%~dp0"

echo ============================================
echo  Setup Gaspy-APBR (pipeline + bot Telegram)
echo ============================================
echo.
echo Pre-requisitos (instalar antes de rodar este script):
echo   - Python 3.11 (python.org) com "Add Python.exe to PATH" marcado
echo   - FFmpeg em C:\ffmpeg (gyan.dev/ffmpeg/builds - release essentials)
echo.

REM 1) Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo        Instale o Python 3.11 em https://www.python.org/downloads/
    echo        e marque a caixa "Add Python.exe to PATH" na instalacao.
    echo        Depois feche e abra este script de novo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% encontrado.

REM 2) Verifica FFmpeg (necessario para renderizar os videos)
where ffmpeg >nul 2>&1
if errorlevel 1 (
    if exist "C:\ffmpeg\bin\ffmpeg.exe" (
        echo [OK] FFmpeg encontrado em C:\ffmpeg\bin
    ) else (
        echo [AVISO] FFmpeg nao encontrado. O bot do Telegram funciona sem ele,
        echo         mas o pipeline de videos NAO renderiza.
        echo         Baixe o "release essentials" em https://www.gyan.dev/ffmpeg/builds/
        echo         extraia para C:\ffmpeg e confira que C:\ffmpeg\bin\ffmpeg.exe existe.
    )
) else (
    echo [OK] FFmpeg encontrado no PATH.
)
echo.

REM 3) Ambiente do pipeline de videos (recria o venv do zero, mesmo se veio quebrado na copia)
echo [1/2] Preparando shorts-pipeline (2-5 minutos)...
cd /d "%~dp0shorts-pipeline"
python -m venv venv --clear
if errorlevel 1 goto :venv_erro
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 goto :pip_erro
call venv\Scripts\deactivate.bat
echo [OK] shorts-pipeline pronto.
echo.

REM 4) Ambiente do bot do Telegram
echo [2/2] Preparando telegram-bot (1-2 minutos)...
cd /d "%~dp0telegram-bot"
python -m venv venv --clear
if errorlevel 1 goto :venv_erro
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 goto :pip_erro
call venv\Scripts\deactivate.bat
echo [OK] telegram-bot pronto.
echo.

echo ============================================
echo  Instalacao concluida!
echo ============================================
echo.
echo Proximos passos:
echo   1. Testar o bot do Telegram:
echo        %~dp0telegram-bot\venv\Scripts\python.exe run.py --now
echo   2. Agendar o pipeline no Agendador de Tarefas (diario, 07:00):
echo        Programa:   %~dp0shorts-pipeline\venv\Scripts\python.exe
echo        Argumentos: run.py
echo        Iniciar em: %~dp0shorts-pipeline
echo   3. Colocar o bot para abrir com o Windows (Win+R, shell:startup)
echo      criando um bot.bat conforme o Passo 15 do Guia-Gaspy-APBR.txt
echo.

choice /C SN /M "Deseja rodar o teste do pipeline de videos agora (demora alguns minutos)"
if errorlevel 2 goto :fim
cd /d "%~dp0shorts-pipeline"
venv\Scripts\python.exe run.py

:fim
echo.
pause
exit /b 0

:venv_erro
echo [ERRO] Falha ao criar o ambiente virtual (venv).
pause
exit /b 1

:pip_erro
echo [ERRO] Falha ao instalar as dependencias. Verifique a conexao com a internet e rode de novo.
pause
exit /b 1
