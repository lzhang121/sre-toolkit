import argparse
import json
import os
import re
import socket
import sys
import uuid
from pathlib import Path

from sretoolkit import VERSION
from sretoolkit.common import execute, result, utc_now
from sretoolkit.tasks import BASIC, TASKS, catalogue, identifier, validate

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_ENTRY = "/usr/local/sbin/sre-maint"


def run_check(task, params, run_id, host):
    params = validate(task, params)
    spec = TASKS[task]
    if spec["privileged"]:
        raise ValueError("maintenance requires plan/apply")
    command = ["bash", str(ROOT / "bin" / "inspect.sh"), task]
    if task == "access_log":
        command = ["bash", str(ROOT / "bin" / "log_analyzer.sh")]
    command.extend(str(params[name]) for name in spec["params"])
    started = utc_now()
    try:
        output = execute(command, spec["timeout"], env=dict(os.environ, LC_ALL="C", NO_COLOR="1"))
    except OSError as exc:
        return result(run_id, host, task, "error", str(exc), started_at=started)
    status = "timeout" if output["timed_out"] else spec["exit_codes"].get(str(output["exit_code"]), "error")
    record = result(run_id, host, task, status, task + ": " + status, started_at=started,
                    duration=output["duration"], exit_code=output["exit_code"],
                    metrics={"output_truncated": output["truncated"]})
    record.update(stdout=output["stdout"], stderr=output["stderr"])
    if task == "system":
        labels = {"CPU": "cpu_percent", "内存": "memory_percent", "磁盘": "disk_percent",
                  "Inode": "inode_percent", "1分钟每核负载": "load_per_cpu"}
        for label, key in labels.items():
            match = re.search(r"\[(?:OK|WARN)\] " + re.escape(label) + r": ([0-9]+(?:\.[0-9]+)?)", output["stdout"])
            if match:
                record["metrics"][key] = float(match.group(1))
    return record


def maintenance(mode, task, params, run_id, host, plan_id=None, plan_digest=None):
    if task not in TASKS or not TASKS[task]["privileged"]:
        raise ValueError("not a maintenance task")
    request = dict(mode=mode, task=task, run_id=run_id, version=VERSION)
    if mode == "plan":
        request["params"] = validate(task, params)
    else:
        request.update(plan_id=identifier(plan_id), digest=plan_digest)
    output = execute(["sudo", "-n", MAINTENANCE_ENTRY], TASKS[task]["timeout"] + 15,
                     stdin=json.dumps(request), output_limit=1048576)
    if output["timed_out"] or output["exit_code"] == 124:
        return result(run_id, host, task, "timeout" if mode == "plan" else "unknown",
                      "privileged deadline exceeded; check state before retrying",
                      changed=False if mode == "plan" else None)
    try:
        record = json.loads(output["stdout"])
        if not isinstance(record, dict) or record.get("run_id") != run_id or record.get("task") != task:
            raise ValueError("invalid maintenance response")
        record["host"] = host
        return record
    except (ValueError, TypeError):
        return result(run_id, host, task, "error" if mode == "plan" else "unknown",
                      "maintenance response missing or invalid", exit_code=output["exit_code"],
                      stderr=output["stderr"], changed=False if mode == "plan" else None)


def exit_status(records):
    if any(r["status"] not in {"ok", "warning", "skipped"} for r in records):
        return 2
    return 1 if any(r["status"] == "warning" for r in records) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="SRE task registry and local execution")
    parser.add_argument("command", choices=["list", "run", "plan", "apply"])
    parser.add_argument("task", nargs="?")
    parser.add_argument("--params", default="{}", help="JSON object, not shell assignments")
    parser.add_argument("--run-id", default=uuid.uuid4().hex)
    parser.add_argument("--host", default=socket.gethostname())
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--plan-id")
    parser.add_argument("--digest")
    args = parser.parse_args(argv)
    try:
        identifier(args.run_id)
        if args.command == "list":
            print(json.dumps(catalogue(), indent=2, ensure_ascii=True) if args.format == "json" else
                  "basic: " + ", ".join(BASIC) + "\n" + "\n".join(TASKS))
            return 0
        params = json.loads(args.params)
        if args.command == "run":
            tasks = BASIC if args.task == "basic" else [args.task]
            records = [run_check(task, params, args.run_id, args.host) for task in tasks]
        else:
            records = [maintenance(args.command, args.task, params, args.run_id, args.host, args.plan_id, args.digest)]
        if args.format == "json":
            print(json.dumps(records, ensure_ascii=True))
        else:
            for record in records:
                print("[{status}] {host} {task}: {summary}".format(**record))
                print(record.get("stdout", ""), end="")
                if "plan" in record["metrics"]:
                    print(json.dumps(record["metrics"], indent=2, ensure_ascii=True))
        return exit_status(records)
    except (ValueError, TypeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
