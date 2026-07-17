#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

stop_pidfile() {
  local f="$1"
  local name="$2"
  if [[ -f "$f" ]]; then
    local pid
    pid="$(cat "$f")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 0.4
      kill -9 "$pid" 2>/dev/null || true
      echo "stopped $name ($pid)"
    fi
    rm -f "$f"
  fi
}

stop_pidfile gunicorn.pid "gunicorn"
stop_pidfile logs/auto_sync.pid "auto_sync"
stop_pidfile logs/cloudflared.pid "cloudflared"

# 兜底：停掉本目录相关 gunicorn
pkill -f "gunicorn.*app:create_app" 2>/dev/null || true
echo "All stopped (tunnel 若由系统其他方式启动需手动检查 pgrep cloudflared)."
