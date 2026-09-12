@echo off
title STG2 Live Trading Monitor (AngelOne SmartAPI)
cd /d "C:\Users\ASUS\.gemini\antigravity\scratch\intraday-bot"
echo ==========================================================
echo   STG2 LIVE TRADING MONITOR (09:15 AM - 03:30 PM IST)
echo   Powered by AngelOne SmartAPI
echo ==========================================================
echo.
"C:\Users\ASUS\AppData\Local\Programs\Python\Python313\python.exe" live_trade_monitor.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Monitor stopped with an error code %ERRORLEVEL%
    pause
)
