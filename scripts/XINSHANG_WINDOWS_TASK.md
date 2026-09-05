# 新商评看板 — 挂在已有 Web 上（对齐经营宝，零复制命令）

经营宝不用从聊天窗口复制代码，是因为任务已经装在那个文件夹里、到点自己跑。

新商评同样：**不要复制 PowerShell**。时钟挂在已经在跑的 `ChuanzangWeb5001`（开机自启的 Flask）里。

## 到点做什么

每周二、周五 **22:00**（本机时间，窗口 10 分钟只跑一次）：

1. CDN 补齐同步脚本（缺文件就拉，不用 git）
2. Power BI 月在线商家数
3. Metabase 主看板
4. 同分群约 117 城
5. 企微 text（成功摘要或失败原因）

企微优先读桌面 `经营宝订单抓取\wecom_config.json`。

## 入口

```
ChuanzangWeb5001（已有，AtLogOn）
  → python scripts/run_web_windows.py
    → app.create_app()
      → xinshang_clock_windows 线程
        → 周二/周五 22:00
          → xinshang_daily_push.py
```

## 日志

`logs\xinshang_push.log`

## 外发页

https://1.chuanzangyiqu.top/evaluation/xinshang
