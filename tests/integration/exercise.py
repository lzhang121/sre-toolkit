"""Run inside disposable controller only. Never accepts production inventory."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sretoolkit.fleet import execute_fleet, prepare

INVENTORY = {"environments": {"test": {
    "hosts": {alias: {"address": "target-" + alias, "port": 22, "user": "sreops"} for alias in ("a", "b")},
    "groups": {"web": ["a", "b"]}}}}
KEY, KNOWN, CONFIG = "/tmp/sre-key", "/tmp/known_hosts", "/tmp/ssh_config"
OUT = Path("test_output/fleet")


def ssh(host, *command):
    return subprocess.check_output(["ssh", "-F", CONFIG, "-i", KEY, "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + KNOWN,
                                    "sreops@target-" + host, *command], text=True)


def run(name, task, params, maintenance=False, apply=True):
    directory = OUT / name
    prepare(INVENTORY, "test", "web", task, params, "plan" if maintenance else "run", directory)
    summary = execute_fleet(directory, KEY, KNOWN, CONFIG)
    assert summary["build_status"] == "SUCCESS", summary
    if maintenance and apply:
        manifest = json.loads((directory / "manifest.json").read_text())
        summary = execute_fleet(directory, KEY, KNOWN, CONFIG, manifest["approval_digest"], "integration-operator")
        assert summary["build_status"] == "SUCCESS", summary
    return directory


def main():
    run("inspect", "service_status", {"service": "sre-demo"})
    run("preview", "service", {"service": "sre-demo", "action": "stop"}, True, False)
    assert all(ssh(h, "systemctl is-active sre-demo").strip() == "active" for h in ("a", "b"))
    run("restart", "service", {"service": "sre-demo", "action": "restart"}, True)
    directory = run("backup", "backup", {"source": "/srv/sre-fixtures/source"}, True)
    rows = json.loads((directory / "results.json").read_text())
    assert all(row["metrics"]["sha256"] and row["metrics"]["bytes"] > 0 for row in rows)
    run("cleanup", "cleanup", {"directory": "/srv/sre-fixtures/archive", "days": 7}, True)
    # Demonstrate partial failure: use a consumed first-host plan. No second-host apply.
    directory = run("fail-stop", "service", {"service": "sre-demo", "action": "restart"}, True, False)
    manifest = json.loads((directory / "manifest.json").read_text())
    metrics = manifest["plans"]["a"]
    import shlex
    request = dict(mode="apply", task="service", run_id=manifest["run_id"], version="1.0.0",
                   plan_id=metrics["plan"]["plan_id"], digest=metrics["digest"])
    ssh("a", "printf %s " + shlex.quote(json.dumps(request)) + " | sudo -n /usr/local/sbin/sre-maint")
    summary = execute_fleet(directory, KEY, KNOWN, CONFIG, manifest["approval_digest"], "integration-operator")
    assert summary["build_status"] == "FAILURE"
    rows = json.loads((directory / "results.json").read_text())
    assert rows[1]["status"] == "skipped", rows


if __name__ == "__main__":
    main()
