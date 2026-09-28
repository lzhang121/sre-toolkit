import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from sretoolkit.jenkins_config import fields, main


class JenkinsConfigTests(unittest.TestCase):
    def settings(self):
        return dict(ssh_credential_id="ssh-key", known_hosts_credential_id="known-hosts",
                    ssh_config_credential_id="ssh-config", approvers="ops,管理员")

    def test_inventory_roundtrip(self):
        settings = self.settings()
        wire = fields("environment", {"environments": {"test": settings}}, "test")
        self.assertEqual(dict(line.split("\t", 1) for line in wire.splitlines()), settings)

    def test_approval_binding_fields_preserved(self):
        approval = dict(task="cleanup", hosts=["a", "b"], run_id="r", commit="abc", digest="123")
        values = dict(line.split("\t", 1) for line in fields("approval", approval, "test").splitlines())
        self.assertEqual(values, dict(task="cleanup", hosts="a, b", run_id="r", commit="abc", digest="123"))

    def test_missing_environment_and_fields_fail(self):
        for document in [{"environments": {}}, {"environments": {"test": {}}}]:
            with self.assertRaises(KeyError):
                fields("environment", document, "test")

    def test_invalid_fields_cannot_inject_wire_values(self):
        for value in [None, [], "", " ", "ops\nother\tvalue", "ops\radmin"]:
            settings = dict(self.settings(), approvers=value)
            with self.assertRaises(ValueError):
                fields("environment", {"environments": {"test": settings}}, "test")

    def test_missing_file_and_invalid_json_have_no_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            for content in [None, "not json"]:
                if content is not None:
                    path.write_text(content, encoding="utf-8")
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(main(["environment", str(path), "test"]), 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue(stderr.getvalue())

    def test_pipelines_do_not_require_json_plugin(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "jenkins").iterdir():
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("readJSON", content)
                self.assertNotIn("JsonSlurper", content)


if __name__ == "__main__":
    unittest.main()
