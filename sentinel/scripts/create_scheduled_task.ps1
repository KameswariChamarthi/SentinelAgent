<#
    create_scheduled_task.ps1

    Registers Sentinel to start automatically at user logon via Windows
    Task Scheduler. This is an alternative/complement to the app's own
    background thread -- useful if you want Sentinel to launch even
    before you open it manually.

    Usage (run from an elevated PowerShell prompt):
        .\create_scheduled_task.ps1 -ExePath "C:\Path\To\Sentinel.exe"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
)

$taskName = "SentinelSystemMaintenanceAgent"

$action = New-ScheduledTaskAction -Execute $ExePath
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Launches Sentinel offline system maintenance agent at logon." `
    -Force

Write-Host "Registered scheduled task '$taskName' to launch $ExePath at logon."
Write-Host "To remove it later: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
