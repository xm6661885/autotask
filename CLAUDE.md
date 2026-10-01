# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AutoTask 是用于管理重复任务和一次性后台任务的本地自动化服务，提供 CLI 和 Flask Web UI。
应用主体是 Python 3.9+ 包 `autotask/`，使用 SQLite 保存任务与运行记录；仓库根目录的 `scripts/` 是实际运行的任务脚本。

## 常用命令

以下路径均相对仓库根目录；测试命令需在 `autotask/` 目录执行。

### 安装与启动

```bash
# 仓库根目录：创建/更新 .venv、editable 安装、设置用户级 CLI 与 systemd 服务
./autotask/install-user.sh

# 仓库根目录：安装后检查配置路径、服务和时区
.venv/bin/autotask status

# 仓库根目录：前台启动服务（使用项目 config.yaml）
AUTOTASK_CONFIG="$PWD/config.yaml" .venv/bin/autotaskd
```

`install-user.sh` 会启动或重启用户级 systemd 服务；只想运行测试时，可在 `autotask/` 用 `python3 -m pip install -e .` 安装包依赖，无需安装服务。

### 测试

测试使用 Python 标准库 `unittest`，没有 pytest 配置。

```bash
# autotask/：全部测试
python3 -m unittest discover -s tests

# autotask/：单个测试文件
python3 -m unittest discover -s tests -p 'test_groups.py'

# autotask/：单个用例（替换模块、类和方法名）
python3 tests/test_groups.py GroupTests.test_v3_database_migrates_existing_tasks_to_ungrouped
```

`autotask/tests/` 当前包含 `test_edit.py`、`test_groups.py` 和 `test_one_off.py`。

### 构建、检查与迁移

仓库没有定义 lint、格式化、类型检查或独立构建命令，也没有数据库迁移 CLI。`autotask/pyproject.toml` 定义 setuptools 构建后端；数据库 schema 迁移由 `DB` 初始化时自动执行，随 `autotaskd` 启动发生。修改 shell 脚本时，README 给出的语法检查命令为：

```bash
# 仓库根目录
bash -n scripts/cron/<任务目录>/<脚本名>.sh
```

## 高层架构

- `autotask/autotask/cli.py` 提供 `autotask` 命令，`daemon.py` 是 `autotaskd` 入口。守护进程读取配置、初始化 SQLite、恢复中断运行，然后启动调度器和 Flask 应用。
- `scheduler.py` 周期扫描任务：cron、interval 和一次性计划任务由调度器触发；manual 任务由 CLI/UI 请求触发，webhook 任务由 Web API 触发。一次性任务通过数据库事务领取，避免调度器与“立即执行”同时重复启动。
- `runner.py` 在独立子进程中运行脚本，把 stdout/stderr 合并写入每次运行的日志，并更新运行记录与任务状态。子进程工作目录是入口脚本所在任务目录。
- `db.py` 管理 SQLite schema、版本迁移、任务/分组/运行记录；`webapp.py` 提供登录保护的任务管理 UI 和 webhook endpoint。UI 与 CLI 共用调度器和数据库层。
- 任务定义引用 `scripts_dir` 下的相对脚本路径。重复任务脚本放在 `scripts/cron/<任务名>/`，一次性任务放在 `scripts/once/<任务名>/`；任务目录可包含状态、输入和辅助文件。

## 仓库约定与易踩的坑

- 主要应用包和测试在 `autotask/`，而仓库级安装脚本、配置、数据和自动化任务在根目录。不要把根目录任务脚本误当作包源码。
- 注册时保存相对 `scripts_dir` 的入口路径；CLI 和 Web 表单校验入口脚本位于对应类型及任务名目录下。注册后不要移动入口文件，否则数据库中的路径会失效。
- 脚本运行时 cwd 是该任务自己的目录。任务脚本的状态文件、prompt 和辅助文件应以脚本自身目录或相对路径定位；不要依赖旧的 `scripts/<文件>` 根路径。
- 服务配置由 `AUTOTASK_CONFIG` 覆盖；否则查找 `/etc/autotask/config.yaml`、`~/.config/autotask/config.yaml`。无配置时会创建用户级默认配置。用户级安装脚本显式让 CLI 和服务共用仓库根目录的 `config.yaml`。
- `scripts_dir` 和 `data_dir` 以当前配置为准。SQLite 数据库为 `<data_dir>/autotask.db`，运行日志在 `<data_dir>/logs/`。数据库迁移随应用启动自动执行，勿手工改库版本绕过迁移。
- cron 表达式和一次性指定时间按运行 `autotaskd` 的主机本地时区解释；数据库时间戳保存为 Unix 秒。调度器默认每 2 秒轮询。
- Webhook 仅用于重复任务，通过 HTTP POST 把 JSON 请求体传给脚本 stdin；请求需提供配置中的 `webhook_secret`。webhook endpoint 不依赖 Web UI 登录态。
- 任务脚本以 `autotaskd` 服务用户权限运行。脚本可调用外部命令或服务；测试和调试时应留意其外部副作用。README 明确提示，除非用户要求，不要为测试而启动会产生外部副作用的任务。
- Web 服务默认端口为 8990；用户级安装配置绑定 `127.0.0.1`，其他安装方式应以当前 config 为准。
- `scripts/cron/` 与 `scripts/once/` 包含运行中任务及其状态文件；其中 `BrowserData`、`browser-profile` 等目录是持久化浏览器数据。不要把这类运行数据当生成后可随意清理的构建产物。
- README 说明任务删除仅删除数据库任务定义和运行记录，不会删除任务目录或磁盘日志。一次性任务完成、失败或取消后保留历史状态，可再次排队执行。

