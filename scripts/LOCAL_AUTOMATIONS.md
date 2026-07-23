# 本机自动化（替代 Cursor Cloud Automations）

本仓库将原先在 Cursor Automations **云端**执行的 5 个任务，改为本机 **launchd** 定时执行。

> **重要限制**：Cloud Agent 无法通过 API 修改 Automations 面板里的 Runtime。  
> 请在本机安装 launchd 后，到 [cursor.com/automations](https://cursor.com/automations) **停用**这 5 个 Cloud 任务，避免重复跑。

## 任务对照

| Automations 名称 | 本机脚本 | 时间 |
|---|---|---|
| 川藏一区Todo周报 | `scripts/run_kpi_todo_local.sh` | 周一/周四 14:00 |
| LR日报日更（Cloud 23:30） | `scripts/run_lr_daily_local.sh` | 每天 23:30 |
| 日利润数据源推送 | 同上（写入 `数据源(日)` + 企微） | 每天 23:30 |
| 拜访检核日更（Cloud） | `scripts/run_visit_check_local.sh` | 每天 09:00 |
| 自配门店早间监控（云端） | `scripts/run_store_morning_monitor_local.sh` | 每天 08:30 |

已知 Cloud Automation ID（可直接打开停用）：

- 拜访检核：https://cursor.com/automations/89caebed-81bd-11f1-a7d1-d6b4613131ce
- LR 日报：https://cursor.com/automations/0e10d6f8-844a-11f1-a7d1-d6b4613131ce

## 一键安装（Mac）

在仓库根目录执行：

```bash
bash scripts/install_local_automations_launchd.sh
```

卸载：

```bash
bash scripts/uninstall_local_automations_launchd.sh
```

## 手动试跑

```bash
# Todo 周报
bash scripts/run_kpi_todo_local.sh

# LR 日报 / 日利润数据源
bash scripts/run_lr_daily_local.sh

# 拜访检核（默认写本地库；推线上 API 则 CZ_VISIT_PUSH_API=1）
bash scripts/run_visit_check_local.sh
CZ_VISIT_PUSH_API=1 bash scripts/run_visit_check_local.sh

# 自配门店早间监控（默认跑代补一次；可覆盖命令）
bash scripts/run_store_morning_monitor_local.sh
CZ_STORE_MORNING_CMD='python scrapers/scrape_delivery_fee_daily_cdp.py' \
  bash scripts/run_store_morning_monitor_local.sh
```

## 依赖

- macOS + launchd
- Python 3 + `.venv`
- Playwright Chromium（脚本会尝试 `python -m playwright install chromium`）
- 业务后台可达：`http://47.112.178.78:13000`
- 默认账号见 `config.py` / `.cursor/rules/automation-defaults.mdc`

## 日志

- `logs/kpi_todo_local.log`
- `logs/lr_daily_local.log`
- `logs/visit_check_local.log`
- `logs/store_morning_monitor_local.log`

## 为什么不用 Automations「改成本机 Runtime」？

个人账号 Automations UI 通常只能选 Cursor Cloud；自托管/My Machines 需 Team 权限。  
因此采用 **停用 Cloud Automations + 本机 launchd** 作为可靠方案。
