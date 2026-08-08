Param(
    [string]$TaskName = "自配上线播报"
)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "任务已删除: $TaskName"
} else {
    Write-Output "任务不存在: $TaskName"
}
