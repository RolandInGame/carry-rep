@echo off
rem Starts bot.py and restarts it 30 s after a crash. Started at boot by the scheduled task
rem that install_windows.ps1 creates; you can also double-click it to run by hand.
rem All settings are in config.txt in this folder. Output is shown here and saved in logs\bot.log.
cd /d "%~dp0"
if not exist config.txt (
  copy config.example.txt config.txt > nul
  echo config.txt created: open it, fill in the token, then run this again.
  pause
  exit /b 1
)
findstr /R /C:"^ *token *= *[^ ]" config.txt > nul
if errorlevel 1 (
  echo The token in config.txt is empty: open config.txt, fill in the token, then run this again.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8
set PY=python
if exist python.txt set /p PY=<python.txt

:loop
"%PY%" bot.py
if errorlevel 2 if not errorlevel 3 (
  echo Configuration problem, see the message above. Fix config.txt and run this again.
  pause
  exit /b 2
)
echo Bot stopped. Restarting in 30 s (close this window to stop it) ...
timeout /t 30 /nobreak > nul
goto loop
