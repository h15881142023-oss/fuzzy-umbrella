Param(
    [string]$TaskName = "todo达成监控"
)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "task removed: $TaskName"
}
else {
    Write-Output "task not found: $TaskName"
}
