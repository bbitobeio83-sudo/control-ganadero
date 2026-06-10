@echo off
chcp 65001 > nul
title Control Ganadero — Ganado Vacuno

echo.
echo  ================================================
echo   SISTEMA DE CONTROL GANADERO - GANADO VACUNO
echo  ================================================
echo.

:: Verificar Python (Windows usa "py" como launcher)
py --version > nul 2>&1
if errorlevel 1 (
    python --version > nul 2>&1
    if errorlevel 1 (
        echo  ERROR: Python no esta instalado.
        echo  Descarga Python desde: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set PYTHON=python
) else (
    set PYTHON=py
)

:: Instalar Flask si no esta instalado
%PYTHON% -c "import flask" > nul 2>&1
if errorlevel 1 (
    echo  Instalando Flask...
    %PYTHON% -m pip install flask -q
)

echo  Iniciando servidor en http://localhost:5000
echo  Presiona Ctrl+C para detener
echo.

start "" http://localhost:5000
%PYTHON% app.py

pause
