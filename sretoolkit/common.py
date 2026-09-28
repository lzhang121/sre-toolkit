"""Shared wire format and bounded subprocess execution."""
import datetime
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

STATUSES = {"ok", "warning", "error", "unreachable", "timeout", "skipped", "unknown"}
OUTPUT_LIMIT = 32768


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def result(run_id, host, task, status, summary, **kwargs):
    record = dict(schema_version=1, run_id=run_id, host=host, task=task,
                  status=status, exit_code=None, started_at=utc_now(), duration=0,
                  changed=False, summary=summary, metrics={}, artifact_refs=[])
    record.update(kwargs)
    return record


def execute(argv, seconds=60, stdin=None, env=None, output_limit=OUTPUT_LIMIT):
    """Kill the process group at deadline and continuously drain bounded output.

    Temporary storage is avoided: commands such as journalctl must not fill the
    disk, even if their output is unexpectedly large. Linux is the runtime.
    """
    import threading

    started = time.monotonic()
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}

    def drain(stream, name):
        while True:
            data = stream.read(8192)
            if not data:
                break
            remaining = output_limit - len(chunks[name])
            chunks[name].extend(data[:max(0, remaining)])
            if len(data) > remaining:
                truncated[name] = True
        stream.close()

    with tempfile.TemporaryFile() as input_file:
        if stdin is not None:
            input_file.write(stdin.encode())
        input_file.seek(0)
        # GNU timeout is a separate watchdog: its deadline survives the Python
        # caller losing its SSH session. Python's timeout remains a fallback.
        command = argv
        watchdog = os.name == "posix" and Path("/usr/bin/timeout").is_file()
        if watchdog:
            command = ["/usr/bin/timeout", "--kill-after=5", str(seconds), *argv]
        process = subprocess.Popen(command, stdin=input_file, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, start_new_session=True)
        threads = [threading.Thread(target=drain, args=(getattr(process, n), n), daemon=True)
                   for n in chunks]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            process.wait(timeout=seconds + 6 if watchdog else seconds)
            timed_out = watchdog and process.returncode in {124, 137}
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass  # sudo children have their own privileged deadline
            else:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        finally:
            # Also stop descendants retaining stdout after their parent exits.
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            for thread in threads:
                thread.join(timeout=2)
    return dict(exit_code=process.returncode, timed_out=timed_out,
                stdout=chunks["stdout"].decode("utf-8", "replace"),
                stderr=chunks["stderr"].decode("utf-8", "replace"),
                truncated=any(truncated.values()), duration=round(time.monotonic() - started, 3))
