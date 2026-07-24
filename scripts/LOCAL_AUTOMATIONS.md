# 本机自动化（替代 Cursor Cloud Automations）

本仓库将原先在 Cursor Automations **云端**执行的任务，改为**本机定时执行**。

> Cloud Agent 无法直接改 Automations 面板 Runtime。  
> 请先停用对应 Cloud 任务，再在本机安装定时任务。

## 任务对照

| Automations / 业务名 | Windows 脚本 | 时间 | 说明 |
|---|---|---|---|
| 川藏一区Todo周报 | `scripts/run_kpi_todo_local.ps1` | 周一/周四 14:00 | |
| **利润数据源推送** | `scripts/run_lr_datasource_local.ps1` | 每天 **23:15** | 只推五城原始日利润 Excel，**不填模板、不截看板** |
| **利润填写推送**（原 LR日报日更） | `scripts/run_lr_profit_fill_local.ps1` | 每天 **23:30** | 填 `数据源(日)` → WPS 五城看板 → 企微 5 图 + Excel |
| 拜访检核日更 | `scripts/run_visit_check_local.ps1` | 每天 09:00 | |
| 自配门店早间监控 | `scripts/run_store_morning_monitor_local.ps1` | 每天 08:30 | |

> **禁止把「利润数据源推送」和「利润填写推送」混成同一个脚本/任务。**

## Windows 一键安装（推荐）

### 前置

1. 已安装 [Python 3](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**
2. 本机已有本仓库代码；利润填写推送需安装 **WPS**

### 安装定时任务

```powershell
cd C:\Users\Administrator\Documents\fuzzy-umbrella
powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1
```

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_local_automations_windows.ps1
```

### 手动试跑

```powershell
# 利润数据源推送（仅原始 Excel）
powershell -ExecutionPolicy Bypass -File scripts\run_lr_datasource_local.ps1 -TargetDate 2026-07-22

# 利润填写推送（填表+五城图+Excel）
powershell -ExecutionPolicy Bypass -File scripts\run_lr_profit_fill_local.ps1 -TargetDate 2026-07-22

powershell -ExecutionPolicy Bypass -File scripts\run_kpi_todo_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_visit_check_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1
```

### 查看是否装上

```powershell
schtasks /Query /TN ChuanzangLrDatasourceLocal
schtasks /Query /TN ChuanzangLrProfitFillLocal
schtasks /Query /TN ChuanzangVisitCheckLocal
```

或打开：**任务计划程序** → 找 `Chuanzang*`。

## 企微 Webhook

| 任务 | 环境变量 | 默认 key |
|---|---|---|
| 利润填写推送 | `LR_WECOM_WEBHOOK` | `103699eb-...` |
| 利润数据源推送 | `LR_DATASOURCE_WECOM_WEBHOOK` | `c44fb1bf-...` |
| Todo 周报 | `WECOM_WEBHOOK` | `103699eb-...` |

## 日志

- `logs/lr_datasource_local.log` — 利润数据源推送
- `logs/lr_profit_fill_local.log` — 利润填写推送
- `logs/kpi_todo_local.log`
- `logs/visit_check_local.log`
- `logs/store_morning_monitor_local.log`
