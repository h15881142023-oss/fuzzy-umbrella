# 自配门店监控（Windows 本机定时）

## 1) 安装依赖

在项目根目录执行：

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

## 2) 手动试跑

```powershell
python scripts/self_delivery_monitor_windows.py
```

可选参数：

- `--headless`：无头运行
- `--temp-dir "C:\Windows\Temp\zpei_monitor"`：临时目录（默认即此）

默认值（可用环境变量覆盖）：

- 看板 URL：`SELF_DELIVERY_BOARD_URL`
- 看板密码：`SELF_DELIVERY_BOARD_PASSWORD`（默认 `mtwm@888`）
- 企微 Webhook：`SELF_DELIVERY_WECOM_WEBHOOK`
- 临时目录：`SELF_DELIVERY_TEMP_DIR`

## 3) 安装 Windows 定时任务（每日执行）

推荐（无人登录也运行 + 每天 10:00）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_self_delivery_task_windows.ps1 -DailyTime "10:00" -TaskName "自配上线播报" -RunWhetherUserLoggedOn -Headless
```

常用参数：

- `-PythonExe "C:\path\to\python.exe"`：指定 Python
- `-TaskName "自配上线播报"`：任务名
- `-DailyTime "10:00"`：每天执行时间
- `-Headless`：无头执行
- `-RunWhetherUserLoggedOn`：无人登录也运行（S4U）

安装后会通过 `scripts/run_self_delivery_monitor_task.ps1` 启动，并写入可靠日志。

## 4) 卸载定时任务

```powershell
powershell -ExecutionPolicy Bypass -File scripts/uninstall_self_delivery_task_windows.ps1 -TaskName "自配上线播报"
```

## 5) 逻辑说明（与原流程一致）

1. 打开看板并自动处理密码弹窗（若出现）
2. 点击 `商家明细-昨日`，下载 Excel 到临时目录
3. 筛选条件：
   - C 列（一级商家配送类型）∈ `{跑腿, 商家配送}`
   - G 列（商家类型）∈ `{城市商家, 全国KA, 区域KA}`
   - R 列（上线时间）为当月
4. 在筛选结果中继续找近 3 天（含当天）上线门店
5. 企业微信推送：
   - 有近 3 天数据：先 markdown，再上传并推送筛选后的 Excel（字段：`城市｜门店｜ID｜配送类型｜商家类型｜上线时间`）
   - 无近 3 天数据：只推送文本 `📋 自配门店监控（{今天日期}）：近3日无自配门店上线`
6. 推送成功（`errcode=0`）后删除临时 Excel，不在电脑保留文件

## 6) 日志

- 定时任务日志：`C:\Windows\Temp\zpei_monitor\monitor.log`
