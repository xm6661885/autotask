# AutoTask

**English** | [简体中文](README.zh-CN.md)

AutoTask is a local automation service that manages **recurring tasks** and **one-off background tasks** (Python / Shell scripts). It ships with a CLI (`autotask`), a daemon (`autotaskd`) and a Flask Web UI. It has a small footprint (SQLite + a polling scheduler) and runs fine under systemd.

## Features

- **Two task kinds**
  - *Recurring*: manual, cron, fixed interval, or webhook; can be triggered again and again.
  - *One-off*: run once at a given local time, or start immediately in the background (good for long jobs).
- **One directory per task**: `scripts/cron/<name>/` or `scripts/once/<name>/`. The script runs with that directory as its working directory, so state files, prompts and helpers live next to it.
- **CLI and Web UI** share the same database and scheduler: create script skeletons, register existing scripts, run now, edit, enable/disable, cancel, group, and read full run logs.
- **SQLite storage**: task definitions and run records are stored in `<data_dir>/autotask.db`; every run gets its own log file. Schema migrations run automatically at startup.
- **Atomic one-off claiming**: a pending one-off task is claimed in a DB transaction, so the scheduler and "run now" can never start it twice.
- **systemd integration**: user-level or system-level service with auto-restart.
- **Agent skill**: a ready-made skill (`skill/autotask/SKILL.md`) that lets AI coding agents such as Claude Code drive the CLI for you.

## Requirements

- Python 3.9+
- Linux with systemd (only needed for the service; you can also run `autotaskd` in the foreground)
- Dependencies (Flask, croniter, ...) are installed automatically by pip

## Installation

```bash
git clone https://github.com/XMWML/autotask.git
cd autotask
```

### User-level install (recommended)

Run once from the repository root; re-run the same command to upgrade:

```bash
./autotask/install-user.sh
```

It will:

1. create/update `.venv` and install `autotask/` in editable mode;
2. create `config.yaml` in the repo root if missing (bind `127.0.0.1`, port `8990`, mode `600`);
3. install `~/.local/bin/autotask` and `~/.local/bin/autotaskd` wrappers that always use that config;
4. link the agent skill to `~/.agents/skills/autotask/SKILL.md`;
5. create, enable and (re)start the user-level `autotask.service`.

Make sure `~/.local/bin` is on your `PATH`, then verify:

```bash
autotask status      # config path, scripts/data dirs, service state, timezone
```

### System-wide install

```bash
cd autotask
sudo ./install.sh
```

Defaults: service user = the user running `sudo`, scripts dir = `~/Automations/scripts`, data dir = `/var/lib/autotask`, port `8990` on IPv4+IPv6, a generated session secret and webhook secret, and a default Web UI password that you **must change after the first login** (Settings page). Customize with environment variables:

```bash
AUTOTASK_USER=deploy \
AUTOTASK_SCRIPTS_DIR=/srv/scripts \
AUTOTASK_DATA_DIR=/var/lib/autotask \
AUTOTASK_PORT=9000 \
sudo -E ./install.sh
```

### Foreground run (no service)

```bash
pip install -e ./autotask
cp config.example.yaml config.yaml    # then edit paths and fill in the secrets
AUTOTASK_CONFIG="$PWD/config.yaml" autotaskd
```

## Configuration

The config file is located via, in order: `$AUTOTASK_CONFIG`, `/etc/autotask/config.yaml`, `~/.config/autotask/config.yaml` (a default one is created if none exists). See [`config.example.yaml`](config.example.yaml):

| Key | Meaning |
| --- | --- |
| `bind_host`, `port` | Web UI listen address (default `127.0.0.1:8990`) |
| `scripts_dir` | Root directory of task scripts (`cron/` and `once/` underneath) |
| `data_dir` | Holds `autotask.db` and `logs/` |
| `python_bin`, `shell_bin` | Interpreters used to run `.py` / `.sh` entry scripts |
| `poll_interval_sec` | Scheduler polling interval (default 2 s) |
| `password_hash` | Werkzeug hash of the Web UI password |
| `secret_key` | Flask session secret |
| `webhook_secret` | Shared secret required by the webhook endpoint |

## Task model and directory layout

| Kind | Data id | Typical use | Triggers | End states |
| --- | --- | --- | --- | --- |
| Recurring | `recurring` | reports, polling, webhooks, re-runnable jobs | manual, cron, interval, webhook | stays available |
| One-off | `one_off` | scheduled or long-running background jobs | at a local time, or run immediately | `completed`, `failed`, `cancelled` |

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

- `.py` entry scripts run with `python_bin`, `.sh` with `shell_bin`; other executables also work.
- **The working directory is the task's own directory.** Locate sibling files relatively, or from the script itself: `TASK_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"` (shell) or `Path(__file__).resolve().parent` (Python).
- Task names are globally unique; the name is also the directory name.
- Task definitions store the entry path relative to `scripts_dir`. Don't move the entry file after registering; use `autotask edit <task> --script ...` if you must.
- A finished/failed/cancelled one-off task keeps its history and can be queued again with `autotask run <task>`.

## CLI usage

Always start with `autotask status` and trust its output over assumptions about paths.

### Create recurring tasks

`create` generates a script skeleton in the task directory; add `--register` to put it in the scheduler.

```bash
# every day at 02:00
autotask create daily_backup --type shell --description "Back up the database" \
  --register --kind recurring --schedule-type cron --schedule-value "0 2 * * *"

# every 3600 seconds
autotask create check_disk --type python --description "Check disk space" \
  --register --kind recurring --schedule-type interval --schedule-value 3600

# manual only (can be run any number of times)
autotask create repair_cache --type shell --description "Repair cache" \
  --register --kind recurring --schedule-type manual
```

Schedule types: `manual` (CLI/UI only), `cron` (standard 5-field expression, host local time), `interval` (seconds, counted from the end of the previous run), `webhook` (HTTP POST only). Other flags: `--args '["--verbose"]'` (default arguments as a JSON array), `--name`, `--disabled`, `--force` (overwrite an existing skeleton).

### Create one-off tasks

```bash
# run once at a local time (must be in the future)
autotask create monthly_export --type python --description "Export this month" \
  --register --kind one-off --once-at "2026-09-21 09:30"

# start now in the background and return immediately
autotask create archive_media --type shell --description "Archive media library" \
  --register --kind one-off --run-once
```

`--once-at` and `--run-once` are mutually exclusive, and one-off tasks cannot use cron/interval/webhook. Don't simulate one-off jobs with a temporary cron.

### Register existing scripts

Put the entry script and its dependencies into the task directory first, then register it using a path relative to `scripts_dir`:

```bash
autotask add cleanup cron/cleanup/cleanup.sh --kind recurring \
  --description "Clean old logs" --schedule-type cron --schedule-value "0 */6 * * *"

autotask add import_once once/import_once/import_once.py --kind one-off \
  --description "Import vendor files" --once-at "2026-09-22 10:00"

autotask add reindex_once once/reindex_once/reindex_once.sh --kind one-off \
  --description "Rebuild search index" --run-once
```

### Run, inspect, manage

```bash
autotask list [--json] [--group <name|id|未分组|所有任务>]
autotask run daily_backup                      # trigger in the background
autotask run daily_backup --wait               # wait and print the log
autotask run daily_backup --wait -- --target /mnt/backup --compress   # extra script args
autotask logs daily_backup --count 10          # last 10 runs
autotask logs archive_media --latest           # full log of the latest run
autotask enable|disable <task>
autotask cancel <task>                         # cancel a pending one-off task
autotask remove <task>                         # delete definition + run records (not the directory or log files)
```

A running recurring task is not started again by default; `run --force` starts a concurrent run, so use it only if the script is re-entrant. Extra arguments and `--force` are not supported for one-off tasks.

### Edit in place

`edit` keeps the task id, group and history (don't `remove` + `add` to change settings). Only the options you pass are changed:

```bash
autotask edit <task> -d "New description"          # empty string clears it
autotask edit <task> --args '["--verbose"]'        # replace default args
autotask edit <task> --clear-args
autotask edit <task> --schedule-type cron --schedule-value "30 6 * * *"
autotask edit <task> --schedule-value 1800         # keep the type, change the value
autotask edit <task> --schedule-type webhook
autotask edit <task> --script cron/<name>/new_entry.py
autotask edit <one-off task> --once-at "2026-10-01 09:00"   # pending one-off tasks only
```

Name and kind can't be changed after creation. Changes apply on the scheduler's next tick; no service restart is needed.

### Groups

Groups only affect how tasks are organized; they don't change the kind, schedule or script path. Deleting a group moves its tasks back to "ungrouped".

```bash
autotask groups list [--json]
autotask groups create Work
autotask groups rename Work Projects
autotask groups move daily_backup Projects
autotask groups ungroup daily_backup
autotask groups delete Projects
```

## Web UI

Open `http://127.0.0.1:8990` (or whatever `bind_host`/`port` you configured) and log in.

- The home page has two tabs, **Recurring** and **One-off**, each with its own "new task" entry that preselects the right kind.
- Filter by *All tasks*, *Ungrouped* or a custom group; create, rename and delete groups, and move tasks from the task card.
- One-off form: "run now" or "run at a time" (local date-time). Pending timed tasks can be started early or cancelled; finished ones offer "run again".
- Recurring form: manual, cron, interval or webhook.
- Enable/disable, run, stop, cancel and delete refresh in place; the edit and run-history pages open separately.
- Each run shows exit code, start/end time and the full stdout/stderr log.

## Webhook tasks

Webhooks are for recurring tasks only. The daemon passes the JSON request body to the script on **stdin**.

```bash
autotask add wechat_print cron/wechat_print/receiver.py \
  --kind recurring --description "Handle callbacks" --schedule-type webhook

curl -X POST http://127.0.0.1:8990/api/webhook/wechat_print \
  -H "X-AutoTask-Webhook-Secret: <webhook_secret>" \
  -H "Content-Type: application/json" \
  -d '{"hello":"world"}'
```

The endpoint does not use the Web UI login; it only checks `webhook_secret`. If the task is already running, a new webhook is rejected instead of running concurrently.

## Scheduling, logs and time zones

- cron expressions and `--once-at` are interpreted in the **host local time zone** of the `autotaskd` process; interval is time-zone independent.
- Timestamps are stored as Unix seconds and converted to local time for display.
- The scheduler polls every 2 s by default, so expect a few seconds of jitter.
- Every run writes stdout+stderr to its own file under `<data_dir>/logs/`. Service logs: `journalctl --user -u autotask -f` (user install) or `journalctl -u autotask -f` (system install).

## Using AutoTask from an AI agent (the skill)

[`skill/autotask/SKILL.md`](skill/autotask/SKILL.md) is an agent skill (name `autotask`) that teaches an AI coding agent how to pick the task kind, create/register/edit tasks, read logs and avoid common pitfalls. Once installed, you can simply say things like *"run a backup script every day at 2am"* or *"start this export in the background and tell me when it finishes"*, and the agent will use the `autotask` CLI.

Install it:

- **Automatically**: `./autotask/install-user.sh` symlinks it to `~/.agents/skills/autotask/SKILL.md`, so edits in the repo are picked up immediately.
- **Claude Code**: link or copy it into the skills directory:
  ```bash
  mkdir -p ~/.claude/skills/autotask
  ln -sfn "$PWD/skill/autotask/SKILL.md" ~/.claude/skills/autotask/SKILL.md
  ```
- Other agents that read `SKILL.md` files: place it wherever that tool looks for skills.

The skill requires the `autotask` CLI on `PATH` (see Installation). Note that the skill text is written in Chinese.

## Running agent jobs inside a task

Long, well-specified agent work fits a one-off shell task: AutoTask manages the background lifecycle and the log, and `exec` makes the agent's exit code the run result.

```bash
#!/usr/bin/env bash
set -euo pipefail
exec codex exec --sandbox danger-full-access --skip-git-repo-check \
  -C /absolute/path/to/workspace <<'PROMPT'
Describe the goal, inputs, allowed side effects, failure handling and how to notify.
PROMPT
```

Never put passwords, cookies, verification codes or payment tokens into scripts, prompts, task arguments or logs.

## Security notes

- Change the default Web UI password after the first login. Keep `config.yaml` private (it contains the password hash, session secret and webhook secret); it is git-ignored in this repository.
- The Web UI binds to `127.0.0.1` in the user-level install. If you expose it, put it behind a firewall or an HTTPS reverse proxy.
- Scripts run with the privileges of the `autotaskd` user and may have external side effects: only register scripts you trust.
- Task arguments are stored in SQLite in plain text; read secrets from protected files or environment variables instead.
- Check shell scripts with `bash -n <script>` before registering them.

## Development

```bash
cd autotask
python3 -m pip install -e .
python3 -m unittest discover -s tests                                   # all tests
python3 -m unittest discover -s tests -p 'test_groups.py'               # one file
python3 tests/test_groups.py GroupTests.test_v3_database_migrates_existing_tasks_to_ungrouped
```

Source layout (`autotask/autotask/`): `cli.py` (CLI), `daemon.py` (`autotaskd` entry), `scheduler.py` (cron/interval/one-off scheduling), `runner.py` (subprocess runner and logs), `db.py` (SQLite schema, migrations, tasks/groups/runs), `webapp.py` (Web UI and webhook endpoint).

## Uninstall

```bash
# user-level install
systemctl --user disable --now autotask
rm -f ~/.config/systemd/user/autotask.service ~/.local/bin/autotask ~/.local/bin/autotaskd

# system-wide install
sudo systemctl disable --now autotask
sudo rm -f /etc/systemd/system/autotask.service /usr/local/bin/autotask /usr/local/bin/autotaskd
sudo rm -rf /opt/autotask
# the next two delete your data and config
sudo rm -rf /var/lib/autotask /etc/autotask
```

The scripts directory is never removed by uninstalling.
