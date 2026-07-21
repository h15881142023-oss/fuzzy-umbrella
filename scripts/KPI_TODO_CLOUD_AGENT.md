# Cursor Cloud Agent — KPI 待办进度（周一/周四 14:00）

在 **Cloud** 环境执行（与拜访检核、LR 日报一致）。筛选 **川藏一区 + 本月**，生成标红表格图片并推送企业微信。

## 目标

1. 登录业务后台，打开 KPI 待办进度页
2. 筛选：区域=`川藏一区`，周期=`本月`
3. 抓取表格 headers + rows → JSON
4. 生成表格 PNG（完成进度 < 1 标红）
5. 企业微信推送：markdown 摘要 + 图片

## 步骤

### 0. 登录

1. 打开 `http://47.112.178.78:13000/signin`
2. 填写 **用户名/邮箱**、**密码**，点 **登录**
3. URL 离开 `/signin` 后再继续

### 1. 打开看板并筛选

1. 打开 `http://47.112.178.78:13000/admin/itgnwhaar7u`
2. 区域选 `川藏一区`
3. 日期/周期选 `本月`（或等价选项）
4. 等待表格刷新（约 30–60 秒）

### 2. 抓取网页表格（不要导出）

```javascript
(() => {
  const headers = Array.from(document.querySelectorAll('thead th'))
    .map(el => el.innerText.trim()).filter(Boolean);
  const rows = Array.from(document.querySelectorAll('tbody tr'))
    .map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()))
    .filter(r => r.length);
  return {
    headers,
    rows,
    scraped_at: new Date().toISOString(),
    filters: { region: '川藏一区', period: '本月' }
  };
})()
```

保存为 `data/kpi_todo_scrape/latest.json`（仅云端工作区）。

### 3. 运行脚本

```bash
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python kpi_todo/run_biweekly.py --scrape-json data/kpi_todo_scrape/latest.json
```

### 4. 推送文案规则

- 每个 **完成进度 < 1** 的单元格计为 1 项未达成（图片中红色格）
- 有未达成：`截止 {更新日期} 有 {N} 项 todo 未达成`
- 全部达成：`截止 {更新日期} todo 均达成`
- 无数据或失败：`python kpi_todo/run_biweekly.py --notify-only --message "具体原因"`

## 智能体指令中的默认值（必填块）

```
ADMIN_USER=qiaoxianhai
ADMIN_PASSWORD=123
WECOM_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=103699eb-8cd7-4af8-9fbe-46f01d315abb
KPI_TODO_ADMIN_URL=http://47.112.178.78:13000/admin/itgnwhaar7u
```

未单独说明账号密码的网址，一律使用上述 `ADMIN_USER` / `ADMIN_PASSWORD`。

## 约束

- **禁止**中途 AskQuestion / 需求对齐；缺信息用默认值，失败写阻塞报告并 `--notify-only` 推送企微
- **禁止**把文件落到用户本机 Downloads
- 抓取失败或无数据也必须推送企微文字说明

## 定时 Automation

- 预填：`scripts/cursor_automation_kpi_todo_biweekly.json`
- 触发：每周一、周四 **14:00**（`0 14 * * 1,4`）
- 仓库：`h15881142023-oss/fuzzy-umbrella` · `main`
