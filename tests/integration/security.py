"""Real root ownership/flock/dir_fd tests, only in disposable target containers."""
import fcntl
import os
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/opt/sre-source")
from sretoolkit import VERSION
from sretoolkit.common import write_json
from sretoolkit.privileged import Maintainer


def reject(call):
    try:
        call()
    except (ValueError, OSError):
        return
    raise AssertionError("unsafe operation was accepted")


def main():
    assert os.environ.get("SRE_INTEGRATION") == "1" and os.geteuid() == 0
    root = Path("/srv") / ("sre-security-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    try:
        (root / "state/plans").mkdir(parents=True, mode=0o700)
        archive = root / "archive"
        archive.mkdir()
        old = archive / "old.log"
        old.write_text("fixture")
        os.utime(old, (1, 1))
        policy = dict(schema_version=1, services={}, backups=[], cleanup=[
            dict(directory=str(archive), pattern="*.log", min_days=7, max_files=10, max_bytes=1000)])
        write_json(root / "policy.json", policy)
        manager = Maintainer(root / "policy.json", root / "state", "/opt/sre-toolkit-privileged")
        request = dict(mode="plan", task="cleanup", params={"directory": str(archive), "days": 7}, run_id="test", version=VERSION)
        os.chmod(archive, 0o777)
        reject(lambda: manager.dispatch(request, 1000))
        os.chmod(archive, 0o755)
        (archive / "link").symlink_to("/etc/passwd")
        reject(lambda: manager.dispatch(request, 1000))
        (archive / "link").unlink()
        with (root / "state/maintenance.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            reject(lambda: manager.dispatch(request, 1000))
        reject(lambda: manager.dispatch(dict(request, version="wrong"), 1000))
        _, _, _, metrics = manager.dispatch(request, 1000)
        apply = dict(mode="apply", task="cleanup", run_id="test", version=VERSION,
                     plan_id=metrics["plan"]["plan_id"], digest=metrics["digest"])
        assert old.exists()  # preview never deletes
        old.write_text("changed")
        reject(lambda: manager.dispatch(apply, 1000))
        os.utime(old, (1, 1))
        _, _, _, metrics = manager.dispatch(request, 1000)
        apply.update(plan_id=metrics["plan"]["plan_id"], digest=metrics["digest"])
        status, _, changed, _ = manager.dispatch(apply, 1000)
        assert status == "ok" and changed and not old.exists()
        reject(lambda: manager.dispatch(apply, 1000))
        print("PASS: real ownership, symlink, lock, version, plan change and replay controls")
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
