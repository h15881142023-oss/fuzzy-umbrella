# Cursor Cloud Agent — LR 日报（23:30）

每天在 **Cloud** 环境执行。数据量小，**直接从网页表格抓取**，不点导出。

## 目标

1. 登录业务后台，打开「LR日利润表数据」
2. 筛选：区域=`川藏一区`，日期=`昨天`
3. 抓取表格 headers + rows → JSON
4. 写入模板 `数据源(日)`（五城按列匹配）
5. 生成「看板-单城」截图 + 填好 Excel，推送企业微信

## 步骤

### 0. 登录

1. 打开 `http://47.112.178.78:13000/signin`
2. 填写 **用户名/邮箱**、**密码**，点 **登录**
3. URL 离开 `/signin` 后再继续

### 1. 打开看板并筛选

1. 打开 `http://47.112.178.78:13000/admin/g303bjgeytq`
2. 区域填 `川藏一区`；城市留空（抓五城）
3. 日期选 `昨天`（或等价「昨日」选项）
4. 等待表格刷新（约 30–60 秒）

### 2. 抓取网页表格（不要导出）

在浏览器控制台或 CDP 执行：

```javascript
(() => {
  const headers = Array.from(document.querySelectorAll('thead th')).map(el => el.innerText.trim()).filter(Boolean);
  const rows = Array.from(document.querySelectorAll('tbody tr')).map(tr =>
    Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
  ).filter(r => r.length);
  return { headers, rows, scraped_at: new Date().toISOString() };
})()
```

将结果保存为仓库 `data/lr_scrape/latest.json`（仅云端工作区）。

### 3. 模板（已在仓库，无需从服务器下载）

直接使用 checkout 内的模板：

`lr/templates/LR日报总表模版5.4版(川藏一区).xlsx`

### 4. 运行脚本

```bash
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python lr/run_daily.py --scrape-json data/lr_scrape/latest.json
```

### 5. 推送结果

脚本会自动：

- 写入 `数据源(日)`（五城：仁寿县/南溪/叙永/彭州市/合江县）
- 生成 `看板-单城` PNG
- 企业微信推送：markdown 摘要 + 图片 + Excel 文件

## 智能体指令中的账号（必填）

```
ADMIN_USER=你的用户名或邮箱
ADMIN_PASSWORD=你的后台密码
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb
LR_TEMPLATE_PATH=lr/templates/LR日报总表模版5.4版(川藏一区).xlsx
```

## 约束

- **禁止**中途 AskQuestion / 需求对齐；缺信息用默认值，失败写阻塞报告
- **禁止**把文件落到用户本机 Downloads
- 抓取失败（五城不全）则停止并报告
- 工作表名是 `数据源(日)`（半角括号），不是 `数据源（日）`

## 定时 Automation

- 预填：`scripts/cursor_automation_lr_daily.json`
- 触发：每天 **23:30**（`30 23 * * *`）
- 仓库：`h15881142023-oss/fuzzy-umbrella` · `main`
