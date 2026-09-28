"""Controller-side orchestration. Only static allowlisted inventory becomes Ansible input."""
import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path

from sretoolkit.common import digest, result, write_json
from sretoolkit import VERSION
from sretoolkit.report import render, transport_records
from sretoolkit.tasks import BASIC, TASKS, identifier, validate

ROOT = Path(__file__).resolve().parents[1]


def resolve_inventory(inventory, environment, selection):
    env = inventory["environments"][identifier(environment)]
    hosts = env["hosts"]
    groups = env["groups"]
    if not isinstance(hosts, dict) or not isinstance(groups, dict):
        raise ValueError("hosts/groups must be objects")
    chosen = set()
    for name in selection.split(","):
        name = identifier(name.strip())
        if name in hosts:
            chosen.add(name)
        elif name in groups:
            if not isinstance(groups[name], list):
                raise ValueError("group must be a list")
            chosen.update(groups[name])
        else:
            raise ValueError("unknown target: " + name)
    if not chosen or len(chosen) > 50:
        raise ValueError("select 1-50 known hosts")
    validated = {}
    for name in sorted(chosen):
        identifier(name)
        info = hosts[name]
        if set(info) != {"address", "port", "user"}:
            raise ValueError("host accepts address, port and user only")
        validate("tcp", {"host": info["address"], "port": info["port"]})
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", info["user"]):
            raise ValueError("invalid SSH username")
        validated[name] = dict(ansible_host=info["address"], ansible_port=info["port"],
                               ansible_user=info["user"], ansible_python_interpreter="/usr/bin/python3")
    return validated


def prepare(inventory, environment, targets, task, params, phase, directory):
    identifier(environment)
    if task == "basic":
        tasks = BASIC
        if params or phase != "run":
            raise ValueError("basic accepts no parameters and is read-only")
    else:
        validate(task, params)
        if (phase == "plan") != TASKS[task]["privileged"]:
            raise ValueError("wrong phase for task")
        tasks = [task]
    hosts = resolve_inventory(inventory, environment, targets)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    bundle = directory / "bundle.tar.gz"
    with tarfile.open(bundle, "w:gz") as archive:
        # Explicit file families; no .git, policies, credentials or symlinks.
        paths = list((ROOT / "bin").glob("*.sh")) + list((ROOT / "sretoolkit").glob("*.py")) + [ROOT / "tools/sre.py"]
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError("bundle cannot contain symlinks")
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    frozen_inventory = {"all": {"hosts": hosts}}
    manifest = dict(schema_version=1, run_id=uuid.uuid4().hex, commit=commit,
                    bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
                    inventory_digest=digest(frozen_inventory),
                    environment=environment, hosts=list(hosts), task=task, tasks=tasks,
                    params=params, phase=phase, plans={})
    write_json(directory / "manifest.json", manifest)
    write_json(directory / "inventory.json", frozen_inventory)
    render(directory, manifest, [result(manifest["run_id"], h, t, "unknown", "not executed yet") for h in hosts for t in tasks])
    return manifest


def argv_for(manifest, host=None):
    argv = ["/usr/bin/python3", "tools/sre.py", manifest["phase"], manifest["task"],
            "--run-id", manifest["run_id"], "--format", "json"]
    if manifest["phase"] == "apply":
        plan = manifest["plans"][host]
        argv += ["--plan-id", plan["plan"]["plan_id"], "--digest", plan["digest"]]
    else:
        argv += ["--params", json.dumps(manifest["params"], ensure_ascii=True)]
    return argv


def approval_binding(manifest):
    return {key: manifest[key] for key in ("run_id", "commit", "bundle_sha256", "inventory_digest", "environment", "hosts", "task", "params", "plans")}


def finalize(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    records = []
    for host in manifest["hosts"]:
        path = directory / "events" / (host + ".json")
        try:
            event = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if event is not None and not isinstance(event, dict):
                raise ValueError("invalid event object")
        except (ValueError, OSError):
            event = {"executing": True, "stdout": "invalid event file"}
        if host in manifest.get("skipped", []):
            rows = [result(manifest["run_id"], host, task, "skipped", "previous maintenance failed; not executed") for task in manifest["tasks"]]
        else:
            rows = transport_records(event, manifest["run_id"], host, manifest["tasks"], manifest["phase"])
        records.extend(rows)
    if manifest["phase"] == "plan":
        plans = {}
        for row in records:
            if row["status"] == "ok":
                metrics = row["metrics"]
                plan = metrics.get("plan", {})
                if (not isinstance(plan, dict) or not plan or digest(plan) != metrics.get("digest") or plan.get("task") != manifest["task"]
                        or plan.get("run_id") != manifest["run_id"] or plan.get("params") != manifest["params"]
                        or plan.get("version") != VERSION):
                    row.update(status="error", summary="invalid maintenance plan")
                else:
                    plans[row["host"]] = metrics
        manifest["plans"] = plans
        manifest["approval_digest"] = digest(approval_binding(manifest))
        write_json(directory / "manifest.json", manifest)
        write_json(directory / "approval.json", dict(digest=manifest["approval_digest"], **approval_binding(manifest)))
    return render(directory, manifest, records)


def launch(directory, manifest, hosts, key, known_hosts, ssh_config):
    directory = Path(directory).resolve()
    events = directory / "events"
    events.mkdir(exist_ok=True)
    argv = argv_for(manifest, hosts[0] if manifest["phase"] == "apply" else None)
    timeout = sum(TASKS[t]["timeout"] for t in manifest["tasks"]) + 30
    extra = dict(sre_targets=hosts, sre_bundle=str(directory / "bundle.tar.gz"),
                 sre_run_id=manifest["run_id"], sre_argv=argv, sre_deadline=timeout)
    write_json(directory / "extra.json", extra)
    env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / "ansible/ansible.cfg"),
               ANSIBLE_CALLBACK_PLUGINS=str(ROOT / "ansible/callback_plugins"),
               SRE_EVENT_DIR=str(events), ANSIBLE_HOST_KEY_CHECKING="True")
    # These paths are local trusted Jenkins credential files, not build parameters.
    import shlex
    ssh_options = " ".join(shlex.quote(x) for x in ["-F", str(Path(ssh_config).resolve()),
                            "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + str(Path(known_hosts).resolve()),
                            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes"])
    cmd = ["ansible-playbook", "-i", str(directory / "inventory.json"), str(ROOT / "ansible/execute.yml"),
           "--private-key", str(Path(key).resolve()), "--ssh-common-args", ssh_options,
           "--forks", "1" if manifest["phase"] == "apply" else "5", "--timeout", "10",
           "--extra-vars", "@" + str(directory / "extra.json")]
    # stdout callback contains no command body/log contents; detailed data is bounded in events.
    process = subprocess.Popen(cmd, env=env, start_new_session=True)
    try:
        return process.wait()
    except BaseException:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()
        raise


def execute_fleet(directory, key, known_hosts, ssh_config, apply_digest=None, approver=None):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256((directory / "bundle.tar.gz").read_bytes()).hexdigest() != manifest["bundle_sha256"]:
        raise ValueError("bundle changed after prepare")
    frozen_inventory = json.loads((directory / "inventory.json").read_text(encoding="utf-8"))
    if digest(frozen_inventory) != manifest["inventory_digest"]:
        raise ValueError("target connections changed after prepare")
    for path in (key, known_hosts, ssh_config):
        if not path or not Path(path).is_file():
            raise ValueError("SSH key, verified known_hosts and SSH config are required")
    if apply_digest is not None:
        if manifest["phase"] != "plan" or not approver or set(manifest["plans"]) != set(manifest["hosts"]):
            raise ValueError("all host previews and an approver are required")
        if digest(approval_binding(manifest)) != apply_digest or manifest.get("approval_digest") != apply_digest:
            raise ValueError("approval does not match preview")
        # Preserve preview artifacts before events are replaced by apply results.
        write_json(directory / "preview-results.json", json.loads((directory / "results.json").read_text(encoding="utf-8")))
        for event in (directory / "events").glob("*.json"):
            event.unlink()
        manifest.update(phase="apply", approver=approver, skipped=[])
        write_json(directory / "manifest.json", manifest)
    elif manifest["phase"] == "apply":
        raise ValueError("an apply run cannot be resumed or retried")
    elif manifest.get("execution_started"):
        raise ValueError("execution already started; prepare a new run instead of reusing results")
    manifest["execution_started"] = True
    write_json(directory / "manifest.json", manifest)
    def interrupted(signum, frame):
        raise KeyboardInterrupt("execution interrupted")
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        if manifest["phase"] == "apply":
            for index, host in enumerate(manifest["hosts"]):
                launch(directory, manifest, [host], key, known_hosts, ssh_config)
                summary = finalize(directory)
                rows = json.loads((directory / "results.json").read_text(encoding="utf-8"))
                if any(row["host"] == host and row["status"] != "ok" for row in rows):
                    manifest["skipped"] = manifest["hosts"][index + 1:]
                    write_json(directory / "manifest.json", manifest)
                    break
        else:
            launch(directory, manifest, manifest["hosts"], key, known_hosts, ssh_config)
    finally:
        signal.signal(signal.SIGTERM, previous)
        summary = finalize(directory)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "execute", "apply", "finalize"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--environment", default="test")
    parser.add_argument("--targets", default="web")
    parser.add_argument("--task", default="basic")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--phase", choices=["run", "plan"], default="run")
    parser.add_argument("--key")
    parser.add_argument("--known-hosts")
    parser.add_argument("--ssh-config")
    parser.add_argument("--approval-digest")
    parser.add_argument("--approver")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
            prepare(inventory, args.environment, args.targets, args.task, json.loads(args.params), args.phase, args.out)
            return 0
        if args.command == "finalize":
            summary = finalize(args.out)
        else:
            if args.command == "apply" and not args.approval_digest:
                raise ValueError("approval digest required")
            summary = execute_fleet(args.out, args.key, args.known_hosts, args.ssh_config,
                                    args.approval_digest if args.command == "apply" else None, args.approver)
        return {"SUCCESS": 0, "UNSTABLE": 1, "FAILURE": 2}[summary["build_status"]]
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
