# Registers Windows scheduled tasks for this folder:
#   CarryRep-<game id>  - one per run_<game id>.bat: runs that game's bot at every boot, even when nobody is logged in
#   CarryRep-Backup     - backs up the shared data.db every day at 04:00
# Run once in PowerShell as Administrator (run it again after adding a game):
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1
# Remove a task later with:  Unregister-ScheduledTask CarryRep-d4

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "python not found in PATH. Install Python 3.10+ and tick 'Add python.exe to PATH'." }
if ($python -like "*WindowsApps*") { throw "PATH points to the Microsoft Store python stub. Install Python from python.org (tick 'Add python.exe to PATH') and reopen PowerShell." }
Set-Content -Path "$dir\python.txt" -Value $python -NoNewline   # the tasks use this exact python
if (-not (Test-Path "$dir\config.txt")) { throw "Create config.txt first (copy config.example.txt and fill in the tokens)." }

$games = Get-ChildItem "$dir\run_*.bat" | Where-Object { $_.Name -ne "run_bot.bat" } |
  ForEach-Object { $_.BaseName.Substring(4) }
if (-not $games) { throw "No run_<game id>.bat files found." }

# S4U = run whether the user is logged on or not, without storing a password (internet access works)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew

foreach ($g in $games) {
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$dir\run_bot.bat`" $g" -WorkingDirectory $dir
  Register-ScheduledTask -TaskName "CarryRep-$g" -Action $action -Principal $principal -Settings $settings `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) -Force | Out-Null
  Start-ScheduledTask -TaskName "CarryRep-$g"
  Write-Host "Task CarryRep-$g registered and started; log: $dir\logs\bot-$g.log"
}

$bk = New-ScheduledTaskAction -Execute $python -Argument "`"$dir\backup.py`"" -WorkingDirectory $dir
Register-ScheduledTask -TaskName "CarryRep-Backup" -Action $bk -Principal $principal -Settings $settings `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 4am) -Force | Out-Null
Write-Host "Task CarryRep-Backup registered (daily 04:00)."

# Keep the machine awake on AC power
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
