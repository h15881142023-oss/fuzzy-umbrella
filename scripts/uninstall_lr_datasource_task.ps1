# Remove obsolete LR datasource scheduled task. ASCII-only.
# Does not delete script files; only stops/unregisters the Windows task.
$ErrorActionPreference = "Continue"
$Name = "ChuanzangLrDatasourceLocal"
try {
    $t = Get-ScheduledTask -TaskName $Name -ErrorAction Stop
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    Write-Host "Removed scheduled task: $Name"
} catch {
    Write-Host "Task not found or already removed: $Name"
}
Write-Host "Remaining LR tasks:"
Get-ScheduledTask -TaskName ChuanzangLr* -ErrorAction SilentlyContinue |
    Format-Table TaskName, State -AutoSize
exit 0
