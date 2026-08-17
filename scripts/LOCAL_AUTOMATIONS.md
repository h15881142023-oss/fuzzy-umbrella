# 本机自动化（替代 Cursor Cloud Automations）

本仓库将原先在 Cursor Automations **云端**执行的任务，改为**本机定时执行**。

> Cloud Agent 无法直接改 Automations 面板 Runtime。  
> 请先停用对应 Cloud 任务，再在本机安装定时任务。

## 任务对照

| Automations / 业务名 | Windows 脚本 | 时间 | 说明 |
|---|---|---|---|
| 川藏一区Todo周报 | `scripts/run_kpi_todo_local.ps1` | 周一/周四 14:00 | |
| **利润填写推送**（原 LR日报日更） | `scripts/run_lr_profit_fill_local.ps1` | 每天 **23:30** | 填 `数据源(日)` + 团购利润 → WPS 五城看板 → 企微 5 图 + Excel |
| 拜访检核日更 | `scripts/run_visit_check_local.ps1` | 每天 09:00 | |
| 自配门店早间监控 | `scripts/run_store_morning_monitor_local.ps1` | 每天 08:30 | |

> 「利润数据源推送」已停用并删除（原 23:15 / `ChuanzangLrDatasourceLocal`）。

## Windows 一键安装（推荐）

### 前置

1. 已安装 [Python 3](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**
2. 本机已有本仓库代码；利润填写推送需安装 **WPS**

### 安装定时任务

**必须用管理员 PowerShell**（开始菜单搜索 PowerShell → 右键「以管理员身份运行」）：

```powershell
cd C:\Users\Administrator\Documents\fuzzy-umbrella
powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1
```

脚本若检测到无管理员权限，会自动弹 UAC 提权；点「是」即可。

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_local_automations_windows.ps1
```

### 手动试跑

```powershell
# 利润填写推送（填表+五城图+Excel）
powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_local.ps1 -TargetDate 2026-07-22

# 探测 32 位 PowerShell（必须 Bypass，否则 Restricted 策略会加载失败）
powershell -ExecutionPolicy Bypass -NoProfile -Command ". .\scripts\_local_common.ps1; Get-WpsMatchedPowerShell"

# 表已填好但看板导出失败时：只导出+推送，不要再 scrape
# 先同步 hotfix（把 SHA 换成最新 short sha）
$sha = "REPLACE_SHA"
.\.venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlretrieve('https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@$sha/lr/download_hotfix.py','lr/download_hotfix.py'); print('ok')"
.\.venv\Scripts\python.exe lr\download_hotfix.py $sha
powershell -ExecutionPolicy Bypass -File scripts\run_lr_kanban_push_existing.ps1 -TargetDate 2026-08-16

# 补齐利润填写推送：默认 2026-07-22 .. 2026-07-25（含），单日失败继续下一天
# 看板导出在 PowerShell -STA 线程（剪贴板），勿用管理员窗口
powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_backfill.ps1
# 或指定区间：
# powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_backfill.ps1 -FromDate 2026-07-20 -ToDate 2026-07-25

powershell -ExecutionPolicy Bypass -File scripts\run_kpi_todo_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_visit_check_local.ps1

# 自配早间监控（08:30）：需 ChromeAutomation 已登录 Power BI
Get-ScheduledTaskInfo -TaskName ChuanzangStoreMorningLocal |
  Select-Object LastRunTime, LastTaskResult, NextRunTime
Get-Content logs\store_morning_monitor_local.log -Tail 40 -Encoding UTF8 -ErrorAction SilentlyContinue
powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1

# 若报「未登录」但地址仍是 reportEmbed：本地缺新脚本时，先一键拉文件（不依赖本地 .ps1）
$sha = "e67a921"
$base = "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@$sha"
@(
  "scrapers/powerbi_subsidy_daily.py",
  "scrapers/powerbi_page_js.py",
  "scrapers/cdp_client.py",
  "scripts/run_store_morning_monitor_local.ps1",
  "scripts/start_chrome_powerbi.ps1",
  "scripts/_local_common.ps1",
  "scripts/sync_store_morning_from_cdn.ps1"
) | ForEach-Object {
  $out = $_ -replace "/", "\"
  New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null
  Invoke-WebRequest "$base/$_" -OutFile $out -UseBasicParsing
  Write-Host "OK $out"
}
# 确认 ChromeAutomation 能看到「补贴监测」后重跑：
powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1
Get-Content logs\store_morning_monitor_local.log -Tail 50 -Encoding UTF8
```

### 查看是否装上

```powershell
schtasks /Query /TN ChuanzangLrProfitFillLocal
schtasks /Query /TN ChuanzangStoreMorningLocal
schtasks /Query /TN ChuanzangVisitCheckLocal
```

或打开：**任务计划程序** → 找 `Chuanzang*`。

## 企微 Webhook

| 任务 | 环境变量 | 默认 key |
|---|---|---|
| 利润填写推送 | `LR_WECOM_WEBHOOK` | `103699eb-...` |
| Todo 周报 | `WECOM_WEBHOOK` | `103699eb-...` |

## 日志

- `logs/lr_profit_fill_local.log` — 利润填写推送
- `logs/kpi_todo_local.log`
- `logs/visit_check_local.log`
- `logs/store_morning_monitor_local.log`
