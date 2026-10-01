import os
import json
import time
import datetime as datetime
import hmac
import hashlib

MAX_WEBHOOK_BODY = 1024 * 1024
WEBHOOK_SECRET_HEADER = "X-AutoTask-Webhook-Secret"
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session, render_template,
    flash, send_file, abort, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash

from . import config as cfgmod
from .db import DB
from .scheduler import Scheduler, compute_next_run
from .runner import ScriptError, resolve_script
from .timezone import system_timezone, system_timezone_name


def _task_folder_name(name):
    name = (name or "").strip()
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise ValueError("任务名称不能为空，且不能含有路径分隔符")
    return name


def _script_root_for_kind(task_kind):
    return "once" if task_kind == "one_off" else "cron"


def _validate_task_script_layout(scripts_dir, script, task_kind, task_name):
    """Resolve the selected script and enforce the per-task folder contract."""
    script_path = resolve_script(scripts_dir, script)
    expected_dir = os.path.realpath(os.path.join(
        scripts_dir, _script_root_for_kind(task_kind), _task_folder_name(task_name)
    ))
    try:
        inside = os.path.commonpath([expected_dir, script_path]) == expected_dir
    except ValueError:
        inside = False
    if not inside:
        root = _script_root_for_kind(task_kind)
        raise ScriptError(
            f"脚本必须位于 scripts/{root}/{_task_folder_name(task_name)}/ 中"
        )
    return script_path


def _parse_task_args(raw):
    try:
        value = json.loads(raw) if raw else []
    except json.JSONDecodeError as e:
        raise ValueError(f"参数必须是 JSON 数组: {e.msg}") from e
    if not isinstance(value, list):
        raise ValueError("参数必须是 JSON 数组，例如 [\"--foo\", \"bar\"]")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("参数 JSON 数组中的每一项都必须是字符串")
    return value


def _parse_local_one_off_time(raw):
    try:
        value = datetime.datetime.fromisoformat((raw or "").strip())
    except ValueError as e:
        raise ValueError("执行时间格式无效，请选择一个未来的本地时间") from e
    if value.tzinfo is None:
        value = value.replace(tzinfo=system_timezone())
    else:
        value = value.astimezone(system_timezone())
    timestamp = value.timestamp()
    if timestamp <= time.time():
        raise ValueError("一次性执行时间必须晚于当前时间")
    return timestamp


def _one_off_state_label(state):
    return {
        "pending": "等待执行",
        "running": "运行中",
        "completed": "已完成",
        "failed": "执行失败",
        "cancelled": "已取消",
    }.get(state, "未知")


def create_app(cfg, cfg_path, db: DB, scheduler: Scheduler):
    app = Flask(__name__)
    app.secret_key = cfg["secret_key"]
    app.permanent_session_lifetime = 60 * 60 * 24 * 30

    # Version the UI assets by content. Static URLs are immutable, so include
    # both CSS and JavaScript to ensure either change gets a fresh URL.
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    @app.context_processor
    def inject_asset_version():
        try:
            digest = hashlib.sha256()
            for filename in ("app.css", "i18n.js"):
                with open(os.path.join(static_dir, filename), "rb") as asset_file:
                    digest.update(filename.encode("utf-8"))
                    digest.update(asset_file.read())
            version = digest.hexdigest()[:12]
        except OSError:
            version = "1"
        return {"asset_version": version}

    @app.context_processor
    def inject_ui_context():
        return {"system_timezone": system_timezone_name()}

    @app.after_request
    def refresh_browser_cache(response):
        if request.endpoint == "static":
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # Revalidate HTML and JSON so Safari does not keep an older UI shell.
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.template_filter("fmt_ts")
    def fmt_ts(ts):
        if not ts:
            return "-"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

    def login_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("authed"):
                return redirect(url_for("login", next=request.path))
            return fn(*args, **kwargs)
        return wrapper

    def task_form_data(existing=None):
        """Validate a create/edit form and normalize it into DB fields."""
        name = _task_folder_name(request.form.get("name", ""))
        description = request.form.get("description", "").strip()
        if len(description) > 1000:
            raise ValueError("任务说明不能超过 1000 个字符")
        task_kind = request.form.get("task_kind", "recurring")
        if task_kind not in ("recurring", "one_off"):
            raise ValueError("无效的任务类型")
        if existing:
            old_kind = existing.get("task_kind", "recurring")
            if task_kind != old_kind:
                raise ValueError("任务类型创建后不能修改；请新建另一类任务")
            if name != existing["name"]:
                raise ValueError("任务名称同时决定脚本目录，创建后不能修改")
            if old_kind == "one_off" and existing.get("one_off_state") != "pending":
                raise ValueError(
                    f"一次性任务当前为“{_one_off_state_label(existing.get('one_off_state'))}”，不能再编辑"
                )

        script = request.form.get("script", "").strip()
        if not script:
            raise ValueError("名称和脚本不能为空")
        _validate_task_script_layout(cfg["scripts_dir"], script, task_kind, name)
        args = _parse_task_args(request.form.get("args", "").strip())

        if task_kind == "recurring":
            schedule_type = request.form.get("schedule_type", "manual")
            if schedule_type not in ("manual", "cron", "interval", "webhook"):
                raise ValueError("无效的调度方式")
            schedule_value = request.form.get("schedule_value", "").strip() or None
            if schedule_type == "webhook":
                schedule_value = None
            if schedule_type in ("cron", "interval") and not schedule_value:
                raise ValueError(f"{schedule_type} 任务需要填写调度值")
            if schedule_type == "interval":
                try:
                    if float(schedule_value) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    raise ValueError("固定间隔必须是大于 0 的秒数")
            if schedule_type == "cron":
                test_task = {
                    "name": name,
                    "task_kind": "recurring",
                    "schedule_type": "cron",
                    "schedule_value": schedule_value,
                }
                if compute_next_run(test_task) is None:
                    raise ValueError("Cron 表达式无效")
            return {
                "name": name,
                "description": description,
                "script": script,
                "args": args,
                "task_kind": "recurring",
                "schedule_type": schedule_type,
                "schedule_value": schedule_value,
                "enabled": request.form.get("enabled") == "on",
                "scheduled_at": None,
                "one_off_trigger": None,
                "one_off_state": None,
            }

        trigger = request.form.get("one_off_trigger", "immediate")
        if trigger not in ("immediate", "scheduled"):
            raise ValueError("无效的一次性执行方式")
        scheduled_at = (
            _parse_local_one_off_time(request.form.get("scheduled_at_local"))
            if trigger == "scheduled" else time.time()
        )
        return {
            "name": name,
            "description": description,
            "script": script,
            "args": args,
            "task_kind": "one_off",
            "schedule_type": "once",
            "schedule_value": None,
            "enabled": True,
            "scheduled_at": scheduled_at,
            "one_off_trigger": trigger,
            "one_off_state": "pending",
        }

    def wants_json():
        return (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.best == "application/json"
        )

    def action_response(message, category="ok", status=200, **payload):
        """Use JSON for in-place UI controls and redirect for normal forms."""
        if wants_json():
            return jsonify({"success": category == "ok", "message": message, **payload}), status
        flash(message, category)
        return redirect(url_for("index"))

    def start_one_off(task_id):
        """Claim a pending one-off, tolerating the scheduler winning a race."""
        run_id = scheduler.run_one_off_now(db.get_task(task_id))
        if run_id is not None:
            return run_id
        fresh = db.get_task(task_id)
        if fresh and fresh.get("one_off_state") == "running":
            # Its due time was reached between creation and this request.  It
            # is already starting in the scheduler thread, so do not report a
            # false failure to the user.
            return None
        raise RuntimeError("一次性任务未能启动")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            pw = request.form.get("password", "")
            if check_password_hash(cfg["password_hash"], pw):
                session["authed"] = True
                session.permanent = True
                nxt = request.args.get("next") or url_for("index")
                return redirect(nxt)
            flash("密码错误", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        tasks = db.list_tasks()
        groups = db.list_groups()
        group_filter = request.args.get("group", "all")
        # Every task is rendered; the group chips filter them in the browser so
        # switching groups or moving a task never needs a page load.
        if group_filter not in ("all", "ungrouped") and not any(str(g["id"]) == group_filter for g in groups):
            group_filter = "all"
        total_count = len(tasks)
        ungrouped_count = sum(t["group_id"] is None for t in tasks)
        for t in tasks:
            t["group_key"] = "ungrouped" if t["group_id"] is None else str(t["group_id"])
            t["args_list"] = json.loads(t["args"] or "[]")
            if t.get("scheduled_at"):
                t["scheduled_at_local"] = datetime.datetime.fromtimestamp(
                    t["scheduled_at"], system_timezone()
                ).strftime("%Y-%m-%dT%H:%M")
        recurring_tasks = [t for t in tasks if t.get("task_kind", "recurring") == "recurring"]
        one_off_tasks = [t for t in tasks if t.get("task_kind", "recurring") == "one_off"]
        return render_template(
            "index.html",
            tasks=tasks,
            recurring_tasks=recurring_tasks,
            one_off_tasks=one_off_tasks,
            groups=groups,
            group_filter=group_filter,
            total_count=total_count,
            ungrouped_count=ungrouped_count,
            scripts=list_scripts(cfg["scripts_dir"], {t["script"] for t in tasks}),
        )

    @app.route("/groups", methods=["POST"])
    @login_required
    def create_group():
        try:
            group_id = db.create_group(request.form.get("name"))
        except ValueError as e:
            if wants_json():
                return jsonify({"success": False, "message": str(e)}), 400
            flash(str(e), "error")
            return redirect(url_for("index"))
        group = db.get_group(group_id)
        if wants_json():
            return jsonify({"success": True, "message": f"已新建分组「{group['name']}」", "group": {"id": group_id, "name": group["name"]}})
        return redirect(url_for("index", group=group_id))

    @app.route("/groups/<int:group_id>/rename", methods=["POST"])
    @login_required
    def rename_group(group_id):
        try:
            db.rename_group(group_id, request.form.get("name"))
        except ValueError as e:
            if wants_json():
                return jsonify({"success": False, "message": str(e)}), 400
            flash(str(e), "error")
            return redirect(url_for("index", group=group_id))
        name = db.get_group(group_id)["name"]
        if wants_json():
            return jsonify({"success": True, "message": "分组已重命名", "group": {"id": group_id, "name": name}})
        flash("分组已重命名", "ok")
        return redirect(url_for("index", group=group_id))

    @app.route("/groups/<int:group_id>/delete", methods=["POST"])
    @login_required
    def delete_group(group_id):
        try:
            moved = db.delete_group(group_id)
        except ValueError as e:
            if wants_json():
                return jsonify({"success": False, "message": str(e)}), 400
            flash(str(e), "error")
            return redirect(url_for("index", group="ungrouped"))
        message = f"分组已删除，{moved} 个任务移至未分组"
        if wants_json():
            return jsonify({"success": True, "message": message, "moved": moved})
        flash(message, "ok")
        return redirect(url_for("index", group="ungrouped"))

    @app.route("/tasks/<int:task_id>/group", methods=["POST"])
    @login_required
    def move_task_group(task_id):
        raw = request.form.get("group_id", "")
        try:
            group_id = None if raw == "" else int(raw)
            db.move_task(task_id, group_id)
            group = db.get_group(group_id) if group_id is not None else None
            return action_response(f"任务已移至{group['name'] if group else '未分组'}")
        except (ValueError, TypeError) as e:
            return action_response(str(e) if str(e) else "分组无效", "error", 400)

    @app.route("/api/webhook/<string:task_name>", methods=["POST"])
    def webhook_trigger(task_name):
        task = db.get_task_by_name(task_name)
        if not task:
            return jsonify({"success": False, "error": "task not found"}), 404
        if task["schedule_type"] != "webhook":
            return jsonify({"success": False, "error": "task is not webhook-triggered"}), 409
        if not task["enabled"]:
            return jsonify({"success": False, "error": "task is disabled"}), 403
        secret = str(cfg.get("webhook_secret", ""))
        provided = request.headers.get(WEBHOOK_SECRET_HEADER, "") or request.args.get("secret", "")
        if not secret or not hmac.compare_digest(provided, secret):
            return jsonify({"success": False, "error": "invalid webhook secret"}), 401
        if request.content_length and request.content_length > MAX_WEBHOOK_BODY:
            return jsonify({"success": False, "error": "request body too large"}), 413
        payload = request.get_data(cache=False)
        if len(payload) > MAX_WEBHOOK_BODY:
            return jsonify({"success": False, "error": "request body too large"}), 413
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return jsonify({"success": False, "error": "request body must be valid JSON"}), 400
        if not isinstance(decoded, dict):
            return jsonify({"success": False, "error": "request body must be a JSON object"}), 400
        if task["running_pid"]:
            return jsonify({"success": False, "error": "task is already running"}), 409
        run_id = scheduler.run_webhook(task, payload)
        return jsonify({"success": True, "run_id": run_id, "task_name": task_name}), 202

    @app.route("/tasks/new", methods=["GET", "POST"])
    @login_required
    def new_task():
        if request.method == "POST":
            try:
                data = task_form_data()
                if db.get_task_by_name(data["name"]):
                    raise ValueError("任务名已存在")
                task_id = db.create_task(**data)
                fresh = db.get_task(task_id)
                db.update_task(task_id, next_run_at=compute_next_run(fresh))
                if data["task_kind"] == "one_off" and data["one_off_trigger"] == "immediate":
                    run_id = start_one_off(task_id)
                    detail = f"（运行 #{run_id}）" if run_id is not None else ""
                    flash(f"一次性任务已创建并在后台启动{detail}", "ok")
                elif data["task_kind"] == "one_off":
                    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data["scheduled_at"]))
                    flash(f"一次性任务已创建，将在 {when} 执行", "ok")
                else:
                    flash("重复任务已创建", "ok")
            except (ValueError, ScriptError, RuntimeError) as e:
                flash(str(e), "error")
                return redirect(url_for("new_task", task_kind=request.form.get("task_kind", "recurring")))
            return redirect(url_for("index"))

        scripts = list_scripts(
            cfg["scripts_dir"], {t["script"] for t in db.list_tasks()}
        )
        return render_template("task_form.html", task=None, scripts=scripts)

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        if request.method == "POST":
            try:
                data = task_form_data(existing=task)
                db.update_task(task_id, **data)
                fresh = db.get_task(task_id)
                db.update_task(task_id, next_run_at=compute_next_run(fresh))
                if data["task_kind"] == "one_off" and data["one_off_trigger"] == "immediate":
                    run_id = start_one_off(task_id)
                    detail = f"（运行 #{run_id}）" if run_id is not None else ""
                    flash(f"任务已更新并在后台启动{detail}", "ok")
                else:
                    flash("任务已更新", "ok")
            except (ValueError, ScriptError, RuntimeError) as e:
                flash(str(e), "error")
                return redirect(url_for("edit_task", task_id=task_id))
            return redirect(url_for("index"))

        task["args_str"] = json.dumps(json.loads(task["args"] or "[]"), ensure_ascii=False)
        if task.get("scheduled_at"):
            task["scheduled_at_local"] = datetime.datetime.fromtimestamp(
                task["scheduled_at"], system_timezone()
            ).strftime("%Y-%m-%dT%H:%M")
        scripts = list_scripts(
            cfg["scripts_dir"], {t["script"] for t in db.list_tasks()}
        )
        return render_template("task_form.html", task=task, scripts=scripts)

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    @login_required
    def delete_task(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        if task["running_pid"]:
            return action_response("请先停止运行中的任务，再删除", "error", 409)
        db.delete_task(task_id)
        return action_response(f"任务 {task['name']} 已删除", deleted_task_id=task_id)

    @app.route("/tasks/<int:task_id>/run", methods=["POST"])
    @login_required
    def run_task_now(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        if task["running_pid"]:
            return action_response("任务正在运行中", "error", 409)
        if task.get("task_kind", "recurring") == "one_off":
            previous_state = task.get("one_off_state")
            if previous_state in ("completed", "failed", "cancelled"):
                if not db.requeue_one_off(task_id):
                    return action_response("一次性任务状态已变化，请刷新后重试", "error", 409)
            run_id = scheduler.run_one_off_now(task)
            if run_id is None:
                return action_response("一次性任务已被执行、取消或正在启动", "error", 409)
            action = "已再次在后台启动" if previous_state in ("completed", "failed", "cancelled") else "已在后台启动"
            return action_response(f"一次性任务 {task['name']} {action}", run_id=run_id)
        run_id = scheduler.run_now(task)
        return action_response(f"任务 {task['name']} 已触发运行", run_id=run_id)

    @app.route("/tasks/<int:task_id>/stop", methods=["POST"])
    @login_required
    def stop_task(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        if not task["running_pid"]:
            return action_response("任务当前未在运行", "error", 409)
        if scheduler.stop_now(task):
            return action_response(f"已发送停止信号给任务 {task['name']}")
        return action_response(f"停止任务 {task['name']} 失败（进程可能已结束）", "error", 409)

    @app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
    @login_required
    def toggle_task(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        if task.get("task_kind", "recurring") == "one_off":
            return action_response("一次性任务请使用“取消”而非启用/停用", "error", 409)
        new_enabled = 0 if task["enabled"] else 1
        db.update_task(task_id, enabled=new_enabled)
        if new_enabled and task["schedule_type"] in ("cron", "interval"):
            fresh = db.get_task(task_id)
            nxt = compute_next_run(fresh)
            db.update_task(task_id, next_run_at=nxt)
        else:
            db.update_task(task_id, next_run_at=None)
        return action_response(f"任务已{'启用' if new_enabled else '停用'}", enabled=bool(new_enabled))

    @app.route("/tasks/<int:task_id>/cancel", methods=["POST"])
    @login_required
    def cancel_one_off_task(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        if task.get("task_kind", "recurring") != "one_off":
            return action_response("只有一次性任务可以取消", "error", 409)
        if not db.cancel_one_off(task_id):
            return action_response("任务不是可取消的等待状态", "error", 409)
        return action_response(f"一次性任务 {task['name']} 已取消")

    @app.route("/tasks/<int:task_id>/runs")
    @login_required
    def task_runs(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        runs = db.list_runs(task_id=task_id, limit=100)
        return render_template("runs.html", task=task, runs=runs)

    @app.route("/runs/<int:run_id>/log")
    @login_required
    def run_log(run_id):
        run = db.get_run(run_id)
        if not run or not run.get("log_path"):
            abort(404)
        log_path = run["log_path"]
        if not os.path.isfile(log_path):
            return "日志文件不存在（可能已被清理）", 404
        with open(log_path, "r", errors="replace") as f:
            content = f.read()
            offset = f.tell()
        return render_template("log.html", run=run, content=content, offset=offset)

    @app.route("/api/tasks/<int:task_id>/status")
    @login_required
    def api_task_status(task_id):
        task = db.get_task(task_id)
        if not task:
            abort(404)
        return jsonify({
            "running": bool(task["running_pid"]),
            "last_run_at": task["last_run_at"],
            "next_run_at": task["next_run_at"],
            "task_kind": task.get("task_kind", "recurring"),
            "one_off_state": task.get("one_off_state"),
            "one_off_trigger": task.get("one_off_trigger"),
            "scheduled_at": fmt_ts(task.get("scheduled_at")),
        })

    @app.route("/api/tasks/status")
    @login_required
    def api_tasks_status():
        tasks = db.list_tasks()
        out = {}
        for t in tasks:
            out[t["id"]] = {
                "running": bool(t["running_pid"]),
                "enabled": bool(t["enabled"]),
                "last_run_at": fmt_ts(t["last_run_at"]),
                "next_run_at": fmt_ts(t["next_run_at"]),
                "last_exit_code": t["last_exit_code"],
                "task_kind": t.get("task_kind", "recurring"),
                "one_off_state": t.get("one_off_state"),
                "one_off_trigger": t.get("one_off_trigger"),
                "scheduled_at": fmt_ts(t.get("scheduled_at")),
            }
        return jsonify(out)

    @app.route("/api/runs/<int:run_id>/status")
    @login_required
    def api_run_status(run_id):
        run = db.get_run(run_id)
        if not run:
            abort(404)
        return jsonify({
            "finished": run["finished_at"] is not None,
            "finished_at": fmt_ts(run["finished_at"]) if run["finished_at"] else None,
            "exit_code": run["exit_code"],
        })

    @app.route("/api/runs/<int:run_id>/tail")
    @login_required
    def api_run_tail(run_id):
        run = db.get_run(run_id)
        if not run or not run.get("log_path"):
            abort(404)
        offset = request.args.get("offset", 0, type=int)
        log_path = run["log_path"]
        content = ""
        size = offset
        if os.path.isfile(log_path):
            with open(log_path, "r", errors="replace") as f:
                f.seek(offset)
                content = f.read()
                size = f.tell()
        return jsonify({
            "content": content,
            "offset": size,
            "finished": run["finished_at"] is not None,
            "exit_code": run["exit_code"],
            "finished_at": fmt_ts(run["finished_at"]) if run["finished_at"] else None,
        })

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            new_pw = request.form.get("new_password", "").strip()
            if new_pw:
                if len(new_pw) < 4:
                    flash("密码至少 4 位", "error")
                    return redirect(url_for("settings"))
                cfg["password_hash"] = generate_password_hash(new_pw)
                cfgmod.save_config(cfg, cfg_path)
                flash("密码已更新", "ok")
                return redirect(url_for("settings"))
        return render_template("settings.html", cfg_path=cfg_path, scripts_dir=cfg["scripts_dir"])

    return app


def list_scripts(scripts_dir, registered_scripts=None):
    """Return runnable scripts grouped by the two task storage areas."""
    groups = {"recurring": [], "one_off": []}
    if not os.path.isdir(scripts_dir):
        return groups
    registered_scripts = (
        {str(path).replace("\\", "/") for path in registered_scripts}
        if registered_scripts is not None else None
    )
    for kind, root_name in (("recurring", "cron"), ("one_off", "once")):
        root = os.path.join(scripts_dir, root_name)
        if not os.path.isdir(root):
            continue
        for directory, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                full = os.path.join(directory, filename)
                if not os.path.isfile(full):
                    continue
                if not (
                    filename.endswith((".py", ".sh"))
                    or os.access(full, os.X_OK)
                ):
                    continue
                relative = os.path.relpath(full, scripts_dir).replace(os.sep, "/")
                # Folders can carry helpers alongside their entry point.  A
                # registered script is authoritative; before registration,
                # the conventional <task>/<task>.py|sh name is selectable.
                task_dir_name = os.path.basename(directory)
                if (
                    registered_scripts is not None
                    and relative not in registered_scripts
                    and os.path.splitext(filename)[0] != task_dir_name
                ):
                    continue
                groups[kind].append(relative)
    return groups
