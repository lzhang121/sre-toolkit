import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sretoolkit.common import OUTPUT_LIMIT, execute, result
from sretoolkit.report import build_status, render, transport_records
from sretoolkit.runner import maintenance, run_check
from sretoolkit.tasks import validate


class ValidationTests(unittest.TestCase):
    def test_parameters_are_closed(self):
        for task, params in [("system", {"command": "id"}), ("unknown", {}),
                             ("tcp", {"host": "x", "port": True}),
                             ("tcp", {"host": "$(id)", "port": 80}),
                             ("service", {"service": "-all", "action": "stop"}),
                             ("cleanup", {"directory": "/tmp/../etc", "days": 1}),
                             ("http", {"url": "file:///etc/passwd"}),
                             ("http", {"url": "https://user:password@example.com"})]:
            with self.subTest(task=task, params=params), self.assertRaises(ValueError):
                validate(task, params)

    def test_valid_parameters(self):
        self.assertEqual(validate("directory", {"path": "/var/my archive"}), {"path": "/var/my archive"})
        self.assertEqual(validate("tcp", {"host": "::1", "port": 80})["port"], 80)

    def test_readonly_cannot_invoke_maintenance(self):
        with self.assertRaises(ValueError):
            run_check("service", {"service": "nginx", "action": "stop"}, "run1", "host1")


class ProcessTests(unittest.TestCase):
    def test_bounded_stdout_and_stderr(self):
        out = execute([sys.executable, "-c", "import sys; print('x'*100000); print('y'*100000, file=sys.stderr)"])
        self.assertEqual(out["exit_code"], 0)
        self.assertEqual(len(out["stdout"]), OUTPUT_LIMIT)
        self.assertEqual(len(out["stderr"]), OUTPUT_LIMIT)
        self.assertTrue(out["truncated"])

    def test_timeout(self):
        out = execute([sys.executable, "-c", "import time; time.sleep(5)"], seconds=0.05)
        self.assertTrue(out["timed_out"])
        self.assertLess(out["duration"], 4)

    def test_stdin_is_data(self):
        text = '"quoted"\n$(id)'
        out = execute([sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"], stdin=text)
        self.assertEqual(out["stdout"], text)

    def test_script_exit_mapping(self):
        for code, expected in [(0, "ok"), (1, "warning"), (2, "error"), (127, "error")]:
            with patch("sretoolkit.runner.execute", return_value=dict(exit_code=code, timed_out=False,
                       stdout="", stderr="", truncated=False, duration=0.1)):
                self.assertEqual(run_check("system", {}, "run1", "h")["status"], expected)

    def test_missing_dependency(self):
        with patch("sretoolkit.runner.execute", side_effect=FileNotFoundError("bash")):
            self.assertEqual(run_check("system", {}, "run1", "h")["status"], "error")

    def test_privileged_missing_response_is_unknown(self):
        with patch("sretoolkit.runner.execute", return_value=dict(exit_code=1, timed_out=False, stdout="", stderr="lost")):
            row = maintenance("apply", "service", {}, "run1", "h", "plan1", "digest")
        self.assertEqual(row["status"], "unknown")
        self.assertIsNone(row["changed"])


class ReportTests(unittest.TestCase):
    def event(self, records, **kwargs):
        return dict(executing=True, rc=0, stdout=json.dumps(records), **kwargs)

    def test_host_and_task_binding(self):
        for record in [result("wrong", "h", "system", "ok", ""),
                       result("r", "wrong", "system", "ok", ""),
                       result("r", "h", "other", "ok", "")]:
            rows = transport_records(self.event([record]), "r", "h", ["system"], "run")
            self.assertEqual(rows[0]["status"], "error")

    def test_valid_results_and_warnings(self):
        records = [result("r", "h", "system", "warning", "load")]
        rows = transport_records(self.event(records), "r", "h", ["system"], "run")
        self.assertEqual(build_status(rows), "UNSTABLE")

    def test_invalid_json_missing_duplicate_and_partial(self):
        cases = [{"executing": True, "stdout": "garbage"}, None,
                 self.event([result("r", "h", "system", "ok", "")]),
                 self.event([result("r", "h", "system", "ok", "")] * 2)]
        for event in cases:
            rows = transport_records(event, "r", "h", ["system", "network"], "run")
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(r["status"] in {"unknown", "error"} for r in rows))

    def test_unreachable_vs_interrupted_apply(self):
        for phase, executing, expected in [("run", True, "unreachable"), ("apply", False, "unreachable"), ("apply", True, "unknown")]:
            rows = transport_records(dict(unreachable=True, executing=executing), "r", "h", ["service"], phase)
            self.assertEqual(rows[0]["status"], expected)

    def test_timeout(self):
        rows = transport_records(dict(executing=True, rc=124), "r", "h", ["system"], "run")
        self.assertEqual(rows[0]["status"], "timeout")

    def test_html_and_csv_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = result("r", "h", "system", "ok", '=HYPERLINK("bad")', stdout="<script>alert(1)</script>")
            render(tmp, dict(run_id="r", commit="c", phase="run"), [row])
            page = Path(tmp, "index.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>", page)
            self.assertIn("&lt;script&gt;", page)
            self.assertIn("'=HYPERLINK", Path(tmp, "results.csv").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
