@echo off
chcp 65001 >nul
title 文心 GEO 服务器采集

cd /d "%~dp0"

echo ============================================================
echo 文心 GEO 服务器采集系统
echo ============================================================
echo.

set "ROOT=%CD%"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "PROFILE=%ROOT%\runtime\chrome_profile"
set "WENXIN_URL=https://wenxin.baidu.com/?enter_type=chat_site"

REM ============================================================
REM Python 环境
REM ============================================================

if not exist "%PYTHON%" (
    echo [ERROR] 未找到虚拟环境：
    echo %PYTHON%
    echo.
    echo 请先执行：
    echo python -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python 环境正常

REM ============================================================
REM 创建运行目录
REM ============================================================

if not exist "%ROOT%\runtime" (
    mkdir "%ROOT%\runtime"
)

if not exist "%PROFILE%" (
    mkdir "%PROFILE%"
)

if not exist "%ROOT%\logs" (
    mkdir "%ROOT%\logs"
)

REM ============================================================
REM 检查 CDP 9222
REM ============================================================

powershell -NoProfile -Command ^
    "try { Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"

if %ERRORLEVEL% EQU 0 (
    echo [OK] Chrome CDP 9222 已运行
    goto RUN
)

echo [INFO] Chrome CDP 未运行，准备启动...

REM ============================================================
REM 查找 Chrome
REM ============================================================

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME%" (
    set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
)

if not exist "%CHROME%" (
    set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if not exist "%CHROME%" (
    echo [ERROR] 未找到 Google Chrome
    pause
    exit /b 1
)

REM ============================================================
REM 启动服务器专用 Chrome
REM ============================================================

start "" "%CHROME%" ^
    --remote-debugging-port=9222 ^
    --user-data-dir="%PROFILE%" ^
    --no-first-run ^
    --no-default-browser-check ^
    "%WENXIN_URL%"

echo [INFO] 等待 Chrome 启动...
timeout /t 5 /nobreak >nul

powershell -NoProfile -Command ^
    "try { Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"

if not %ERRORLEVEL% EQU 0 (
    echo [ERROR] Chrome 已启动，但 CDP 9222 不可访问
    pause
    exit /b 2
)

echo [OK] Chrome CDP 启动成功

REM ============================================================
REM 运行正式 Pipeline
REM ============================================================

:RUN

echo.
echo ============================================================
echo 启动文心 GEO Pipeline
echo ============================================================
echo.

"%PYTHON%" -m scripts.check_wenxin_server
if errorlevel 1 (
    echo [ERROR] Wenxin server health check failed
    pause
    exit /b 3
)

"%PYTHON%" -m scripts.run_wenxin_pipeline

set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo ============================================================
echo Pipeline 已结束
echo EXIT CODE: %EXIT_CODE%
echo ============================================================
echo.

pause

exit /b %EXIT_CODE%