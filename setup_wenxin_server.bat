@echo off
chcp 65001 >nul
title 文心 GEO 服务器初始化

cd /d "%~dp0"

echo ============================================================
echo 文心 GEO 服务器初始化
echo ============================================================
echo.

set "ROOT=%CD%"
set "VENV=%ROOT%\.venv"
set "PYTHON=%VENV%\Scripts\python.exe"

REM ============================================================
REM 1. 检查系统 Python
REM ============================================================

echo [1/7] 检查系统 Python...

python --version >nul 2>&1

if errorlevel 1 (
    echo.
    echo [ERROR] 未检测到 Python
    echo 请先安装 Python 3.11
    echo.
    pause
    exit /b 1
)

python --version

REM ============================================================
REM 2. 创建虚拟环境
REM ============================================================

echo.
echo [2/7] 检查虚拟环境...

if exist "%PYTHON%" (
    echo [OK] .venv 已存在
) else (
    echo [INFO] 正在创建 .venv...

    python -m venv "%VENV%"

    if errorlevel 1 (
        echo [ERROR] 创建 .venv 失败
        pause
        exit /b 1
    )

    echo [OK] .venv 创建成功
)

REM ============================================================
REM 3. 检查 requirements.txt
REM ============================================================

echo.
echo [3/7] 检查 requirements.txt...

if not exist "%ROOT%\requirements.txt" (
    echo [ERROR] requirements.txt 不存在
    pause
    exit /b 1
)

echo [OK] requirements.txt 已找到

REM ============================================================
REM 4. 安装 / 更新依赖
REM ============================================================

echo.
echo [4/7] 安装 Python 依赖...

"%PYTHON%" -m pip install --upgrade pip

if errorlevel 1 (
    echo [ERROR] pip 更新失败
    pause
    exit /b 1
)

"%PYTHON%" -m pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] requirements 安装失败
    pause
    exit /b 1
)

echo [OK] Python 依赖安装完成

REM ============================================================
REM 5. pip check
REM ============================================================

echo.
echo [5/7] 检查依赖完整性...

"%PYTHON%" -m pip check

if errorlevel 1 (
    echo.
    echo [ERROR] Python 依赖存在冲突或缺失
    pause
    exit /b 1
)

echo [OK] pip check PASS

REM ============================================================
REM 6. 自动化测试
REM ============================================================

echo.
echo [6/7] 执行自动化测试...

"%PYTHON%" -m pytest -q

if errorlevel 1 (
    echo.
    echo [ERROR] pytest 未通过
    echo 正式采集不会启动
    pause
    exit /b 1
)

echo [OK] pytest PASS

REM ============================================================
REM 7. 创建服务器运行目录
REM ============================================================

echo.
echo [7/7] 初始化服务器目录...

if not exist "%ROOT%\output" (
    mkdir "%ROOT%\output"
)

if not exist "%ROOT%\runtime" (
    mkdir "%ROOT%\runtime"
)

if not exist "%ROOT%\runtime\chrome_profile" (
    mkdir "%ROOT%\runtime\chrome_profile"
)

if not exist "%ROOT%\logs" (
    mkdir "%ROOT%\logs"
)

echo [OK] 运行目录初始化完成

echo.
echo ============================================================
echo WENXIN SERVER SETUP: PASS
echo ============================================================
echo.
echo Python:
"%PYTHON%" --version
echo.
echo 项目目录:
echo %ROOT%
echo.
echo 下一步：
echo 双击 run_wenxin_server.bat
echo.
pause

exit /b 0