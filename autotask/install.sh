#!/usr/bin/env bash
# AutoTask 安装脚本（系统级安装，需要 sudo/root）
#
# 用法:
#   sudo ./install.sh
#
# 环境变量（可选，覆盖默认值）:
#   AUTOTASK_USER        运行服务的系统用户，默认为调用 sudo 的用户 ($SUDO_USER)
#   AUTOTASK_SCRIPTS_DIR  脚本存放目录，默认 <用户家目录>/Automations/scripts
#   AUTOTASK_DATA_DIR     数据目录（数据库、日志），默认 /var/lib/autotask
#   AUTOTASK_PORT         Web UI 监听端口，默认 8990
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "错误: 请使用 sudo 运行此脚本" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RUN_USER="${AUTOTASK_USER:-${SUDO_USER:-}}"
if [[ -z "$RUN_USER" || "$RUN_USER" == "root" ]]; then
  echo "错误: 无法确定运行用户，请用 sudo（非 root 直接登录）运行，或设置 AUTOTASK_USER=<用户名>" >&2
  exit 1
fi

RUN_HOME=$(getent passwd "$RUN_USER" | cut -d: -f6)
if [[ -z "$RUN_HOME" ]]; then
  echo "错误: 找不到用户 $RUN_USER 的家目录" >&2
  exit 1
fi

SCRIPTS_DIR="${AUTOTASK_SCRIPTS_DIR:-$RUN_HOME/Automations/scripts}"
DATA_DIR="${AUTOTASK_DATA_DIR:-/var/lib/autotask}"
PORT="${AUTOTASK_PORT:-8990}"
VENV_DIR="/opt/autotask/venv"
CONFIG_DIR="/etc/autotask"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

echo "== AutoTask 安装 =="
echo "运行用户   : $RUN_USER"
echo "脚本目录   : $SCRIPTS_DIR"
echo "数据目录   : $DATA_DIR"
echo "Web 端口   : $PORT"
echo "虚拟环境   : $VENV_DIR"
echo "配置文件   : $CONFIG_FILE"
echo

command -v python3 >/dev/null || { echo "错误: 未找到 python3"; exit 1; }

echo "[1/6] 创建虚拟环境..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip

echo "[2/6] 安装 autotask 包..."
"$VENV_DIR/bin/pip" install --quiet "$SCRIPT_DIR"

echo "[3/6] 创建目录..."
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$DATA_DIR/logs"
mkdir -p "$CONFIG_DIR"
chown -R "$RUN_USER":"$RUN_USER" "$SCRIPTS_DIR" "$DATA_DIR"

echo "[4/6] 生成配置文件..."
if [[ -f "$CONFIG_FILE" ]]; then
  echo "  配置文件已存在，跳过生成（保留现有密码等设置）: $CONFIG_FILE"
else
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  PW_HASH=$("$VENV_DIR/bin/python3" -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('070827'))")
  cat > "$CONFIG_FILE" <<EOF
bind_host: "::"
port: $PORT
scripts_dir: "$SCRIPTS_DIR"
data_dir: "$DATA_DIR"
python_bin: "python3"
shell_bin: "bash"
poll_interval_sec: 2
webhook_secret: "$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")"
password_hash: "$PW_HASH"
secret_key: "$SECRET_KEY"
EOF
  chown "$RUN_USER":"$RUN_USER" "$CONFIG_FILE"
  chmod 600 "$CONFIG_FILE"
  echo "  已生成配置文件，默认密码: 070827（登录后请在“设置”页修改）"
fi

echo "[5/6] 安装命令行工具到 /usr/local/bin ..."
ln -sf "$VENV_DIR/bin/autotask" /usr/local/bin/autotask
ln -sf "$VENV_DIR/bin/autotaskd" /usr/local/bin/autotaskd

echo "[6/6] 安装并启动 systemd 服务..."
cat > /etc/systemd/system/autotask.service <<EOF
[Unit]
Description=AutoTask - 自动化脚本调度与 Web 管理
After=network.target

[Service]
Type=simple
User=$RUN_USER
Environment=AUTOTASK_CONFIG=$CONFIG_FILE
ExecStart=$VENV_DIR/bin/autotaskd
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable autotask.service
systemctl restart autotask.service

sleep 1
if systemctl is-active --quiet autotask.service; then
  echo
  echo "✅ 安装完成，服务运行中。"
else
  echo
  echo "⚠️  服务未能正常启动，请查看: journalctl -u autotask -n 50 --no-pager"
  exit 1
fi

IPV4=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "Web UI 访问地址:"
echo "  http://127.0.0.1:$PORT"
[[ -n "$IPV4" ]] && echo "  http://$IPV4:$PORT"
echo "  http://[::1]:$PORT"
echo
echo "默认密码: 070827  （请登录后在“设置”页修改）"
echo "CLI 用法: autotask --help"
echo "服务管理: systemctl {status|restart|stop} autotask"
