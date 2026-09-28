import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sretoolkit import VERSION
from sretoolkit.common import digest, result, write_json
from sretoolkit.fleet import execute_fleet, finalize, prepare, resolve_inventory

INVENTORY = {"environments": {"test": {
    "hosts": {"a": {"address": "192.0.2.1", "port": 22, "user": "sreops"},
              "b": {"address": "192.0.2.2", "port": 22, "user": "sreops"}},
    "groups": {"web": ["a", "b"]}}}}


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "run"
        self.key = Path(self.temp.name) / "credential"
        self.key.write_text("fixture", encoding="utf-8")

    def prepare(self, phase="run"):
        task, params = ("system", {}) if phase == "run" else ("service", {"service": "demo", "action": "restart"})
        return prepare(INVENTORY, "test", "web", task, params, phase, self.out)

    def event(self, host, manifest, status="ok", metrics=None):
        row = result(manifest["run_id"], host, manifest["task"], status, "test", metrics=metrics or {})
        write_json(self.out / "events" / (host + ".json"), dict(executing=True, rc=0, stdout=json.dumps([row])))

    def preview(self):
        manifest = self.prepare("plan")
        for host in manifest["hosts"]:
            plan = dict(plan_id="plan-" + host, task="service", run_id=manifest["run_id"], version=VERSION, params=manifest["params"])
            self.event(host, manifest, metrics={"plan": plan, "digest": digest(plan)})
        finalize(self.out)
        return json.loads((self.out / "manifest.json").read_text())

    def test_inventory_disallows_patterns(self):
        for selection in ["all", "*", "web:!a", "a;id", "a,b,missing"]:
            with self.assertRaises((ValueError, KeyError)):
                resolve_inventory(INVENTORY, "test", selection)
        self.assertEqual(list(resolve_inventory(INVENTORY, "test", "web,a")), ["a", "b"])

    def test_missing_results_are_completed(self):
        manifest = self.prepare()
        self.event("a", manifest)
        summary = finalize(self.out)
        records = json.loads((self.out / "results.json").read_text())
        self.assertEqual([r["status"] for r in records], ["ok", "unknown"])
        self.assertEqual(summary["build_status"], "FAILURE")

    def test_corrupt_event_still_produces_complete_report(self):
        manifest = self.prepare()
        self.event("a", manifest)
        (self.out / "events/b.json").write_text("invalid", encoding="utf-8")
        summary = finalize(self.out)
        self.assertEqual(summary["build_status"], "FAILURE")
        rows = json.loads((self.out / "results.json").read_text())
        self.assertEqual([r["status"] for r in rows], ["ok", "error"])

    def test_no_credentials_fails_before_remote_execution(self):
        self.prepare()
        with patch("sretoolkit.fleet.launch") as launch, self.assertRaises(ValueError):
            execute_fleet(self.out, None, None, None)
        launch.assert_not_called()

    def test_approval_mismatch_does_not_execute(self):
        self.preview()
        with patch("sretoolkit.fleet.launch") as launch, self.assertRaises(ValueError):
            execute_fleet(self.out, self.key, self.key, self.key, "wrong", "approver")
        launch.assert_not_called()

    def test_first_failure_skips_second_host(self):
        manifest = self.preview()
        calls = []
        def launch(directory, current, hosts, *args):
            calls.append(hosts)
            self.event(hosts[0], current, "error")
            return 0
        with patch("sretoolkit.fleet.launch", side_effect=launch):
            summary = execute_fleet(self.out, self.key, self.key, self.key, manifest["approval_digest"], "operator")
        self.assertEqual(calls, [["a"]])
        self.assertEqual(summary["build_status"], "FAILURE")
        rows = json.loads((self.out / "results.json").read_text())
        self.assertEqual([row["status"] for row in rows], ["error", "skipped"])

    def test_successful_serial_apply_and_no_replay(self):
        manifest = self.preview()
        calls = []
        def launch(directory, current, hosts, *args):
            calls.append(hosts)
            self.event(hosts[0], current)
        with patch("sretoolkit.fleet.launch", side_effect=launch):
            summary = execute_fleet(self.out, self.key, self.key, self.key, manifest["approval_digest"], "operator")
        self.assertEqual(calls, [["a"], ["b"]])
        self.assertEqual(summary["build_status"], "SUCCESS")
        with self.assertRaises(ValueError):
            execute_fleet(self.out, self.key, self.key, self.key)

    def test_interruption_finalizes_partial_results(self):
        manifest = self.prepare()
        def launch(*args):
            self.event("a", manifest)
            raise KeyboardInterrupt()
        with patch("sretoolkit.fleet.launch", side_effect=launch), self.assertRaises(KeyboardInterrupt):
            execute_fleet(self.out, self.key, self.key, self.key)
        rows = json.loads((self.out / "results.json").read_text())
        self.assertEqual([r["status"] for r in rows], ["ok", "unknown"])

    def test_bundle_tamper_rejected(self):
        self.prepare()
        (self.out / "bundle.tar.gz").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            execute_fleet(self.out, self.key, self.key, self.key)

    def test_target_connection_tamper_rejected(self):
        self.prepare()
        write_json(self.out / "inventory.json", {"all": {"hosts": {}}})
        with self.assertRaises(ValueError):
            execute_fleet(self.out, self.key, self.key, self.key)

    def test_old_results_cannot_make_a_retry_look_successful(self):
        manifest = self.prepare()
        def launch(*args):
            for host in manifest["hosts"]:
                self.event(host, manifest)
        with patch("sretoolkit.fleet.launch", side_effect=launch):
            execute_fleet(self.out, self.key, self.key, self.key)
        with self.assertRaises(ValueError):
            execute_fleet(self.out, self.key, self.key, self.key)


if __name__ == "__main__":
    unittest.main()
