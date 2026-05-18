@echo off
title JARVIS Agent Installer
color 0A

echo ============================================
echo        JARVIS Remote Agent Installer
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed!
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo [OK] Python found
echo.

:: Install dependencies
echo Installing dependencies...
pip install websockets psutil --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

:: Get user input
set /p DEVICE_NAME="Avanish Laptop"

if "%DEVICE_NAME%"=="" (
    set DEVICE_NAME=%COMPUTERNAME%
)

:: Create config directory
if not exist "%USERPROFILE%\.jarvis" mkdir "%USERPROFILE%\.jarvis"

:: Copy agent script
copy /Y "%~dp0jarvis_agent.py" "%USERPROFILE%\.jarvis\jarvis_agent.py" >nul


:: Create config file
echo Creating configuration...
(
echo JARVIS_SERVER=https://precommercial-nubbly-theda.ngrok-free.dev
echo JARVIS_DEVICE_NAME=%DEVICE_NAME%
) > "%USERPROFILE%\.jarvis\config.env"

:: Create run script
(
echo @echo off
echo title JARVIS Agent - %DEVICE_NAME%
echo cd /d "%USERPROFILE%\.jarvis"
echo for /f "tokens=1,* delims==" %%%%a in ^(config.env^) do set %%%%a=%%%%b
echo python jarvis_agent.py
echo pause
) > "%USERPROFILE%\.jarvis\run_agent.bat"

:: Create desktop shortcut
echo Creating desktop shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\JARVIS Agent.lnk'); $s.TargetPath = '%USERPROFILE%\.jarvis\run_agent.bat'; $s.WorkingDirectory = '%USERPROFILE%\.jarvis'; $s.IconLocation = 'shell32.dll,21'; $s.Save()"

echo.
echo ============================================
echo        Installation Complete!
echo ============================================
echo.
echo A shortcut "JARVIS Agent" has been created on your desktop.
echo Double-click it to start the agent.
echo.
echo Your laptop will appear in the JARVIS mobile app!
echo.
pause
