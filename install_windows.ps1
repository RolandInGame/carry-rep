# Registers two Windows scheduled tasks for the bot folder this script lives in:
#   CarryRep-<folder>         - runs run_bot.bat at every boot, even when nobody is logged in
#   CarryRep-<folder>-Backup  - runs backup.py every day at 04:00
# (<folder> = this folder's name, so one bot per game can run on the same PC in separate folders)
# Run once in PowerShell as Administrator:
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1
# Remove later with:
#   Unregister-ScheduledTask CarryRep-<folder>; Unregister-ScheduledTask CarryRep-<folder>-Backup

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$task = "CarryRep-" + (Split-Path -Leaf $dir)

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "python not found in PATH. Install Python 3.10+ and tick 'Add python.exe to PATH'." }
if ($python -like "*WindowsApps*") { throw "PATH points to the Microsoft Store python stub. Install Python from python.org (tick 'Add python.exe to PATH') and reopen PowerShell." }
Set-Content -Path "$dir\python.txt" -Value $python -NoNewline   # the task uses this exact python
if (-not (Select-String -Path "$dir\config.txt" -Pattern '^\s*token\s*=\s*\S' -Quiet -ErrorAction SilentlyContinue)) {
  throw "Fill in the token in config.txt first (copy config.example.txt to config.txt if it does not exist)." }

# S4U = run whether the user is logged on or not, without storing a password (internet access works)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew

$bot = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$dir\run_bot.bat`"" -WorkingDirectory $dir
Register-ScheduledTask -TaskName $task -Action $bot -Principal $principal -Settings $settings `
  -Trigger (New-ScheduledTaskTrigger -AtStartup) -Force | Out-Null

$bk = New-ScheduledTaskAction -Execute $python -Argument "`"$dir\backup.py`"" -WorkingDirectory $dir
Register-ScheduledTask -TaskName "$task-Backup" -Action $bk -Principal $principal -Settings $settings `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 4am) -Force | Out-Null

# Keep the machine awake on AC power
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0

Start-ScheduledTask -TaskName $task
Write-Host "Done. Tasks $task and $task-Backup registered; log: $dir\logs\bot.log"
