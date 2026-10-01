import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autotask.cli import build_parser
from autotask.db import DB
from autotask.webapp import create_app


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.scripts = root / "scripts"
        self.scripts.mkdir()
        self.data = root / "data"
        self.data.mkdir()
        self.cfg = {
            "scripts_dir": str(self.scripts), "data_dir": str(self.data),
            "secret_key": "test-key", "password_hash": "unused",
        }
        self.db = DB(str(self.data))

    def tearDown(self):
        self.temp.cleanup()

    def task(self, name="job"):
        return self.db.create_task(name, f"cron/{name}/{name}.py", [], "manual", None)

    def test_group_lifecycle_preserves_task_and_script(self):
        task_id = self.task()
        old = self.db.get_task(task_id)
        self.assertIsNone(old["group_id"])
        group_id = self.db.create_group("工作")
        self.db.move_task(task_id, group_id)
        self.assertEqual(self.db.get_task(task_id)["group_id"], group_id)
        self.assertEqual(self.db.list_tasks()[0]["group_name"], "工作")
        self.db.rename_group(group_id, "项目")
        self.assertEqual(self.db.list_groups()[0]["task_count"], 1)
        self.assertEqual(self.db.delete_group(group_id), 1)
        fresh = self.db.get_task(task_id)
        self.assertIsNone(fresh["group_id"])
        self.assertEqual(fresh["script"], old["script"])
        with self.assertRaises(ValueError):
            self.db.move_task(task_id, group_id)
        with self.assertRaises(ValueError):
            self.db.create_group("未分组")

    def test_cli_and_web_share_group_state(self):
        task_id = self.task()
        parser = build_parser()
        def run(*words):
            out = io.StringIO()
            with patch("autotask.cli.cfgmod.load_config", return_value=(self.cfg, "test-config")), contextlib.redirect_stdout(out):
                result = parser.parse_args(words).func(parser.parse_args(words))
            self.assertEqual(result, 0)
            return out.getvalue()
        run("groups", "create", "运维")
        run("groups", "move", "job", "运维")
        self.assertIn("job", run("list", "--group", "运维"))
        self.assertEqual(self.db.list_groups()[0]["task_count"], 1)

        app = create_app(self.cfg, "test-config", self.db, None)
        app.testing = True
        client = app.test_client()
        with client.session_transaction() as session:
            session["authed"] = True
        group_id = self.db.get_group("运维")["id"]
        page = client.get(f"/?group={group_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("运维".encode(), page.data)
        self.assertIn(b'data-task-id="1"', page.data)
        moved = client.post(f"/tasks/{task_id}/group", data={"group_id": ""}, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(moved.status_code, 200)
        self.assertIsNone(self.db.get_task(task_id)["group_id"])
        # All cards are rendered; the ones outside the requested group start hidden.
        self.assertIn(b'data-group-id="ungrouped" hidden', client.get(f"/?group={group_id}").data)
        self.assertIn(b'data-group-id="ungrouped">', client.get("/?group=ungrouped").data)
        self.assertEqual(client.get("/?group=999").status_code, 200)

    def test_web_group_management_answers_json_for_in_place_ui(self):
        app = create_app(self.cfg, "test-config", self.db, None)
        app.testing = True
        client = app.test_client()
        with client.session_transaction() as session:
            session["authed"] = True
        xhr = {"X-Requested-With": "XMLHttpRequest"}
        created = client.post("/groups", data={"name": "工作"}, headers=xhr).get_json()
        self.assertTrue(created["success"])
        group_id = created["group"]["id"]
        self.assertEqual(client.post("/groups", data={"name": "工作"}, headers=xhr).status_code, 400)
        renamed = client.post(f"/groups/{group_id}/rename", data={"name": "项目"}, headers=xhr).get_json()
        self.assertEqual(renamed["group"]["name"], "项目")
        self.db.move_task(self.task(), group_id)
        self.assertEqual(client.post(f"/groups/{group_id}/delete", headers=xhr).get_json()["moved"], 1)
        # Plain form posts still redirect back to the dashboard.
        self.assertEqual(client.post("/groups", data={"name": "运维"}).status_code, 302)

    def test_v3_database_migrates_existing_tasks_to_ungrouped(self):
        db_path = self.data / "autotask.db"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA user_version = 3")
        conn.execute("INSERT INTO tasks(name, script, created_at, updated_at) VALUES ('old', 'old.py', 1, 1)")
        conn.execute("DROP INDEX idx_tasks_group_id")
        conn.execute("ALTER TABLE tasks DROP COLUMN group_id")
        conn.commit()
        conn.close()
        db = DB(str(self.data))
        self.assertIsNone(db.get_task_by_name("old")["group_id"])
        self.assertEqual(db.list_groups(), [])


if __name__ == "__main__":
    unittest.main()
