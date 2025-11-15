@echo off
chcp 65001 >nul

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
REM 切换到脚本所在目录
cd /d "%SCRIPT_DIR%"
REM 再回到上级目录（项目根目录）
cd ..

echo ========================================
echo 表情包自动重命名工具
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未检测到Python，请先安装Python 3.7+
    echo.
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查配置文件
if not exist "tools\config.bat" (
    echo 未找到配置文件，正在创建...
    echo.
    (
        echo @echo off
        echo REM ========== API配置 ==========
        echo set OPENAI_API_KEY=your-api-key-here
        echo set OPENAI_BASE_URL=https://api.openai.com/v1
        echo set OPENAI_MODEL=gpt-4-vision-preview
        echo.
        echo REM ========== 表情包目录 ==========
        echo REM 可以使用相对路径或绝对路径
        echo REM 示例: data/avatars/yuki/emoji
        echo REM 示例: C:\Users\Username\Pictures\emoji
        echo set EMOJI_DIR=data/avatars/yuki/emoji
        echo.
        echo REM 常见配置示例：
        echo REM Gemini: set OPENAI_MODEL=gemini-pro-vision
        echo REM Claude: set OPENAI_MODEL=claude-3-opus-20240229
    ) > tools\config.bat
    
    echo 已创建配置文件: tools\config.bat
    echo.
    echo 请先编辑配置文件，设置你的API密钥和模型
    echo 按任意键打开配置文件进行编辑...
    pause >nul
    notepad tools\config.bat
    echo.
    echo 编辑完成后请再次运行此脚本
    pause
    exit /b 0
)

REM 加载配置
call tools\config.bat

REM 检查API密钥
if "%OPENAI_API_KEY%"=="your-api-key-here" (
    echo 错误: 请先在 tools\config.bat 中设置你的API密钥
    echo.
    echo 按任意键打开配置文件进行编辑...
    pause >nul
    notepad tools\config.bat
    echo.
    echo 编辑完成后请再次运行此脚本
    pause
    exit /b 1
)

REM 显示当前配置
echo 当前配置:
echo    API密钥: %OPENAI_API_KEY:~0,20%...
echo    API地址: %OPENAI_BASE_URL%
echo    使用模型: %OPENAI_MODEL%
echo    表情目录: %EMOJI_DIR%
echo.

REM 提示用户是否使用自定义路径
echo 是否使用自定义表情包路径？
echo [1] 使用配置文件中的路径: %EMOJI_DIR%
echo [2] 输入自定义路径
echo [3] 拖拽文件夹到此窗口
echo.
set /p choice="请选择 (1/2/3，直接回车默认选1): "

if "%choice%"=="2" (
    echo.
    echo 请输入表情包文件夹的完整路径:
    echo 示例: C:\Users\Username\Pictures\emoji
    echo 或相对路径: data\avatars\yuki\emoji
    set /p EMOJI_DIR="路径: "
    echo.
    echo 使用路径: %EMOJI_DIR%
)

if "%choice%"=="3" (
    echo.
    echo 请将表情包文件夹拖拽到此窗口，然后按回车:
    set /p EMOJI_DIR="路径: "
    REM 移除可能的引号
    set EMOJI_DIR=%EMOJI_DIR:"=%
    echo.
    echo 使用路径: %EMOJI_DIR%
)

REM 检查目录是否存在
if not exist "%EMOJI_DIR%" (
    echo.
    echo 错误: 目录不存在: %EMOJI_DIR%
    echo 请检查路径是否正确
    pause
    exit /b 1
)

echo.
echo 目录验证成功！
echo.

REM 检查并安装依赖
echo 检查依赖...
python -c "import openai" >nul 2>&1
if errorlevel 1 (
    echo 未安装openai库，正在安装...
    pip install openai
    if errorlevel 1 (
        echo 安装失败，请手动运行: pip install openai
        pause
        exit /b 1
    )
    echo 依赖安装完成
    echo.
)

REM 运行脚本
echo 启动重命名工具...
echo.
python tools\auto_rename_emoji.py

REM 完成
echo.
echo ========================================
echo 处理完成！
echo ========================================
pause