# 新商评看板 · 可复制制作方案

把川藏一区这套「新商评」从数据源做到外发页的完整做法写在这一份里。别人照着改城市和区域名，就能复制出同一口径的看板。

**不要让接收方从聊天窗口复制 PowerShell。** 脚本已经在仓库里，时钟挂在已有 Web 进程上；分享时只发本文件 + 仓库地址。

| 项 | 现值（川藏一区样板） |
|----|----------------------|
| 外发页 | https://1.chuanzangyiqu.top/evaluation/xinshang （免登录） |
| 公开页 | https://h15881142023-oss.github.io/fuzzy-umbrella/xinshang/ |
| 仓库 | https://github.com/h15881142023-oss/fuzzy-umbrella |
| 热覆盖分支 | `cursor/cz1-merchant-dashboard-74a9` |
| 考核节奏 | 每周一、周四出数；本机周二、周五 22:00 自动同步 |
| 本城 | 仁寿县 / 合江县 / 南溪 / 叙永（**彭州只当友商，不当本城**） |

---

## 1. 这套东西到底是什么

不是后台系统，也不是 NocoBase 观测舱。它是一个**单页 HTML**，数据写死在页面里的 `const DATA = {...}`。

```
初心 Metabase 公开看板（真源）
        │
        ├─ sync_xinshang_from_chuxin.py     → 四城主表 DATA.cities
        └─ sync_peer_compare_from_chuxin.py → 约 117 城 DATA.peerCompare
        │
        ▼
static/dashboards/cz1-xinshang-pingjia.html
docs/xinshang/index.html          （同一份，GitHub Pages）
        │
        ▼
Flask /evaluation/xinshang        （免登录外发）
```

同步脚本只改 `DATA` 这段 JSON，不改渲染逻辑。换区域时优先复用同一 HTML，只改城市名单和同步常量。

---

## 2. 产品口径（锁死，复制时不要改公式）

这些是踩过坑后定下来的，换区域也必须原样带上。

### 2.1 展什么、不展什么

- 页面只展六块：**外卖 / 团购 / 履约 / 零售 / 商业增值 / 用户体验**。
- **组织、综合治理不进主表。** 脚本里 `HIDDEN_MODULES = {"组织", "综合治理"}`，`sanitize_dashboard()` 会再剥一遍。
- 不展示能力得分，只看预警区间。
- 无团购的城：团购模块整块「不预警」，指标值「—」。
- 彭州（以及任何非本城）只出现在同分群对比，城市/区域显示为「友商」，**不能塞进本城筛选**。

### 2.2 考核日怎么取

- 考核日跟**周一 / 周四**节奏，不能只信汇总表日期下拉（经常落后一期）。
- 取这些参数下拉里的并集最新一日：`fe957d70`（汇总表）、`20b71f6`（外卖）、`141a2780`（零售）、`74a547b9`（组织）、`21c403b0`（总商能力看板）、`bda69947`（新商预警）。
- **不要把用户体验等日更参数并进考核日**，否则会选到 `9/1` 这类非考核日。
- 上期 = 同一套节奏参数里、比本期更早的最近一日。

### 2.3 汇总表未出数

- 本期汇总表缺本城时：回退到汇总表下拉里最近一次**四城齐套**的考核日。
- 再用**本期模块页**覆盖指标值。
- **模块空表不覆盖**，避免把上期履约等抹成空。
- `meta.summaryFallbackDate` 有值就说明走了回退，验收时必须看一眼。

### 2.4 餐饮商家渗透率（最容易抄错）

| 字段 | 含义 | 能不能当考核值 |
|------|------|----------------|
| 汇总表「餐饮商家渗透率指标值-外卖」/「餐饮商家渗透率」 | 考核渗透率 | **只用这个** |
| 外卖模块「餐饮渗透率」 | 交易商家数 ÷ 公海商家数 | **禁止覆盖考核值** |

`MODULE_VALUE_TO_SUMMARY` 里**没有**餐饮渗透率，是故意的。合江模块页曾出现 0.3779，考核值完全不是这个。

渗透率分母（页面子行）：

```
渗透率分母 = round(月交易商家数 ÷ 考核渗透率)
```

率如果是百分数（>1）先除 100。分母不是公海商家数。

### 2.5 完成率

- 页面名：**餐饮订单完成率 / 餐饮实付完成率**（不要写回「市场开发率(订单量/GTV)」）。
- 取值顺序：
  1. 外卖模块页「餐饮订单量完成率 / 餐饮交易额完成率」（列名始终正确）
  2. 汇总表「市场开发率（订单/实付）指标值-外卖」
  3. 汇总表「餐饮订单量完成率 / 餐饮交易额完成率」（全国 100+ 城同一口径）
- 预警区间跟指标值走。汇总表指标值与模块页对调时，排名区间也要对调（脚本里差 >2pp 才对调）。

### 2.6 月在线商家数 / 月动销率

- **月在线商家数来自 Power BI JSON**（`data/xinshang/powerbi_online_merchants.json`），抓不到就用脚本内默认值。
- 默认值（川藏一区）：仁寿 1290 / 合江 545 / 南溪 488 / 叙永 363。换区域必须改这组数。
- **不要用公海商家数顶替在线商家数**（公海另有一行）。
- 月动销率 = 交易商家数 ÷ 在线商家数。

### 2.7 加权预警 ≠ 大盘区间平均

- 页面「加权预警」直接读汇总表「加权排名区间」（或能力看板「加权预警」）。
- **本仓库不重算加权分。** 源头算法是：T-2 / T-1 / 当月**得分**滚动加权后再全国重排名，落成 10-30 / 50-70 这类区间。
- 不能用「7 月 10-30、8 月 50-70、9 月 50-70」去平均区间。区间不是分数。
- 近月权重大。举例：7 月分 44.92、8 月分 70.26、9 月只有预警没有分 → 加权分大约在 60 附近，落到 10-30 区间不成立（除非 9 月分极低且权重大到压过前两月）。

### 2.8 同分群对比

- 城市名单 = **本期汇总表 ∪ 上期汇总表**（约 117 城）。模块页独有的城不要并进名单。
- 本城只勾四城；选定指标后，按该城该指标的分群列出同一分群全部城市。
- 非本城城市名、区域名一律显示「友商」。
- 对比差值 = 目标本期值 − 本城本期值。
- 追平缺口在前端算，脚本只提供底数：

| 模式 | 用在哪 | 月累计 | 剩余日均 |
|------|--------|--------|----------|
| `month_first` | 默认 | 追平率差 × 本城分母 | 月累计 / 剩余天数 |
| `gap_scale_to_month=true` | 外卖订单/实付完成率 | 分母先按整月放大：`分母 × 当月天数 / (模块日+2)`，再 × 率差 | 同上 |
| `yoy_catchup` | 零售 YoY | `本城基期 × (1+目标YoY) × 当月天数 − 本城日均 × (模块日+2)` | 同上 |
| `higher_better=false` | 超时占比、万服、虚假业绩等 | 按压降：`(本城−目标) × 分母` | 同上 |
| `prefer_implied_denom` | 餐饮渗透率、优质商家渗透率 | 分母优先用 `分子 / 考核率` 反推 | 同上 |

剩余天数：

```
剩余天数 = 当月天数 − (模块最左日期的日号 + 2)
例：模块日 8/24 → 31 − 26 = 5
```

---

## 3. 数据源（唯一真源）

正确路径：

```
数据平台 → 业务看板 → 新商评 → 新商考核 → 模块数据汇总表
```

NocoBase 页面只是 iframe。**不要去测评集合 / html_pages 观测舱当主数据。**

| 项 | 值 |
|----|----|
| NocoBase | http://www.chuxin.city |
| 管理页 | http://www.chuxin.city/v/admin/b7v8t424ohb |
| Metabase | http://47.112.178.78:3000 |
| 公开看板 UUID | `5d509c91-583b-4229-89ee-51721035ae71` |
| 公开接口 | `{MB}/api/public/dashboard/{UUID}/dashcard/{dashcard}/card/{card}?parameters=...` |
| 日期参数 | `date/range` 传 `2026-09-17~2026-09-17`；`date/all-options` 传 `2026-09-17` |

主表卡片（脚本常量 `CARDS` / `EXTRA_MODULE_CARDS` / `MODULE_CARDS`）：

| 用途 | dashcard | card | 日期参数 id |
|------|----------|------|-------------|
| 模块数据汇总表 | 192 | 214 | `fe957d70` |
| 城市能力看板 | 168 | 191 | `54dcbdb2` |
| 外卖 | 198 | 217 | `20b71f6` |
| 团购 | 197 | 215 | `c717dd65` |
| 零售 | 199 | 219 | `141a2780` |
| 商业增值 | 177 | 202 | `145eb979` |
| 履约 | 178 | 204 | `3dbda5d5` |
| 用户体验 | 189 | 211 | `c8d3a576` |
| 综合治理（仅同分群） | 316 | 335 | `44123529` |

换区域若仍用同一张「新商考核」全国看板：**卡片 ID 不用改**，只改区域过滤和本城名单。

Power BI 月在线商家数：

- 报表 `reportId=1a6f7a23-0fd5-44d8-a37f-8cef116b8ad9`
- 脚本 `scrapers/scrape_powerbi_wind_online.py`，依赖本机 Chrome CDP `9222`
- 失败则沿用上次 JSON / 默认值，**不要让整次同步失败**

Excel 预警表是可选捷径，不是真源：

- 文件名形如 `新商考核预警数据_YYYYMMDD_HHMMSS.xlsx`
- **Excel 日期早于最新考核日必须跳过**，否则会把新数据盖回去
- 日常以 Metabase 为准；Excel 只在「表比看板先到、且日期不落后」时用

---

## 4. 文件地图

| 路径 | 干什么 |
|------|--------|
| `static/dashboards/cz1-xinshang-pingjia.html` | 外发页本体（`const DATA`） |
| `docs/xinshang/index.html` | 同上，给 GitHub Pages |
| `docs/xinshang/index-v1-frozen-202607.html` | 已外发旧版，不要动 |
| `scripts/sync_xinshang_from_chuxin.py` | 四城主表 |
| `scripts/sync_peer_compare_from_chuxin.py` | 同分群 ~117 城 |
| `scripts/sync_xinshang_from_excel.py` | Excel 捷径（过期自动跳过） |
| `scripts/xinshang_daily_push.py` | 日更入口：热文件 → Power BI → Excel → Metabase → 同分群 → 企微 |
| `scripts/xinshang_hot_html.py` | 从 GitHub 热覆盖 HTML |
| `scripts/xinshang_self_update.py` | Web 启动时补齐脚本，不用 git pull |
| `scripts/xinshang_clock_windows.py` | 周二/周五 22:00 + 每 5 分钟拉 HTML |
| `scripts/xinshang_wecom.py` | 企微 text |
| `scrapers/scrape_powerbi_wind_online.py` | 月在线商家数 |
| `data/xinshang/powerbi_online_merchants.json` | 在线商家数缓存 |
| `data/xinshang/metabase_latest.json` | 主表抓数底稿 |
| `app.py` | `/evaluation/xinshang` 免登录；`/api/xinshang/sync`、`/api/xinshang/hot-html` |

`DATA` 关键字段：

```text
DATA.meta.period / dataDate / prevPeriod / summaryDate / summaryFallbackDate
DATA.modules                  = ["外卖","团购","履约","零售","商业增值","用户体验"]
DATA.cities[]                 = 仅本城，顺序固定
  .warnWeighted / warnMarket  = 加权预警 / 大盘预警
  .bands / details            = 模块预警与指标
DATA.peerCompare.mineCities   = 本城
DATA.peerCompare.records[]    = 全名单，mine=true 才是本城
DATA.layouts                  = 指标行/子行（渗透率展开交易、分母、在线、公海、动销）
```

---

## 5. 同步顺序（照这个跑，不要重排）

`xinshang_daily_push.py` 的顺序是验收过的：

```
1. 热覆盖同步脚本和 HTML（从 cursor/cz1-merchant-dashboard-74a9 拉）
2. 确保 Chrome CDP 9222；能连再抓 Power BI 月在线商家数
3. 试 Excel：日期不落后才写入并结束
4. 否则 Metabase 主表（sync_xinshang_from_chuxin.py）
5. 同分群（sync_peer_compare_from_chuxin.py）
6. 企微 text：成功摘要或失败原因
```

手动（Linux / 云端 / 本机 Python 均可，**不要发 PowerShell 给别人**）：

```bash
python scripts/sync_xinshang_from_chuxin.py
python scripts/sync_peer_compare_from_chuxin.py
```

指定考核日：

```bash
python scripts/sync_xinshang_from_chuxin.py --date 2026-09-17
python scripts/sync_peer_compare_from_chuxin.py --date 2026-09-17
```

只热覆盖页面、不抓数：

```bash
python scripts/xinshang_daily_push.py --html-only
```

只同步不推企微：

```bash
python scripts/xinshang_daily_push.py --skip-wecom
```

时钟（已有 `ChuanzangWeb5001` 会自动起）：

```
周二 / 周五 22:00（本机时区，10 分钟窗口只跑一次）
每 5 分钟拉一次 HTML
日志：logs/xinshang_push.log
```

外发页打开时 Flask 也会后台拉一次 HTML（45 秒内去重）。**老 `app.py` 没有 `/api/xinshang/hot-html`，404 正常**，以时钟 5 分钟拉取为准。

云端触发 `POST /api/xinshang/sync` 经常 502 / 超时，但 Windows 进程仍会跑完。以 `logs/xinshang_push.log` 和页面 `DATA.meta.dataDate` 为准，不要只看 HTTP 状态。

---

## 6. 换一个区域怎么复制

目标：另一个合作区拿到**同一口径**的看板，而不是另起一套公式。

### 6.1 先确认三件事

1. 初心仍是这张「新商考核」公开看板（同一 UUID）。
2. 本城名单、城市别名（仁寿/仁寿县这类）。
3. 外发域名、企微 webhook、热覆盖用的 Git 分支。

### 6.2 必须改的常量（checklist）

同一仓库复制时，下列名字必须一起改，漏一个就会出现「五城/四城」文案打架或彭州进本城。

| 位置 | 常量 | 川藏一区现值 |
|------|------|--------------|
| `sync_xinshang_from_chuxin.py` | `REGION` / `REGIONS` | `川藏一区` |
| 同上 | `CITIES` | `["仁寿县", "合江县", "南溪", "叙永"]` |
| 同上 | `CITY_ALIASES` | 仁寿→仁寿县，南溪区→南溪 … |
| 同上 | `DEFAULT_POWERBI_ONLINE` | 四城在线商家数 |
| `sync_peer_compare_from_chuxin.py` | `TARGET_CITIES` / `CITY_KEYS` | 与 `CITIES` 一致 |
| `scrape_powerbi_wind_online.py` | `need = (...)` | 与 `CITIES` 一致 |
| HTML `canonPeerCity()` | 本城别名表 | 含彭州仅用于识别友商，不要放进 `CITIES` |
| HTML 文案 | 「四城」「川藏一区」 | 改成新区名称 |
| `sanitize_dashboard()` | `replace("五城", "四城")` | 按新区城数改 |
| `xinshang_hot_html.py` / `xinshang_self_update.py` / `xinshang_daily_push.py` | `BRANCH` / `HOT_BRANCH` | 新区自己的热覆盖分支 |
| `xinshang_wecom.py` | `DEFAULT_PAGE` / webhook | 新区外发页和群 |
| `app.py` | `/evaluation/xinshang` | 可复用路径，或改成 `/evaluation/<区>` |

区域过滤：主表 `query_card` 带 `region_id` + `REGION`。同分群拉全国，**不要加区域过滤**。

### 6.3 建议的落地顺序

1. 复制 `cz1-xinshang-pingjia.html` 为新区文件（或先共用，改 `CITIES` 验证数据）。
2. 改第 6.2 节全部常量，提交到新区热覆盖分支。
3. 跑主表脚本，确认 `DATA.cities` 只有本城、顺序对、彭州不在列表。
4. 跑同分群脚本，确认 `mineCities` 正确、`records` 约 117、非本城显示友商。
5. 硬核四城（或新区本城）的：考核日、上期、餐饮订单/实付完成率、**考核渗透率**、渗透率分母、在线商家数、加权/大盘预警。
6. 把 HTML 推到热覆盖分支；外发 Web 每 5 分钟自己拉，不要让别人手工覆盖。
7. 企微改成新区机器人。时钟可继续挂同一 Web 进程，或再起一条。

### 6.4 不要做的事

- 不要把 NocoBase 测评集合当主数据。
- 不要用模块页「餐饮渗透率」覆盖 KPI。
- 不要把用户体验日更日期当考核日。
- 不要把组织 / 综合治理加回主表。
- 不要把彭州（或任何非考核本城）加进 `CITIES`。
- 不要让过期 Excel 覆盖 Metabase。
- 不要先快进热覆盖分支再开 PR：快进后 stacked PR 会空。应先提交 PR，再决定是否快进 `cursor/cz1-merchant-dashboard-74a9`。
- 不要从对话里复制命令给业务同事。把本文件和「打开外发页」发给他们即可。

---

## 7. 验收清单（每次更新都过一遍）

对照初心看板同一考核日，抽本城逐项打勾。

- [ ] `DATA.meta.dataDate` = 节奏最新考核日（不是汇总表掉队的那天）
- [ ] `prevPeriod` = 上一考核日（通常间隔 3 天：周一↔周四）
- [ ] 若 `summaryFallbackDate` 非空：主表日期是回退日，模块指标值仍是本期
- [ ] 本城恰好 N 个，无彭州；`richCz1Count` = N
- [ ] `modules` 只有六块，无组织 / 综合治理
- [ ] 餐饮订单完成率、餐饮实付完成率与模块页列名一致
- [ ] **餐饮商家渗透率 = 汇总表考核值**，不是交易/公海
- [ ] 渗透率分母 ≈ 月交易商家数 ÷ 考核渗透率
- [ ] 月在线商家数 = Power BI / 默认值，不是公海
- [ ] 月动销率 = 交易 ÷ 在线
- [ ] 加权预警、大盘预警与汇总表区间一致；箭头由区间升降重算
- [ ] 无团购城团购整块不预警
- [ ] `peerCompare.records` 约 117；本城 `mine=true`
- [ ] 非本城在对比表里显示「友商」
- [ ] 外卖完成率追平缺口已整月放大；剩余天数 = 当月天数 − (模块日+2)
- [ ] 外发页硬刷新后日期和四城 KPI 与 `DATA` 一致
- [ ] 企微（若开）带本期日期、上期、城数、页面链接

川藏一区 2026-09-17 样板（上期 09-14），便于对照脚本是否被改坏：

| 城 | 餐饮订单完成率 | 餐饮实付完成率 | 在线商家数 |
|----|----------------|----------------|------------|
| 仁寿县 | 40.62% | 106.91% | 1290 |
| 合江县 | 35.57% | 106.37% | 545 |
| 南溪 | 45.74% | 107.31% | 488 |
| 叙永 | 39.65% | 103.78% | 363 |

---

## 8. 已知踩坑

1. **考核日用了 `max(所有卡片日期)`**  
   用户体验日更会把日期拉到月初。只并 `CADENCE_DATE_PARAMS`。

2. **`latest_summary_date` 选了 09-14，汇总表却是空的**  
   必须 `fetch_summary_with_fallback`：空表回退齐套日，再用模块页补值。

3. **餐饮商家渗透率抄了模块「餐饮渗透率」**  
   合江会变成交易/公海。KPI 只允许汇总表考核字段。

4. **插入渗透率辅助字段时误删 `waimai_order_gtv_values`**  
   完成率和渗透率是两套函数，不要缠在一次重构里。

5. **在线商家数用公海顶上**  
   公海通常更大，动销率会被压低。Power BI 失败时用默认值，不要改口径。

6. **Excel 文件躺在仓库里日期是 09-08**  
   日更必须先比考核日，落后就 `usedExcel=false` 回退 Metabase。

7. **热覆盖 SHA 写死过期**  
   `xinshang_hot_html.py` 用分支名拉最新；`xinshang_self_update.py` 的 SHA 只是 CDN 兜底。改逻辑后要推到 `HOT_BRANCH`，否则本机 5 分钟后又被旧 HTML 盖回去。

8. **云端 `POST /api/xinshang/sync` 502**  
   抓 117 城经常超过网关超时。Windows 时钟仍会跑完。看日志和页面，不要重跑到半截。

9. **老 Web 没有 `/api/xinshang/hot-html`**  
   升级 `app.py` 或等时钟 5 分钟拉取。不要为此让业务同事跑脚本。

10. **加权预警被理解成区间平均**  
    它是得分加权再排名。没有当月得分时，用前两月分只能判断「大概落在哪一档」，不能反推必须进 10-30。

11. **stacked PR 先快进后开 PR**  
    热覆盖分支一快进，原 PR diff 变空。顺序：功能分支提交 → 开 PR → 需要外发再生效到 `cursor/cz1-merchant-dashboard-74a9`。

---

## 9. 分享给别人时发什么

最小包裹（推荐）：

1. 本文件：`docs/xinshang/PLAYBOOK.md`
2. 仓库地址 + 热覆盖分支名
3. 外发页链接（打开即用，免登录）

需要对方自己落地新区时，再加：

4. 本城名单、城市别名、是否含团购
5. 外发域名、企微 webhook
6. Power BI 是否同一张风向看板（否则先改在线商家数默认值，允许抓取失败）

对方是看数的人：只发外发页。  
对方是做另一个区看板的人：发本文件，按第 6 节改常量，按第 7 节验收。  
不要发 PowerShell，不要让他们从聊天窗口贴命令。
