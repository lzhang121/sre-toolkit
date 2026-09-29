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

    def test_target_credentials_and_mixed_group(self):
        settings = dict(self.settings(), hosts={
            host: dict(address="192.0.2." + str(index), port=22, user="ec2-user")
            for index, host in enumerate(["a", "b", "c"], 1)
        }, groups={"new": ["a", "b"], "mixed": ["a", "c"]},
            ssh_credential_overrides={"a": "new-key", "b": "new-key"})
        document = {"environments": {"test": settings}}
        for targets, expected in [("a", "new-key"), ("new", "new-key"), ("c", "ssh-key")]:
            wire = fields("environment", document, "test", targets)
            self.assertEqual(dict(line.split("\t", 1) for line in wire.splitlines())["ssh_credential_id"], expected)
        for targets in ["mixed", "a,c"]:
            with self.assertRaisesRegex(ValueError, "different SSH credentials"):
                fields("environment", document, "test", targets)
        settings["ssh_credential_overrides"]["a"] = "key\ninjected\tvalue"
        with self.assertRaisesRegex(ValueError, "invalid field"):
            fields("environment", document, "test", "a")

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
