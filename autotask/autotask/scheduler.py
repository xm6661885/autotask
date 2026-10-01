import time
import threading
import logging
from croniter import croniter

from .runner import Runner
from .timezone import local_datetime

log = logging.getLogger("autotask.scheduler")


def compute_next_run(task, now=None):
    now = time.time() if now is None else now
    if task.get("task_kind", "recurring") == "one_off":
        if task.get("one_off_state") != "pending" or not task.get("enabled"):
            return None
        try:
            return float(task["scheduled_at"])
        except (KeyError, TypeError, ValueError):
            return None
    if task["schedule_type"] == "cron":
        try:
            # croniter interprets a float timestamp as UTC. Passing an aware
            # local datetime makes the expression follow the host timezone.
            itr = croniter(task["schedule_value"], local_datetime(now))
            return itr.get_next(float)
        except Exception:
            log.exception("bad cron expr for task %s: %s", task["name"], task["schedule_value"])
            return None
    if task["schedule_type"] == "interval":
        try:
            interval = float(task["schedule_value"])
        except (TypeError, ValueError):
            return None
        last = task.get("last_run_at") or task.get("created_at") or now
        nxt = last + interval
        if nxt <= now:
            nxt = now
        return nxt
    return None


class Scheduler:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.runner = Runner(cfg, db)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        poll = self.cfg.get("poll_interval_sec", 2)
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("scheduler tick failed")
            self._stop.wait(poll)

    def _tick(self):
        now = time.time()
        for task in self.db.list_tasks():
            if task["running_pid"] and not self.runner.reconcile(task):
                task = self.db.get_task(task["id"])  # refresh after reconcile cleared it

            if task.get("task_kind", "recurring") == "one_off":
                self._tick_one_off(task, now)
                continue

            if not task["enabled"]:
                continue
            if task["schedule_type"] not in ("cron", "interval"):
                continue
            if task["running_pid"]:
                continue  # already running, skip this tick

            next_run = task.get("next_run_at")
            if next_run is None:
                next_run = compute_next_run(task, now)
                if next_run is not None:
                    self.db.update_task(task["id"], next_run_at=next_run)
                continue

            if next_run <= now:
                trigger = task["schedule_type"]
                log.info("triggering task %s (%s)", task["name"], trigger)
                self.runner.run_task(task, trigger=trigger)
                fresh = self.db.get_task(task["id"])
                new_next = compute_next_run(fresh, now + 0.001)
                self.db.update_task(task["id"], next_run_at=new_next)

    def _tick_one_off(self, task, now):
        """Launch a due temporary task exactly once.

        ``claim_one_off`` is transactional, which also covers a simultaneous
        Web UI "run now" request.  A task remains in the UI after it finishes
        so its status and log can be inspected or deleted deliberately.
        """
        if (
            not task.get("enabled")
            or task.get("one_off_state") != "pending"
            or task.get("running_pid")
        ):
            return
        try:
            due_at = float(task.get("scheduled_at"))
        except (TypeError, ValueError):
            log.error("one-off task %s has no valid scheduled time", task["name"])
            self.db.update_task(
                task["id"], enabled=0, next_run_at=None, one_off_state="failed"
            )
            return
        if due_at > now:
            if task.get("next_run_at") != due_at:
                self.db.update_task(task["id"], next_run_at=due_at)
            return

        claimed = self.db.claim_one_off(task["id"])
        if claimed:
            self._run_claimed_one_off(claimed, trigger="once_scheduled")

    def _run_claimed_one_off(self, task, *, trigger, background=True):
        try:
            return self.runner.run_task(task, trigger=trigger, background=background)
        except Exception:
            # A resolution/Popen failure after the atomic claim must not leave
            # a temporary task displayed as permanently running.
            self.db.complete_one_off(task["id"], -1)
            raise

    def run_one_off_now(self, task, *, background=True):
        """Start a pending one-off immediately, even if it was scheduled later.

        Returns ``None`` if another request/scheduler tick already claimed it.
        """
        if task.get("task_kind") != "one_off":
            raise ValueError("task is not a one-off task")
        claimed = self.db.claim_one_off(task["id"], allow_early=True)
        if not claimed:
            return None
        return self._run_claimed_one_off(
            claimed, trigger="once_immediate", background=background
        )

    def run_now(self, task, extra_args=None, stdin_data=None, background=True):
        return self.runner.run_task(
            task, trigger="manual", extra_args=extra_args, stdin_data=stdin_data,
            background=background,
        )

    def run_webhook(self, task, payload):
        return self.runner.run_task(task, trigger="webhook", stdin_data=payload)

    def stop_now(self, task):
        return self.runner.stop_task(task)
