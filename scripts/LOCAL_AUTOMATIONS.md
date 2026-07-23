# 本机自动化（替代 Cursor Cloud Automations）

本仓库将原先在 Cursor Automations **云端**执行的 5 个任务，改为**本机定时执行**。

> Cloud Agent 无法直接改 Automations 面板 Runtime。  
> 请先停用那 5 个 Cloud 任务，再在本机安装定时任务。

## 任务对照

| Automations 名称 | Windows 脚本 | 时间 |
|---|---|---|
| 川藏一区Todo周报 | `scripts/run_kpi_todo_local.ps1` | 周一/周四 14:00 |
| LR日报日更 / 日利润数据源推送 | `scripts/run_lr_daily_local.ps1` | 每天 23:30 |
| 拜访检核日更 | `scripts/run_visit_check_local.ps1` | 每天 09:00 |
| 自配门店早间监控 | `scripts/run_store_morning_monitor_local.ps1` | 每天 08:30 |

## Windows 一键安装（推荐）

### 前置

1. 已安装 [Python 3](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**
2. 本机已有本仓库代码（可用 Git 或 Cursor 打开后拉取）

### 安装定时任务

1. 打开 **PowerShell**（开始菜单搜「PowerShell」；若提示权限不足，右键「以管理员身份运行」）
2. 进入仓库目录（路径改成你自己的）：

```powershell
cd D:\你的路径\fuzzy-umbrella
```

3. 拉最新代码：

```powershell
git fetch origin
git checkout cursor/automations-to-local-7100
git pull
```

4. 安装：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_local_automations_windows.ps1
```

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_local_automations_windows.ps1
```

### 手动试跑

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_kpi_todo_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_lr_daily_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_visit_check_local.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1
```

拜访检核若要推线上 API：

```powershell
$env:CZ_VISIT_PUSH_API="1"
powershell -ExecutionPolicy Bypass -File scripts\run_visit_check_local.ps1
```

自配门店早间监控依赖本机 Chrome CDP（9222）+ 已登录的 Power BI：

```powershell
# 第一次：会自动打开 ChromeAutomation 窗口，请在里面登录 Power BI 后重跑
powershell -ExecutionPolicy Bypass -File scripts\run_store_morning_monitor_local.ps1
```

### 查看是否装上

```powershell
schtasks /Query /TN ChuanzangVisitCheckLocal
schtasks /Query /TN ChuanzangLrDailyLocal
schtasks /Query /TN ChuanzangKpiTodoMonLocal
```

或打开：**任务计划程序** → 任务计划程序库，找 `Chuanzang*`。

## Mac（可选）

```bash
bash scripts/install_local_automations_launchd.sh
```

## 依赖

- Windows 10/11 + 任务计划程序（或 macOS launchd）
- Python 3 + `.venv`
- Playwright Chromium（脚本会自动尝试安装）
- 业务后台可达：`http://47.112.178.78:13000`

## 日志

- `logs/kpi_todo_local.log`
- `logs/lr_daily_local.log`
- `logs/visit_check_local.log`
- `logs/store_morning_monitor_local.log`
