#!/usr/bin/env bash
# 一键启动：Web(Gunicorn) + Excel 监控（可选 cloudflared）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PATH="$HOME/bin:$PATH"

mkdir -p logs

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export CZ_SITE_PASSWORD="${CZ_SITE_PASSWORD:-chuanzang2026}"
export CZ_SECRET_KEY="${CZ_SECRET_KEY:-chuanzang-change-me-in-production}"

python - <<'PY'
import db
db.init_db()
db.seed_demo_if_empty()
print("DB ready:", db.DB_PATH)
PY

if [[ -f gunicorn.pid ]] && kill -0 "$(cat gunicorn.pid)" 2>/dev/null; then
  echo "Gunicorn already running (pid $(cat gunicorn.pid))"
else
  gunicorn \
    --workers 2 \
    --bind 0.0.0.0:5001 \
    --pid gunicorn.pid \
    --access-logfile access.log \
    --error-logfile error.log \
    --capture-output \
    --daemon \
    "app:create_app()"
  echo "Web started on http://127.0.0.1:5001"
fi

if [[ -f logs/auto_sync.pid ]] && kill -0 "$(cat logs/auto_sync.pid)" 2>/dev/null; then
  echo "auto_sync already running"
else
  nohup python auto_sync.py > logs/auto_sync.log 2>&1 &
  echo $! > logs/auto_sync.pid
  echo "Excel watcher started (pid $(cat logs/auto_sync.pid))"
fi

if command -v cloudflared >/dev/null 2>&1; then
  if [[ -f "$HOME/.cloudflared/config.yml" ]]; then
    if pgrep -fl "cloudflared tunnel" >/dev/null 2>&1; then
      echo "cloudflared already running"
    else
      nohup cloudflared tunnel --config "$HOME/.cloudflared/config.yml" run chuanzang-data \
        > /tmp/cloudflared-chuanzang.log 2>&1 &
      echo $! > logs/cloudflared.pid
      echo "cloudflared started (see /tmp/cloudflared-chuanzang.log)"
    fi
  else
    echo "提示：尚未配置 ~/.cloudflared/config.yml，外网域名暂不可用。见 README。"
  fi
else
  echo "提示：未安装 cloudflared。本机可先用 http://127.0.0.1:5001 验收。"
fi

echo "Password: \$CZ_SITE_PASSWORD (default chuanzang2026)"
echo "Done."
