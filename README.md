# 川藏一区数据平台

从零搭建、对齐教程架构的本地区域数据看板。

## 已实现

| 项 | 说明 |
|----|------|
| 区域 | 川藏一区 · 仁寿县 / 南溪 / 叙永 / 彭州市 / 合江县 |
| 本机 Web | Flask + Gunicorn · `http://127.0.0.1:5001` |
| 鉴权 | 共用密码（默认 `chuanzang2026`，可用 `CZ_SITE_PASSWORD` 覆盖） |
| 数据库 | SQLite `data.db` |
| Excel 监控 | `~/Desktop/川藏一区数据更新/` 下各子目录 |
| 外网域名 | `https://1.chuanzangyiqu.top`（需 Cloudflare Tunnel） |
| LR 日报 | 独立脚本 `lr/run_daily.py`（不挂网站） |
| 开机自启 | Web/Excel **未**开机自启；代补抓取已装 launchd **每天 09:00** |
| 代补看板 | Power BI 五城四块表；快照日=页面大标题日期；历史不覆盖；缺日自动补齐 |

页面路由与教程一致：`/kpi/catering`、`/evaluation`、`/notice` 等。

## 快速开始

```bash
cd "/Users/qxh/月度工作/2026年/26年7月工作/chuanzang_data_platform"
chmod +x start_all.sh stop.sh
./start_all.sh
```

浏览器打开：http://127.0.0.1:5001  
默认密码：`chuanzang2026`

停止：

```bash
./stop.sh
```

## Excel 导入

桌面目录（已创建）：

- `餐饮KPI` / `非餐KPI` / `实付配送费` / `团队管理` / `经营管理` / `城市警告` / `餐饮预警`

表头支持中英文（如 `城市`→city、`得分`→score）。拖入 `.xlsx` 后自动入库。

## Cloudflare 绑定（域名迁入）

域名：`chuanzangyiqu.top` → 子域 `1.chuanzangyiqu.top`

1. 注册 [Cloudflare](https://dash.cloudflare.com)，添加站点 `chuanzangyiqu.top`
2. 按提示到域名注册商修改 NS
3. 安装隧道：`brew install cloudflare/cloudflare/cloudflared`
4. `cloudflared tunnel login`
5. `cloudflared tunnel create chuanzang-data`
6. 参考仓库内 `cloudflared.config.example.yml` 写好 `~/.cloudflared/config.yml`
7. `cloudflared tunnel route dns chuanzang-data 1.chuanzangyiqu.top`
8. 再执行 `./start_all.sh`（检测到 config 会尝试拉起 tunnel）

NS 生效后访问：https://1.chuanzangyiqu.top

### Windows 域名恢复（站点密码保留，看板免登录）

目标看板地址：`https://1.chuanzangyiqu.top/evaluation/xinshang`

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
git fetch origin "cursor/cz1-merchant-dashboard-74a9"
git restore --source="origin/cursor/cz1-merchant-dashboard-74a9" -- app.py static/dashboards/cz1-xinshang-pingjia.html scripts/start_domain_windows.ps1 scripts/check_domain_windows.ps1 cloudflared.config.windows.example.yml

# 先自检缺什么
powershell -ExecutionPolicy Bypass -File .\scripts\check_domain_windows.ps1

# 再启动 Web + 隧道
powershell -ExecutionPolicy Bypass -File .\scripts\start_domain_windows.ps1
```

说明：
- 看板 `/evaluation/xinshang` **免登录**
- 站点其它页面仍用 `CZ_SITE_PASSWORD`（默认 `chuanzang2026`）
- 域名打不开时，优先看自检脚本：5001 是否监听、cloudflared 是否安装/配置/在跑

## 新商评价看板（免登录外发）

单页 HTML：`static/dashboards/cz1-xinshang-pingjia.html`  
公开站点目录：`docs/xinshang/`（GitHub Pages）

| 场景 | 地址 |
|------|------|
| **公开分享（推荐）** | `https://h15881142023-oss.github.io/fuzzy-umbrella/xinshang/` |
| 本机 | `http://127.0.0.1:5001/evaluation/xinshang` |
| 自有域名 | `https://1.chuanzangyiqu.top/evaluation/xinshang` |

公开链接**无需登录**。  

版本说明：
- **当前详表版**：`docs/xinshang/index.html` / `static/dashboards/cz1-xinshang-pingjia.html`  
  无图表、不展示能力得分，只看预警区间，八大模块一次铺开。
- **已外发冻结版（不变）**：`docs/xinshang/index-v1-frozen-202607.html`  
  此前发出去的旧版拷贝不受后续改动影响；需要旧版时发这个文件即可。

### Windows 更新看板（推荐，不依赖 GitHub git）

用 CDN 覆盖本机 HTML（**请用提交号，不要用带 `/` 的分支名**，否则 jsDelivr 可能 Forbidden）：

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"

# 直接更新看板（提交号可按我最新通知替换）
powershell -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1 -Ref b276487
```

若本机脚本损坏/不存在，先下载再跑（同样用提交号）：

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
$ref = "b276487"
$u = "https://cdn.jsdelivr.net/gh/h15881142023-oss/fuzzy-umbrella@$ref/scripts/update_xinshang_html_windows.ps1"
Invoke-WebRequest $u -OutFile ".\scripts\update_xinshang_html_windows.ps1" -UseBasicParsing
powershell -ExecutionPolicy Bypass -File .\scripts\update_xinshang_html_windows.ps1 -Ref $ref
```

或双击：`scripts\update_xinshang_html_windows.cmd`

更新后打开 `https://1.chuanzangyiqu.top/evaluation/xinshang` 并强制刷新。

首次启用 GitHub Pages：

1. 合并本仓库到 `main`
2. GitHub 仓库 → **Settings** → **Pages**
3. Build and deployment → Source 选 **GitHub Actions**
4. 等待 Actions 里 `Deploy GitHub Pages` 跑绿后即可外发上面链接

Windows 本机启动（Web + 可选隧道）：

```powershell
cd "C:\Users\Administrator\Documents\fuzzy-umbrella"
powershell -ExecutionPolicy Bypass -File .\scripts\start_xinshang_windows.ps1
```

## 美团看板 CDP 抓取

### 1. 安装依赖（已含 websocket-client）

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动 Chrome 并登录美团

```bash
bash scripts/start_chrome_meituan.sh
```

在打开的 Chrome 里登录 `igate.waimai.meituan.com`，并打开你的 **unitDashboard / 绩效看板** 页面。

### 3.（首次推荐）嗅探真实 API

```bash
python scripts/discover_meituan_apis.py
```

把输出里正确的接口 URL 填进 `scrapers/meituan_endpoints.json` 的 `api_fetch_urls`，并把看板地址写到 `pages.dashboard`。

也可设置环境变量：

```bash
export MEITUAN_DASHBOARD_URL='你的看板完整URL'
export MEITUAN_API_FETCH_URLS='https://...,https://...'
```

## 代补看板（Power BI）日更

- **快照日期**以页面大标题为准（如 `2026/7/15`），不用本机今天
- **同日同城已存在则跳过**，不覆盖历史
- **缺日补齐**：从库内最早日期到页面日期，缺城就补
- **每天 09:00** launchd 自动跑；若页面还不是 t-1，每 10 分钟刷新直到出数

```bash
# 安装/卸载定时任务
bash scripts/install_powerbi_daily_launchd.sh
bash scripts/uninstall_powerbi_daily_launchd.sh

# 手动：先开已登录的 Power BI Chrome（CDP 9222）
bash scripts/start_chrome_powerbi.sh
bash scripts/run_powerbi_subsidy_daily.sh          # 等到 t-1
bash scripts/run_powerbi_subsidy_daily.sh --once   # 只跑一轮
```

日志：`logs/powerbi_subsidy_daily.log`

### 4. 运行抓取

```bash
# 绩效看板
python scrapers/scrape_dashboard_cdp.py

# 餐饮 / 非餐 KPI（会优先用当日看板快照）
python scrapers/sync_catering_scores.py
python scrapers/sync_non_catering_scores.py

# TODO 达成 / 通知函
python scrapers/scrape_todo_achievement_cdp.py
python scrapers/scrape_meituan_cdp.py
```

或在网站对应页面点 **「同步数据」** 按钮（调用相同脚本）。

抓取逻辑：复用已登录 Chrome → 页面内 `fetch` / 网络嗅探 / DOM 表格解析 → 按城市写入 SQLite。

## CDP 抓取说明（旧）

`scrapers/*.py` 已接入 CDP；若页面结构特殊，请用 `discover_meituan_apis.py` 补齐 `meituan_endpoints.json`。

## LR 日报

每天 **23:30** Cloud Agent 自动：抓取 [LR日利润表](http://47.112.178.78:13000/admin/g303bjgeytq) 网页表格 → 写入模板 `数据源(日)` → 推送「看板-单城」截图 + Excel 到企业微信。

```bash
# 手动试跑（需先有抓取 JSON）
python lr/run_daily.py --scrape-json data/lr_scrape/latest.json --dry-run
```

- 说明：`scripts/LR_DAILY_CLOUD_AGENT.md`
- Automation 预填：`scripts/cursor_automation_lr_daily.json`

## 健康检查

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/health
# 登录前页面会 302 到 /login；health 接口无需密码
```

## 改密码

```bash
export CZ_SITE_PASSWORD='你的新密码'
./stop.sh && ./start_all.sh
```
