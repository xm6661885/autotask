# AutoTask

[English](README.md) | **简体中文**

AutoTask 是本地自动化服务，用来管理**重复任务**和**一次性后台任务**（Python / Shell 脚本）。提供命令行 `autotask`、守护进程 `autotaskd` 和 Flask Web UI。资源占用小（SQLite + 轮询调度器），可由 systemd 托管。

## 特性

- **两类任务**
  - 重复任务：手动、cron、固定间隔或 webhook，可反复触发。
  - 一次性任务：在某个本地时间点运行一次，或立即放到后台执行（适合长耗时任务）。
- **每个任务独占一个目录**：`scripts/cron/<任务名>/` 或 `scripts/once/<任务名>/`。脚本运行时的工作目录就是该目录，状态文件、prompt 和辅助文件都放在旁边。
- **CLI 与 Web UI 共用数据库和调度器**：创建脚本骨架、注册已有脚本、立即运行、编辑、启停、取消、分组、查看完整运行日志。
- **SQLite 存储**：任务与运行记录保存在 `<data_dir>/autotask.db`，每次运行有独立日志文件；schema 迁移在启动时自动完成。
- **一次性任务原子领取**：待执行任务通过数据库事务领取，调度器与“立即执行”不会重复启动。
- **systemd 集成**：支持用户级和系统级服务，异常退出自动重启。
- **Agent 技能**：自带 `skill/autotask/SKILL.md`，让 Claude Code 等 AI 编程代理直接帮你操作 CLI。

## 环境要求

- Python 3.9+
- 带 systemd 的 Linux（仅服务模式需要；也可前台运行 `autotaskd`）
- 依赖（Flask、croniter 等）由 pip 自动安装

## 安装

```bash
git clone https://github.com/XMWML/autotask.git
cd autotask
```

### 用户级安装（推荐）

在仓库根目录运行一次，升级时重复运行同一命令：

```bash
./autotask/install-user.sh
```

脚本会：

1. 创建/更新 `.venv`，以 editable 模式安装 `autotask/`；
2. 若根目录没有 `config.yaml` 则生成（监听 `127.0.0.1`、端口 `8990`、权限 `600`）；
3. 安装 `~/.local/bin/autotask` 和 `~/.local/bin/autotaskd` 包装脚本，固定使用该配置；
4. 把 agent 技能链接到 `~/.agents/skills/autotask/SKILL.md`；
5. 创建、启用并（重新）启动用户级 `autotask.service`。

确认 `~/.local/bin` 在 `PATH` 中，然后检查：

```bash
autotask status      # 配置路径、脚本/数据目录、服务状态、时区
```

### 系统级安装

```bash
cd autotask
sudo ./install.sh
```

默认：服务账号为运行 sudo 的用户，脚本目录为 `~/Automations/scripts`，数据目录为 `/var/lib/autotask`，监听 IPv4+IPv6 的 `8990` 端口，自动生成 session 密钥和 webhook 密钥；Web UI 有一个默认初始密码，**首次登录后必须在“设置”页修改**。可用环境变量自定义：

```bash
AUTOTASK_USER=deploy \
AUTOTASK_SCRIPTS_DIR=/srv/scripts \
AUTOTASK_DATA_DIR=/var/lib/autotask \
AUTOTASK_PORT=9000 \
sudo -E ./install.sh
```

### 前台运行（不装服务）

```bash
pip install -e ./autotask
cp config.example.yaml config.yaml    # 修改路径并填写密钥
AUTOTASK_CONFIG="$PWD/config.yaml" autotaskd
```

## 配置

配置文件按顺序查找：`$AUTOTASK_CONFIG`、`/etc/autotask/config.yaml`、`~/.config/autotask/config.yaml`（都没有时自动创建默认配置）。示例见 [`config.example.yaml`](config.example.yaml)：

| 配置项 | 含义 |
| --- | --- |
| `bind_host`、`port` | Web UI 监听地址（默认 `127.0.0.1:8990`） |
| `scripts_dir` | 任务脚本根目录（下设 `cron/`、`once/`） |
| `data_dir` | 存放 `autotask.db` 与 `logs/` |
| `python_bin`、`shell_bin` | 运行 `.py` / `.sh` 入口脚本的解释器 |
| `poll_interval_sec` | 调度器轮询间隔（默认 2 秒） |
| `password_hash` | Web UI 密码的 Werkzeug 哈希 |
| `secret_key` | Flask session 密钥 |
| `webhook_secret` | webhook 接口要求的共享密钥 |

## 任务模型与目录结构

| 类型 | 数据标识 | 典型用途 | 触发方式 | 终态 |
| --- | --- | --- | --- | --- |
| 重复任务 | `recurring` | 日报、轮询、webhook、可多次运行的工作 | manual、cron、interval、webhook | 持续可用 |
| 一次性任务 | `one_off` | 预约执行或后台长任务 | 指定时间或立即执行 | `completed`、`failed`、`cancelled` |

```text
scripts/
├── cron/
│   └── daily_backup/
│       ├── daily_backup.sh
│       └── state.json
└── once/
    └── export_2026_09/
        ├── export_2026_09.py
        └── input.csv
```

- `.py` 入口用 `python_bin` 运行，`.sh` 用 `shell_bin`；其他可执行文件也支持。
- **工作目录是任务自己的目录。** 引用旁路文件时用相对路径，或从脚本位置推导：Shell 用 `TASK_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"`，Python 用 `Path(__file__).resolve().parent`。
- 任务名全局唯一，同时也是任务目录名。
- 数据库保存相对 `scripts_dir` 的入口路径；注册后不要移动入口文件，确需更换请用 `autotask edit <任务> --script ...`。
- 一次性任务完成、失败或取消后保留历史，可用 `autotask run <任务>` 再次排队执行。

## CLI 用法

先执行 `autotask status`，以其输出的实际路径为准。

### 创建重复任务

`create` 会在任务目录生成脚本骨架，加 `--register` 才会写入调度数据库。

```bash
# 每天 02:00 执行
autotask create daily_backup --type shell --description "备份数据库" \
  --register --kind recurring --schedule-type cron --schedule-value "0 2 * * *"

# 每 3600 秒执行一次
autotask create check_disk --type python --description "检查磁盘空间" \
  --register --kind recurring --schedule-type interval --schedule-value 3600

# 仅手动触发（可反复执行）
autotask create repair_cache --type shell --description "修复缓存" \
  --register --kind recurring --schedule-type manual
```

调度类型：`manual`（仅 CLI/网页触发）、`cron`（标准 5 段表达式，按主机本地时间）、`interval`（秒，从上次运行完成时刻累计）、`webhook`（仅 HTTP POST 触发）。其他参数：`--args '["--verbose"]'`（默认参数，JSON 数组）、`--name`、`--disabled`、`--force`（覆盖已存在的骨架）。

### 创建一次性任务

```bash
# 在本地时间点运行一次（必须是未来时刻）
autotask create monthly_export --type python --description "导出本月数据" \
  --register --kind one-off --once-at "2026-09-21 09:30"

# 立即后台执行，命令马上返回
autotask create archive_media --type shell --description "归档媒体库" \
  --register --kind one-off --run-once
```

`--once-at` 与 `--run-once` 二选一，一次性任务不能用 cron/interval/webhook。不要用临时 cron 模拟一次性任务。

### 注册已有脚本

先把入口脚本和依赖放进任务目录，再用相对 `scripts_dir` 的路径注册：

```bash
autotask add cleanup cron/cleanup/cleanup.sh --kind recurring \
  --description "清理历史日志" --schedule-type cron --schedule-value "0 */6 * * *"

autotask add import_once once/import_once/import_once.py --kind one-off \
  --description "导入供应商文件" --once-at "2026-09-22 10:00"

autotask add reindex_once once/reindex_once/reindex_once.sh --kind one-off \
  --description "重建搜索索引" --run-once
```

### 运行、查看与管理

```bash
autotask list [--json] [--group <名称|ID|未分组|所有任务>]
autotask run daily_backup                      # 后台触发
autotask run daily_backup --wait               # 等待完成并打印日志
autotask run daily_backup --wait -- --target /mnt/backup --compress   # 附加脚本参数
autotask logs daily_backup --count 10          # 最近 10 次运行记录
autotask logs archive_media --latest           # 最近一次的完整日志
autotask enable|disable <任务>
autotask cancel <任务>                         # 取消尚未开始的一次性任务
autotask remove <任务>                         # 删除任务定义和运行记录（不删任务目录与日志文件）
```

重复任务运行中默认不会再次启动；`run --force` 会并发执行，仅在脚本可重入时使用。一次性任务不支持附加参数和 `--force`。

### 原地修改

`edit` 保留任务 ID、分组和运行记录（不要用 `remove` + `add` 改配置），只修改传入的项：

```bash
autotask edit <任务> -d "新说明"                  # 空字符串清空说明
autotask edit <任务> --args '["--verbose"]'       # 替换默认参数
autotask edit <任务> --clear-args
autotask edit <任务> --schedule-type cron --schedule-value "30 6 * * *"
autotask edit <任务> --schedule-value 1800        # 保持类型，只改值
autotask edit <任务> --schedule-type webhook
autotask edit <任务> --script cron/<任务名>/new_entry.py
autotask edit <一次性任务> --once-at "2026-10-01 09:00"   # 仅限等待中的一次性任务
```

任务名称和类型创建后不能改。修改在调度器下一轮生效，无需重启服务。

### 分组

分组只影响管理视图，不改变任务类型、调度方式或脚本路径。删除分组时其中的任务回到“未分组”。

```bash
autotask groups list [--json]
autotask groups create 工作
autotask groups rename 工作 项目工作
autotask groups move daily_backup 项目工作
autotask groups ungroup daily_backup
autotask groups delete 项目工作
```

## Web UI

访问 `http://127.0.0.1:8990`（或你配置的 `bind_host`/`port`）并登录。

- 首页分为“重复任务”和“一次性任务”两个 Tab，各有预设类型的新建入口。
- 可按“所有任务”“未分组”或自建分组筛选；可新建、重命名、删除分组，并在任务卡片上移动任务。
- 一次性表单提供“立即执行”和“指定时间”（本地日期时间）；等待中的定时任务可提前执行或取消，完成的任务可“再次执行”。
- 重复任务表单提供 manual、cron、interval、webhook。
- 启停、执行、停止、取消、删除就地刷新；编辑页与运行记录页单独打开。
- 每次运行可查看退出码、起止时间和完整的标准输出/错误日志。

## Webhook 任务

Webhook 仅限重复任务，守护进程会把 JSON 请求体通过 **stdin** 传给脚本。

```bash
autotask add wechat_print cron/wechat_print/receiver.py \
  --kind recurring --description "处理回调" --schedule-type webhook

curl -X POST http://127.0.0.1:8990/api/webhook/wechat_print \
  -H "X-AutoTask-Webhook-Secret: <webhook_secret>" \
  -H "Content-Type: application/json" \
  -d '{"hello":"world"}'
```

该接口不依赖 Web UI 登录态，只校验 `webhook_secret`。任务已在运行时，新的 webhook 会被拒绝而不是并发启动。

## 调度、日志与时区

- cron 与 `--once-at` 按 `autotaskd` 进程所在主机的**本地时区**解释；interval 与时区无关。
- 时间戳以 Unix 秒保存，展示时转换为本地时间。
- 调度器默认每 2 秒轮询，存在数秒误差。
- 每次运行的 stdout+stderr 写入 `<data_dir>/logs/` 下独立文件。服务日志：`journalctl --user -u autotask -f`（用户级）或 `journalctl -u autotask -f`（系统级）。

## 通过 AI 代理使用（技能）

[`skill/autotask/SKILL.md`](skill/autotask/SKILL.md) 是名为 `autotask` 的 agent 技能，教 AI 编程代理如何选择任务类型、创建/注册/修改任务、查看日志并避开常见坑。安装后你可以直接说“每天凌晨 2 点跑一下备份脚本”“把这个导出放到后台跑，完成后告诉我”，代理会自行调用 `autotask` CLI。

安装方式：

- **自动**：`./autotask/install-user.sh` 会把它软链到 `~/.agents/skills/autotask/SKILL.md`，仓库里的修改立即生效。
- **Claude Code**：链接或复制到技能目录：
  ```bash
  mkdir -p ~/.claude/skills/autotask
  ln -sfn "$PWD/skill/autotask/SKILL.md" ~/.claude/skills/autotask/SKILL.md
  ```
- 其他读取 `SKILL.md` 的代理：放到对应工具的技能目录即可。

技能依赖 `PATH` 中的 `autotask` 命令（见“安装”）。

## 在任务中运行代理作业

步骤明确的长耗时代理工作适合做成一次性 shell 任务：AutoTask 负责后台生命周期和日志，`exec` 让代理的退出码直接成为运行结果。

```bash
#!/usr/bin/env bash
set -euo pipefail
exec codex exec --sandbox danger-full-access --skip-git-repo-check \
  -C /absolute/path/to/workspace <<'PROMPT'
说明目标、输入来源、允许的外部副作用、失败处理和通知方式。
PROMPT
```

不要把密码、Cookie、验证码或支付 token 写进脚本、prompt、任务参数或日志。

## 安全提示

- 首次登录后立即修改 Web UI 默认密码。`config.yaml` 含密码哈希、session 密钥和 webhook 密钥，请妥善保管（本仓库已将其加入 `.gitignore`）。
- 用户级安装默认只绑定 `127.0.0.1`；若对外开放，请配合防火墙或 HTTPS 反向代理。
- 脚本以 `autotaskd` 用户的权限运行，可能产生外部副作用，只注册可信脚本。
- 任务参数以明文存入 SQLite；机密请从受保护的文件或环境变量读取。
- 注册 shell 脚本前先用 `bash -n <脚本>` 检查语法。

## 开发

```bash
cd autotask
python3 -m pip install -e .
python3 -m unittest discover -s tests                                   # 全部测试
python3 -m unittest discover -s tests -p 'test_groups.py'               # 单个文件
python3 tests/test_groups.py GroupTests.test_v3_database_migrates_existing_tasks_to_ungrouped
```

源码位于 `autotask/autotask/`：`cli.py`（命令行）、`daemon.py`（`autotaskd` 入口）、`scheduler.py`（cron/间隔/一次性调度）、`runner.py`（子进程运行与日志）、`db.py`（SQLite schema、迁移、任务/分组/运行记录）、`webapp.py`（Web UI 与 webhook 接口）。

## 卸载

```bash
# 用户级安装
systemctl --user disable --now autotask
rm -f ~/.config/systemd/user/autotask.service ~/.local/bin/autotask ~/.local/bin/autotaskd

# 系统级安装
sudo systemctl disable --now autotask
sudo rm -f /etc/systemd/system/autotask.service /usr/local/bin/autotask /usr/local/bin/autotaskd
sudo rm -rf /opt/autotask
# 以下两步会删除数据和配置，谨慎操作
sudo rm -rf /var/lib/autotask /etc/autotask
```

卸载不会删除脚本根目录。
