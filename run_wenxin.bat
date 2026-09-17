@echo off
chcp 65001 >nul
title 文心 GEO 采集系统

cd /d "%~dp0"

echo ============================================================
echo 文心 GEO 采集系统
echo ============================================================
echo.

REM ============================================================
REM 检查 Python 虚拟环境
REM ============================================================

set "PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] 未找到 Python 虚拟环境：
    echo %PYTHON%
    echo.
    echo 请先创建 .venv 并安装 requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python 虚拟环境已找到

REM ============================================================
REM 检查 Chrome CDP 9222
REM ============================================================

powershell -NoProfile -Command ^
    "try { Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"

if %ERRORLEVEL% EQU 0 (
    echo [OK] Chrome CDP 9222 已启动
    goto RUN_PIPELINE
)

echo [INFO] 未检测到 Chrome CDP 9222
echo [INFO] 正在尝试启动 Chrome...
echo.

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
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM 启动独立 CDP Chrome
REM ============================================================

set "CHROME_PROFILE=%CD%\chrome_profile"

start "" "%CHROME%" ^
    --remote-debugging-port=9222 ^
    --user-data-dir="%CHROME_PROFILE%" ^
    "https://wenxin.baidu.com/?enter_type=chat_site"

echo [INFO] 等待 Chrome 启动...

timeout /t 4 /nobreak >nul

REM ============================================================
REM 再次检查 9222
REM ============================================================

powershell -NoProfile -Command ^
    "try { Invoke-RestMethod 'http://127.0.0.1:9222/json/version' -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"

if not %ERRORLEVEL% EQU 0 (
    echo.
    echo [ERROR] Chrome 已启动，但 CDP 9222 暂时不可访问
    echo 请检查 Chrome 是否正常启动。
    echo.
    pause
    exit /b 1
)

echo [OK] Chrome CDP 9222 启动成功

REM ============================================================
REM 正式运行
REM ============================================================

:RUN_PIPELINE

echo.
echo ============================================================
echo 启动文心 GEO Pipeline
echo ============================================================
echo.

"%PYTHON%" -m scripts.run_wenxin_pipeline

set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo ============================================================

if %EXIT_CODE% EQU 0 (
    echo 文心 GEO Pipeline 执行结束
) else (
    echo 文心 GEO Pipeline 执行异常
    echo EXIT CODE: %EXIT_CODE%
)

echo ============================================================
echo.

pause

exit /b %EXIT_CODE%