@echo off
chcp 65001 >nul
title Fractal Monitor
setlocal enabledelayedexpansion

:: ============================================================
::      FRACTAL MONITORING SYSTEM — CONSTITUTION v4.0
::         河与岸 · 三级嵌套包络分形 · 自愈系统
::                    2026-07-25
:: ============================================================
::
:: ═══════════ [唯一数据路径] ═══════════
::
::   券商终端导出根目录:
::     D:\海王星金融终端-中国银河证券\T0002\export\
::
::   5分钟K线 (按日期子目录):
::     {ROOT}\{YYYY-MM-DD}\SH#601985.txt
::     {ROOT}\{YYYY-MM-DD}\SZ#000001.txt
::
::   日线K线 (根目录直接):
::     {ROOT}\SH#601985.txt
::     {ROOT}\SZ#000001.txt
::
::   格式:  日期 [时间] 开 高 低 收 量 额   (GBK编码, 制表符分隔)
::
::   盘中实时数据源:
::     http://ifzq.gtimg.cn/appstock/app/kline/mkline
::     拉取当日320根5分钟K线，与本地历史拼接
::
:: ═══════════ [唯一宪法] ═══════════
::
::   1. 本BAT是系统唯一入口。禁止直接运行py。
::   2. auto_fractal.py 是唯一生产代码。
::   3. 拐点检测: CZSC+分形融合 (fractal_fusion.py)
::      - CZSC骨架: 包含合并→分型→笔→干净H-L交替
::      - 分形精雕: 笔端点±7根K线精确取岸
::      - 自愈引擎: 诊断6项指标→自治调参→降级保底 (self_heal.py)
::   4. 三级嵌套: 日线⊃30min⊃5min 包络约束投射
::   5. 日线从实际导出文件读取 — 不从5min合成。
::   6. 任意6位代码自动识别市场 (6=SH, 0/3=SZ)。
::   7. 输出: auto_fractal_chart.html + .svg。不污染工作区。
::   8. 归档: archive\ 保留最近30份快照。
::   9. 报错即停，不吞异常。Ctrl+C 优雅退出。
::   10. Web Service: serve.py → localhost:8765 实时切换标的。
::
:: ═══════════ [代码地图] ═══════════
::
::   分形监控.bat          — 唯一入口 + 本宪法
::   auto_fractal.py       — 核心引擎 (数据→检测→投射→渲染)
::   fractal_fusion.py     — 融合拐点检测 (CZSC骨架+分形精雕)
::   self_heal.py          — 自愈引擎 (诊断→自治→降级)
::   fractal_core.py       — 包络衰减/段振幅计算
::   czsc_pivots.py        — CZSC底层 (包含合并/分型/笔)
::   serve.py              — Web服务 (localhost:8765)
::   long_rank.py          — 盘后做多排名轮动系统
::   fractal_app.html      — PWA纯前端 (GitHub Pages部署)
::
:: ═══════════ [数据流] ═══════════
::
::   本地文件 ─┐
::   腾讯API  ─┤→ bars5/daily_bars → 分形检测 → 投射 → HTML/SVG
::             │                      │
::             │               ┌──────┴──────┐
::             │         30min: window=5  日线: window=2
::             │          5min: 融合+自愈 (FractalDoctor)
::             │               └──────┬──────┘
::             │                      ↓
::             │             三级嵌套包络约束 → 共振点
::
:: ============================================================

:: --- Environment self-check ---
set "WORKDIR=C:\Users\Administrator\.copaw\workspaces\waNTgq"
set "SCRIPT=%WORKDIR%\auto_fractal.py"
set "CHART=%WORKDIR%\auto_fractal_chart.html"

if not exist "%WORKDIR%" (
    echo [FATAL] Workspace missing: %WORKDIR%
    pause & exit /b 1
)
if not exist "%SCRIPT%" (
    echo [FATAL] Core script missing: %SCRIPT%
    pause & exit /b 1
)

:: Find Python
set "PY="
for %%p in (py python3 python) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY=%%p"
        goto :found_py
    )
)
echo [FATAL] Python not found
pause & exit /b 1

:found_py
:: Default ticker
set "LAST_CODE=601238"

:: ============================================================
::                        MAIN MENU
:: ============================================================
:menu
cls
echo.
:: Count archives
set "ARC_COUNT=0"
set "ARC_DIR=%WORKDIR%\archive"
if exist "%ARC_DIR%" (
    dir /b "%ARC_DIR%\chart_*.html" 2>nul > "%TEMP%\f_arc.tmp"
    for /f "usebackq" %%a in ("%TEMP%\f_arc.tmp") do set /a ARC_COUNT+=1
    del "%TEMP%\f_arc.tmp" 2>nul
)

echo   +------------------------------------------+
echo   ^|   FRACTAL MONITOR  v4.0                  ^|
echo   +------------------------------------------+
echo   ^|   Detect : CZSC ^+ Fractal Fusion        ^|
echo   ^|   Heal   : Self-Diagnose ^& Auto-Fix     ^|
echo   ^|   Level  : 30min ^< 5min Nested Envelope  ^|
echo   ^|   Ticker : %LAST_CODE%                   ^|
echo   ^|   Archive: !ARC_COUNT! snapshots             ^|
echo   +------------------------------------------+
echo   ^|                                          ^|
echo   ^|   [1] Run (3-Level Nested)               ^|
echo   ^|   [2] Run (30min Only)                   ^|
echo   ^|   [3] Run (5min Only)                    ^|
echo   ^|   [4] Run (Daily Only)                   ^|
echo   ^|                                          ^|
echo   ^|   [5] Open Latest Chart                  ^|
echo   ^|   [6] Live Loop (every 5 min)            ^|
echo   ^|   [7] Enter Code                         ^|
echo   ^|   [8] Open Archive Folder                ^|
echo   ^|                                          ^|
echo   ^|   [9] Web Service  (localhost:8765)       ^|
echo   ^|                                          ^|
echo   ^|   [V] Long Rank Scan  (盘后扫描)          ^|
echo   ^|   [B] Block Scan      (板块做多排序)       ^|
echo   ^|   [D] Deploy Pivots   (推送拐点到GitHub)    ^|
echo   ^|                                          ^|
echo   ^|   [0] Exit                               ^|
echo   ^|                                          ^|
echo   +------------------------------------------+
echo.
set /p choice="   > Select [0-9, V, B]: "

if "%choice%"=="1" goto :run_default
if "%choice%"=="2" goto :run_30min
if "%choice%"=="3" goto :run_5min
if "%choice%"=="4" goto :run_daily
if "%choice%"=="5" goto :open_chart
if "%choice%"=="6" goto :live_loop
if "%choice%"=="7" goto :custom_code
if "%choice%"=="8" goto :open_archive
if "%choice%"=="9" goto :web_service
if /i "%choice%"=="V" goto :long_rank
if /i "%choice%"=="B" goto :block_scan
if /i "%choice%"=="D" goto :deploy_pivots
if "%choice%"=="0" goto :end
echo   Invalid choice
timeout /t 1 >nul
goto :menu

:: ============================================================
::                    [1] 3-Level Nested
:: ============================================================
:run_default
call :do_run "%LAST_CODE%"
goto :menu

:: ============================================================
::                    [2] 30min Only
:: ============================================================
:run_30min
call :do_run "%LAST_CODE%" "30min"
goto :menu

:: ============================================================
::                    [3] 5min Only
:: ============================================================
:run_5min
call :do_run "%LAST_CODE%" "5min"
goto :menu

:: ============================================================
::                    [4] Daily Only
:: ============================================================
:run_daily
call :do_run "%LAST_CODE%" "daily"
goto :menu
::                    [2] Open chart
:: ============================================================
:open_chart
if not exist "%CHART%" (
    echo   [WARN] No chart yet, running analysis first...
    call :do_run "%LAST_CODE%"
    if !errorlevel! neq 0 goto :menu
)
echo   Opening chart...
start "" "%CHART%"
timeout /t 1 >nul
goto :menu

:: ============================================================
::                  [3] Analyze + Open
:: ============================================================
:run_and_open
call :do_run "%LAST_CODE%"
if !errorlevel! neq 0 goto :menu
start "" "%CHART%"
timeout /t 1 >nul
goto :menu

:: ============================================================
::            [4] Live loop (every 5 minutes)
:: ============================================================
:live_loop
cls
echo.
echo   +------------------------------------------+
echo   ^|   LIVE LOOP - Ctrl+C to stop             ^|
echo   ^|   Every 5 minutes                        ^|
echo   ^|   Ticker: %LAST_CODE%                           ^|
echo   +------------------------------------------+
echo.
set /a round=0

:loop_body
set /a round+=1
echo   -- Round !round! [%date% %time:~0,8%] --
call :do_run "%LAST_CODE%"
if !errorlevel! equ 0 (
    echo   [OK] Waiting 5 min...
) else (
    echo   [WARN] Round failed, continuing...
)
timeout /t 300 >nul
goto :loop_body

:: ============================================================
::              [5] Enter any 6-digit code
:: ============================================================
:custom_code
cls
echo.
echo   +------------------------------------------+
echo   ^|   Enter 6-digit stock code                ^|
echo   ^|   SH: 6xxxxx    SZ: 0xxxxx / 3xxxxx     ^|
echo   +------------------------------------------+
echo   ^|   Ex: 601238 601985 000001 300750        ^|
echo   +------------------------------------------+
echo.
set /p code="   > Code: "
if "%code%"=="" (
    echo   No code entered, returning...
    timeout /t 1 >nul
    goto :menu
)
:: Validate: 6 digits
echo %code%^| findstr /r "^[0-9][0-9][0-9][0-9][0-9][0-9]$" >nul
if !errorlevel! neq 0 (
    echo   [ERR] Must be exactly 6 digits
    timeout /t 2 >nul
    goto :custom_code
)
call :do_run "%code%"
if !errorlevel! equ 0 set "LAST_CODE=%code%"
goto :menu

:: ============================================================
::           CORE: do_run  code  [level]
::           level: default/all  or  daily / 30min / 5min
::           Returns: 0=success  3=script failed  2=no output
:: ============================================================
:do_run
echo.
if "%~2"=="" (
    echo   ===========================================
    echo     Analyzing: %~1
    echo   ===========================================
) else (
    echo   ===========================================
    echo     Analyzing: %~1  (Level: %~2)
    echo   ===========================================
)
cd /d "%WORKDIR%"
if "%~2"=="" (
    %PY% "%SCRIPT%" "%~1"
) else (
    %PY% "%SCRIPT%" "%~1" "--level=%~2"
)
if !errorlevel! equ 0 (
    if exist "%CHART%" (
        echo   [OK] Chart generated
        :: --- Archive versioned copy ---
        set "ARCHIVE=%WORKDIR%\archive"
        if not exist "!ARCHIVE!" mkdir "!ARCHIVE!"
        for /f "tokens=1-6 delims=/: " %%a in ('echo %date% %time%') do (
            set "TS=%%a%%b%%c_%%d%%e"
        )
        if "%~2"=="" (
            copy "%CHART%" "!ARCHIVE!\chart_!TS!.html" >nul
            echo   [ARC] Archived to archive\chart_!TS!.html
        ) else (
            copy "%CHART%" "!ARCHIVE!\chart_%~2_!TS!.html" >nul
            echo   [ARC] Archived to archive\chart_%~2_!TS!.html
        )
        :: Keep last 30 archives, delete older
        for /f "skip=30" %%f in ('dir /b /o-d "!ARCHIVE!\chart_*.html" 2^>nul') do (
            del "!ARCHIVE!\%%f" >nul 2>&1
        )
        exit /b 0
    ) else (
        echo   [ERR] Script finished but no chart file
        exit /b 2
    )
) else (
    echo   [FAIL] Script exited with code !errorlevel!
    exit /b 3
)

:: ============================================================
::              [8] Open archive folder
:: ============================================================
:open_archive
if not exist "%ARC_DIR%" mkdir "%ARC_DIR%"
explorer "%ARC_DIR%"
goto :menu

:: ============================================================
::            [9] Web Service  Start / Stop
:: ============================================================
:web_service
set "WEB_PORT=8765"
set "SERVE_SCRIPT=%WORKDIR%\serve.py"
set "LT_LOG=%TEMP%\localtunnel_url.txt"

:: --- Auto-clean any leftover on this port ---
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":%WEB_PORT% " ^| findstr "LISTENING"') do (
    echo   清理旧进程 PID=%%p ...
    taskkill /f /pid %%p >nul 2>&1
)
timeout /t 1 >nul

:: --- START ---
if not exist "%SERVE_SCRIPT%" (
    echo   [ERR] serve.py not found: %SERVE_SCRIPT%
    pause
    goto :menu
)
echo.
echo   启动 Web 服务: http://127.0.0.1:%WEB_PORT%
echo   请保持弹出的 Python 窗口运行，关闭即停止服务。
echo.
start "FractalWeb" %PY% "%SERVE_SCRIPT%" %LAST_CODE%
timeout /t 4 >nul

:: Verify
netstat -ano 2>nul | findstr ":%WEB_PORT% " | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo   [OK] 服务运行中，正在打开浏览器...
    start http://127.0.0.1:%WEB_PORT%

    :: ============================================================
    ::      启动 localtunnel — 手机远程访问（蜂窝数据）
    :: ============================================================
    echo.
    echo   +------------------------------------------+
    echo   ^|  正在获取公网地址...（首次需下载 ~2MB）    ^|
    echo   +------------------------------------------+

    where npx >nul 2>&1
    if !errorlevel! neq 0 (
        echo   [!] 需要 Node.js（npx 命令未找到）
        echo      安装: https://nodejs.org  ^(选 LTS 版^)
        echo      安装后重启此 BAT 即可
        goto :web_done
    )

    :: Clean old log
    del "%LT_LOG%" 2>nul

    :: Fire-and-forget: npx writes to log file
    start "Localtunnel" cmd /c "npx localtunnel --port %WEB_PORT% > "%LT_LOG%" 2>&1"

    echo   [?] 等待 localtunnel 启动...

    :: Poll log file for URL (max 20 seconds)
    set "LT_URL="
    for /l %%i in (1,1,20) do (
        timeout /t 1 >nul
        if exist "%LT_LOG%" (
            for /f "usebackq tokens=*" %%a in ("%LT_LOG%") do (
                echo %%a | findstr /i "url" >nul
                if !errorlevel! equ 0 (
                    set "LT_LINE=%%a"
                )
            )
        )
        if not "!LT_LINE!"=="" goto :lt_found
    )

:lt_found
    if not "!LT_LINE!"=="" (
        :: Parse "your url is: https://xxxx.loca.lt"
        for /f "tokens=3 delims=: " %%u in ("!LT_LINE!") do set "LT_URL=https:%%u"
        :: Clean trailing dots/spaces
        set "LT_URL=!LT_URL: =!"
    )

    if not "!LT_URL!"=="" (
        echo.
        echo   ╔══════════════════════════════════════╗
        echo   ║                                      ║
        echo   ║   📱 手机远程访问（蜂窝数据可用）:    ║
        echo   ║                                      ║
        echo   ║   !LT_URL!
        echo   ║                                      ║
        echo   ║   ⚠ 首次打开需点 "Continue"          ║
        echo   ║   然后「添加到主屏幕」= 独立 App      ║
        echo   ║                                      ║
        echo   ╚══════════════════════════════════════╝
        echo.
        start !LT_URL!
    ) else (
        echo   [!] localtunnel 未返回地址，可手动:
        echo       在新终端运行: npx localtunnel --port %WEB_PORT%
    )
) else (
    echo   [WARN] 服务可能未成功启动。请检查 FractalWeb 窗口的错误信息。
    echo   [提示] 可能需要: pip install 所需的包
)
:web_done
timeout /t 8 >nul
goto :menu

:: ============================================================
::        [B] Block Scan — 板块做多排序
:: ============================================================
:block_scan
cls
set "LR_SCRIPT=%WORKDIR%\long_rank.py"
echo.
echo   +------------------------------------------+
echo   ^|   BLOCK SCAN — 板块做多排序              ^|
echo   +------------------------------------------+
echo   ^|                                          ^|
echo   ^|   [1] DRBGWY  (当日八卦五阳)              ^|
echo   ^|   [2] JQBGWY  (近期八卦五阳)              ^|
echo   ^|   [3] ZXG2    (自选股2)                  ^|
echo   ^|   [4] YXG     (优选股)                   ^|
echo   ^|   [5] JXG     (精选股)                   ^|
echo   ^|   [6] zxg     (自选股)                   ^|
echo   ^|                                          ^|
echo   ^|   [L] List all blocks                    ^|
echo   ^|   [C] Custom block (输入文件名)           ^|
echo   ^|   [R] Open rank\ folder                  ^|
echo   ^|                                          ^|
echo   ^|   [M] Back to menu                       ^|
echo   ^|                                          ^|
echo   +------------------------------------------+
echo.
set /p blk="   > Select [1-6/L/C/R/M]: "
if "%blk%"=="1" call :do_blk DRBGWY
if "%blk%"=="2" call :do_blk JQBGWY
if "%blk%"=="3" call :do_blk ZXG2
if "%blk%"=="4" call :do_blk YXG
if "%blk%"=="5" call :do_blk JXG
if "%blk%"=="6" call :do_blk zxg
if /i "%blk%"=="L" goto :blk_list
if /i "%blk%"=="C" goto :blk_custom
if /i "%blk%"=="R" goto :blk_open
if /i "%blk%"=="M" goto :menu
echo   Invalid choice
timeout /t 1 >nul
goto :block_scan

:do_blk
echo.
echo   === 板块扫描: %~1 ===
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" --blk %~1 --fast
if !errorlevel! neq 0 (
    echo   [FAIL] 扫描出错 (code !errorlevel!)
)
echo.
echo   按任意键返回...
pause >nul
goto :block_scan

:blk_list
echo.
echo   === 板块列表 ===
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" --blk-list
echo.
echo   按任意键返回...
pause >nul
goto :block_scan

:blk_custom
echo.
set /p blkname="   板块文件名(不含.blk): "
if "%blkname%"=="" goto :block_scan
call :do_blk "%blkname%"
goto :block_scan

:blk_open
set "RANK_DIR=%WORKDIR%\rank"
if not exist "%RANK_DIR%" mkdir "%RANK_DIR%"
explorer "%RANK_DIR%"
goto :block_scan

:: ============================================================
::        [D] Deploy Pivots — 盘后流水线发布拐点到GitHub
:: ============================================================
:deploy_pivots
cls
set "PUB_SCRIPT=%WORKDIR%\publish_pivots.py"
set "DEPLOY_DIR=%WORKDIR%\deploy"
echo.
echo   +------------------------------------------+
echo   ^|   DEPLOY PIVOTS — 推送拐点到GitHub       ^|
echo   +------------------------------------------+
echo   ^|                                          ^|
echo   ^|   [1] Quick  (long_rank前100名, ~4min)    ^|
echo   ^|   [2] Full   (全部沪深主板, ~40min)       ^|
echo   ^|   [3] Single (单个标的, 测试)              ^|
echo   ^|   [T] Test   (601985, 不推送)             ^|
echo   ^|                                          ^|
echo   ^|   [M] Back to menu                       ^|
echo   ^|                                          ^|
echo   +------------------------------------------+
echo.
set /p dp="   > Select [1/2/3/T/M]: "
if "%dp%"=="1" goto :dp_quick
if "%dp%"=="2" goto :dp_full
if "%dp%"=="3" goto :dp_single
if /i "%dp%"=="T" goto :dp_test
if /i "%dp%"=="M" goto :menu
echo   Invalid choice
timeout /t 1 >nul
goto :deploy_pivots

:dp_quick
echo.
echo   === 快速推送: long_rank 前100名 ===
echo   步骤1: 先跑排名扫描...
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" 30 --fast
echo.
echo   步骤2: 生成拐点JSON...
%PY% "%PUB_SCRIPT%" --top 100
goto :dp_push

:dp_full
echo.
echo   === 全量推送: 全部沪深主板 (~40min) ===
cd /d "%WORKDIR%"
%PY% "%PUB_SCRIPT%" --batch
goto :dp_push

:dp_single
echo.
set /p dpcode="   输入6位代码: "
if "%dpcode%"=="" goto :deploy_pivots
cd /d "%WORKDIR%"
%PY% "%PUB_SCRIPT%" "%dpcode%"
echo.
echo   按任意键返回...
pause >nul
goto :deploy_pivots

:dp_test
echo.
echo   === 测试模式: 601985 中国核电 ===
cd /d "%WORKDIR%"
%PY% "%PUB_SCRIPT%" 601985
echo.
echo   按任意键返回...
pause >nul
goto :deploy_pivots

:dp_push
if exist "%DEPLOY_DIR%\pivots_index.json" (
    echo.
    echo   ═══════════════════════════════════════
    echo   === 步骤3: git push 到 GitHub Pages ===
    echo   ═══════════════════════════════════════
    cd /d "%WORKDIR%"
    git add deploy\*.json
    git commit -m "拐点更新 %date%"
    git push
    echo.
    if !errorlevel! equ 0 (
        echo   [OK] 推送成功！手机 PWA 自动获取最新拐点。
    ) else (
        echo   [WARN] git push 失败。请检查网络和认证。
    )
) else (
    echo   [ERR] 未生成部署文件，检查 publish_pivots.py 输出。
)
echo.
echo   按任意键返回...
pause >nul
goto :deploy_pivots

:: ============================================================
::        [V] Long Rank — 做多排名 · 轮动梯队 · 永动循环
:: ============================================================
:long_rank
cls
set "LR_SCRIPT=%WORKDIR%\long_rank.py"
if not exist "%LR_SCRIPT%" (
    echo   [ERR] long_rank.py not found: %LR_SCRIPT%
    pause
    goto :menu
)
echo.
echo   +------------------------------------------+
echo   ^|   LONG RANK — 做多排名 v4.0             ^|
echo   +------------------------------------------+
echo   ^|                                          ^|
echo   ^|   [S] Standard  (带名称, Top 30)         ^|
echo   ^|   [F] Fast      (无名称, Top 30)         ^|
echo   ^|   [T] Top 50    (Fast + Top 50)         ^|
echo   ^|                                          ^|
echo   ^|   [P] 持仓管理  (增/删/查)               ^|
echo   ^|   [R] 轮动快报  (今日升降级)             ^|
echo   ^|   [O] Open rank\ folder                 ^|
echo   ^|                                          ^|
echo   ^|   [M] Back to menu                       ^|
echo   ^|                                          ^|
echo   +------------------------------------------+
echo.
set /p lr="   > Select [S/F/T/P/R/O/M]: "
if /i "%lr%"=="S" goto :lr_standard
if /i "%lr%"=="F" goto :lr_fast
if /i "%lr%"=="T" goto :lr_top50
if /i "%lr%"=="P" goto :lr_manage
if /i "%lr%"=="R" goto :lr_rotation
if /i "%lr%"=="O" goto :lr_open
if /i "%lr%"=="M" goto :menu
echo   Invalid choice
timeout /t 1 >nul
goto :long_rank

:lr_standard
echo.
echo   === 做多排名扫描 (标准模式, Top 30) ===
echo.
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" 30
if !errorlevel! neq 0 (
    echo   [FAIL] 扫描出错 (code !errorlevel!)
)
echo.
echo   按任意键返回...
pause >nul
goto :long_rank

:lr_fast
echo.
echo   === 做多排名扫描 (快速模式, Top 30) ===
echo.
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" 30 --fast
if !errorlevel! neq 0 (
    echo   [FAIL] 扫描出错 (code !errorlevel!)
)
echo.
echo   按任意键返回...
pause >nul
goto :long_rank

:lr_top50
echo.
echo   === 做多排名扫描 (快速模式, Top 50) ===
echo.
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" 50 --fast
if !errorlevel! neq 0 (
    echo   [FAIL] 扫描出错 (code !errorlevel!)
)
echo.
echo   按任意键返回...
pause >nul
goto :long_rank

:lr_manage
echo.
echo   === 持仓管理 ===
cd /d "%WORKDIR%"
%PY% "%LR_SCRIPT%" --manage
goto :long_rank

:lr_rotation
echo.
echo   === 轮动快报 ===
echo.
cd /d "%WORKDIR%"
set "TODAY=%date:~0,10%"
set "TODAY=%TODAY:/=-%"
if exist "rank\long_%TODAY%.txt" (
    echo   [今日排名] rank\long_%TODAY%.txt
    echo.
    type "rank\long_%TODAY%.txt" | findstr /c:"轮动对比"
    echo.
    echo   完整排名见 rank\ 文件夹
) else (
    echo   [!] 今日排名文件不存在。请先运行 [S]/[F]/[T] 扫描。
)
echo.
echo   按任意键返回...
pause >nul
goto :long_rank

:lr_open
set "RANK_DIR=%WORKDIR%\rank"
if not exist "%RANK_DIR%" mkdir "%RANK_DIR%"
explorer "%RANK_DIR%"
goto :long_rank

:: ============================================================
::                        EXIT
:: ============================================================
:end
echo.
echo   Goodbye.
timeout /t 1 >nul
exit /b 0
