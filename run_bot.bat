@echo off
rem Runs one game's bot:  run_bot.bat <game id>   e.g. run_bot.bat d4
rem Normally started by run_<game id>.bat (double-click) or by the scheduled task from install_windows.ps1.
rem Restarts the bot 30 s after a crash. Settings: config.txt. Output is shown here and saved in logs\bot-<game id>.log.
cd /d "%~dp0"
set GAME=%~1
if "%GAME%"=="" (
  echo Usage: run_bot.bat ^<game id^>, e.g. run_bot.bat d4. Or double-click run_d4.bat.
  pause
  exit /b 1
)
if not exist config.txt (
  copy config.example.txt config.txt > nul
  echo config.txt created: open it, fill in the token under [%GAME%], then run this again.
  pause
  exit /b 1
)
title CarryRep %GAME%
set PYTHONIOENCODING=utf-8
set PY=python
if exist python.txt set /p PY=<python.txt

:loop
"%PY%" bot.py %GAME%
if errorlevel 2 if not errorlevel 3 (
  echo Configuration problem, see the message above. Fix config.txt and run this again.
  pause
  exit /b 2
)
echo Bot stopped. Restarting in 30 s (close this window to stop it) ...
timeout /t 30 /nobreak > nul
goto loop
