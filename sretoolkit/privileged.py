"""Root-owned, allowlisted maintenance. No user-selected code/config paths.

Only the fixed installed entry point calls main(). Repository tests instantiate
Maintainer with temporary paths; those overrides are not exposed to the CLI.
"""
import fnmatch
import json
import os
import re
import socket
import stat
import time
import uuid
from pathlib import Path

from sretoolkit import VERSION
from sretoolkit.common import digest, execute, result, utc_now, write_json
from sretoolkit.tasks import TASKS, identifier, validate

POLICY = Path("/etc/sre-toolkit/policy.json")
STATE = Path("/var/lib/sre-toolkit")
INSTALL = Path("/opt/sre-toolkit-privileged")


def trusted_path(path):
    """Reject writable ancestors and symlinks, including the leaf."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute canonical path required")
    for item in [*reversed(path.parents), path]:
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("path is not root-controlled: " + str(item))
    return path


def identity(info):
    return {"dev": info.st_dev, "ino": info.st_ino, "size": info.st_size,
            "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {"schema_version", "services", "backups", "cleanup"} or policy["schema_version"] != 1:
        raise ValueError("invalid policy schema")
    if not isinstance(policy["services"], dict) or not isinstance(policy["backups"], list) or not isinstance(policy["cleanup"], list):
        raise ValueError("invalid policy lists")
    for service, actions in policy["services"].items():
        if not isinstance(actions, list) or not actions:
            raise ValueError("service actions must be a nonempty list")
        for action in actions:
            validate("service", {"service": service, "action": action})
    for rule in policy["backups"]:
        if set(rule) != {"source", "destination"}:
            raise ValueError("invalid backup rule")
        validate("backup", {"source": rule["source"]})
        validate("backup", {"source": rule["destination"]})
    for rule in policy["cleanup"]:
        if set(rule) != {"directory", "pattern", "min_days", "max_files", "max_bytes"}:
            raise ValueError("invalid cleanup rule")
        validate("cleanup", {"directory": rule["directory"], "days": rule["min_days"]})
        if not isinstance(rule["pattern"], str) or not rule["pattern"] or "/" in rule["pattern"]:
            raise ValueError("cleanup pattern must match basenames")
        if any(type(rule[k]) is not int or rule[k] < 1 for k in ("max_files", "max_bytes")):
            raise ValueError("positive cleanup limits required")
    return policy


class Maintainer:
    def __init__(self, policy_path=POLICY, state=STATE, install=INSTALL):
        self.policy_path, self.state, self.install = map(Path, (policy_path, state, install))

    def policy(self):
        trusted_path(self.policy_path)
        return validate_policy(json.loads(self.policy_path.read_text(encoding="utf-8")))

    def authorize(self, task, params, policy):
        params = validate(task, params)
        if task == "service":
            if params["action"] not in policy["services"].get(params["service"], []):
                raise ValueError("service/action not allowlisted")
            return {}
        key, field = ("backups", "source") if task == "backup" else ("cleanup", "directory")
        rules = [r for r in policy[key] if r[field] == params[field]]
        if len(rules) != 1:
            raise ValueError("path not uniquely allowlisted")
        rule = rules[0]
        source = trusted_path(params[field])
        if str(source) == "/":
            raise ValueError("root filesystem is not a maintenance target")
        if task == "backup":
            destination = trusted_path(rule["destination"])
            if not destination.is_dir() or destination == source or source in destination.parents:
                raise ValueError("invalid backup destination")
        elif params["days"] < rule["min_days"]:
            raise ValueError("retention below policy minimum")
        return rule

    def candidates(self, params, rule):
        base = trusted_path(params["directory"])
        device = base.stat().st_dev
        cutoff = time.time() - params["days"] * 86400
        candidates, total = [], 0
        for directory, dirs, files in os.walk(base, followlinks=False):
            trusted_path(directory)
            for name in dirs:
                child = trusted_path(Path(directory) / name)
                if child.stat().st_dev != device:
                    raise ValueError("cleanup cannot cross filesystem boundaries")
            for name in sorted(files):
                path = Path(directory) / name
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("cleanup tree contains a symlink")
                if not fnmatch.fnmatchcase(name, rule["pattern"]) or not stat.S_ISREG(info.st_mode) or info.st_mtime >= cutoff:
                    continue
                trusted_path(path)
                if info.st_dev != device or info.st_nlink != 1:
                    raise ValueError("cleanup candidate is a hardlink or different filesystem")
                total += info.st_size
                candidates.append(dict(path=str(path.relative_to(base)), **identity(info)))
                if len(candidates) > min(rule["max_files"], 500) or total > rule["max_bytes"]:
                    raise ValueError("cleanup limit exceeded (hard maximum 500 files per plan)")
        return sorted(candidates, key=lambda item: item["path"]), total

    def plan(self, request, uid):
        policy = self.policy()
        task, params = request["task"], validate(request["task"], request["params"])
        rule = self.authorize(task, params, policy)
        details = {}
        if task == "cleanup":
            files, size = self.candidates(params, rule)
            details = {"files": files, "count": len(files), "bytes": size}
        elif task == "backup":
            details = {"destination": rule["destination"]}
        else:
            check = execute(["/usr/bin/systemctl", "show", "--property=LoadState", "--value", "--", params["service"]], 10)
            if check["exit_code"] != 0 or check["stdout"].strip() != "loaded":
                raise ValueError("service is not loaded")
        plan = dict(plan_id=uuid.uuid4().hex, run_id=request["run_id"], version=VERSION,
                    host=socket.gethostname(), uid=uid, task=task, params=params,
                    policy_digest=digest(policy), created_at=time.time(), expires_at=time.time() + 1800,
                    details=details)
        if len(json.dumps(plan, ensure_ascii=True).encode()) > 262144:
            raise ValueError("plan exceeds 256 KiB; narrow the cleanup scope")
        write_json(self.state / "plans" / (plan["plan_id"] + ".json"), plan)
        return {"plan": plan, "digest": digest(plan)}

    def load_plan(self, request, uid):
        plan_id = identifier(request["plan_id"])
        path = trusted_path(self.state / "plans" / (plan_id + ".json"))
        plan = json.loads(path.read_text(encoding="utf-8"))
        if digest(plan) != request["digest"] or plan["uid"] != uid or plan["run_id"] != request["run_id"]:
            raise ValueError("plan binding mismatch")
        if plan["task"] != request["task"] or plan["version"] != VERSION or plan["host"] != socket.gethostname():
            raise ValueError("plan task/version/host mismatch")
        if time.time() >= plan["expires_at"]:
            raise ValueError("plan expired; create a new preview")
        policy = self.policy()
        if digest(policy) != plan["policy_digest"]:
            raise ValueError("policy changed after preview")
        rule = self.authorize(plan["task"], plan["params"], policy)
        return path, plan, rule

    def apply(self, request, uid):
        path, plan, rule = self.load_plan(request, uid)
        task, params = plan["task"], plan["params"]
        if task == "cleanup":
            # Verify every approved object BEFORE deleting any. Newly aged files
            # are not added; the approval refers only to the stored candidate set.
            base = trusted_path(params["directory"])
            for candidate in plan["details"]["files"]:
                target = trusted_path(base / candidate["path"])
                info = target.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or identity(info) != {k: candidate[k] for k in identity(info)}:
                    raise ValueError("cleanup file changed after preview")
        # A failed/interrupted apply can never be replayed with the same plan.
        os.replace(path, path.with_suffix(".consumed"))
        if task == "cleanup":
            removed = 0
            try:
                for candidate in plan["details"]["files"]:
                    target = trusted_path(base / candidate["path"])
                    directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    try:
                        info = os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
                        if identity(info) != {k: candidate[k] for k in identity(info)} or not stat.S_ISREG(info.st_mode):
                            raise ValueError("cleanup candidate changed during execution")
                        os.unlink(target.name, dir_fd=directory_fd)
                        removed += 1
                    finally:
                        os.close(directory_fd)
            except (OSError, ValueError) as exc:
                return "error", "partial cleanup: " + str(exc), bool(removed), {"removed": removed}
            return "ok", "approved files removed", bool(removed), {"removed": removed, "bytes": plan["details"]["bytes"]}
        if task == "service":
            out = execute(["/usr/bin/systemctl", params["action"], "--", params["service"]], 45)
            if out["timed_out"]:
                return "unknown", "systemctl timed out; job may still be running", None, {}
            if out["exit_code"]:
                return "error", "systemctl failed", None, {"stderr": out["stderr"], "exit_code": out["exit_code"]}
            check = execute(["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", "--", params["service"]], 10)
            desired = "inactive" if params["action"] == "stop" else "active"
            good = check["exit_code"] == 0 and check["stdout"].strip() == desired
            return ("ok" if good else "error"), "service state verification: " + check["stdout"].strip(), True, {}
        trusted_path(self.install / "bin" / "backup.sh")
        out = execute(["/usr/bin/bash", str(self.install / "bin" / "backup.sh"), params["source"]], 880,
                      env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "BACKUP_DIR": rule["destination"]})
        if out["timed_out"]:
            return "timeout", "backup timed out; inspect private staging directories", None, {}
        if out["exit_code"]:
            return "error", "backup failed", None, {"stderr": out["stderr"]}
        archive = Path(out["stdout"].strip().split(": ", 1)[-1])
        trusted_path(archive)
        if archive.parent != Path(rule["destination"]):
            raise ValueError("backup output outside allowlisted destination")
        import hashlib
        checksum = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(block)
        return "ok", "backup created and archive verified", True, {"path": str(archive), "bytes": archive.stat().st_size, "sha256": checksum.hexdigest()}

    def dispatch(self, request, uid):
        import fcntl

        if not isinstance(request, dict) or request.get("version") != VERSION:
            raise ValueError("maintenance version mismatch")
        mode = request.get("mode")
        required = {"mode", "task", "run_id", "version"} | ({"params"} if mode == "plan" else {"plan_id", "digest"})
        if set(request) != required or mode not in {"plan", "apply"}:
            raise ValueError("invalid maintenance request")
        identifier(request["run_id"])
        if request["task"] not in {"service", "backup", "cleanup"}:
            raise ValueError("unsupported maintenance task")
        trusted_path(self.state)
        trusted_path(self.state / "plans")
        lock_path = self.state / "maintenance.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if mode == "plan":
                return "ok", "preview only; no maintenance performed", False, self.plan(request, uid)
            return self.apply(request, uid)
        finally:
            os.close(fd)


def main():
    import signal
    import sys

    os.umask(0o077)
    os.environ.clear()
    # SUDO_UID must be captured by the trusted launcher before environment reset.
    uid = CALLER_UID
    os.environ.update(PATH="/usr/sbin:/usr/bin:/sbin:/bin", LC_ALL="C")
    request = {}
    started = utc_now()
    begin = time.monotonic()
    try:
        if os.geteuid() != 0 or len(sys.argv) != 1:
            raise ValueError("fixed root entry point accepts JSON stdin only")
        # Deadline survives loss of SSH/Jenkins. A consumed plan is never replayed.
        signal.signal(signal.SIGALRM, lambda *_: sys.exit(124))
        signal.alarm(900)
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:
            raise ValueError("request too large")
        request = json.loads(raw)
        if isinstance(request, dict):
            signal.alarm(TASKS.get(request.get("task"), {}).get("timeout", 60))
        status, summary, changed, metrics = Maintainer().dispatch(request, uid)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        status, summary, changed, metrics = "error", str(exc), False, {}
        if isinstance(request, dict) and request.get("mode") == "apply":
            plan_id = request.get("plan_id", "")
            if isinstance(plan_id, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", plan_id) and (STATE / "plans" / (plan_id + ".consumed")).exists():
                status, changed = "unknown", None
    record = result(request.get("run_id", "invalid") if isinstance(request, dict) else "invalid",
                    socket.gethostname(), request.get("task", "invalid") if isinstance(request, dict) else "invalid",
                    status, summary, changed=changed, metrics=metrics, started_at=started,
                    duration=round(time.monotonic() - begin, 3), exit_code=0 if status == "ok" else 2)
    print(json.dumps(record, ensure_ascii=True))
    return record["exit_code"]


CALLER_UID = int(os.environ.get("SUDO_UID", os.getuid() if hasattr(os, "getuid") else 0))
