@echo off
setlocal EnableExtensions

rem ============================================================
rem  run_server.bat - Launch TestImpact AI (Backend + Frontend)
rem ============================================================

cd /d "%~dp0"
set "ROOT_DIR=%~dp0"
set "FRONTEND_DIR=%ROOT_DIR%frontend"

rem Prefer local .venv Python if present, otherwise fall back to PATH python
if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

rem 1. Verify Python & uvicorn
if "%PYTHON_EXE%"=="python" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python was not found in .venv or on PATH.
        goto :fail
    )
)
"%PYTHON_EXE%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uvicorn is not installed for "%PYTHON_EXE%".
    echo         Activate .venv or run: pip install -r requirements.txt
    goto :fail
)

rem 2. Verify Frontend dependencies & config
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Frontend directory not found at "%FRONTEND_DIR%".
    goto :fail
)
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js / npm was not found on PATH.
    goto :fail
)
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [ERROR] frontend\node_modules not found.
    echo         Run "cd frontend && npm install" first.
    goto :fail
)
if not exist "%FRONTEND_DIR%\.env" (
    if exist "%FRONTEND_DIR%\.env.example" (
        copy "%FRONTEND_DIR%\.env.example" "%FRONTEND_DIR%\.env" >nul
        echo [INFO] Created frontend\.env from frontend\.env.example
    )
)

rem 3. Check if ports 8000 or 5173 are already bound
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [ERROR] Port 8000 is already in use. Stop the existing backend process first.
    goto :fail
)
netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [ERROR] Port 5173 is already in use. Stop the existing frontend process first.
    goto :fail
)

echo ============================================================
echo   TestImpact AI - Starting Backend and Frontend
echo ============================================================
echo   Frontend UI : http://127.0.0.1:5173
echo   Backend API : http://127.0.0.1:8000
echo   Swagger UI  : http://127.0.0.1:8000/docs
echo ============================================================
echo.

rem Launch React + Vite Frontend in a dedicated window
start "TestImpact AI - Frontend (5173)" /D "%FRONTEND_DIR%" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

rem Run FastAPI Backend in this primary window so errors/logs remain visible
"%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo Backend server stopped. Close the Frontend window separately if it is still open.
pause
exit /b 0

:fail
echo.
echo Startup aborted.
pause
exit /b 1
