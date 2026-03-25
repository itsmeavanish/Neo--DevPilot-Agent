@echo off
title JARVIS APK Builder
echo ============================================
echo        JARVIS APK Build Script
echo ============================================
echo.

cd /d "%~dp0"

:: Check for Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed!
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

:: Check for npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is not installed!
    pause
    exit /b 1
)
echo [OK] npm found

:: Install dependencies
echo.
echo Installing dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: Install EAS CLI if needed
echo.
echo Checking EAS CLI...
call npx eas-cli --version >nul 2>&1
if errorlevel 1 (
    echo Installing EAS CLI...
    call npm install -g eas-cli
)
echo [OK] EAS CLI ready

:: Login to Expo (if needed)
echo.
echo Checking Expo login...
call npx eas whoami >nul 2>&1
if errorlevel 1 (
    echo You need to login to Expo first:
    call npx eas login
)

:: Build APK
echo.
echo ============================================
echo Building APK (this may take 10-20 minutes)
echo ============================================
echo.
call npx eas build --platform android --profile production --non-interactive

echo.
echo ============================================
echo Build submitted! Check https://expo.dev for progress.
echo The APK will be available for download when complete.
echo ============================================
pause
