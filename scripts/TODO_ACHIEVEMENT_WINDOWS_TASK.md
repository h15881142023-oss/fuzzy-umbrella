# Todo 达成监控（Windows 本机定时）

周一 / 周三 / 周五 **14:00** 自动拉取川藏一区本月 Todo，生成表格图片并推送企业微信。

后台页面：`http://www.chuxin.city/v/admin/itgnwhaar7u`  
API 基址：`http://www.chuxin.city`

## 安装依赖

```powershell
pip install pillow requests
```

（项目 `requirements.txt` 已含 Pillow/requests 时可直接 `pip install -r requirements.txt`）

## 手动试跑

```powershell
python scripts/todo_achievement_monitor_windows.py
```

默认双通道企微推送（原群 + 新群）。可用环境变量 `TODO_WECOM_WEBHOOKS`（逗号分隔）自定义。

## 安装定时任务（无人登录也运行）

建议管理员 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_todo_achievement_task_windows.ps1 -AtTime "14:00" -TaskName "todo达成监控" -RunWhetherUserLoggedOn
```

## 卸载

```powershell
powershell -ExecutionPolicy Bypass -File scripts/uninstall_todo_achievement_task_windows.ps1 -TaskName "todo达成监控"
```

## 日志

`C:\Windows\Temp\todo_monitor\monitor.log`
