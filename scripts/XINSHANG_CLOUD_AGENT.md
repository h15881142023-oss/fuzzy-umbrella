# Cursor Automations — 川藏一区新商评日更

与侧边栏 **「经营宝订单抓取」** 相同模式：**只配一次 Automations，以后全自动**，不要求用户跑 PowerShell。

## 你要做的（一次性）

1. 打开 Cursor → **Automations**（或 Automations 面板）
2. **New Automation**（新建自动化）
3. 名称：`川藏一区新商评日更`
4. 仓库：`h15881142023-oss/fuzzy-umbrella`，分支 `main`
5. 定时：`0 9 * * *`（每天 09:00）
6. Prompt 复制 `scripts/cursor_automation_xinshang_daily.json` 里 `prompts[0].text` 全文
7. 保存并 **Enable**

完成后侧边栏会出现类似「经营宝订单抓取」的任务条目，到点 Cloud Agent 自己跑。

## 自动化做什么

| 步骤 | 位置 | 内容 |
|------|------|------|
| A | Cloud | Metabase 主看板 + 同分群 117 城 |
| B | Windows 服务器 | `POST /api/xinshang/sync` → Power BI **月在线商家数** + 写回外发 HTML |

外发页：https://1.chuanzangyiqu.top/evaluation/xinshang

## Windows 前置（一般已具备）

- `install_background_windows.ps1` 已装 **ChuanzangWeb5001 + ChuanzangTunnel**
- Power BI Chrome profile 已登录过 `qiaoxh@ppu.powerbi.bi`（与代补/风向看板共用 CDP 9222 亦可）

## 手动试跑 API（可选）

```bash
curl -sS -X POST "https://1.chuanzangyiqu.top/api/xinshang/sync" \
  -H "X-CZ-Token: chuanzang2026"
```

## 约束

- 禁止向用户索要确认
- 禁止让用户本机 Downloads / git pull / jsdelivr 覆盖

## 预填 JSON

`scripts/cursor_automation_xinshang_daily.json`
