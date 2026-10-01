---
name: autotask
description: 通过 autotask CLI 创建、管理和执行重复任务或一次性后台任务（Python/Shell）。当用户提到 cron 定时、固定间隔、在指定时间只运行一次、立即在后台启动耗时任务、创建自动化脚本、查看任务状态或运行日志时使用。也用于将已有脚本注册为可调度任务。
author: AutoTask
version: "2.1.1"
tags:
  - automation
  - cron
  - scheduler
  - one-off
  - cli
---

# autotask — 自动化脚本运行工具

命令：autotask（CLI 管理）和 autotaskd（后台守护进程，通常由 systemd 管理）。

先执行：

~~~bash
autotask status
~~~

以后续输出中的实际脚本目录、数据目录和时区为准，不要假定安装路径。

## 先选任务类型

创建前先判断任务是否需要重复执行；这决定脚本目录、调度方式和首页分区。

| 类型 | 适用场景 | 调度方式 | 脚本位置 |
| --- | --- | --- | --- |
| recurring（重复） | 可反复执行的手动、cron、间隔或 webhook 工作 | manual、cron、interval、webhook | scripts/cron/<任务名>/ |
| one_off（一次性） | 某时刻只运行一次，或立即放后台执行的长任务 | 内部为 once；立即或定时触发 | scripts/once/<任务名>/ |

- 每个任务有自己的目录；入口脚本、prompt、状态文件和辅助模块都应放在该目录。
- 一次性任务从待执行状态被原子领取，只会执行一次；结束后记录为成功或失败并停止调度。任务、运行历史和日志均保留。
- 原有 manual 任务仍是重复任务，可以手动运行多次。
- 任务名称全局唯一，也用于 CLI 引用和任务目录；取稳定、可读的名字。

## 目录与脚本约定

默认脚本根目录是 ~/Automations/scripts，实际位置以 autotask status 为准：

~~~text
scripts/
├── cron/
│   └── daily_backup/
│       ├── daily_backup.sh
│       └── state.json
└── once/
    └── export_2026_09/
        ├── export_2026_09.py
        └── input.csv
~~~

- .py 用 python3，.sh 用 bash；也支持带执行权限的其他可执行文件。
- cwd 是当前任务目录，不是 scripts 根目录。引用旁路文件时优先使用相对路径或从脚本自身位置推导，不能写死旧的 .../scripts/<文件> 路径。
- Shell 可用 TASK_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"，Python 可用 Path(__file__).resolve().parent。
- 注册后不要自行移动入口脚本；若确需改入口，先把新脚本放进同一任务目录，再用 `autotask edit <任务> --script cron/<任务名>/<新文件>` 更新。
- 本次升级会先复制已注册的旧任务到 scripts/cron/<任务名>/，再在停服切换时更新任务路径。旧任务一律视为重复任务；迁移后检查旧根目录的硬编码路径。共享脚本若有独立状态需求，会保留各任务自己的副本。
- 旧根入口和关联文件只会在切换验证后删除，便于短暂回退；BrowserData、.playwright-cli、__pycache__ 等不属于任务入口的目录不会被迁移或删除。

## 创建重复任务

create 会按类型创建任务目录和骨架；加 --register 后才会写入调度数据库。

~~~bash
# 每天凌晨 2 点重复执行
autotask create daily_backup --type shell --description "备份数据库" \
  --register --kind recurring --schedule-type cron --schedule-value "0 2 * * *"

# 每小时执行一次
autotask create check_disk --type python --description "检查磁盘空间" \
  --register --kind recurring --schedule-type interval --schedule-value 3600

# 可反复手动执行
autotask create repair_cache --type shell --description "修复缓存" \
  --register --kind recurring --schedule-type manual
~~~

- --kind recurring 是默认类型。
- --schedule-type manual|cron|interval|webhook 默认 manual；manual、webhook 不需要 --schedule-value。
- --description / -d 是任务用途说明。create 同时写入骨架注释，该说明也展示在任务列表。
- --args 是默认参数的 JSON 数组，例如 '["--verbose"]'；--name 可覆盖由文件名推导的任务名；--disabled 可注册但不启用。

## 创建一次性任务

一次性任务用于一次预约或后台长耗时工作。创建时必须注册，不要用临时 cron 来模拟一次性执行。

~~~bash
# 在主机本地时间的指定时刻运行一次
autotask create monthly_export --type python --description "导出本月数据" \
  --register --kind one-off --once-at "2026-09-21 09:30"

# 立即启动一次长任务；CLI 返回后由后台继续执行
autotask create archive_media --type shell --description "归档媒体库" \
  --register --kind one-off --run-once
~~~

- --kind one-off 创建一次性任务，脚本进入 scripts/once/<任务名>/。
- --once-at 'YYYY-MM-DD HH:MM' 在主机本地时区安排一次执行，须为未来时刻。
- --run-once 创建后立即后台投递一次执行，适合长任务；不用前台等待，用日志或 Web UI 观察进度。
- --once-at 和 --run-once 二选一；一次性任务不能配置 cron、interval 或 webhook。

## 注册已有脚本

先将入口脚本和依赖放入目标任务目录，再以相对 scripts 根目录的路径使用 add：

~~~bash
# scripts/cron/cleanup/cleanup.sh
autotask add cleanup cron/cleanup/cleanup.sh --kind recurring \
  --description "清理历史日志" --schedule-type cron --schedule-value "0 */6 * * *"

# scripts/once/import_once/import_once.py
autotask add import_once once/import_once/import_once.py --kind one-off \
  --description "导入供应商文件" --once-at "2026-09-22 10:00"

# 已有脚本立即作为后台一次性长任务执行
autotask add reindex_once once/reindex_once/reindex_once.sh --kind one-off \
  --description "重建搜索索引" --run-once
~~~

add --description 是显示在 CLI/网页列表的任务元数据，不等同于文件名。迁移前的既有任务描述为空，可用 `autotask edit <任务> -d "说明"` 补充。

## 管理与查看

~~~bash
autotask list
autotask list --json
autotask list --group 未分组
autotask enable <任务名或ID>
autotask disable <任务名或ID>
autotask cancel <任务名或ID>       # 取消尚未开始的一次性任务
autotask remove <任务名或ID>       # 删除任务定义与运行记录，不删任务目录

# 手动运行可重复任务
autotask run daily_backup
autotask run daily_backup --wait
autotask run daily_backup --wait -- --target /mnt/backup --compress

# 查看记录或最近一次完整日志
autotask logs daily_backup --count 10
autotask logs archive_media --latest
~~~

- autotask run 通常用于重复任务的人工触发。尚在等待的一次性任务也可用它提前启动一次，但不能追加参数或使用 --force；创建时需要立即后台执行则用 --run-once。
- 任务运行中默认不会再启动；run --force 会并发执行，只在脚本可重入时使用。
- 一次性任务处于等待状态时可用 autotask cancel 取消；完成、失败或取消后可用 `autotask run <任务名或ID>` 开始一轮新的立即执行。该操作不删除历史记录，且不能追加参数或使用 `--force`。
- 删除一次性任务前，其终态和运行记录会保留；删除不会清理任务目录或日志文件。

## 修改已有任务

用 edit 原地修改，保留任务 ID、分组和运行记录；不要用 remove + add 来改配置（会丢失运行记录）。只改传入的项，其余保持不变。

~~~bash
autotask edit <任务名或ID> -d "新说明"                 # 空字符串清空说明
autotask edit <任务名或ID> --args '["--verbose"]'      # 替换默认参数（JSON 字符串数组）
autotask edit <任务名或ID> --clear-args                # 清空默认参数
autotask edit <任务名或ID> --schedule-type cron --schedule-value "30 6 * * *"
autotask edit <任务名或ID> --schedule-value 1800       # 保持调度方式，只改 cron/间隔值
autotask edit <任务名或ID> --schedule-type webhook     # manual/webhook 不需要调度值
autotask edit <任务名或ID> --script cron/<任务名>/new_entry.py
autotask edit <一次性任务> --once-at "2026-10-01 09:00" # 仅限等待中的一次性任务
~~~

- 任务名称和类型（重复/一次性）创建后不能改：名称即任务目录。启停用 enable/disable，分组用 groups move。
- 改调度会按新设置重算下次运行时间；校验规则与网页编辑一致（cron 须有效、间隔须 > 0、脚本须在任务专属目录内）。
- 一次性任务只能在等待中编辑，且没有 cron/间隔选项。
- 修改立即写入数据库，autotaskd 下一轮调度即生效，无需重启服务；正在运行的那次不受影响。

## 任务分组

分组只影响管理视图，不改变重复/一次性任务类型、调度方式或脚本路径。新建任务默认未分组。删除分组时其中的任务回到“未分组”，任务和运行记录保留。

~~~bash
autotask groups list                 # 查询分组及每组任务数；支持 --json
autotask groups create 工作
autotask groups rename 工作 项目工作   # 分组名称或 ID 均可
autotask groups move daily_backup 项目工作  # 任务名称或 ID 均可
autotask groups ungroup daily_backup
autotask groups delete 项目工作       # 任务转为未分组
autotask list --group 项目工作        # 也可用 未分组 / 所有任务
~~~

## Web UI

Web UI 默认位于 http://<主机>:8990。首页在同一页中分为“重复任务”和“一次性任务”两个 Tab；各自的新建入口预设相应类型，不需要反复跳页。启停、立即执行、停止、取消和删除会局部刷新；编辑页与运行记录页仍可单独打开。

首页的分组筛选提供“所有任务”“未分组”和自建分组；在分组栏可新建、重命名、删除，在任务卡片上可直接移动任务。分组筛选与任务类型 Tab 可同时使用。

本机用户安装/升级可在项目目录执行 `./autotask/install-user.sh`。它从同一源码目录以 editable 模式安装 CLI 和服务、连接 skill，并让 CLI 与服务读取同一配置。升级后先用 `autotask status` 核对数据目录。

“描述”是列表展示的任务说明。选择一次性任务后，选“立即执行”或“指定时间”；后者使用本地日期时间，等待中的定时任务也可提前立即执行或取消。完成、失败或取消的一次性任务会显示“再次执行”；它创建新的立即执行轮次，并保留旧运行记录。选择重复任务后，才显示 cron、间隔、手动和 webhook 调度项；脚本选择按 scripts/cron/ 和 scripts/once/ 分组。

## 调度与时区

- cron 是标准五段表达式（分 时 日 月 周），按 autotaskd 的系统本地时区解释。
- interval 是秒数，从上一次完成时刻开始累计。
- once-at 也按系统本地时区解释；实际时刻以 Unix 秒保存，展示时再转为本地时间。
- 调度器默认每 2 秒检查一次，允许数秒误差。一次性任务被领取后不会进入下一轮调度。

## 在脚本中运行 Codex 代理任务

有明确步骤的长任务可把 codex exec 放进一次性 shell 脚本，让 AutoTask 管理后台生命周期和日志。使用绝对工作目录，并以单引号 heredoc 传入 prompt：

~~~bash
#!/usr/bin/env bash
set -euo pipefail

exec codex exec \
  --sandbox danger-full-access \
  --skip-git-repo-check \
  -C /absolute/path/to/workspace <<'PROMPT'
你正在执行一次性后台代理任务。

写明目标、输入来源、允许的外部副作用、失败处理、完成通知方式，
以及何时需要用户授权或人工决定。
PROMPT
~~~

- -C 必须为绝对路径；不要依赖旧 scripts 根目录作为工作目录。
- 使用 exec 把退出码传回 AutoTask，正确标记一次性任务成功或失败。
- 不要将密码、Cookie、验证码、支付 token 或其他秘密写进脚本、prompt、任务参数或日志。
- 后台 codex exec 没有交互式前台；需要通知完成、失败或登录阻塞时，在 prompt 中要求使用 notify。
- 修改脚本后可先运行 bash -n <脚本绝对路径>；除非用户明确要求，不能为了测试而启动有外部副作用的任务。

## 排查与安全

- 一次性任务未启动：确认仍为待执行状态、时间使用主机本地时区，并查看 autotask logs <任务名> 与 journalctl -u autotask -f。
- 重复任务未按时触发：检查启用状态、cron/interval 值和系统时区；升级后重启一次 autotask.service 可重算旧 cron 的下次时间。
- 脚本找不到文件：检查任务是否已迁入正确目录，改用脚本目录相对路径或由 __file__ / BASH_SOURCE 推导的路径。
- 默认 Web UI 密码为 070827，首次登录后应修改；服务绑定 IPv4/IPv6 时请用防火墙或 HTTPS 反向代理限制访问。
- 脚本以 autotaskd 的系统用户权限运行，任务参数会明文存入 SQLite；只运行可信脚本，机密应从受保护的配置文件或环境变量读取。
