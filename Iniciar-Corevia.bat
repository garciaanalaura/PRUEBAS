@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo Instala Python 3.12 o superior desde python.org y volve a abrir este archivo.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe (
 py -3 -m venv .venv
 if errorlevel 1 goto error
)
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if errorlevel 1 goto error
start "" /b powershell -NoProfile -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8080'"
.venv\Scripts\python.exe app.py
pause
exit /b
:error
echo No se pudo preparar Corevia. Revisa tu conexion y la instalacion de Python.
pause
exit /b 1
