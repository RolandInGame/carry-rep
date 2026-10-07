# Registers Windows scheduled tasks for this folder:
#   CarryRep         - runs every bot listed in "games" in config.txt at each boot, even when nobody is logged in
#   CarryRep-Backup  - backs up the shared data.db every day at 04:00
# Adding a game needs no change here: add it to "games" in config.txt and restart the CarryRep task.
# Run once in PowerShell as Administrator:
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1
# Remove the tasks later with:  Unregister-ScheduledTask CarryRep; Unregister-ScheduledTask CarryRep-Backup

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "python not found in PATH. Install Python 3.10+ and tick 'Add python.exe to PATH'." }
if ($python -like "*WindowsApps*") { throw "PATH points to the Microsoft Store python stub. Install Python from python.org (tick 'Add python.exe to PATH') and reopen PowerShell." }
Set-Content -Path "$dir\python.txt" -Value $python -NoNewline   # the tasks use this exact python
if (-not (Test-Path "$dir\config.txt")) { throw "Create config.txt first (copy config.example.txt and fill in the tokens)." }

# S4U = run whether the user is logged on or not, without storing a password (internet access works)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew

# Replaced by the single CarryRep task below; leaving them would start each bot twice.
Get-ScheduledTask -TaskName "CarryRep-*" -ErrorAction SilentlyContinue |
  Where-Object { $_.TaskName -ne "CarryRep-Backup" } |
  ForEach-Object {
    Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
    Write-Host "Removed the old task $($_.TaskName)."
  }

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$dir\run_bot.bat`"" -WorkingDirectory $dir
Register-ScheduledTask -TaskName "CarryRep" -Action $action -Principal $principal -Settings $settings `
  -Trigger (New-ScheduledTaskTrigger -AtStartup) -Force | Out-Null
Start-ScheduledTask -TaskName "CarryRep"
Write-Host "Task CarryRep registered and started; logs: $dir\logs\bot-<game id>.log"

$bk = New-ScheduledTaskAction -Execute $python -Argument "`"$dir\backup.py`"" -WorkingDirectory $dir
Register-ScheduledTask -TaskName "CarryRep-Backup" -Action $bk -Principal $principal -Settings $settings `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 4am) -Force | Out-Null
Write-Host "Task CarryRep-Backup registered (daily 04:00)."

# Keep the machine awake on AC power
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
