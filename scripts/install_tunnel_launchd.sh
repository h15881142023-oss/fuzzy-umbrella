#!/usr/bin/env bash
# 安装 launchd：登录后自动启动 Cloudflare 隧道（供 Cloud Agent push-api 访问）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="top.chuanzangyiqu.cloudflared"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
CF_CONFIG="$HOME/.cloudflared/config.yml"

if [[ ! -f "$CF_CONFIG" ]]; then
  echo "缺少 $CF_CONFIG，请先配置 Cloudflare 隧道" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"

cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>export PATH="\$HOME/bin:\$PATH"; cloudflared tunnel --config ${CF_CONFIG} run chuanzang-data</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/cloudflared.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/cloudflared.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/${LABEL}" 2>/dev/null || true

echo "已安装: $PLIST"
echo "登录后自动保持 cloudflared 运行"
echo "日志: $ROOT/logs/cloudflared.out.log"
echo "卸载: bash $ROOT/scripts/uninstall_tunnel_launchd.sh"
