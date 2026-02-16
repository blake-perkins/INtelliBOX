@echo off
REM EmailTools Local Test Script (No containers needed)
REM Tests the application directly using your Python environment

echo ========================================
echo EmailTools Local Test
echo ========================================
echo.

set PYTHON=venv\Scripts\python.exe

echo [1/5] Testing database initialization...
%PYTHON% -c "from emailtools.database import get_session; from emailtools.models import Email; print('[OK] Database models loaded')"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Database test failed
    exit /b 1
)

echo [2/5] Testing email parser...
%PYTHON% -c "from emailtools.ingestion.parser import parse_eml_file; print('[OK] Email parser loaded')"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Parser test failed
    exit /b 1
)

echo [3/5] Testing AI client...
%PYTHON% -c "from emailtools.ai.processor import get_ai_client; client = get_ai_client(); print(f'[OK] AI client: {client.__class__.__name__}')"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] AI client test failed
    exit /b 1
)

echo [4/5] Testing report generator...
%PYTHON% -c "from emailtools.reporter.generator import generate_report_data; print('[OK] Report generator loaded')"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Report generator test failed
    exit /b 1
)

echo [5/5] Testing CLI...
venv\Scripts\emailtools.exe --help >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CLI test failed
    exit /b 1
)
echo [OK] CLI working

echo.
echo ========================================
echo All tests passed!
echo ========================================
echo.
echo Next steps:
echo 1. Install Podman Desktop from: https://podman-desktop.io/
echo 2. Run: podman build -t emailtools:latest .
echo 3. Run: podman run -d --name emailtools --env-file .env -v ./data:/app/data:Z emailtools:latest
echo.
pause
