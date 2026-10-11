# DSH-KRouter daily timer on Windows: one scheduled task, 09:10 local time, runs extras\host-daily-evolution\run.py.
# Usage (PowerShell, as yourself - no admin needed):
#   $env:OBSIDIAN_VAULT = "D:\Obsidian\MyVault"; .\scripts\install_windows_task.ps1
#   .\scripts\install_windows_task.ps1 -Uninstall
# Output goes to %LOCALAPPDATA%\dsh-krouter\daily.log. The vault is never touched by this script.
param(
    [switch]$Uninstall,
    [string]$Vault = $env:OBSIDIAN_VAULT,
    [string]$Python = "",
    [string]$At = "09:10"
)
$ErrorActionPreference = "Stop"
$TaskName = "DSH-KRouter daily evolution"

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "timer removed: $TaskName"
    } else {
        Write-Output "no timer named: $TaskName"
    }
    exit 0
}

if (-not $Vault) {
    Write-Output "timer not registered: set OBSIDIAN_VAULT to YOUR vault (or pass -Vault), then re-run."
    exit 1
}
if (-not $Python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $cmd) { Write-Output "HOST ACTION: install Python 3.10+ first."; exit 1 }
    $Python = $cmd.Source
}
$Root = Split-Path -Parent $PSScriptRoot
$RunPy = Join-Path $Root "extras\host-daily-evolution\run.py"
$LogDir = Join-Path $env:LOCALAPPDATA "dsh-krouter"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "daily.log"

# cmd /c so the task can set OBSIDIAN_VAULT and append to the log; the vault path is quoted
$Arg = "/c set `"OBSIDIAN_VAULT=$Vault`" && `"$Python`" `"$RunPy`" >> `"$Log`" 2>&1"
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $Arg -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Output "self-evolution timer registered: $TaskName at $At vault=$Vault"
Write-Output "log: $Log"
Write-Output "undo: .\scripts\install_windows_task.ps1 -Uninstall"
