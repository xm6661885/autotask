import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from autotask.cli import cmd_run
from autotask.db import DB
from autotask.scheduler import Scheduler
from autotask.webapp import create_app, list_scripts


def make_cfg(root):
    scripts = root / "scripts"
    data = root / "data"
    scripts.mkdir()
    data.mkdir()
    return {
        "scripts_dir": str(scripts),
        "data_dir": str(data),
        "python_bin": "python3",
        "shell_bin": "bash",
        "poll_interval_sec": 0.01,
        "secret_key": "test-secret",
        "password_hash": "scrypt:32768:8:1$R0zHiwsYASQDy41F$e48f1e942692b5cf168b5a9ccf6fa8b02d635bd536cb5cc8d0fb125535b28a4fda2e17ae269770b02359045eec23dc92aaeb58dc59ad195aaae2be05c3149404",
        "webhook_secret": "test-webhook-secret",
    }


class OneOffTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = make_cfg(self.root)
        self.db = DB(self.cfg["data_dir"])

    def tearDown(self):
        self.tmp.cleanup()

    def add_script(self, kind, name, filename="job.py", source="print('ok')\n"):
        directory = Path(self.cfg["scripts_dir"]) / kind / name
        directory.mkdir(parents=True)
        path = directory / filename
        path.write_text(source)
        return str(path.relative_to(self.cfg["scripts_dir"]))

    def wait_for(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    def test_old_database_migrates_description_and_one_off_columns(self):
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = make_cfg(self.root)
        db_path = Path(self.cfg["data_dir"]) / "autotask.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
                script TEXT NOT NULL, args TEXT NOT NULL DEFAULT '[]',
                schedule_type TEXT NOT NULL DEFAULT 'manual', schedule_value TEXT,
                enabled INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL,
                updated_at REAL NOT NULL, last_run_at REAL, next_run_at REAL,
                running_pid INTEGER
            );
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
                started_at REAL NOT NULL, finished_at REAL, exit_code INTEGER,
                trigger TEXT NOT NULL DEFAULT 'manual', log_path TEXT
            );
            PRAGMA user_version = 1;
            INSERT INTO tasks (name, script, created_at, updated_at)
            VALUES ('legacy', 'legacy.py', 1, 1);
            """
        )
        conn.commit()
        conn.close()

        db = DB(self.cfg["data_dir"])
        task = db.get_task_by_name("legacy")
        self.assertEqual(task["task_kind"], "recurring")
        self.assertEqual(task["description"], "")
        self.assertIn("one_off_state", task)

    def test_due_one_off_runs_exactly_once_and_keeps_terminal_state(self):
        script = self.add_script("once", "single", source="print('done')\n")
        task_id = self.db.create_task(
            "single", script, [], "once", None,
            description="single test", task_kind="one_off", scheduled_at=time.time() - 1,
            one_off_trigger="scheduled", one_off_state="pending",
        )
        self.db.update_task(task_id, next_run_at=time.time() - 1)
        scheduler = Scheduler(self.cfg, self.db)
        scheduler._tick()
        self.assertTrue(self.wait_for(
            lambda: self.db.get_task(task_id)["one_off_state"] in ("completed", "failed")
        ))
        task = self.db.get_task(task_id)
        self.assertEqual(task["one_off_state"], "completed")
        self.assertEqual(task["enabled"], 0)
        first_run_count = len(self.db.list_runs(task_id))
        scheduler._tick()
        time.sleep(0.1)
        self.assertEqual(len(self.db.list_runs(task_id)), first_run_count)
        self.assertIsNone(scheduler.run_one_off_now(task))

    def test_pending_one_off_can_be_cancelled_but_not_reclaimed(self):
        script = self.add_script("once", "cancel-me")
        task_id = self.db.create_task(
            "cancel-me", script, [], "once", None,
            task_kind="one_off", scheduled_at=time.time() + 3600,
            one_off_trigger="scheduled", one_off_state="pending",
        )
        self.assertTrue(self.db.cancel_one_off(task_id))
        self.assertFalse(self.db.cancel_one_off(task_id))
        self.assertIsNone(self.db.claim_one_off(task_id, allow_early=True))

    def test_terminal_one_off_can_be_requeued_for_one_new_run(self):
        script = self.add_script("once", "rerun-me")
        task_id = self.db.create_task(
            "rerun-me", script, [], "once", None,
            task_kind="one_off", scheduled_at=time.time(),
            one_off_trigger="immediate", one_off_state="completed", enabled=False,
        )
        self.assertTrue(self.db.requeue_one_off(task_id))
        task = self.db.get_task(task_id)
        self.assertEqual(task["one_off_state"], "pending")
        self.assertEqual(task["enabled"], 1)
        self.assertEqual(task["one_off_trigger"], "immediate")
        self.assertFalse(self.db.requeue_one_off(task_id))

    def test_cli_run_queues_pending_one_off_for_the_daemon(self):
        script = self.add_script("once", "queue-me")
        future = time.time() + 3600
        task_id = self.db.create_task(
            "queue-me", script, [], "once", None,
            task_kind="one_off", scheduled_at=future,
            one_off_trigger="scheduled", one_off_state="pending",
        )
        self.db.update_task(task_id, next_run_at=future)
        args = SimpleNamespace(name="queue-me", force=False, wait=False, extra_args=[])
        with patch("autotask.cli._load", return_value=(self.cfg, "test.yaml", self.db)):
            self.assertEqual(cmd_run(args), 0)
        task = self.db.get_task(task_id)
        self.assertEqual(task["one_off_trigger"], "immediate")
        self.assertLess(task["scheduled_at"], time.time() + 1)
        self.assertEqual(task["next_run_at"], task["scheduled_at"])

    def test_cli_run_requeues_terminal_one_off_for_the_daemon(self):
        script = self.add_script("once", "rerun-queue")
        task_id = self.db.create_task(
            "rerun-queue", script, [], "once", None,
            task_kind="one_off", scheduled_at=time.time() - 60,
            one_off_trigger="immediate", one_off_state="completed", enabled=False,
        )
        args = SimpleNamespace(name="rerun-queue", force=False, wait=False, extra_args=[])
        with patch("autotask.cli._load", return_value=(self.cfg, "test.yaml", self.db)):
            self.assertEqual(cmd_run(args), 0)
        task = self.db.get_task(task_id)
        self.assertEqual(task["one_off_state"], "pending")
        self.assertEqual(task["enabled"], 1)
        self.assertEqual(task["one_off_trigger"], "immediate")
        self.assertEqual(task["next_run_at"], task["scheduled_at"])

    def test_web_form_persists_description_and_groups_scripts(self):
        script = self.add_script("once", "web-one", source="print('web')\n")
        self.add_script("cron", "repeat", filename="repeat.sh", source="#!/usr/bin/env bash\necho repeat\n")
        groups = list_scripts(self.cfg["scripts_dir"])
        self.assertEqual(groups["one_off"], [script])
        self.assertEqual(groups["recurring"], ["cron/repeat/repeat.sh"])

        scheduler = Scheduler(self.cfg, self.db)
        app = create_app(self.cfg, "test.yaml", self.db, scheduler)
        app.config["TESTING"] = True
        client = app.test_client()
        with client.session_transaction() as session:
            session["authed"] = True
        future = time.strftime("%Y-%m-%dT%H:%M", time.localtime(time.time() + 3600))
        response = client.post("/tasks/new", data={
            "name": "web-one",
            "description": "用于验证任务说明",
            "script": script,
            "args": "[]",
            "task_kind": "one_off",
            "one_off_trigger": "scheduled",
            "scheduled_at_local": future,
        })
        self.assertEqual(response.status_code, 302)
        task = self.db.get_task_by_name("web-one")
        self.assertEqual(task["description"], "用于验证任务说明")
        self.assertEqual(task["task_kind"], "one_off")
        self.assertEqual(task["one_off_state"], "pending")


if __name__ == "__main__":
    unittest.main()
