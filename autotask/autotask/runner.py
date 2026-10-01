import os
import signal
import subprocess
import threading
import time


class ScriptError(ValueError):
    pass


def resolve_script(scripts_dir, script):
    """Resolve a script name/relative path to an absolute path inside scripts_dir.
    Rejects anything that escapes scripts_dir (no path traversal)."""
    scripts_dir = os.path.realpath(scripts_dir)
    candidate = os.path.realpath(os.path.join(scripts_dir, script))
    if os.path.commonpath([scripts_dir, candidate]) != scripts_dir:
        raise ScriptError(f"script path escapes scripts_dir: {script}")
    if not os.path.isfile(candidate):
        raise ScriptError(f"script not found: {script}")
    return candidate


def interpreter_for(path, cfg):
    if path.endswith(".py"):
        return [cfg.get("python_bin", "python3")]
    if path.endswith(".sh"):
        return [cfg.get("shell_bin", "bash")]
    if os.access(path, os.X_OK):
        return []
    raise ScriptError(f"unsupported script type (need .py/.sh or +x): {path}")


class Runner:
    """Runs one task's script as a subprocess and records its run."""

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db

    def run_task(self, task, trigger="manual", extra_args=None, stdin_data=None,
                 background=True):
        if task.get("task_kind") == "one_off" and task.get("one_off_state") != "running":
            raise ScriptError("one-off task must be claimed before it can run")
        script_path = resolve_script(self.cfg["scripts_dir"], task["script"])
        cmd = interpreter_for(script_path, self.cfg) + [script_path]

        import json
        args = json.loads(task["args"]) if task.get("args") else []
        if extra_args:
            args = args + list(extra_args)
        cmd += args

        logs_dir = os.path.join(self.cfg["data_dir"], "logs")
        os.makedirs(logs_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        log_path = os.path.join(logs_dir, f"{task['name']}-{ts}.log")

        run_id = self.db.create_run(task["id"], trigger, log_path)

        def target():
            exit_code = -1
            try:
                with open(log_path, "wb") as logf:
                    logf.write(f"$ {' '.join(cmd)}\n".encode())
                    logf.flush()
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                        stdout=logf,
                        stderr=subprocess.STDOUT,
                        cwd=os.path.dirname(script_path),
                        env=os.environ.copy(),
                        start_new_session=True,
                    )
                    self.db.update_task(task["id"], running_pid=proc.pid)
                    if stdin_data is not None:
                        proc.stdin.write(stdin_data)
                        proc.stdin.close()
                    exit_code = proc.wait()
            except Exception as e:
                try:
                    with open(log_path, "ab") as logf:
                        logf.write(f"\n[autotask] execution error: {e}\n".encode())
                except OSError:
                    pass
            finally:
                self.db.update_task(task["id"], running_pid=None, last_run_at=time.time())
                self.db.finish_run(run_id, exit_code)
                if task.get("task_kind") == "one_off":
                    # ``claim_one_off`` disables the task before spawning the
                    # process; this final transition records whether its one
                    # permitted execution succeeded or failed.
                    self.db.complete_one_off(task["id"], exit_code)

        if background:
            # The service process is long-lived, so its worker threads may be
            # daemon threads.  Short-lived CLI processes must use
            # ``background=False`` instead; otherwise Python exits and kills
            # the worker before the script has even been spawned.
            t = threading.Thread(target=target, daemon=True)
            t.start()
        else:
            target()
        return run_id

    def stop_task(self, task):
        pid = task.get("running_pid")
        if not pid:
            return False
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._reconcile_dead(task)
            return False
        except PermissionError:
            return False
        return True

    def _reconcile_dead(self, task):
        self.db.update_task(task["id"], running_pid=None)
        open_run = self.db.get_open_run(task["id"])
        if open_run:
            self.db.finish_run(open_run["id"], None)

    def reconcile(self, task):
        pid = task.get("running_pid")
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            self._reconcile_dead(task)
            return False
        except PermissionError:
            return True
