@echo off
rem Double-click this file to run every bot listed in "games" in config.txt, all in this one window.
rem   run_bot.bat            -> every game in "games"
rem   run_bot.bat d4         -> only that game (same as double-clicking run_d4.bat)
rem Settings: config.txt. Each bot also keeps its own logs\bot-<game id>.log.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=python
if exist python.txt set /p PY=<python.txt

if not exist config.txt (
  copy config.example.txt config.txt > nul
  echo config.txt created: open it, fill in the tokens, then run this again.
  pause
  exit /b 1
)

set GAME=%~1
if not "%GAME%"=="" goto single

rem --- every game: run_all.py starts one process per game and restarts them itself ---
title CarryRep
"%PY%" run_all.py
if errorlevel 2 (
  echo Configuration problem, see the message above. Fix config.txt and run this again.
  pause
  exit /b 2
)
echo All bots stopped.
pause
exit /b 0

rem --- one game only ---
:single
title CarryRep %GAME%
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
