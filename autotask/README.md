# AutoTask

自动化脚本运行工具。它把需要反复执行的工作和只做一次的后台长任务分开管理：用 CLI 或网页创建、调度、观察状态和查看完整日志；后台守护进程常驻，支持 systemd 开机自启。

## 功能一览

- 两类任务：
  - 重复任务：手动、cron、固定间隔或 webhook，可反复触发。
  - 一次性任务：在一个本地时间点运行一次，或创建后立即放到后台执行；适合耗时任务。
- 脚本按任务类型和任务名隔离：
  - 重复任务：scripts/cron/<任务名>/
  - 一次性任务：scripts/once/<任务名>/
- 每个任务都有独立目录，可放入口脚本、状态文件、prompt、临时输入和辅助模块。
- CLI autotask：创建脚本骨架、注册任务、立即执行、查看运行记录和日志、查看系统状态。
- Web UI：首页同页分为“重复任务”和“一次性任务”两个 Tab，局部刷新常用操作，不必在多个列表页间反复跳转。
- 任务描述：创建、注册和网页编辑都可填写说明；列表中展示，便于区别相似脚本。
- 任务分组：新建、重命名、删除分组，把任务移入或移出；所有任务和未分组均可单独查看。分组不改变脚本位置或调度方式。
- 数据存储：SQLite 保存任务定义和运行记录；每次运行生成独立日志文件。
- systemd 服务：autotask.service，开机自启，异常退出自动重启。

## 任务模型

| 类型 | 数据标识 | 用途 | 触发方式 | 终态 |
| --- | --- | --- | --- | --- |
| 重复任务 | recurring | 日报、轮询、webhook、可多次手动执行的工作 | manual、cron、interval、webhook | 持续可用 |
| 一次性任务 | one_off | 预约执行或后台长任务 | 指定时间或立即执行，内部 schedule_type 为 once | completed、failed 或 cancelled |

一次性任务从 pending 状态被原子领取后才启动，同一轮不会被执行两次。运行完成后自动停止调度，但任务条目、运行历史和日志会保留，方便确认结果和排查失败。完成、失败或取消后，可在网页点“再次执行”，或使用 `autotask run <任务名或ID>` 创建一轮新的立即执行；历史记录会保留。

原有 manual 任务会迁移为重复任务，因为它们本来就可以被手动运行多次。

## 脚本目录

配置中的 scripts_dir 是脚本根目录，默认值通常是 ~/Automations/scripts；请以 autotask status 的输出为准。

~~~text
scripts/
├── cron/
│   └── weather_report/
│       ├── weather_report.sh
│       ├── state.json
│       └── helper.py
└── once/
    └── export_september/
        ├── export_september.py
        └── input.csv
~~~

运行脚本时，当前工作目录就是该任务自己的文件夹，而不是 scripts 根目录。因此：

- Shell 脚本可用 TASK_DIR="$(cd -- "$(dirname -- "$0")" && pwd)" 取得任务目录。
- Python 脚本可用 Path(__file__).resolve().parent 取得任务目录。
- 将状态文件、prompt、辅助脚本写为相对任务目录的路径，不能写死旧的 scripts/<文件> 路径。
- 注册后不要手工移动入口脚本；任务数据库中保存了相对路径。

### 升级与现有脚本迁移

本次升级会先复制已注册的旧任务到 scripts/cron/<任务名>/，再在停服切换时同步更新数据库路径；重复使用同一源脚本但拥有不同状态的任务会保留独立副本。旧任务的 description 保持为空，可在网页编辑或后续注册时补充。

迁移完成后，检查每个任务目录中的脚本是否仍然引用旧的 scripts 根目录，并改为根据自身位置或相对路径定位文件。旧根入口和关联文件会在切换验证后删除，以保留短暂回退窗口。BrowserData、.playwright-cli、__pycache__ 等不属于任务入口的目录会原样保留，不会被迁移或删除。

## 安装

### 用户级安装（推荐用于当前工作目录）

在项目根目录运行一次，升级时重复运行同一命令：

~~~bash
./autotask/install-user.sh
~~~

它在项目根目录维护一份 `.venv`，用 editable 模式指向 `autotask/` 源码；CLI、用户级 systemd 服务和 agent skill 共用同一套源码。项目根目录的 `config.yaml` 是唯一配置，CLI 包装脚本会显式指定它。已有不同内容的用户配置不会被覆盖，安装脚本会提示先合并。已有用户级 systemd 服务文件会保留。

### 系统级安装

~~~bash
cd autotask
sudo ./install.sh
~~~

默认安装会：

1. 使用运行 sudo 的用户作为服务运行账号。
2. 将脚本根目录设为该用户家目录下的 Automations/scripts。
3. 将数据目录设为 /var/lib/autotask。
4. 将 Web UI 监听在端口 8990，并同时绑定 IPv4 和 IPv6。
5. 生成 session 密钥；Web UI 初始密码为 070827。
6. 安装并启动 autotask.service。

可用环境变量自定义安装参数：

~~~bash
AUTOTASK_USER=deploy \
AUTOTASK_SCRIPTS_DIR=/srv/scripts \
AUTOTASK_DATA_DIR=/var/lib/autotask \
AUTOTASK_PORT=9000 \
sudo -E ./install.sh
~~~

## Web UI

访问 http://<服务器IP>:8990 或 http://[服务器IPv6]:8990 后登录。

- 首页的“重复任务”和“一次性任务”Tab 分开显示两类任务，同时保留在一个页面。
- Tab 上方可按“所有任务”“未分组”或自建分组筛选；可创建、重命名和删除分组。每张任务卡可切换分组。删除分组只会把任务移至未分组。
- 每个 Tab 都有对应的新建入口，会预选正确任务类型。
- 一次性表单提供“立即执行”和“指定时间”两种触发方式；指定时间使用主机本地日期时间，仍在等待的定时任务可提前立即执行或取消。
- 重复任务表单才显示 manual、cron、interval、webhook 调度选项。
- 描述字段会在任务列表显示。
- 启用/停用、立即执行、停止、取消和删除会就地刷新；编辑页和运行记录页仍独立打开。
- 已完成、失败或取消的一次性任务保留运行记录与删除操作，并可“再次执行”；不能再编辑。
- 脚本选择器按 scripts/cron/ 和 scripts/once/ 分组。
- 每次运行都可查看退出码、开始/结束时间和完整标准输出/错误日志。

首次登录后请在“设置”中修改初始密码。

## CLI 快速开始

先确认实际路径、服务和时区：

~~~bash
autotask status
~~~

分组管理：

~~~bash
autotask groups list                 # 也支持 --json
autotask groups create 工作
autotask groups rename 工作 项目工作
autotask groups move daily_backup 项目工作
autotask groups ungroup daily_backup
autotask groups delete 项目工作       # 任务回到未分组
autotask list --group 未分组         # 或分组名称、ID、所有任务
~~~

### 创建重复任务

~~~bash
# 每天 02:00 执行
autotask create daily_backup --type shell --description "备份数据库" \
  --register --kind recurring --schedule-type cron --schedule-value "0 2 * * *"

# 每 3600 秒执行一次
autotask create check_disk --type python --description "检查磁盘空间" \
  --register --kind recurring --schedule-type interval --schedule-value 3600

# 可以反复手动执行
autotask create repair_cache --type shell --description "修复缓存" \
  --register --kind recurring --schedule-type manual
~~~

重复任务默认类型是 recurring。调度参数含义：

- manual：仅手动运行。
- cron：标准 5 段表达式，按服务进程的系统本地时区计算。
- interval：数字秒数，从上次运行完成时刻开始累计。
- webhook：只通过 HTTP POST 触发，不参与定时扫描。

### 创建一次性任务

~~~bash
# 只在一个本地时间点执行一次
autotask create monthly_export --type python --description "导出本月数据" \
  --register --kind one-off --once-at "2026-09-21 09:30"

# 立即交给后台执行一次，适合长任务
autotask create archive_media --type shell --description "归档媒体库" \
  --register --kind one-off --run-once
~~~

--once-at 与 --run-once 二选一。一次性任务不能同时设置 cron、interval 或 webhook。--run-once 返回后任务仍由后台运行；通过 autotask logs <任务名> 或网页查看状态，而不是让终端一直等待。

### 注册已有脚本

将脚本放进目标任务目录后，以相对 scripts 根目录的路径注册：

~~~bash
# scripts/cron/cleanup/cleanup.sh
autotask add cleanup cron/cleanup/cleanup.sh --kind recurring \
  --description "清理历史日志" --schedule-type cron --schedule-value "0 */6 * * *"

# scripts/once/import_once/import_once.py
autotask add import_once once/import_once/import_once.py --kind one-off \
  --description "导入供应商文件" --once-at "2026-09-22 10:00"

# 已有脚本立即后台执行一次
autotask add reindex_once once/reindex_once/reindex_once.sh --kind one-off \
  --description "重建搜索索引" --run-once
~~~

### 常用管理命令

~~~bash
autotask list
autotask list --json
autotask enable <任务名或ID>
autotask disable <任务名或ID>
autotask cancel <任务名或ID>       # 取消尚未开始的一次性任务
autotask remove <任务名或ID>

# 手动执行重复任务
autotask run daily_backup
autotask run daily_backup --wait
autotask run daily_backup --wait -- --target /mnt/backup --compress

# 查看历史与完整日志
autotask logs daily_backup --count 10
autotask logs archive_media --latest
~~~

删除任务会删除数据库里的任务定义和运行记录，但不会删除任务目录或磁盘上的日志文件。等待执行的一次性任务可用 autotask cancel 取消；完成、失败或取消后可用 `autotask run <任务名或ID>` 再次执行，它会原子地创建新的等待轮次，不能附带额外参数或 --force。正在运行的重复任务默认不会再次启动；run --force 会并发执行，只应在脚本确认可重入时使用。

## Webhook 任务

Webhook 仅限重复任务。守护进程接收 HTTP POST 后将 JSON 请求体通过 stdin 传给脚本：

~~~bash
autotask add wechat_print cron/wechat_print/wechat_webhook_receiver.py \
  --kind recurring --description "处理微信回调" --schedule-type webhook
~~~

请求必须带配置文件中的 webhook_secret：

~~~bash
curl -X POST http://127.0.0.1:8990/api/webhook/wechat_print \
  -H "X-AutoTask-Webhook-Secret: <webhook_secret>" \
  -H "Content-Type: application/json" \
  -d '{"type":"new_message","data":{"content_text":"你好"}}'
~~~

Webhook endpoint 不使用 Web UI 登录态。请限制端口访问范围；同一任务正在运行时，新的 webhook 会被拒绝而不会并发启动。

## 调度、日志和时区

- cron 与一次性指定时间均按运行 autotaskd 的系统本地时区解释。
- interval 不受时区影响，按 Unix 时间累计。
- 数据库里的创建、开始、结束与指定执行时间保存为 Unix 秒；CLI 和网页转换为主机本地时间展示。
- 调度器默认每 2 秒扫描一次，时间允许数秒误差。
- 单个任务的输出和错误都写入数据目录 logs/ 下的独立文件；使用网页或 autotask logs 查看。
- 服务日志可用 journalctl -u autotask -f 观察。

## 运行 Codex 代理任务

需要长时间运行且步骤明确的 Codex 工作，适合建立为一次性任务。脚本中用绝对工作目录，并把 prompt 用单引号 heredoc 交给 codex exec：

~~~bash
#!/usr/bin/env bash
set -euo pipefail

exec codex exec \
  --sandbox danger-full-access \
  --skip-git-repo-check \
  -C /absolute/path/to/workspace <<'PROMPT'
这是一次性后台代理任务。

说明目标、输入来源、允许的外部副作用、失败处理和通知方式；
任何发送、付款、下单等动作都要有明确授权。
PROMPT
~~~

使用 exec 使脚本退出码直接成为 AutoTask 的运行结果。后台代理没有对话式前台；需要报告完成、失败、登录阻塞或人工决策时，在 prompt 中要求调用 notify（默认带 `-C telegram_push` 只推 Telegram；不带 `--channel` 会推送到全部渠道，含 QQ 群）。不要把 Cookie、密码、验证码、支付 token 或其他秘密写到脚本、参数或日志里。

## 安全与运维

- 初始密码 070827 只用于首次安装，请立即修改。
- Web UI 可能对 IPv4/IPv6 网络接口开放；使用防火墙限制 8990 端口，或通过 HTTPS 反向代理暴露。
- 脚本以 autotaskd 服务用户的权限执行，只注册可信脚本。
- 任务参数会明文保存到 SQLite；机密应从受保护的配置文件或环境变量读取。
- 修改脚本后，先用 bash -n <脚本绝对路径> 检查 shell 语法。除非用户明确要求，不要为测试而启动有外部副作用的任务。

~~~bash
sudo systemctl status autotask
sudo systemctl restart autotask
sudo systemctl stop autotask
journalctl -u autotask -f
~~~

## 卸载

~~~bash
sudo systemctl disable --now autotask
sudo rm -f /etc/systemd/system/autotask.service
sudo rm -f /usr/local/bin/autotask /usr/local/bin/autotaskd
sudo rm -rf /opt/autotask
# 以下两步会删除任务数据和配置，谨慎操作
sudo rm -rf /var/lib/autotask
sudo rm -rf /etc/autotask
~~~

脚本根目录默认不会被卸载流程删除，任务目录和脚本由用户自行管理。
