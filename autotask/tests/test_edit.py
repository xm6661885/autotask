import contextlib
import json
import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from autotask.cli import build_parser
from autotask.db import DB


class EditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.scripts = root / "scripts"
        for name in ("job.py", "other.py"):
            path = self.scripts / "cron" / "job" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("print(1)\n")
        self.data = root / "data"
        self.data.mkdir()
        self.cfg = {"scripts_dir": str(self.scripts), "data_dir": str(self.data)}
        self.db = DB(str(self.data))
        self.task_id = self.db.create_task(
            "job", "cron/job/job.py", ["--old"], "cron", "0 2 * * *")
        self.db.create_run(self.task_id, "manual", "x.log")

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *words):
        parser = build_parser()
        out, err = io.StringIO(), io.StringIO()
        with patch("autotask.cli.cfgmod.load_config", return_value=(self.cfg, "test-config")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(words)
            code = args.func(args)
        return code, out.getvalue() + err.getvalue()

    def test_edit_args_description_and_keep_runs(self):
        code, _ = self.run_cli("edit", "job", "--clear-args", "-d", "新说明")
        self.assertEqual(code, 0)
        task = self.db.get_task(self.task_id)
        self.assertEqual(json.loads(task["args"]), [])
        self.assertEqual(task["description"], "新说明")
        self.assertEqual(task["schedule_value"], "0 2 * * *")
        self.assertEqual(len(self.db.list_runs(task_id=self.task_id)), 1)
        code, _ = self.run_cli("edit", str(self.task_id), "--args", '["-v"]')
        self.assertEqual((code, json.loads(self.db.get_task(self.task_id)["args"])), (0, ["-v"]))

    def test_edit_schedule_recomputes_next_run(self):
        code, _ = self.run_cli("edit", "job", "--schedule-type", "interval", "--schedule-value", "600")
        self.assertEqual(code, 0)
        task = self.db.get_task(self.task_id)
        self.assertEqual((task["schedule_type"], task["schedule_value"]), ("interval", "600"))
        self.assertIsNotNone(task["next_run_at"])
        self.run_cli("edit", "job", "--schedule-type", "webhook")
        task = self.db.get_task(self.task_id)
        self.assertEqual((task["schedule_type"], task["schedule_value"], task["next_run_at"]),
                         ("webhook", None, None))

    def test_edit_script_must_stay_in_task_dir(self):
        self.assertEqual(self.run_cli("edit", "job", "--script", "cron/job/other.py")[0], 0)
        self.assertEqual(self.db.get_task(self.task_id)["script"], "cron/job/other.py")
        self.assertEqual(self.run_cli("edit", "job", "--script", "cron/elsewhere/x.py")[0], 1)

    def test_edit_rejects_invalid_input(self):
        for words in (("--schedule-type", "cron", "--schedule-value", "bad cron"),
                      ("--schedule-type", "interval", "--schedule-value", "-1"),
                      ("--args", '{"a": 1}'),
                      ("--args", "[]", "--clear-args"),
                      ("--once-at", "2099-01-01 00:00"),
                      ()):
            self.assertEqual(self.run_cli("edit", "job", *words)[0], 1, words)
        self.assertEqual(self.run_cli("edit", "missing", "-d", "x")[0], 1)
        self.assertEqual(json.loads(self.db.get_task(self.task_id)["args"]), ["--old"])

    def test_edit_pending_one_off_time(self):
        path = self.scripts / "once" / "later" / "later.py"
        path.parent.mkdir(parents=True)
        path.write_text("print(1)\n")
        task_id = self.db.create_task(
            "later", "once/later/later.py", [], "once", None, task_kind="one_off",
            scheduled_at=time.time() + 3600, one_off_trigger="scheduled", one_off_state="pending")
        code, _ = self.run_cli("edit", "later", "--once-at", "2099-01-01 08:00")
        self.assertEqual(code, 0)
        self.assertEqual(self.db.get_task(task_id)["next_run_at"], self.db.get_task(task_id)["scheduled_at"])
        self.assertEqual(self.run_cli("edit", "later", "--schedule-type", "manual")[0], 1)
        self.db.cancel_one_off(task_id)
        self.assertEqual(self.run_cli("edit", "later", "-d", "x")[0], 1)


if __name__ == "__main__":
    unittest.main()
