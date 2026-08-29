# Cursor Cloud Agent — 新商评日更

每天在 **Cloud** 环境执行，**禁止**向用户索要确认、禁止 AskQuestion。  
Metabase 公开看板可 HTTP 拉取；Power BI「月在线商家数」在云端用浏览器抓取后写入 JSON，再跑主看板同步。

## 目标

1. 从初心 Metabase「新商考核 / 模块数据汇总表」同步五城主看板 + 环比 + 测试成绩
2. 同步同分群数值对比（城市名单 = 本期汇总表 ∪ 上期汇总表，约 117 城）
3. 打开 Power BI「业务数据风向看板」，抓取川藏一区五城 **月在线商家数**，写入 `data/xinshang/powerbi_online_merchants.json`
4. 将 Power BI 在线数合并进 HTML，提交并 push 到 `main`

外发页由 Windows 服务器上的计划任务从 `@main` 自动拉 HTML（用户无需手动操作）。

## 步骤

### 1. Metabase 主看板 + 同分群（必做）

```bash
cd /workspace   # 或仓库根目录
python3 scripts/sync_xinshang_from_chuxin.py
python3 scripts/sync_peer_compare_from_chuxin.py
```

确认输出含 `periodDate`、`cities: 117`（或 `universeCities: 117`）。

### 2. Power BI 月在线商家数（必做，失败则沿用仓库内 JSON）

1. 打开报表（embed）：
   `https://app.powerbi.com/reportEmbed?reportId=1a6f7a23-0fd5-44d8-a37f-8cef116b8ad9&autoAuth=true&ctid=7c792a97-2300-4444-aa97-172fed9b0501`
2. 若需登录：`qiaoxh@ppu.powerbi.bi`（密码见团队密钥；禁止向用户提问）
3. 筛选：**最新日期=是**、**区域=川藏一区**、**餐饮**
4. 在「城市数据」表读取五城在线商家数：彭州市、仁寿县、合江县、南溪、叙永
5. 写入 `data/xinshang/powerbi_online_merchants.json`，格式示例：

```json
{
  "ok": true,
  "date": "2026-08-27",
  "metric": "在线商家数",
  "cities": {
    "彭州市": 843,
    "仁寿县": 1341,
    "合江县": 579,
    "南溪": 524,
    "叙永": 429
  },
  "source": "业务数据风向看板",
  "scrapedAt": "2026-08-29T..."
}
```

6. **再次执行** `python3 scripts/sync_xinshang_from_chuxin.py`（把在线数写进 HTML）

也可在环境允许时：`python3 scrapers/scrape_powerbi_wind_online.py`（需本机 Chrome CDP 9222；Cloud 通常用浏览器逐步操作代替）。

### 3. 提交

```bash
git add static/dashboards/cz1-xinshang-pingjia.html docs/xinshang/index.html data/xinshang/
git commit -m "chore: 新商评日更 $(date +%Y-%m-%d)"
git push origin main
```

### 4. 汇报（简短）

- 数据日期 `periodDate`
- 同分群城市数 `universeCities`
- Power BI 在线数是否更新（date + 五城数值）
- commit SHA

失败则写阻塞原因，**不要**向用户提问。

## 约束

- 禁止中途 AskQuestion / 需求对齐
- 禁止要求用户在 Windows 上手动跑 PowerShell
- 文件只落云端工作区并 push GitHub

## 定时 Automation

- 预填：`scripts/cursor_automation_xinshang_daily.json`
- 建议触发：每天 **09:00**（`0 9 * * *`），在 Metabase 更新后
- 仓库：`h15881142023-oss/fuzzy-umbrella` · 分支 **`main`**
