@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
title Pre-deploy check and preview

REM ===== Pre-deploy check + local preview =====
REM 1) runs tools\check_site.py (files, data, sizes, raw-data leaks)
REM 2) if no FAIL, serves the "site" folder and opens the browser
REM This file does NOT run git. Upload to GitHub yourself (docs\02_deploy_guide).

REM --- find Python: course .venv -> Anaconda -> py -> python ---
set "PY="
if exist "%~dp0..\..\..\.venv\Scripts\python.exe" set "PY=%~dp0..\..\..\.venv\Scripts\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (where py >nul 2>nul && set "PY=py")
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython

echo.
echo ============================================================
echo  STEP 1  Pre-deploy check
echo ============================================================
cd /d "%~dp0"
"%PY%" tools\check_site.py
if errorlevel 1 goto failed

echo.
echo ============================================================
echo  STEP 2  Local preview  (close this window to stop)
echo ============================================================
set "PORT=8000"
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul && set "PORT=8001"
netstat -ano | findstr /R /C:":8001 .*LISTENING" >nul && set "PORT=8002"
echo   Preview:  http://localhost:%PORT%
echo   Check in the browser: hero chart, both maps (zoom, stage ribbon),
echo   Toronto toggle, flow / dong toggle, 4 charts, formulas.
echo.
start "" cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%"
cd /d "%~dp0site"
"%PY%" -m http.server %PORT% --bind 127.0.0.1
pause
exit /b 0

:failed
echo.
echo [STOP] Fix the FAIL items above, then run this file again.
pause
exit /b 1

:nopython
echo [ERROR] Python not found. Install Anaconda or create the course .venv.
pause
exit /b 1
