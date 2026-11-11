@echo off
rem ============================================================
rem  run_server.bat  -  Start the TestImpact AI FastAPI server
rem ============================================================

rem Move to the directory containing this script
cd /d "%~dp0"

echo ============================================================
echo   TestImpact AI  -  FastAPI Server
echo ============================================================
echo.

rem Start the server (foreground, so you see all output)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo Server stopped.
pause
