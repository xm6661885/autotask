# AutoTask

本地自动化服务，用来管理**重复任务**和**一次性后台任务**（Python / Shell 脚本），提供 CLI 与 Flask Web UI。适合部署在家用服务器或小主机上，低资源占用，开机自启。

## 特性

- **两类任务**：重复任务（手动 / cron / 固定间隔 / webhook）和一次性任务（指定时间运行一次，或立即放到后台执行）。
- **独立任务目录**：脚本放在 `scripts/cron/<任务名>/` 或 `scripts/once/<任务名>/`，运行时工作目录就是任务自己的目录，可存放状态、输入与辅助文件。
- **CLI + Web UI**：创建脚本骨架、注册、立即执行、查看运行记录与完整日志；网页支持任务分组、描述与局部刷新。
- **SQLite 存储**：任务定义与运行记录入库，每次运行有独立日志文件；数据库迁移在启动时自动完成。
- **systemd 集成**：用户级或系统级服务，异常退出自动重启。

## 快速开始

需要 Python 3.9+。

```bash
git clone https://github.com/XMWML/autotask.git
cd autotask
./autotask/install-user.sh       # 创建 .venv、安装 CLI，并配置用户级 systemd 服务
.venv/bin/autotask status        # 检查配置路径、服务与时区
```

只想前台运行：

```bash
cp config.example.yaml config.yaml   # 按需修改路径，并填写 password_hash / secret_key / webhook_secret
AUTOTASK_CONFIG="$PWD/config.yaml" .venv/bin/autotaskd
```

Web UI 默认监听 `127.0.0.1:8990`。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `autotask/` | Python 包源码、安装脚本与测试 |
| `skill/autotask/` | 供 Claude Code 使用的 autotask 技能说明 |
| `config.example.yaml` | 配置示例（密钥留空） |
| `scripts/`、`data/` | 运行时的任务脚本与数据，**不随仓库发布** |

## 测试

```bash
cd autotask
python3 -m unittest discover -s tests
```

## 文档

完整的使用说明（任务模型、CLI 命令、webhook、迁移与卸载）见 [autotask/README.md](autotask/README.md)。
