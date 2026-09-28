"""Static compatibility/contracts; not a substitute for Jenkins/Ansible integration."""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArtifactTests(unittest.TestCase):
    def test_target_python39_syntax(self):
        for path in [*(ROOT / "sretoolkit").glob("*.py"), ROOT / "tools/sre.py", ROOT / "admin/sre-maint"]:
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_example_policy_denies_all(self):
        policy = json.loads((ROOT / "configs/policy.example.json").read_text())
        self.assertFalse(policy["services"])
        self.assertFalse(policy["backups"])
        self.assertFalse(policy["cleanup"])

    def test_jenkins_has_separate_readonly_and_approval_paths(self):
        maintenance = (ROOT / "jenkins/Jenkinsfile.maintain").read_text()
        inspect = (ROOT / "jenkins/Jenkinsfile.inspect").read_text()
        self.assertIn("defaultValue: false", maintenance)
        self.assertIn("submitter: settings.approvers", maintenance)
        self.assertIn("submitterParameter: 'APPROVED_BY'", maintenance)
        self.assertIn("timeout(time: 30, unit: 'MINUTES')", maintenance)
        self.assertNotIn("ops.execute(settings, true", inspect)
        self.assertIn("approval.digest", maintenance)
        self.assertIn("always", maintenance)

    def test_no_generic_become_or_shell_module(self):
        playbook = (ROOT / "ansible/execute.yml").read_text()
        self.assertIn("become: false", playbook)
        self.assertNotIn("ansible.builtin.shell", playbook)
        self.assertIn("argv:", playbook)
        self.assertIn("--kill-after=5", playbook)


if __name__ == "__main__":
    unittest.main()
