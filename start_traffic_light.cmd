@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Traffic Light AI Web App
echo ==========================================
echo Project: %CD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo Put this file in the same folder as app.py and .venv.
    echo.
    pause
    exit /b 1
)

if not exist "app.py" (
    echo [ERROR] app.py not found.
    echo Put this file in the same folder as app.py.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [WARNING] .env not found.
    echo Roboflow API key may not load.
    echo.
)

echo Starting server...
echo URL: http://127.0.0.1:8000
echo Stop server: Ctrl+C
echo.

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000'"

".venv\Scripts\python.exe" -m uvicorn app:app --reload

echo.
echo Server stopped. Exit code: %ERRORLEVEL%
pause
endlocal
