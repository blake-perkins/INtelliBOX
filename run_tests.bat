@echo off
REM Run all tests individually to avoid cross-contamination
REM Uses the virtual environment Python

echo.
echo ========================================
echo INtelliBOX Test Suite Runner
echo ========================================
echo.

venv\Scripts\python.exe run_tests.py
exit /b %ERRORLEVEL%
