#!/usr/bin/env bash
# Install CLI, Web UI service and agent skill from this checkout.
set -euo pipefail

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname -- "$PACKAGE_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
CONFIG_FILE="$PROJECT_DIR/config.yaml"
USER_CONFIG_DIR="$HOME/.config/autotask"
USER_CONFIG="$USER_CONFIG_DIR/config.yaml"
SERVICE_FILE="$HOME/.config/systemd/user/autotask.service"
SKILL_FILE="$PROJECT_DIR/skill/autotask/SKILL.md"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install --quiet --python "$VENV_DIR/bin/python" --editable "$PACKAGE_DIR"
else
  if ! "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
    "$VENV_DIR/bin/python" -m ensurepip --upgrade >/dev/null
  fi
  "$VENV_DIR/bin/python" -m pip install --quiet --editable "$PACKAGE_DIR"
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  PROJECT_DIR="$PROJECT_DIR" CONFIG_FILE="$CONFIG_FILE" "$VENV_DIR/bin/python" - <<'PY'
import os
from autotask.config import _default_config, save_config

root = os.environ["PROJECT_DIR"]
path = os.environ["CONFIG_FILE"]
cfg = _default_config(os.path.join(root, "scripts"), os.path.join(root, "data"))
cfg["bind_host"] = "127.0.0.1"
save_config(cfg, path)
os.chmod(path, 0o600)
PY
fi

mkdir -p "$USER_CONFIG_DIR" "$HOME/.local/bin" "$HOME/.agents/skills/autotask" "$(dirname -- "$SERVICE_FILE")"
if [[ -e "$USER_CONFIG" && "$(readlink -f -- "$USER_CONFIG")" != "$(readlink -f -- "$CONFIG_FILE")" ]]; then
  if ! cmp -s -- "$USER_CONFIG" "$CONFIG_FILE"; then
    echo "错误: $USER_CONFIG 与 $CONFIG_FILE 内容不同；请先合并配置，避免 CLI 与服务使用不同数据库。" >&2
    exit 1
  fi
fi
ln -sfn -- "$CONFIG_FILE" "$USER_CONFIG"

for command in autotask autotaskd; do
  command_path="$HOME/.local/bin/$command"
  wrapper_path="$(mktemp "$HOME/.local/bin/.${command}.XXXXXX")"
  cat > "$wrapper_path" <<EOF
#!/usr/bin/env bash
export AUTOTASK_CONFIG='$CONFIG_FILE'
exec '$VENV_DIR/bin/$command' "\$@"
EOF
  chmod 755 "$wrapper_path"
  mv -f -- "$wrapper_path" "$command_path"
done
ln -sfn -- "$SKILL_FILE" "$HOME/.agents/skills/autotask/SKILL.md"

if [[ ! -f "$SERVICE_FILE" ]]; then
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=AutoTask scheduler and web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment=AUTOTASK_CONFIG=$CONFIG_FILE
ExecStart=$VENV_DIR/bin/autotaskd
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
elif ! grep -Fqx "Environment=AUTOTASK_CONFIG=$CONFIG_FILE" "$SERVICE_FILE" ||
     ! grep -Fqx "ExecStart=$VENV_DIR/bin/autotaskd" "$SERVICE_FILE"; then
  echo "错误: 现有服务文件 $SERVICE_FILE 未指向本项目的配置和虚拟环境；请先检查后再升级。" >&2
  exit 1
fi

systemctl --user daemon-reload
systemctl --user enable autotask.service >/dev/null
systemctl --user restart autotask.service
echo "安装完成：CLI、Web UI 和 skill 均使用 $PACKAGE_DIR；配置文件 $CONFIG_FILE"
"$HOME/.local/bin/autotask" status
