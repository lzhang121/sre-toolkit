import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sretoolkit import VERSION
from sretoolkit.common import write_json
from sretoolkit.privileged import Maintainer, trusted_path, validate_policy


class PathSecurityTests(unittest.TestCase):
    def test_writable_parent_and_symlink_rejected(self):
        for mode, uid in [(stat.S_IFDIR | 0o777, 0), (stat.S_IFLNK | 0o777, 0), (stat.S_IFDIR | 0o755, 1000)]:
            with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=mode, st_uid=uid)), self.assertRaises(ValueError):
                trusted_path(Path("/var/archives"))

    def test_unknown_policy_fields_rejected(self):
        with self.assertRaises(ValueError):
            validate_policy({"schema_version": 1, "services": {}, "backups": [], "cleanup": [], "command": "id"})


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        (self.state / "plans").mkdir(parents=True)
        self.directory = self.root / "archive"
        self.directory.mkdir()
        self.file = self.directory / "old.log"
        self.file.write_text("data", encoding="utf-8")
        old = time.time() - 10 * 86400
        os.utime(self.file, (old, old))
        self.policy = dict(schema_version=1, services={"demo": ["restart"]}, backups=[],
                           cleanup=[dict(directory=str(self.directory), pattern="*.log", min_days=7, max_files=10, max_bytes=10000)])
        self.policy_path = self.root / "policy.json"
        write_json(self.policy_path, self.policy)
        self.manager = Maintainer(self.policy_path, self.state, self.root)
        # Windows fixture paths/owners differ. Security checks themselves are
        # tested above and in real Linux integration; never exposed as CLI flags.
        trust = patch("sretoolkit.privileged.trusted_path", side_effect=lambda p: Path(p))
        trust.start()
        self.addCleanup(trust.stop)
        validate_patch = patch("sretoolkit.privileged.validate", side_effect=lambda task, params: params)
        validate_patch.start()
        self.addCleanup(validate_patch.stop)

    def request(self):
        return dict(mode="plan", task="cleanup", run_id="run1", version=VERSION,
                    params={"directory": str(self.directory), "days": 7})

    def create(self):
        data = self.manager.plan(self.request(), 1000)
        return dict(mode="apply", task="cleanup", run_id="run1", version=VERSION,
                    plan_id=data["plan"]["plan_id"], digest=data["digest"])

    def test_plan_is_readonly(self):
        plan = self.manager.plan(self.request(), 1000)
        self.assertTrue(self.file.exists())
        self.assertEqual(plan["plan"]["details"]["count"], 1)

    def test_unallowlisted_service_and_path(self):
        with self.assertRaises(ValueError):
            self.manager.authorize("service", {"service": "sshd", "action": "stop"}, self.policy)
        with self.assertRaises(ValueError):
            self.manager.authorize("cleanup", {"directory": str(self.root), "days": 7}, self.policy)

    def test_retention_and_size_limit(self):
        with self.assertRaises(ValueError):
            self.manager.authorize("cleanup", {"directory": str(self.directory), "days": 1}, self.policy)
        self.policy["cleanup"][0]["max_bytes"] = 1
        write_json(self.policy_path, self.policy)
        with self.assertRaises(ValueError):
            self.manager.plan(self.request(), 1000)

    def test_expired_plan(self):
        request = self.create()
        with patch("sretoolkit.privileged.time.time", return_value=time.time() + 1801), self.assertRaises(ValueError):
            self.manager.load_plan(request, 1000)

    def test_owner_run_digest_and_task_binding(self):
        request = self.create()
        for changes, uid in [({}, 1001), ({"run_id": "other"}, 1000), ({"digest": "wrong"}, 1000), ({"task": "service"}, 1000)]:
            with self.subTest(changes=changes, uid=uid), self.assertRaises(ValueError):
                self.manager.load_plan(dict(request, **changes), uid)

    def test_changed_policy(self):
        request = self.create()
        self.policy["cleanup"][0]["min_days"] = 8
        write_json(self.policy_path, self.policy)
        with self.assertRaises(ValueError):
            self.manager.load_plan(request, 1000)

    def test_changed_file_refused_before_any_delete(self):
        request = self.create()
        self.file.write_text("changed", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.manager.apply(request, 1000)
        self.assertTrue(self.file.exists())

    @unittest.skipUnless(os.name == "posix", "Linux dir_fd and flock semantics")
    def test_cleanup_apply_and_replay(self):
        request = self.create()
        status, _, changed, _ = self.manager.apply(request, 1000)
        self.assertEqual(status, "ok")
        self.assertTrue(changed)
        self.assertFalse(self.file.exists())
        with self.assertRaises(FileNotFoundError):
            self.manager.apply(request, 1000)

    @unittest.skipUnless(os.name == "posix", "Linux flock semantics")
    def test_version_and_lock_conflict(self):
        import fcntl
        with self.assertRaises(ValueError):
            self.manager.dispatch(dict(self.request(), version="wrong"), 1000)
        with (self.state / "maintenance.lock").open("w") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.manager.dispatch(self.request(), 1000)


if __name__ == "__main__":
    unittest.main()
