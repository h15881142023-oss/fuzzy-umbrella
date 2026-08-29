# 新商评看板 — Windows 计划任务（对齐经营宝订单抓取，不是 Cursor Automations）

目标：装一次后，每周二、周五 22:00 自动更新外发页，成功/失败推到与经营宝同一企微群。

外发页：https://1.chuanzangyiqu.top/evaluation/xinshang

## 一次性安装（管理员 PowerShell，整段复制）

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_xinshang_task.ps1
```

或双击：`scripts\install_xinshang_task.bat`

## 手动补跑（整段复制）

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
cmd /c call .\scripts\run_xinshang_daily_push.bat
```

## 链路（与经营宝同一结构）

```
Windows 计划任务 CZ1_Xinshang_WeCom_TueFriPush  (周二/周五 22:00)
    → cmd /c call run_xinshang_daily_push.bat
        → python.exe xinshang_daily_push.py
            → 启动/复用 Power BI Chrome CDP 9222
            → scrape_powerbi_wind_online.py   # 月在线商家数
            → sync_xinshang_from_chuxin.py     # 主看板
            → sync_peer_compare_from_chuxin.py # 同分群 ~117 城
            → 企微 text（成功摘要或失败原因）
```

## 企微

优先读桌面 `经营宝订单抓取\wecom_config.json` 的 `webhook_url`，没有则用仓库 `scripts/xinshang_wecom_config.json`（与 LR 日报同一 key）。

## 日志

`logs\xinshang_push_YYYYMMDD.log`

## 卸载

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall_xinshang_daily_windows.ps1
```

## 前置

- Web+隧道：`install_background_windows.ps1`（ChuanzangWeb5001 + ChuanzangTunnel）
- Power BI Chrome 独立 profile 首次若弹登录：`qiaoxh@ppu.powerbi.bi`
