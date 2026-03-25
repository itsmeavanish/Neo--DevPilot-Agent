@echo off
echo ====================================================
echo              JARVIS Server Starter
echo ====================================================
echo.
echo Starting JARVIS backend server...
echo.
echo Once you see "Application startup complete",
echo the server is ready for agent connections.
echo.
echo Keep this window open while using JARVIS.
echo Press Ctrl+C to stop the server.
echo.
echo ====================================================

cd /d "C:\Users\7CIN\Desktop\Jarvis"
python -m src.jarvis.main

pause