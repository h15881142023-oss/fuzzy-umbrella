# Cursor Cloud Agent — 拜访检核日更

每天在 **Cloud** 环境执行（Excel 只落云端工作区，禁止下载到用户本机 Downloads）。

## 目标
1. 打开后台拜访页并按当前列表条件导出昨天数据
2. 将 Excel 保存到仓库 `data/visit_exports/`（云端）
3. 推送到平台入库后删除云端 Excel

## 步骤
1. 打开：`http://47.112.178.78:13000/admin/iefct5mpj1o/tab/47nekzoybbv`（需已登录；未登录则停在登录页并报告）
2. 确认在「拜访」Tab
3. 筛选：区域=`川藏一区`，拜访时间=`昨天`；城市不选
4. 等待表格刷新（约 1–2 分钟），总条数应变小（通常数百级，不是几十万）
5. 点击「导出」→ 弹窗「确定」；把下载文件保存/移动到 `data/visit_exports/`（不要用用户本机 Downloads）
6. 在仓库根目录执行：

```bash
source .venv/bin/activate
python scrapers/visit_check_daily.py --push-api
```

7. 确认 API 返回 `ok: true` 与五城结果；脚本默认会删除已消费的 xlsx

## 约束
- 金山文档已弃用，不要再读 kdocs
- 不要把文件下载到用户电脑
- 若浏览器无法登录后台，停止并说明阻塞原因
