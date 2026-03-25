@echo off
echo ====================================================
echo                JARVIS Agent Starter
echo ====================================================
echo.
echo This script will help you run the JARVIS agent properly.
echo.
echo STEP 1: First, start the JARVIS server
echo ----------------------------------------
echo Open a NEW Command Prompt window and run:
echo.
echo   cd C:\Users\7CIN\Desktop\Jarvis
echo   python -m src.jarvis.main
echo.
echo Wait until you see "Application startup complete" message
echo.
echo STEP 2: Then run the agent
echo --------------------------
echo In THIS window, the agent will now start:
echo.

cd /d "C:\Users\7CIN\Desktop\Jarvis\agent-installer"
python jarvis_agent.py

pause