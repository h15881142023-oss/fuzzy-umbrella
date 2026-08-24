# 拜访检核日更 — 已迁移本机

> **推荐**：本机 launchd，见 `scripts/LOCAL_AUTOMATIONS.md` 与 `scripts/run_visit_check_local.sh`。  
> 请停用 Cursor Cloud Automation「拜访检核日更（Cloud）」。

以下步骤保留作排查参考。Excel 落仓库 `data/visit_exports/`。

## 目标
1. 登录业务后台并导出昨天「川藏一区」拜访数据
2. 将 Excel 保存到仓库 `data/visit_exports/`（云端）
3. 推送到平台入库后删除云端 Excel

## 步骤

### 0. 登录（Cloud 必须先做）
1. 打开 `http://47.112.178.78:13000/signin`
2. 若已在后台页则跳过
3. 填写 **用户名/邮箱**、**密码**，点橙色 **「登录」**
4. 登录成功后 URL 不应再是 `/signin`

### 1–7. 导出与入库
1. 打开：`http://47.112.178.78:13000/admin/iefct5mpj1o/tab/47nekzoybbv`，确认「拜访」Tab
2. 筛选：区域=`川藏一区`，拜访时间=`昨天`；城市不选
3. 等待表格刷新（约 1–2 分钟），总条数应为数百级
4. 点击「导出」→「确定」；xlsx 保存到 `data/visit_exports/`（禁止用户本机 Downloads）
5. `source .venv/bin/activate` 或创建 venv 并 `pip install -r requirements.txt`
6. `python scrapers/visit_check_daily.py --push-api`
7. 确认 API 返回 `ok: true` 与五城结果；默认删除已消费 xlsx

## 智能体指令中的账号（必填）

Automation **没有单独的环境变量页**，请写在「智能体指令」顶部：

```
ADMIN_USER=你的用户名或邮箱
ADMIN_PASSWORD=你的后台密码
CZ_PUBLIC_ORIGIN=https://1.chuanzangyiqu.top
CZ_SITE_PASSWORD=chuanzang2026
```

登录页字段：**用户名/邮箱**、**密码**、按钮 **登录**（NocoBase）。

## 约束
- **必须在云端一次跑完，禁止中途停下来向用户提问、确认需求或对齐意图**（不要「需求对齐确认」、不要 AskQuestion）
- 缺信息时：用本文件默认值继续；无法继续则直接写阻塞报告并结束
- 金山文档已弃用，不要再读 kdocs
- 不要把文件下载到用户电脑
- 登录失败则停止并报告

## 外网 API 依赖（重要）

Cloud Agent 通过 `https://1.chuanzangyiqu.top/api/visit_check/import` 入库。该域名走 **Cloudflare 隧道**，本机需保持：

```bash
./start_all.sh
# 或安装开机自启：bash scripts/install_tunnel_launchd.sh
```

隧道离线时会报 **Cloudflare 1033**，导出成功但无法入库。推送前可先测：

```bash
curl -s https://1.chuanzangyiqu.top/api/health
# 应返回 ok:true
```

## 定时 Automation

- 预填：`scripts/cursor_automation_visit_check.json`
- 触发：每天 **09:00**（`0 9 * * *`）
- 仓库：`h15881142023-oss/fuzzy-umbrella` · `main`
